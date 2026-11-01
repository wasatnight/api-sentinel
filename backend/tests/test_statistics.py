from datetime import timedelta

import pytest
from sqlalchemy.orm import Session

from sentinel.analytics import activity, statistics
from sentinel.models import Alert, Check, Incident, Service, now


@pytest.fixture
def historical_data(migrated_engine):
    end = now().replace(microsecond=0)
    with Session(migrated_engine) as db:
        measured = Service(
            name="Histórico medido",
            url="https://example.com",
            collection_id="00000000-0000-0000-0000-000000000001",
            enabled=False,
        )
        empty = Service(
            name="No data",
            url="https://example.org",
            collection_id="00000000-0000-0000-0000-000000000001",
            enabled=False,
        )
        db.add_all([measured, empty])
        db.flush()
        identifier, empty_id = measured.id, empty.id
        for minutes, latency, status, success in [
            (5, 100, "healthy", True),
            (15, 200, "down", False),
            (30, 300, "degraded", True),
            (40, 400, "unknown", False),
        ]:
            db.add(
                Check(
                    service_id=identifier,
                    checked_at=end - timedelta(minutes=minutes),
                    latency_ms=latency,
                    status=status,
                    success=success,
                    status_code=200,
                )
            )
        db.add(
            Check(
                service_id=identifier,
                checked_at=end - timedelta(days=2),
                latency_ms=700,
                status="down",
                success=False,
                status_code=503,
            )
        )
        db.add(
            Incident(
                service_id=identifier,
                started_at=end - timedelta(hours=2),
                resolved_at=end - timedelta(minutes=2),
                state="resolved",
                cause="Prueba histórica",
            )
        )
        db.commit()
    yield {"id": identifier, "empty": empty_id, "end": end}
    with Session(migrated_engine) as db:
        for sid in (identifier, empty_id):
            db.delete(db.get(Service, sid))
        db.commit()


def test_weighted_availability_percentiles_and_missing_data(migrated_engine, historical_data):
    with Session(migrated_engine) as db:
        data = statistics(db, "1H", end=historical_data["end"])
    summary = data["summary"]
    assert summary["total_checks"] == 4 and summary["evaluated_checks"] == 3
    assert summary["unknown_checks"] == 1 and summary["successes"] == 2 and summary["failures"] == 1
    assert summary["availability"] == 66.6667 and summary["error_rate"] == 33.3333
    assert (
        summary["latency_avg"] == 250
        and summary["latency_min"] == 100
        and summary["latency_max"] == 400
    )
    assert summary["p50"] == 250 and summary["p95"] == 385 and summary["p99"] == 397
    assert summary["incident_count"] == 1  # Episode started before window but overlaps it.
    empty = next(s for s in data["services"] if s["id"] == historical_data["empty"])
    assert empty["total_checks"] == 0 and empty["availability"] is None and empty["p95"] is None
    assert any(p[historical_data["id"]] is None for p in data["points"])
    assert data["empty_periods"] == "unknown"


@pytest.mark.parametrize("period,count", [("1H", 4), ("6H", 4), ("24H", 4), ("7D", 5), ("30D", 5)])
def test_periods(migrated_engine, historical_data, period, count):
    with Session(migrated_engine) as db:
        data = statistics(db, period, end=historical_data["end"])
    assert data["summary"]["total_checks"] == count
    assert len(data["points"]) <= 97


def test_empty_window_null_latency_and_bounds(migrated_engine, historical_data):
    end = historical_data["end"]
    with Session(migrated_engine) as db:
        db.add_all(
            [
                Check(
                    service_id=historical_data["empty"],
                    checked_at=end,
                    success=True,
                    status="healthy",
                    latency_ms=2,
                ),
                Check(
                    service_id=historical_data["empty"],
                    checked_at=end - timedelta(hours=1, microseconds=1),
                    success=True,
                    status="healthy",
                    latency_ms=3,
                ),
                Check(
                    service_id=historical_data["empty"],
                    checked_at=end - timedelta(minutes=1),
                    success=True,
                    status="healthy",
                    latency_ms=None,
                ),
            ]
        )
        db.commit()
        data = statistics(db, "1H", service_id=historical_data["empty"], end=end)
        assert data["summary"]["total_checks"] == 1 and data["summary"]["availability"] == 100
        assert data["summary"]["latency_count"] == 0 and data["summary"]["latency_avg"] is None
        empty = statistics(
            db, "1H", service_id=historical_data["empty"], end=end - timedelta(days=10)
        )
        assert empty["summary"]["availability"] is None and empty["summary"]["total_checks"] == 0


def test_activity_severity_and_unknown_hours(migrated_engine, historical_data):
    with Session(migrated_engine) as db:
        for state in ("healthy", "degraded", "down"):
            db.add(
                Check(
                    service_id=historical_data["id"],
                    checked_at=historical_data["end"] - timedelta(seconds=1),
                    latency_ms=10,
                    status=state,
                    success=state != "down",
                )
            )
        db.commit()
        data = activity(db, end=historical_data["end"])
    row = next(r for r in data["rows"] if r["id"] == historical_data["id"])
    assert len(row["cells"]) == 24 and row["cells"][-1]["status"] == "down"
    assert row["cells"][0]["status"] == "unknown" and row["cells"][0]["samples"] == 0
    empty = next(r for r in data["rows"] if r["id"] == historical_data["empty"])
    assert all(c["status"] == "unknown" and c["samples"] == 0 for c in empty["cells"])


def test_statistics_rest_and_alert_reads(historical_data, client, migrated_engine):
    sid = historical_data["id"]
    assert client.get("/api/v1/statistics?period=bad").status_code == 422
    assert client.get("/api/v1/statistics?service_id=missing").status_code == 404
    data = client.get("/api/v1/statistics?period=1H&service_id=" + sid).json()
    assert data["summary"]["evaluated_checks"] == 3
    assert client.get("/api/v1/activity").status_code == 200
    with Session(migrated_engine) as db:
        first = Alert(service_id=sid, kind="failure", message="Fallo observado")
        second = Alert(service_id=sid, kind="recovery", message="Recovery observada")
        db.add_all([first, second])
        db.commit()
        first_id = first.id
    rows = client.get("/api/v1/alerts?unread_only=true").json()
    assert len(rows) == 2
    assert len(client.get("/api/v1/alerts?kind=failure").json()) == 1
    assert client.get("/api/v1/alerts?kind=invalid").status_code == 422
    assert client.get("/api/v1/workspace").json()["unread_alert_count"] == 2
    read = client.put("/api/v1/alerts/" + first_id + "/read").json()
    assert read["read_at"]
    assert client.put("/api/v1/alerts/" + first_id + "/read").json()["read_at"] == read["read_at"]
    assert client.post("/api/v1/alerts/read-all").json()["updated"] == 1
    assert client.get("/api/v1/workspace").json()["unread_alert_count"] == 0
    assert client.get("/api/v1/alerts?unread_only=true").json() == []
    assert client.put("/api/v1/alerts/missing/read").status_code == 404


def test_availability_weights_checks_not_service_percentages(migrated_engine, historical_data):
    with Session(migrated_engine) as db:
        db.add(
            Check(
                service_id=historical_data["empty"],
                checked_at=historical_data["end"] - timedelta(minutes=1),
                latency_ms=50,
                success=True,
                status="healthy",
            )
        )
        db.commit()
        data = statistics(db, "1H", end=historical_data["end"])
        assert (
            data["summary"]["availability"] == 75
        )  # 3 successful / 4 evaluable, not a mean of percentages.


def test_unknown_only_is_not_assumed_available(migrated_engine, historical_data):
    with Session(migrated_engine) as db:
        db.add(
            Check(
                service_id=historical_data["empty"],
                checked_at=historical_data["end"] - timedelta(minutes=1),
                latency_ms=50,
                success=True,
                status="unknown",
            )
        )
        db.commit()
        data = statistics(db, "1H", service_id=historical_data["empty"], end=historical_data["end"])
        assert data["summary"]["total_checks"] == 1
        assert data["summary"]["availability"] is None and data["summary"]["error_rate"] is None
