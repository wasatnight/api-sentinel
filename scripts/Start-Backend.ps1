param([int]$Port = 8002)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
& ".\.venv\Scripts\python.exe" -m alembic -c backend/alembic.ini upgrade head
if ($LASTEXITCODE -ne 0) { throw "Migrations failed; the backend will not start." }
& ".\.venv\Scripts\python.exe" -m uvicorn sentinel.main:app --app-dir backend --host 127.0.0.1 --port $Port --no-access-log
