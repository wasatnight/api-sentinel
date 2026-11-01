from alembic import context
from sqlalchemy import create_engine, pool

from sentinel import models  # noqa: F401
from sentinel.config import get_settings
from sentinel.database import Base

target_metadata = Base.metadata


def run(connection):
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    context.configure(
        url=get_settings().connection_url(), target_metadata=target_metadata, literal_binds=True
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    provided = context.config.attributes.get("connection")
    if provided is not None:
        run(provided)
    else:
        engine = create_engine(
            get_settings().connection_url(), poolclass=pool.NullPool, hide_parameters=True
        )
        with engine.connect() as connection:
            run(connection)
