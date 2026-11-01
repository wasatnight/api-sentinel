import asyncio
from datetime import timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from sentinel.models import Check, Incident, Service, now
from sentinel.monitor import Monitor
from sentinel.probe import Result

GENERAL = "00000000-0000-0000-0000-000000000001"


@pytest.fixture
def service_id(migrated_engine):
    with Session(migrated_engine) as db:
        service = Service(
            name="Monitor test",
            url="https://example.com/health",
            collection_id=GENERAL,
            interval_seconds=10,
            timeout_seconds=1,
        )
        db.add(service)
        db.commit()
        identifier = service.id
    yield identifier
    with Session(migrated_engine) as db:
        db.delete(db.get(Service, identifier))
        db.commit()


@pytest.mark.asyncio
async def test_incident_open_once_then_recovery(migrated_engine, service_id):
    result = Result(503, 42, False, "down", "HTTP 503 outside the expected range.", 1)

    async def fake(target):
        return result

    monitor = Monitor(migrated_engine, probe_fn=fake)
    await monitor.run(service_id, manual=True)
    await monitor.run(service_id, manual=True)
    with Session(migrated_engine) as db:
        assert (
            db.scalar(select(func.count()).select_from(Check).where(Check.service_id == service_id))
            == 2
        )
        incidents = list(db.scalars(select(Incident).where(Incident.service_id == service_id)))
        assert len(incidents) == 1 and incidents[0].state == "investigating"
        assert db.get(Service, service_id).status == "down"
    result = Result(200, 31, True, "healthy", None, 1)
    await monitor.run(service_id, manual=True)
    with Session(migrated_engine) as db:
        incident = db.scalar(select(Incident).where(Incident.service_id == service_id))
        assert incident.state == "resolved" and incident.resolved_at
        service = db.get(Service, service_id)
        assert service.status == "healthy" and service.last_latency_ms == 31
        assert service.last_checked_at and service.next_check_at > service.last_checked_at


@pytest.mark.asyncio
async def test_cross_worker_duplicate_and_edit_lock(migrated_engine, service_id, client):
    entered, finish = asyncio.Event(), asyncio.Event()
    calls = 0

    async def fake(target):
        nonlocal calls
        calls += 1
        entered.set()
        await finish.wait()
        return Result(200, 20, True, "healthy", None, 1)

    first = Monitor(migrated_engine, probe_fn=fake)
    second = Monitor(migrated_engine, probe_fn=fake)
    task = asyncio.create_task(first.run(service_id, manual=True))
    await asyncio.wait_for(entered.wait(), 2)
    try:
        await second.run(service_id, manual=True)
        assert calls == 1
        # API writes share the same per-service lock.
        deleted = await asyncio.to_thread(client.delete, "/api/v1/services/" + service_id)
        assert deleted.status_code == 409
    finally:
        finish.set()
        await task
    with Session(migrated_engine) as db:
        assert (
            db.scalar(select(func.count()).select_from(Check).where(Check.service_id == service_id))
            == 1
        )


@pytest.mark.asyncio
async def test_pause_and_scheduler_without_frontend(migrated_engine, service_id):
    complete = asyncio.Event()

    async def fake(target):
        complete.set()
        return Result(200, 10, True, "healthy", None, 1)

    monitor = Monitor(migrated_engine, probe_fn=fake)
    with Session(migrated_engine) as db:
        service = db.get(Service, service_id)
        service.enabled = False
        db.commit()
    await monitor.run(service_id)
    assert not complete.is_set()
    # Manual checks can inspect paused services.
    await monitor.run(service_id, manual=True)
    assert complete.is_set()
    complete.clear()
    with Session(migrated_engine) as db:
        service = db.get(Service, service_id)
        service.enabled = True
        service.next_check_at = now() - timedelta(seconds=1)
        db.commit()
    monitor.start()
    await asyncio.wait_for(complete.wait(), 3)
    await monitor.close()
    with Session(migrated_engine) as db:
        assert (
            db.scalar(select(func.count()).select_from(Check).where(Check.service_id == service_id))
            == 2
        )


@pytest.mark.asyncio
async def test_concurrency_limit_and_failure_isolation(migrated_engine, service_id):
    gate = asyncio.Event()

    async def failing(target):
        await gate.wait()
        raise RuntimeError("internal worker failure")

    monitor = Monitor(migrated_engine, concurrent=1, probe_fn=failing)
    assert monitor.enqueue(service_id, manual=True)
    assert not monitor.enqueue(service_id, manual=True)
    assert not monitor.enqueue("another-id", manual=True)
    gate.set()
    await monitor.close()
    assert not monitor.running
    # Internal engine errors never invent a failed endpoint result or incident.
    with Session(migrated_engine) as db:
        assert (
            db.scalar(select(func.count()).select_from(Check).where(Check.service_id == service_id))
            == 0
        )


@pytest.mark.asyncio
async def test_cancelled_check_releases_advisory_lock(migrated_engine, service_id):
    entered = asyncio.Event()

    async def waiting(target):
        entered.set()
        await asyncio.Event().wait()

    first = Monitor(migrated_engine, probe_fn=waiting)
    task = asyncio.create_task(first.run(service_id, manual=True))
    await asyncio.wait_for(entered.wait(), 2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    async def healthy(target):
        return Result(200, 10, True, "healthy", None, 1)

    second = Monitor(migrated_engine, probe_fn=healthy)
    await second.run(service_id, manual=True)
    with Session(migrated_engine) as db:
        assert (
            db.scalar(select(func.count()).select_from(Check).where(Check.service_id == service_id))
            == 1
        )


@pytest.mark.asyncio
async def test_alerts_transitions_deduplication_and_recovery(migrated_engine, service_id):
    from sentinel.models import Alert

    result = Result(200, 800, True, "degraded", "Latency superior al umbral.", 1)

    async def fake(target):
        return result

    monitor = Monitor(migrated_engine, probe_fn=fake)
    await monitor.run(service_id, manual=True)
    await monitor.run(service_id, manual=True)
    result = Result(503, 20, False, "down", "HTTP 503 observado.", 1)
    await monitor.run(service_id, manual=True)
    await monitor.run(service_id, manual=True)
    result = Result(200, 15, True, "healthy", None, 1)
    await monitor.run(service_id, manual=True)
    await monitor.run(service_id, manual=True)
    with Session(migrated_engine) as db:
        rows = list(
            db.scalars(
                select(Alert).where(Alert.service_id == service_id).order_by(Alert.created_at)
            )
        )
        assert [a.kind for a in rows] == ["degradation", "failure", "recovery"]
        assert len({a.incident_id for a in rows}) == 1


@pytest.mark.asyncio
async def test_alert_preferences_do_not_disable_incidents(migrated_engine, service_id):
    from sentinel.models import Alert, Configuration

    with Session(migrated_engine) as db:
        config = db.get(Configuration, 1)
        original = (config.failure_alerts, config.recovery_alerts)
        config.failure_alerts = False
        config.recovery_alerts = False
        db.commit()
    try:
        result = Result(503, 5, False, "down", "HTTP 503.", 1)

        async def fake(target):
            return result

        monitor = Monitor(migrated_engine, probe_fn=fake)
        await monitor.run(service_id, manual=True)
        with Session(migrated_engine) as db:
            assert (
                db.scalar(
                    select(func.count())
                    .select_from(Incident)
                    .where(Incident.service_id == service_id)
                )
                == 1
            )
            assert (
                db.scalar(
                    select(func.count()).select_from(Alert).where(Alert.service_id == service_id)
                )
                == 0
            )
        result = Result(200, 5, True, "healthy", None, 1)
        await monitor.run(service_id, manual=True)
        with Session(migrated_engine) as db:
            assert (
                db.scalar(select(Incident).where(Incident.service_id == service_id)).state
                == "resolved"
            )
            assert (
                db.scalar(
                    select(func.count()).select_from(Alert).where(Alert.service_id == service_id)
                )
                == 0
            )
    finally:
        with Session(migrated_engine) as db:
            config = db.get(Configuration, 1)
            config.failure_alerts, config.recovery_alerts = original
            db.commit()


@pytest.mark.asyncio
async def test_initial_healthy_check_is_not_a_recovery_alert(migrated_engine, service_id):
    from sentinel.models import Alert

    async def fake(target):
        return Result(200, 10, True, "healthy", None, 1)

    monitor = Monitor(migrated_engine, probe_fn=fake)
    await monitor.run(service_id, manual=True)
    await monitor.run(service_id, manual=True)
    with Session(migrated_engine) as db:
        assert (
            db.scalar(select(func.count()).select_from(Alert).where(Alert.service_id == service_id))
            == 0
        )
