from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import Session

from sentinel.analytics import statistics
from sentinel.config import get_settings


def test_empty_statistics_uses_only_the_scope_query(migrated_engine):
    queries = []

    def capture(conn, cursor, statement, parameters, context, executemany):
        queries.append(statement)

    event.listen(migrated_engine, "before_cursor_execute", capture)
    try:
        with Session(migrated_engine) as db:
            result = statistics(db, "30D")
        assert result["summary"]["availability"] is None
        assert result["summary"]["total_checks"] == 0 and result["services"] == []
        assert result["points"] == []
        assert len(queries) == 1
    finally:
        event.remove(migrated_engine, "before_cursor_execute", capture)


def test_migrations_upgrade_downgrade_and_upgrade_again():
    url = get_settings().connection_url()
    admin = create_engine(url, hide_parameters=True)
    schema = "migration_test_" + uuid4().hex
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
            assert "alerts" in inspect(connection).get_table_names()
            command.downgrade(config, "base")
            assert "services" not in inspect(connection).get_table_names()
            command.upgrade(config, "head")
            assert connection.scalar(text("SELECT count(*) FROM collections")) == 1
            assert "last_latency_ms" in {
                c["name"] for c in inspect(connection).get_columns("services")
            }
    finally:
        engine.dispose()
        with admin.begin() as db:
            db.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()
