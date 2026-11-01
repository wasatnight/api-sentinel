# Linux / Windows WSL2 setup

Status on 2026-11-01: `wsl --status` and `wsl --list --verbose` reported WSL is not installed. No WSL installation, elevation or reboot was attempted. The Linux helper was reviewed and linted, **not executed under Linux/WSL**. GitHub Actions has now passed its automated checks on Ubuntu 24.04; this does not verify the native WSL startup procedure.

## 1. Optional WSL installation (owner action)

Microsoft's installation instructions require an administrator PowerShell and may require reboot. Save work first and decide when to allow these system changes. Do not execute this as a routine project startup command:

```powershell
wsl --install -d Ubuntu-24.04
# Restart Windows if requested; then create the Linux user interactively.
wsl --list --verbose
```

Confirm the distribution shows VERSION 2. If it does not, use Microsoft's WSL troubleshooting guidance. Source: https://learn.microsoft.com/windows/wsl/install . This document is an instruction, not evidence that WSL was installed or accepted by Alignerr.

Work in Linux home, e.g. `~/projects/api-sentinel`, rather than reusing the existing Windows checkout under /mnt/c. Copy only the reviewed source or clone the repository **after it has been approved and created**. Do not copy Windows .venv, node_modules, .env, .runtime or DPAPI secrets. All commands below run as a regular Linux user; use sudo only for package installation.

## 2. Prerequisites (Ubuntu 24.04)

```bash
sudo apt update
sudo apt install -y python3.12 python3.12-venv python3-pip git curl ca-certificates xz-utils
```

Install Node.js 22.x, at least 22.12, using an official distribution or a reviewed version manager. The official archive approach below selects 22.22.0 and verifies the archive checksum from nodejs.org. Choose the matching CPU architecture; do not use x64 on ARM.

```bash
case "$(uname -m)" in x86_64) NODE_ARCH=x64;; aarch64) NODE_ARCH=arm64;; *) echo 'Unsupported architecture'; exit 1;; esac
NODE_VERSION=v22.22.0
mkdir -p "$HOME/.local/node-download" "$HOME/.local/node"
cd "$HOME/.local/node-download"
curl -fSLO "https://nodejs.org/dist/$NODE_VERSION/node-$NODE_VERSION-linux-$NODE_ARCH.tar.xz"
curl -fSLO "https://nodejs.org/dist/$NODE_VERSION/SHASUMS256.txt"
grep " node-$NODE_VERSION-linux-$NODE_ARCH.tar.xz$" SHASUMS256.txt | sha256sum -c -
tar -xJf "node-$NODE_VERSION-linux-$NODE_ARCH.tar.xz" -C "$HOME/.local/node" --strip-components=1
export PATH="$HOME/.local/node/bin:$PATH"
node --version
npm --version
```

Keep the PATH export in your Linux shell profile if desired. Verify release availability/checksums at https://nodejs.org/dist/ ; checksum verification over the same HTTPS source is not independent signature verification.

Install PostgreSQL 18 from the PostgreSQL repository (changes Linux package sources; review the vendor's instructions first):

```bash
sudo apt install -y postgresql-common
sudo /usr/share/postgresql-common/pgdg/apt.postgresql.org.sh
sudo apt update
sudo apt install -y postgresql-18 postgresql-client-18
/usr/lib/postgresql/18/bin/postgres --version
```

Reference: https://www.postgresql.org/download/linux/ubuntu/ . Package installation may create/start a system cluster on 5432; this project does not modify or use that cluster. The project helper creates its own cluster under this checkout's ignored .runtime and refuses a port collision.

## 3. Native isolated project database (preferred without Docker)

From a fresh source directory:

```bash
cd "$HOME/projects/api-sentinel"
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.lock.txt
npm ci --ignore-scripts
python scripts/init-linux-db.py init --pg-bin /usr/lib/postgresql/18/bin
python -m alembic -c backend/alembic.ini upgrade head
bash scripts/start-linux.sh
```

The helper refuses to overwrite .env or an existing data directory. It uses SCRAM authentication, a dedicated non-superuser application role, a generated password in .env mode 0600, a temporary initdb password file removed after use, loopback TCP and port 55434. It runs initdb as the Linux user, never as root. It does not import Windows secrets or use DPAPI.

In another terminal in the same checkout: `npm run dev`. Open http://127.0.0.1:5175/; API http://127.0.0.1:8002/docs. Do not change Vite binding to expose it publicly. If Windows cannot reach the WSL loopback listener, consult Microsoft's networking guidance; do not add a public port-forward as a workaround.

On subsequent runs: `python scripts/init-linux-db.py start`, then migrations/API/UI. Stop API/UI with Ctrl+C and `python scripts/init-linux-db.py stop`; do not delete the data directory.

## 4. Docker alternative (use instead of the native helper)

Requires Docker Engine/Compose installed in Linux or Docker Desktop WSL integration, neither verified on this computer. Use the same fresh checkout and Python/Node preparation. Create .env and export two independent generated disposable passwords:

```bash
umask 077
cp .env.example .env
export SENTINEL_DB_ADMIN_PASSWORD="$(python -c 'import secrets; print(secrets.token_hex(32))')"
export SENTINEL_DB_PASSWORD="$(python -c 'import secrets; print(secrets.token_hex(32))')"
docker compose -p api-sentinel-review up -d db
# Keep SENTINEL_DB_PASSWORD exported in the API/test terminal.
python -m alembic -c backend/alembic.ini upgrade head
bash scripts/start-linux.sh
```

Docker's initialization script creates a non-superuser sentinel_app role. Admin password is not the app password. Keep exported passwords in the terminal until provisioning is finished; securely retain the app password locally if the cluster is reused. Never commit them or paste them into documentation. An already initialized volume does not rotate credentials when environment variables change. `docker compose -p api-sentinel-review stop` retains data. Do not use `down -v` on data you want to keep.

## 5. Ports and data separation

| Installation | UI | API | PostgreSQL | Database |
|---|---:|---:|---:|---|
| Earlier original copy | 5173 | 8000 | 55432 | api_sentinel |
| Existing Windows user copy | 5174 | 8001 | 55433 | api_sentinel |
| Publication candidate | 5175 | 8002 | 55434 | api_sentinel_review |

These are distinct installations, not interchangeable connection settings. Native Linux and Docker alternatives both use 55434, so run only one at a time. Never point the candidate/test suite at either existing Windows database. Local audit QA used a separate temporary 55436/55437 clusters, stopped after the tests; it is not a published default.

## 6. Fictional review fixtures and tests

No fixtures are seeded automatically. With monitoring disabled and an empty api_sentinel_review database, opt in explicitly:

```bash
SENTINEL_ALLOW_FICTIONAL_SEED=yes python scripts/seed-review.py
```

The script inserts 3 paused fictional services and 72 synthetic check rows; it sends no HTTP request and refuses to run if services already exist or the configured database name differs. These figures must never be presented as live monitoring evidence. See README for tests. Use only your own/authorized endpoints for live checks, GET/HEAD, with monitoring deliberately enabled.

## Pending platform verification

Run the complete README procedure and tests in a clean WSL2 environment, confirm migrations and shutdown/restart, and inspect permissions. These native startup checks remain pending. The first real GitHub Actions run passed separately on Ubuntu 24.04: https://github.com/wasatnight/api-sentinel/actions/runs/41297019150
