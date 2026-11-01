param([string]$PgBin = "C:\Program Files\PostgreSQL\18\bin")
$root = Split-Path $PSScriptRoot -Parent
$dataDir = Join-Path $root ".runtime\postgres"
if (!(Test-Path (Join-Path $dataDir "PG_VERSION"))) { throw "The database instance for this project does not exist." }
& (Join-Path $PgBin "pg_ctl.exe") -D $dataDir -w stop -m fast
