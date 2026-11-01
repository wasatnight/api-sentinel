"""Prepare only the isolated API Sentinel database and a non-administrative login."""

import sys
from pathlib import Path

import psycopg
from psycopg import sql

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "backend"))
from sentinel.secrets import decrypt_windows_secret

with psycopg.connect(
    host="127.0.0.1",
    port=int(sys.argv[1]),
    dbname="postgres",
    user="sentinel_admin",
    password=decrypt_windows_secret(root / ".runtime/admin-password.dpapi"),
    autocommit=True,
) as db:
    directory = Path(db.execute("SHOW data_directory").fetchone()[0]).resolve()
    if directory != (root / ".runtime/postgres").resolve():
        raise RuntimeError(
            "The instance on this port does not belong to this project."
        )
    if not db.execute(
        "SELECT 1 FROM pg_roles WHERE rolname = 'sentinel_app'"
    ).fetchone():
        db.execute(
            sql.SQL(
                "CREATE ROLE sentinel_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD {}"
            ).format(
                sql.Literal(decrypt_windows_secret(root / ".runtime/db-password.dpapi"))
            )
        )
    if not db.execute(
        "SELECT 1 FROM pg_database WHERE datname = 'api_sentinel_review'"
    ).fetchone():
        db.execute("CREATE DATABASE api_sentinel_review OWNER sentinel_app")
print("Non-administrative application role and project database are ready.")
