import pytest
from sqlalchemy import text

from sentinel.config import get_settings
from sentinel.schemas import ServiceInput

GENERAL = "00000000-0000-0000-0000-000000000001"


def payload(**values):
    return {
        "name": "Prueba",
        "url": "https://example.com/health",
        "method": "GET",
        "interval_seconds": 60,
        "timeout_seconds": 10,
        "collection_id": GENERAL,
        **values,
    }


def test_crud_and_empty_workspace(client):
    data = client.get("/api/v1/workspace").json()
    assert data["services"] == []
    assert data["monitoring_enabled"] is False
    assert data["collections"][0]["name"] == "General"
    created = client.post("/api/v1/services", json=payload())
    assert created.status_code == 201
    service = created.json()
    assert service["status"] == "unknown"
    assert service["last_checked_at"] is None
    assert service["created_at"]
    identifier = service["id"]
    assert client.get("/api/v1/services/" + identifier).json()["name"] == "Prueba"
    assert (
        client.put("/api/v1/services/" + identifier, json=payload(name="Editado")).status_code
        == 200
    )
    assert client.get("/api/v1/services?q=Editado").json()[0]["id"] == identifier
    assert client.get("/api/v1/services?q=no-coincide").json() == []
    assert client.get("/api/v1/services?limit=0").status_code == 422
    assert client.delete("/api/v1/services/" + identifier).status_code == 204
    assert client.get("/api/v1/services/" + identifier).status_code == 404


@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.com",
        "https://u:p@example.com",
        "http://localhost",
        "http://127.0.0.1",
        "http://10.0.0.1",
        "http://172.16.0.1",
        "http://192.168.1.1",
        "http://169.254.169.254",
        "http://[::1]",
        "http://[::ffff:127.0.0.1]",
        "http://2130706433",
        "http://0x7f000001",
        "http://127.1",
        "http://host.internal",
        "http://foo.local",
        "http://example.com:99999",
        "https://example.com/#secret",
        "https://exam ple.com",
        "http://[fc00::1]",
    ],
)
def test_url_rejections(client, url):
    assert client.post("/api/v1/services", json=payload(url=url)).status_code == 422


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com",
        "https://example.com:8443/health?q=ok",
        "https://8.8.8.8",
        "https://[2606:4700:4700::1111]",
    ],
)
def test_public_urls(url):
    assert ServiceInput(**payload(url=url)).url == url


@pytest.mark.parametrize(
    "override",
    [
        {"name": "   "},
        {"interval_seconds": 9},
        {"timeout_seconds": 61},
        {"interval_seconds": True},
        {"method": "TRACE"},
        {"status": "healthy"},
        {"password": "must-not-be-stored"},
    ],
)
def test_invalid_or_readonly_fields(client, override):
    assert client.post("/api/v1/services", json=payload(**override)).status_code == 422


def test_collection_relationships(client):
    created = client.post("/api/v1/collections", json={"name": "Production"})
    assert created.status_code == 201
    identifier = created.json()["id"]
    assert client.post("/api/v1/collections", json={"name": "PRODUCTION"}).status_code == 409
    assert client.post("/api/v1/services", json=payload(collection_id="missing")).status_code == 404
    sid = client.post("/api/v1/services", json=payload(collection_id=identifier)).json()["id"]
    assert client.delete("/api/v1/collections/" + identifier).status_code == 409
    assert (
        client.put("/api/v1/collections/" + identifier, json={"name": "Renombrada"}).status_code
        == 200
    )
    assert client.get("/api/v1/services?collection_id=" + identifier).json()[0]["id"] == sid
    assert client.put("/api/v1/services/" + sid, json=payload()).status_code == 200
    assert client.delete("/api/v1/collections/" + identifier).status_code == 204


def test_configuration_and_origin_guard(client):
    config = {"failure_alerts": False, "recovery_alerts": True, "latency_threshold": 250}
    assert client.put("/api/v1/configuration", json=config).status_code == 200
    assert client.get("/api/v1/configuration").json() == config
    assert (
        client.put("/api/v1/configuration", json={**config, "latency_threshold": 0}).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/collections",
            json={"name": "Blocked"},
            headers={"Origin": "https://untrusted.example"},
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/collections",
            json={"name": "Allowed"},
            headers={"Origin": get_settings().allowed_origins.split(",")[0]},
        ).status_code
        == 201
    )
    assert client.get("/api/v1/health").json()["status"] == "ok"


def test_migration_schema_constraints_and_cascades(migrated_engine):
    from sqlalchemy.orm import Session

    from sentinel.models import Alert, Check, Incident, Service

    with migrated_engine.connect() as connection:
        transaction = connection.begin()
        with Session(bind=connection, join_transaction_mode="create_savepoint") as db:
            service = Service(name="Cascade", url="https://example.com", collection_id=GENERAL)
            db.add(service)
            db.flush()
            sid = service.id
            incident = Incident(service_id=sid)
            db.add(incident)
            db.flush()
            db.add_all(
                [
                    Check(service_id=sid, success=False),
                    Alert(service_id=sid, incident_id=incident.id, kind="failure", message="test"),
                ]
            )
            db.commit()
            db.delete(db.get(Service, sid))
            db.commit()
            assert (
                connection.scalar(
                    text("SELECT count(*) FROM checks WHERE service_id=:id"), {"id": sid}
                )
                == 0
            )
            assert (
                connection.scalar(
                    text("SELECT count(*) FROM incidents WHERE service_id=:id"), {"id": sid}
                )
                == 0
            )
            assert (
                connection.scalar(
                    text("SELECT count(*) FROM alerts WHERE service_id=:id"), {"id": sid}
                )
                == 0
            )
        transaction.rollback()


def test_persistence_across_connections(migrated_engine):
    from sqlalchemy.orm import Session

    from sentinel.models import Collection

    identifier = None
    try:
        with Session(migrated_engine) as first:
            row = Collection(name="Persistencia", name_key="persistencia")
            first.add(row)
            first.commit()
            identifier = row.id
        with Session(migrated_engine) as second:
            assert second.get(Collection, identifier).name == "Persistencia"
    finally:
        if identifier:
            with Session(migrated_engine) as session:
                session.delete(session.get(Collection, identifier))
                session.commit()


def test_database_outage_is_sanitized(client):
    from sqlalchemy.exc import OperationalError

    from sentinel.database import get_db

    def unavailable():
        raise OperationalError(
            "sensitive query", {"password": "do-not-expose"}, Exception("private driver detail")
        )
        yield  # keep the dependency a generator

    client.app.dependency_overrides[get_db] = unavailable
    response = client.get("/api/v1/workspace")
    assert response.status_code == 503
    assert "unavailable" in response.json()["detail"]
    assert "do-not-expose" not in response.text
    assert "private driver" not in response.text


@pytest.mark.parametrize(
    "values",
    [
        {"expected_status_min": 500, "expected_status_max": 200},
        {"expected_status_min": 99},
        {"expected_status_max": 600},
        {"enabled": 1},
    ],
)
def test_monitoring_validation(client, values):
    assert client.post("/api/v1/services", json=payload(**values)).status_code == 422


def test_monitoring_endpoints_and_pausing(client):
    row = client.post("/api/v1/services", json=payload()).json()
    identifier = row["id"]
    assert (
        row["enabled"] and row["expected_status_min"] == 200 and row["expected_status_max"] == 299
    )
    paused = client.put("/api/v1/services/" + identifier + "/monitoring", json={"enabled": False})
    assert paused.status_code == 200 and not paused.json()["enabled"]
    assert client.post("/api/v1/services/" + identifier + "/check").status_code == 503
    assert client.get("/api/v1/checks?service_id=" + identifier).json() == []
    assert client.get("/api/v1/incidents?service_id=" + identifier).json() == []
    assert client.get("/api/v1/checks?limit=501").status_code == 422

    class StubMonitor:
        def __init__(self):
            self.running = set()

        async def close(self):
            self.running.clear()

        def enqueue(self, service_id, manual=False):
            if service_id in self.running:
                return False
            self.running.add(service_id)
            return True

    client.app.state.monitor = StubMonitor()
    assert client.post("/api/v1/services/" + identifier + "/check").status_code == 202
    assert client.post("/api/v1/services/" + identifier + "/check").status_code == 409
    assert client.get("/api/v1/workspace").json()["running_service_ids"] == [identifier]


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/health?token=not-a-real-secret",
        "https://example.com/health?apiKey=not-a-real-secret",
        "https://example.com/health?%74oken=not-a-real-secret",
        "https://example.com/health?PASSWORD=not-a-real-secret",
    ],
)
def test_credentials_in_url_are_not_persisted(client, url):
    assert client.post("/api/v1/services", json=payload(url=url)).status_code == 422
