param([string]$PgBin = "C:\Program Files\PostgreSQL\18\bin", [int]$Port = 55434)
$ErrorActionPreference = "Stop"
function New-DatabasePassword {
 $bytes = New-Object byte[] 32
 $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
 try { $rng.GetBytes($bytes); return [BitConverter]::ToString($bytes).Replace("-", "") } finally { $rng.Dispose() }
}
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
$runtime = Join-Path $root ".runtime"
$dataDir = Join-Path $runtime "postgres"
New-Item -ItemType Directory -Force $runtime | Out-Null
if (!(Test-Path (Join-Path $PgBin "pg_ctl.exe"))) { throw "PostgreSQL was not found. Use -PgBin with its bin directory or Docker Compose." }
if (!(Test-Path (Join-Path $dataDir "PG_VERSION"))) {
    if (Test-NetConnection -ComputerName 127.0.0.1 -Port $Port -InformationLevel Quiet -WarningAction SilentlyContinue) { throw "Port $Port is in use. No database instance was changed." }
    $adminPassword = New-DatabasePassword
    $appPassword = New-DatabasePassword
    ConvertTo-SecureString $adminPassword -AsPlainText -Force | ConvertFrom-SecureString | Set-Content -LiteralPath (Join-Path $runtime "admin-password.dpapi")
    ConvertTo-SecureString $appPassword -AsPlainText -Force | ConvertFrom-SecureString | Set-Content -LiteralPath (Join-Path $runtime "db-password.dpapi")
    $env:SENTINEL_INIT_PASSWORD = $adminPassword
    try { & ".\.venv\Scripts\python.exe" "scripts\init_cluster.py" (Join-Path $PgBin "initdb.exe") $dataDir }
    finally { Remove-Item Env:SENTINEL_INIT_PASSWORD -ErrorAction SilentlyContinue }
    if ($LASTEXITCODE -ne 0) { throw "initdb failed." }
    Add-Content -LiteralPath (Join-Path $dataDir "postgresql.conf") -Value "listen_addresses = '127.0.0.1'"
    Add-Content -LiteralPath (Join-Path $dataDir "postgresql.conf") -Value "port = $Port"
}
& (Join-Path $PgBin "pg_isready.exe") -h 127.0.0.1 -p $Port -d postgres -U sentinel_admin *> $null
if ($LASTEXITCODE -ne 0) {
    & (Join-Path $PgBin "pg_ctl.exe") -D $dataDir -l (Join-Path $runtime "postgres.log") -w start
    if ($LASTEXITCODE -ne 0) { throw "Could not start PostgreSQL. Check .runtime/postgres.log." }
}
if (!(Test-Path ".env")) {
    Copy-Item -LiteralPath ".env.example" -Destination ".env"
    Add-Content -LiteralPath ".env" -Value "SENTINEL_DB_PASSWORD_FILE=.runtime/db-password.dpapi"
}
& ".\.venv\Scripts\python.exe" "scripts\bootstrap_db.py" $Port
if ($LASTEXITCODE -ne 0) { throw "Could not prepare the database." }
Write-Host "Project PostgreSQL is available at 127.0.0.1:$Port."
