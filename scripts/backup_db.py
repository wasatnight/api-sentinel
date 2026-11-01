"""Create a PostgreSQL custom-format backup without credentials in arguments or files."""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from sentinel.config import get_settings


def main():
    parser = argparse.ArgumentParser(
        description="Create a logical backup of the configured API Sentinel database."
    )
    parser.add_argument(
        "--output",
        required=True,
        help="New .dump file; existing files are never overwritten.",
    )
    parser.add_argument("--pg-dump", default=None, help="Optional path to pg_dump.")
    args = parser.parse_args()
    executable = (
        args.pg_dump
        or shutil.which("pg_dump")
        or (
            "C:/Program Files/PostgreSQL/18/bin/pg_dump.exe"
            if os.name == "nt"
            else None
        )
    )
    if not executable or not Path(executable).is_file():
        parser.error("pg_dump was not found. Use --pg-dump with its path.")
    url = get_settings().connection_url()
    if url.get_backend_name() != "postgresql":
        parser.error("Backup requires PostgreSQL.")
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "PGPASSWORD": url.password or ""}
    command = [
        executable,
        "--host",
        url.host or "127.0.0.1",
        "--port",
        str(url.port or 5432),
        "--username",
        url.username or "sentinel_app",
        "--dbname",
        url.database,
        "--format=custom",
        "--no-owner",
        "--no-acl",
        "--no-password",
    ]
    complete = False
    # Exclusive creation prevents an accidental overwrite or a concurrent file collision.
    with output.open("xb") as stream:
        try:
            result = subprocess.run(
                command, stdout=stream, stderr=subprocess.PIPE, env=env, check=False
            )
            if result.returncode:
                raise RuntimeError(
                    "pg_dump could not complete the backup. Check the connection and permissions."
                )
            complete = True
        finally:
            if not complete:
                stream.close()
                output.unlink(missing_ok=True)
    print(f"Backup created: {output}")


if __name__ == "__main__":
    main()
