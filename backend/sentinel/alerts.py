from sqlalchemy import select

from .models import Alert, Service
from .schemas import AlertOut


def list_alerts(db, *, unread_only=False, kind=None, service_id=None, limit=50, offset=0):
    query = select(Alert, Service.name).join(Service, Alert.service_id == Service.id)
    if unread_only:
        query = query.where(Alert.read_at.is_(None))
    if kind:
        query = query.where(Alert.kind == kind)
    if service_id:
        query = query.where(Alert.service_id == service_id)
    rows = db.execute(
        query.order_by(Alert.created_at.desc(), Alert.id).offset(offset).limit(limit)
    ).all()
    return [
        AlertOut.model_validate(row).model_copy(update={"service_name": name}) for row, name in rows
    ]
