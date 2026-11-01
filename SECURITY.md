# Security and privacy

Local development/review software, not a public monitoring service. Bind API and UI to 127.0.0.1. Do not expose PostgreSQL, use --host 0.0.0.0, add a tunnel or deploy this candidate publicly. The application has no authentication.

Outbound checks accept GET/HEAD only in the UI and request schema, with a defensive probe guard and a database constraint. URL and resolved-address checks reject private destinations, mixed public/private DNS, credentials, common secret query keys and unsafe redirects. Tests cover these boundaries with controlled transports/sockets, not requests to arbitrary live systems. Public does not mean authorized.

Do not place tokens in service URLs or profile text. Do not use real customer data in screenshots, fixtures or issue reports. .env.example contains no active credential. Runtime passwords, .env*, DPAPI files, clusters, dumps, SQL exports, logs, installed dependencies, private keys and IDE settings are ignored and excluded from the reviewed staged snapshot. Git ignore rules alone do not remove previously committed secrets.

The Linux helper writes a generated application password to an ignored .env with mode 0600 and deletes the temporary initdb password file. Windows helpers use DPAPI tied to the local user. Docker uses separately generated admin/application environment values. These are local-development mechanisms, not a production secret vault. Do not print environment variables or paste logs containing connection strings into GitHub.

No exploit payloads or exploitation tooling were identified in the reviewed source. This is not a penetration-test certification or a comprehensive independent security audit. PyPI advisory metadata and npm audit were checked on 2026-11-01; clean results do not guarantee absence of vulnerabilities.

Before reporting a suspected security issue, provide only a minimal reproduction with fictional endpoints and no credentials. A private reporting channel must be configured by the owner before publication; none is asserted here.
