#!/usr/bin/env bash
set -euo pipefail
# Uses the disposable cluster password without echoing it or embedding it in SQL.
psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --set=ON_ERROR_STOP=1 <<'SQL'
\getenv app_password SENTINEL_DB_PASSWORD
CREATE ROLE sentinel_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD :'app_password';
ALTER DATABASE api_sentinel_review OWNER TO sentinel_app;
SQL
