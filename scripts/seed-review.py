"""Insert fictional, paused screenshot fixtures into an EMPTY review database only."""
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from sentinel.config import get_settings
from sentinel.database import engine
from sentinel.models import Check, Collection, Service

if os.environ.get("SENTINEL_ALLOW_FICTIONAL_SEED") != "yes":
    raise SystemExit("Set SENTINEL_ALLOW_FICTIONAL_SEED=yes for this explicit fixture operation.")
settings = get_settings()
if settings.connection_url().database != "api_sentinel_review" or settings.monitoring_enabled:
    raise SystemExit("Requires api_sentinel_review with monitoring disabled.")
with Session(engine) as db:
    if db.scalar(select(func.count()).select_from(Service)):
        raise SystemExit("Refusing to seed a database that already contains services.")
    group = db.scalar(select(Collection).limit(1))
    if group is None:
        group = Collection(name="Fictional fixtures", name_key="fictional fixtures")
        db.add(group)
        db.flush()
    now = datetime.now(UTC)
    for index, name in enumerate(["Fixture Catalog API", "Fixture Payments API", "Fixture Notifications API"]):
        service = Service(name=name, url=f"https://service{index}.example.com/health", method="GET", collection_id=group.id, enabled=False, status="healthy", last_checked_at=now, last_latency_ms=95 + index * 35)
        db.add(service)
        db.flush()
        for n in range(24):
            db.add(Check(service_id=service.id, checked_at=now - timedelta(minutes=n * 5), status_code=200, latency_ms=95 + index * 35 + n % 7, success=True, status="healthy", attempts=1))
    db.commit()
print("Created fictional paused fixtures. No HTTP requests were sent.")
