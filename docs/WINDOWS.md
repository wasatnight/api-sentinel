# Separate Windows review checkout

The existing Desktop installation is not modified by this candidate. Open the new candidate folder itself, not its parent. Install Python 3.12+, Node.js 22.12+ (22.x) and PostgreSQL 18 first. Create a fresh environment and dependencies:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.lock.txt
npm.cmd ci --ignore-scripts
```

Database terminal:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\scripts\Start-Database.ps1
```

API terminal (same directory):

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\scripts\Start-Backend.ps1
```

UI terminal (same directory): `npm.cmd run dev`. Candidate UI 5175; API 8002; database 55434/api_sentinel_review. Startup scripts do not install software and refuse to initialize a new database if the port is occupied. Review a downloaded script before individually unblocking it if Windows marks it as downloaded. Do not change execution policy permanently.

The helper creates this checkout's own .runtime and encrypted DPAPI password files bound to your Windows account; it never imports existing ones. .env is created from .env.example only if absent; monitoring defaults to false. A locally enabled monitoring flag requires an intentional restart. Use only authorized GET/HEAD health endpoints. Stop API/UI with Ctrl+C and then scripts/Stop-Database.ps1. Runtime and credentials are never part of the source publication.

Do not use the review code to upgrade an existing operational database. The new GET/HEAD migration refuses existing unsupported-method services without changing them. Review any legacy upgrade independently and back up first.
