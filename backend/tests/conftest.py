import os
from functools import partial
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from alembic import command
from alembic.config import Config
from anyio.from_thread import start_blocking_portal
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from sentinel.database import get_db
from sentinel.main import create_app


@pytest.fixture(scope="session")
def migrated_engine():
    url = os.environ.get("SENTINEL_TEST_DATABASE_URL")
    if not url:
        pytest.fail("Set SENTINEL_TEST_DATABASE_URL to a disposable review/test database. Runtime data is never a test fallback.")
    admin = create_engine(url, hide_parameters=True)
    # Each run owns a random schema; no existing schema or database is deleted.
    schema = "test_" + uuid4().hex
    with admin.begin() as db:
        db.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(
        url, connect_args={"options": f"-csearch_path={schema}"}, hide_parameters=True
    )
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    try:
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
        yield engine
    finally:
        engine.dispose()
        # schema is generated above and cannot include user input.
        with admin.begin() as db:
            db.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


@pytest.fixture
def client(migrated_engine):
    connection = migrated_engine.connect()
    transaction = connection.begin()
    app = create_app()

    def session_override():
        with Session(
            bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
        ) as session:
            yield session

    app.dependency_overrides[get_db] = session_override

    class Client:
        def __init__(self, wrapped, portal):
            self.app = app
            self.wrapped = wrapped
            self.portal = portal

        def request(self, method, path, **kwargs):
            return self.portal.call(partial(self.wrapped.request, method, path, **kwargs))

        def get(self, path, **kwargs):
            return self.request("GET", path, **kwargs)

        def post(self, path, **kwargs):
            return self.request("POST", path, **kwargs)

        def put(self, path, **kwargs):
            return self.request("PUT", path, **kwargs)

        def delete(self, path, **kwargs):
            return self.request("DELETE", path, **kwargs)

    try:
        with start_blocking_portal() as portal:
            with portal.wrap_async_context_manager(app.router.lifespan_context(app)):
                transport = httpx.ASGITransport(app=app)
                with portal.wrap_async_context_manager(
                    httpx.AsyncClient(transport=transport, base_url="http://testserver")
                ) as wrapped:
                    yield Client(wrapped, portal)
    finally:
        transaction.rollback()
        connection.close()
