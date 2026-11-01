"""Sample-based availability and latency aggregates. Empty periods stay unknown."""

import math
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import DateTime, Interval, cast, func, literal, select
from sqlalchemy.orm import Session

from .database import get_db
from .models import Check, Incident, Service, now

Period = Literal["1H", "6H", "24H", "7D", "30D"]
WINDOWS = {
    "1H": (3600, 60),
    "6H": (21600, 300),
    "24H": (86400, 900),
    "7D": (604800, 7200),
    "30D": (2592000, 28800),
}
router = APIRouter(prefix="/api/v1", tags=["Statistics"])
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def aggregate_columns():
    evaluable = Check.status != "unknown"
    return [
        func.count(Check.id).label("total_checks"),
        func.count(Check.id).filter(evaluable).label("evaluated_checks"),
        func.count(Check.id).filter(evaluable, Check.success.is_(True)).label("successes"),
        func.count(Check.latency_ms).label("latency_count"),
        func.avg(Check.latency_ms).label("latency_avg"),
        func.min(Check.latency_ms).label("latency_min"),
        func.max(Check.latency_ms).label("latency_max"),
        func.percentile_cont(0.5).within_group(Check.latency_ms).label("p50"),
        func.percentile_cont(0.95).within_group(Check.latency_ms).label("p95"),
        func.percentile_cont(0.99).within_group(Check.latency_ms).label("p99"),
    ]


def metrics(row):
    source = dict(row)
    total = int(source.get("total_checks") or 0)
    evaluated = int(source.get("evaluated_checks") or 0)
    successes = int(source.get("successes") or 0)
    result = {
        "total_checks": total,
        "evaluated_checks": evaluated,
        "unknown_checks": total - evaluated,
        "successes": successes,
        "failures": evaluated - successes,
        "availability": round(100 * successes / evaluated, 4) if evaluated else None,
        "error_rate": round(100 * (evaluated - successes) / evaluated, 4) if evaluated else None,
        "latency_count": int(source.get("latency_count") or 0),
    }
    for key in ("latency_avg", "latency_min", "latency_max", "p50", "p95", "p99"):
        value = source.get(key)
        result[key] = round(float(value), 2) if value is not None else None
    return result


def statistics(db, period="24H", service_id=None, collection_id=None, end=None):
    end = end or now()
    seconds, bucket_seconds = WINDOWS[period]
    start = end - timedelta(seconds=seconds)
    scope = select(Service).order_by(Service.name, Service.id)
    if service_id:
        scope = scope.where(Service.id == service_id)
    if collection_id:
        scope = scope.where(Service.collection_id == collection_id)
    chosen = list(db.scalars(scope))
    if service_id and not chosen:
        raise HTTPException(404, "The service does not exist in this selection.")
    if not chosen:
        return {
            "period": period,
            "start": start,
            "end": end,
            "bucket_seconds": bucket_seconds,
            "summary": {**metrics({}), "incident_count": 0, "active_incidents": 0},
            "services": [],
            "series": [],
            "series_total": 0,
            "points": [],
            "incidents": [],
            "availability_basis": "successful_evaluated_checks / evaluated_checks",
            "empty_periods": "unknown",
        }
    ids = [service.id for service in chosen]
    conditions = [Check.service_id.in_(ids), Check.checked_at >= start, Check.checked_at < end]
    summary = metrics(db.execute(select(*aggregate_columns()).where(*conditions)).mappings().one())
    grouped = (
        db.execute(
            select(Check.service_id, *aggregate_columns())
            .where(*conditions)
            .group_by(Check.service_id)
        )
        .mappings()
        .all()
    )
    by_id = {row["service_id"]: metrics(row) for row in grouped}
    services = [{"id": s.id, "name": s.name, **by_id.get(s.id, metrics({}))} for s in chosen]
    # Cap displayed series, not the aggregate calculations. Any service can be selected individually.
    displayed = chosen[:6]
    chart_ids = [s.id for s in displayed]
    bucket = func.date_bin(
        cast(f"{bucket_seconds} seconds", Interval),
        Check.checked_at,
        literal(EPOCH, type_=DateTime(timezone=True)),
    ).label("time")
    rows = (
        db.execute(
            select(
                Check.service_id,
                bucket,
                func.avg(Check.latency_ms).label("latency_ms"),
                func.count(Check.id).label("samples"),
            )
            .where(*conditions, Check.service_id.in_(chart_ids))
            .group_by(Check.service_id, bucket)
            .order_by(bucket)
        )
        .mappings()
        .all()
    )
    first = math.floor(start.timestamp() / bucket_seconds) * bucket_seconds
    last = (
        math.floor((end - timedelta(microseconds=1)).timestamp() / bucket_seconds) * bucket_seconds
    )
    grid = {
        int(stamp): {
            "time": datetime.fromtimestamp(stamp, timezone.utc).isoformat(),
            **{identifier: None for identifier in chart_ids},
        }
        for stamp in range(first, last + 1, bucket_seconds)
    }
    for row in rows:
        stamp = int(row["time"].timestamp())
        if stamp in grid and row["latency_ms"] is not None:
            grid[stamp][row["service_id"]] = round(float(row["latency_ms"]), 2)
    overlap = [
        Incident.service_id.in_(ids),
        Incident.started_at < end,
        (Incident.resolved_at.is_(None) | (Incident.resolved_at >= start)),
    ]
    incident_count, active_incidents = db.execute(
        select(func.count(), func.count().filter(Incident.state != "resolved"))
        .select_from(Incident)
        .where(*overlap)
    ).one()
    incident_rows = db.execute(
        select(Incident, Service.name)
        .join(Service)
        .where(*overlap)
        .order_by(Incident.started_at.desc())
        .limit(100)
    ).all()
    episodes = [
        {
            "id": i.id,
            "service_id": i.service_id,
            "name": name,
            "state": i.state,
            "started_at": i.started_at,
            "resolved_at": i.resolved_at,
            "cause": i.cause,
            "duration_seconds": max(
                0, int(((i.resolved_at or end) - i.started_at).total_seconds())
            ),
        }
        for i, name in incident_rows
    ]
    return {
        "period": period,
        "start": start,
        "end": end,
        "bucket_seconds": bucket_seconds,
        "summary": {
            **summary,
            "incident_count": incident_count,
            "active_incidents": active_incidents,
        },
        "services": services,
        "series": [{"id": s.id, "name": s.name} for s in displayed],
        "series_total": len(chosen),
        "points": list(grid.values()),
        "incidents": episodes,
        "availability_basis": "successful_evaluated_checks / evaluated_checks",
        "empty_periods": "unknown",
    }


@router.get("/statistics")
def get_statistics(
    period: Period = "24H",
    service_id: str | None = None,
    collection_id: str | None = None,
    db: Session = Depends(get_db),
):
    return statistics(db, period, service_id, collection_id)


def activity(db, end=None):
    end = end or now()
    # The current partial hour plus 23 complete hours.
    final = end.replace(minute=0, second=0, microsecond=0)
    start = final - timedelta(hours=23)
    hour = func.date_trunc("hour", Check.checked_at, "UTC").label("hour")
    rows = (
        db.execute(
            select(
                Check.service_id,
                hour,
                func.count().label("samples"),
                func.count().filter(Check.status == "down").label("down"),
                func.count().filter(Check.status == "degraded").label("degraded"),
                func.count().filter(Check.status == "healthy").label("healthy"),
            )
            .where(Check.checked_at >= start, Check.checked_at < end)
            .group_by(Check.service_id, hour)
        )
        .mappings()
        .all()
    )
    lookup = {(r["service_id"], r["hour"]): r for r in rows}
    services = list(db.scalars(select(Service).order_by(Service.name, Service.id).limit(8)))
    result = []
    for service in services:
        cells = []
        for index in range(24):
            stamp = start + timedelta(hours=index)
            row = lookup.get((service.id, stamp), {})
            state = (
                "down"
                if row.get("down")
                else "degraded"
                if row.get("degraded")
                else "healthy"
                if row.get("healthy")
                else "unknown"
            )
            cells.append({"time": stamp, "status": state, "samples": row.get("samples", 0)})
        result.append({"id": service.id, "name": service.name, "cells": cells})
    return {
        "start": start,
        "end": end,
        "rows": result,
        "total_services": db.scalar(select(func.count()).select_from(Service)),
    }


@router.get("/activity")
def get_activity(db: Session = Depends(get_db)):
    return activity(db)
