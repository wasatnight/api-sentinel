"""Create/start only this checkout's isolated Linux PostgreSQL cluster."""
import argparse
import os
import secrets
import socket
import subprocess
import tempfile
from pathlib import Path

import psycopg
from psycopg import sql

ROOT = Path(__file__).resolve().parents[1]
PORT = 55434


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["init", "start", "stop"])
    parser.add_argument("--pg-bin", default="/usr/lib/postgresql/18/bin")
    args = parser.parse_args()
    if os.name == "nt" or os.geteuid() == 0:
        parser.error("Use a regular Linux/WSL user, not root or Windows.")
    pg = Path(args.pg_bin)
    data = ROOT / ".runtime/linux-postgres"
    runtime = data.parent
    if not (pg / "pg_ctl").is_file():
        parser.error("PostgreSQL binaries not found; set --pg-bin.")
    if args.action == "stop":
        if not (data / "PG_VERSION").exists():
            parser.error("This checkout has no Linux cluster.")
        subprocess.run([str(pg / "pg_ctl"), "-D", str(data), "-m", "fast", "-w", "stop"], check=True)
        return
    with socket.socket() as check:
        check.bind(("127.0.0.1", PORT))
    if args.action == "start":
        if not (data / "PG_VERSION").exists():
            parser.error("Run init first.")
        subprocess.run([str(pg / "pg_ctl"), "-D", str(data), "-l", str(runtime / "linux-postgres.log"), "-w", "start"], check=True)
        return
    if data.exists() or (ROOT / ".env").exists():
        parser.error("Refusing to overwrite an existing cluster or .env. Use a fresh checkout.")
    runtime.mkdir(mode=0o700, exist_ok=True)
    password = secrets.token_hex(32)
    app_password = secrets.token_hex(32)
    fd, password_path = tempfile.mkstemp(dir=runtime)
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(password + "\n")
        subprocess.run([str(pg / "initdb"), "-D", str(data), "-U", "sentinel_admin", "--auth=scram-sha-256", "--encoding=UTF8", "--locale=C", "--pwfile=" + password_path], check=True)
    finally:
        Path(password_path).unlink(missing_ok=True)
    with (data / "postgresql.conf").open("a") as stream:
        stream.write("\nlisten_addresses = '127.0.0.1'\nport = 55434\nunix_socket_directories = ''\n")
    subprocess.run([str(pg / "pg_ctl"), "-D", str(data), "-l", str(runtime / "linux-postgres.log"), "-w", "start"], check=True)
    with psycopg.connect(host="127.0.0.1", port=PORT, user="sentinel_admin", password=password, dbname="postgres", autocommit=True, connect_timeout=10) as connection:
        connection.execute(sql.SQL("CREATE ROLE sentinel_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD {}").format(sql.Literal(app_password)))
        connection.execute("CREATE DATABASE api_sentinel_review OWNER sentinel_app")
    config = (ROOT / ".env.example").read_text().replace("SENTINEL_DB_PASSWORD=\n", "SENTINEL_DB_PASSWORD=" + app_password + "\n")
    fd = os.open(ROOT / ".env", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as stream:
        stream.write(config)
    print("Fresh local cluster initialized on 55434. Credentials are in ignored .env (0600); monitoring is disabled.")


if __name__ == "__main__":
    main()
