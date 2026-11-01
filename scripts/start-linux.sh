#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
exec .venv/bin/python -m uvicorn sentinel.main:app --app-dir backend --host 127.0.0.1 --port 8002 --no-access-log
