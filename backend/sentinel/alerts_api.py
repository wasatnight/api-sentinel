from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import update
from sqlalchemy.orm import Session

from .alerts import list_alerts
from .api import commit, required
from .database import get_db
from .models import Alert, now
from .schemas import AlertOut

router = APIRouter(prefix="/api/v1", tags=["Alerts"])


@router.get("/alerts", response_model=list[AlertOut])
def get_alerts(
    unread_only: bool = False,
    kind: Literal["failure", "degradation", "recovery"] | None = None,
    service_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    return list_alerts(
        db, unread_only=unread_only, kind=kind, service_id=service_id, limit=limit, offset=offset
    )


@router.put("/alerts/{identifier}/read", response_model=AlertOut)
def mark_read(identifier: str, db: Session = Depends(get_db)):
    obj = required(db, Alert, identifier)
    obj.read_at = obj.read_at or now()
    commit(db)
    from .models import Service

    return AlertOut.model_validate(obj).model_copy(
        update={"service_name": required(db, Service, obj.service_id).name}
    )


@router.post("/alerts/read-all")
def mark_all(db: Session = Depends(get_db)):
    result = db.execute(update(Alert).where(Alert.read_at.is_(None)).values(read_at=now()))
    commit(db)
    return {"updated": result.rowcount}
