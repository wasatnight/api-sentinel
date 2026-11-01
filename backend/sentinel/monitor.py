"""Backend-owned scheduler with bounded tasks and PostgreSQL per-service advisory locks."""

import asyncio
import logging
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import or_, select, text
from sqlalchemy.orm import Session

from .models import Alert, Check, Configuration, Incident, Service, now
from .probe import Target, probe

log = logging.getLogger("sentinel.monitor")
LOCK_SQL = "SELECT pg_try_advisory_lock(hashtextextended(:id, 0))"
UNLOCK_SQL = "SELECT pg_advisory_unlock(hashtextextended(:id, 0))"


@dataclass
class Claim:
    connection: object
    target: Target


class Monitor:
    def __init__(self, engine, *, concurrent=4, probe_fn=probe):
        self.engine = engine
        self.concurrent = concurrent
        self.probe_fn = probe_fn
        self.running: set[str] = set()
        self.tasks: set[asyncio.Task] = set()
        self.slots = asyncio.Semaphore(concurrent)
        self.scheduler = None
        self.stopping = False

    def _claim(self, identifier, manual):
        connection = self.engine.connect()
        locked = False
        claimed = False
        try:
            locked = connection.scalar(text(LOCK_SQL), {"id": identifier})
            connection.commit()
            if not locked:
                return None
            with Session(bind=connection, expire_on_commit=False) as db:
                service = db.get(Service, identifier)
                if service is None or (not manual and not service.enabled):
                    return None
                if not manual and service.next_check_at and service.next_check_at > now():
                    return None
                config = db.get(Configuration, 1)
                target = Target(
                    service.id,
                    service.url,
                    service.method,
                    service.timeout_seconds,
                    service.expected_status_min,
                    service.expected_status_max,
                    config.latency_threshold,
                )
                service.next_check_at = now() + timedelta(seconds=service.interval_seconds)
                db.commit()
            claimed = True
            return Claim(connection, target)
        finally:
            # Successful claims keep this exact connection and lock until _release.
            if not claimed:
                try:
                    if locked:
                        connection.rollback()
                        connection.execute(text(UNLOCK_SQL), {"id": identifier})
                        connection.commit()
                finally:
                    connection.close()

    def _finish(self, claim, result):
        with Session(bind=claim.connection, expire_on_commit=False) as db:
            service = db.get(Service, claim.target.id)
            if service is None:
                return
            timestamp = now()
            previous_status = service.status
            config = db.get(Configuration, 1)
            db.add(
                Check(
                    service_id=service.id,
                    checked_at=timestamp,
                    status_code=result.code,
                    latency_ms=result.latency_ms,
                    success=result.success,
                    status=result.status,
                    error=result.error,
                    attempts=result.attempts,
                )
            )
            service.status = result.status
            service.last_checked_at = timestamp
            service.last_latency_ms = result.latency_ms
            service.next_check_at = timestamp + timedelta(seconds=service.interval_seconds)
            incident = db.scalar(
                select(Incident).where(
                    Incident.service_id == service.id, Incident.state != "resolved"
                )
            )
            new_incident = result.status != "healthy" and incident is None
            if new_incident:
                incident = Incident(
                    service_id=service.id,
                    state="investigating",
                    started_at=timestamp,
                    cause=result.error,
                )
                db.add(incident)
                db.flush()
            elif result.status == "healthy" and incident is not None:
                incident.state = "resolved"
                incident.resolved_at = timestamp

            escalated = result.status == "down" and previous_status == "degraded"
            if result.status != "healthy" and (new_incident or escalated) and config.failure_alerts:
                db.add(
                    Alert(
                        service_id=service.id,
                        incident_id=incident.id,
                        kind="degradation" if result.status == "degraded" else "failure",
                        message=f"{service.name}: {result.error or 'Availability conditions were not met.'}",
                        created_at=timestamp,
                    )
                )
            recovered = result.status == "healthy" and (
                incident is not None or previous_status in {"down", "degraded"}
            )
            if recovered and config.recovery_alerts:
                db.add(
                    Alert(
                        service_id=service.id,
                        incident_id=incident.id if incident else None,
                        kind="recovery",
                        message=f"{service.name} is responding within the configured conditions again.",
                        created_at=timestamp,
                    )
                )
            db.commit()

    def _release(self, claim):
        connection = claim.connection
        try:
            connection.rollback()
            connection.execute(text(UNLOCK_SQL), {"id": claim.target.id})
            connection.commit()
        finally:
            connection.close()

    async def run(self, identifier, *, manual=False):
        claim = None
        try:
            async with self.slots:
                claiming = asyncio.create_task(asyncio.to_thread(self._claim, identifier, manual))
                try:
                    claim = await asyncio.shield(claiming)
                except asyncio.CancelledError:
                    # A synchronous DB claim cannot be cancelled mid-thread; collect and release it.
                    claim = await claiming
                    raise
                if claim is not None:
                    result = await self.probe_fn(claim.target)
                    finishing = asyncio.create_task(asyncio.to_thread(self._finish, claim, result))
                    try:
                        await asyncio.shield(finishing)
                    except asyncio.CancelledError:
                        await finishing
                        raise
        except asyncio.CancelledError:
            raise
        except Exception as error:
            # Engine errors never fabricate a target outage or expose URL/driver details.
            log.error("Check could not be completed (%s)", type(error).__name__)
        finally:
            try:
                if claim is not None:
                    await asyncio.to_thread(self._release, claim)
            except Exception as error:
                log.error("Check lock could not be released (%s)", type(error).__name__)
            finally:
                self.running.discard(identifier)

    def enqueue(self, identifier, *, manual=False):
        if self.stopping or identifier in self.running or len(self.running) >= self.concurrent:
            return False
        self.running.add(identifier)
        task = asyncio.create_task(self.run(identifier, manual=manual))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return True

    def _due(self):
        with Session(self.engine) as db:
            return list(
                db.scalars(
                    select(Service.id)
                    .where(
                        Service.enabled.is_(True),
                        or_(Service.next_check_at.is_(None), Service.next_check_at <= now()),
                    )
                    .order_by(Service.next_check_at.asc().nullsfirst(), Service.created_at)
                    .limit(self.concurrent * 2)
                )
            )

    async def loop(self):
        while not self.stopping:
            try:
                if len(self.running) < self.concurrent:
                    for identifier in await asyncio.to_thread(self._due):
                        self.enqueue(identifier)
            except Exception as error:
                log.error("Scheduler unavailable (%s)", type(error).__name__)
            await asyncio.sleep(1)

    def start(self):
        self.scheduler = asyncio.create_task(self.loop())

    async def close(self):
        self.stopping = True
        if self.scheduler:
            self.scheduler.cancel()
            await asyncio.gather(self.scheduler, return_exceptions=True)
        # Let in-flight requests finish within their configured total timeout.
        if self.tasks:
            await asyncio.gather(*list(self.tasks), return_exceptions=True)
