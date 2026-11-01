# Third-party notices

Project code is licensed under MIT (see LICENSE). Dependencies remain under upstream licenses; the project license does not replace them. This inventory records metadata and retained notices; it is not legal certification.

## Important distinctions

- Psycopg and psycopg-binary: LGPL-3.0-only. Installed as external Python dependencies; not copied into this source repository. Preserve licensing and replacement/relinking rights for any future bundled distribution. Binary wheels may contain separately licensed native libraries; inspect their notices before distributing a packaged runtime.
- Certifi: MPL-2.0 for the certificate bundle. No upstream modifications made; its notices must remain intact.
- caniuse-lite: CC-BY-4.0 data attribution. See the package entry and upstream notice; its dataset is not project-owned.
- Lucide: ISC plus MIT for Feather-derived icons. Full installed notice retained in docs/licenses/lucide-react-LICENSE.txt.
- Other packages include MIT, Apache-2.0, BSD, ISC and PSF variants. Full lockfile metadata inventory is docs/dependency-licenses.json.

## Python dependency inventory

| Package | Version | License metadata |
|---|---|---|
| alembic | 1.20.1 | MIT |
| annotated-doc | 0.0.5 | MIT |
| annotated-types | 0.8.0 | MIT |
| anyio | 4.15.1 | MIT |
| certifi | 2026.10.23 | MPL-2.0 |
| click | 8.5.0 | BSD-3-Clause |
| colorama | 0.4.6 | BSD-3-Clause (installed LICENSE.txt) |
| fastapi | 0.162.0 | MIT |
| greenlet | 3.5.6 | MIT AND PSF-2.0 |
| h11 | 0.16.0 | MIT |
| httpcore | 1.0.9 | BSD-3-Clause |
| httpx | 0.28.1 | BSD-3-Clause |
| idna | 3.20 | BSD-3-Clause |
| iniconfig | 2.3.1 | MIT |
| Mako | 1.4.3 | MIT |
| MarkupSafe | 3.0.4 | BSD-3-Clause |
| opentelemetry-api | 1.45.1 | Apache-2.0 |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause |
| pluggy | 1.7.0 | MIT |
| psycopg | 3.3.6 | LGPL-3.0-only |
| psycopg-binary | 3.3.6 | LGPL-3.0-only |
| pydantic | 2.14.1 | MIT |
| pydantic_core | 2.50.1 | MIT |
| pydantic-settings | 2.16.1 | MIT |
| Pygments | 2.21.0 | BSD-2-Clause |
| pytest | 9.1.1 | MIT |
| pytest-asyncio | 1.4.1 | Apache-2.0 |
| python-dotenv | 1.2.4 | BSD-3-Clause |
| ruff | 0.17.3 | MIT |
| SQLAlchemy | 2.0.55 | MIT |
| starlette | 1.10.0 | BSD-3-Clause |
| typing_extensions | 4.16.0 | PSF-2.0 |
| typing-inspection | 0.4.4 | MIT |
| tzdata | 2026.5 | Apache-2.0 |
| uvicorn | 0.54.0 | BSD-3-Clause |

## npm graph

161 dependency entries including optional platform binaries. SPDX metadata and versions are recorded in docs/dependency-licenses.json. Installed upstream license texts are retained under docs/licenses; uninstalled platform-specific optional artifacts were not downloaded for this review. Re-run inventory and review notices when dependencies change.

## References

- https://www.psycopg.org/psycopg3/docs/ (Psycopg licensing and installation)
- https://github.com/certifi/python-certifi (Certifi license)
- https://github.com/browserslist/caniuse-lite (CC-BY data)
- https://lucide.dev/license (icons)
- https://choosealicense.com/licenses/mit/ (approved project license)
