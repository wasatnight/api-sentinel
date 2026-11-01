# Alignerr LBLX135 candidate — approval request draft

## Short description (English)

API Sentinel is a personal, AI-assisted local HTTP monitoring application built with React/TypeScript, FastAPI and PostgreSQL. It supports authorized public GET/HEAD checks, latency and availability history, incidents, in-app alerts, charts and CSV reports. It includes English/Spanish localization, light/dark themes and customizable browser-local profiles. The published candidate has passing local checks and a successful GitHub Actions run on Ubuntu 24.04 covering 106 backend tests, 24 frontend tests and the production frontend build; native WSL2 startup validation remains pending. It is intended for local review and has no multiuser authentication, email/webhook delivery or automatic retention. I would like to request confirmation that this existing project is eligible for LBLX135 before using it in sessions.

## Potential session tasks (not implemented yet)

1. Implement configurable retention with migration, boundary tests and an explicit data-deletion policy.
2. Add authenticated workspace access and authorization tests before any public hosting is considered.
3. Design an opt-in notification adapter with safe fake-delivery tests, retries and redacted logs.
4. Verify native Linux/WSL2 startup from a clean checkout and extend the passing CI with a fixture-only end-to-end smoke test.
5. Improve accessibility and split the large dashboard component into smaller tested units.

## Eligibility questions still pending

- Does LBLX135 accept a pre-existing personal project developed with AI assistance?
- What are the required ownership, repository visibility, licensing, confidentiality and third-party resource conditions?
- What environment, recording, tool/model, language and task requirements apply to sessions?
- Which tasks and project scope must Alignerr approve before work begins?
- Does the reference-inspired visual design need replacement or additional permission evidence?

No official LBLX135 requirements were supplied, and no authoritative public project-specific requirements were found in a focused search on 2026-11-01. These questions are not claims about Alignerr policy. Only Alignerr can approve eligibility. This file is a draft; it has not been sent. It does not complete evaluations or provide comparison justifications that must represent the participant's own judgment.
