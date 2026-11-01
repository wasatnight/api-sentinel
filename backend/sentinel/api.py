import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from .alerts import list_alerts
from .config import get_settings
from .database import get_db
from .models import Alert, Check, Collection, Configuration, Incident, Service, now
from .schemas import (
    CheckOut,
    CollectionInput,
    CollectionOut,
    ConfigurationInput,
    ConfigurationOut,
    EnabledInput,
    IncidentInput,
    IncidentOut,
    ServiceInput,
    ServiceOut,
)

router = APIRouter(prefix="/api/v1")
logger = logging.getLogger("sentinel")


def required(db, model, identifier):
    obj = db.get(model, identifier)
    if obj is None:
        raise HTTPException(404, "The record does not exist.")
    return obj


def commit(db):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "The record already exists or has dependencies.") from None


@router.get("/health")
def health(request: Request, db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {
        "status": "ok",
        "phase": 5,
        "version": "1.1.0",
        "monitoring_enabled": getattr(request.app.state, "monitor", None) is not None,
    }


@router.get("/collections", response_model=list[CollectionOut])
def collections(db: Session = Depends(get_db)):
    return db.scalars(select(Collection).order_by(Collection.created_at, Collection.id)).all()


@router.post("/collections", response_model=CollectionOut, status_code=201)
def create_collection(body: CollectionInput, db: Session = Depends(get_db)):
    if db.scalar(select(func.count()).select_from(Collection)) >= 100:
        raise HTTPException(409, "The limit of 100 collections has been reached.")
    obj = Collection(name=body.name, name_key=body.name.casefold())
    db.add(obj)
    commit(db)
    return obj


@router.put("/collections/{identifier}", response_model=CollectionOut)
def update_collection(identifier: str, body: CollectionInput, db: Session = Depends(get_db)):
    obj = required(db, Collection, identifier)
    obj.name = body.name
    obj.name_key = body.name.casefold()
    commit(db)
    return obj


@router.delete("/collections/{identifier}", status_code=204)
def delete_collection(identifier: str, db: Session = Depends(get_db)):
    obj = required(db, Collection, identifier)
    if db.scalar(
        select(func.count()).select_from(Service).where(Service.collection_id == identifier)
    ):
        raise HTTPException(409, "Move or delete the services before deleting this collection.")
    db.delete(obj)
    commit(db)
    return Response(status_code=204)


@router.get("/services", response_model=list[ServiceOut])
def services(
    collection_id: str | None = None,
    q: str = Query(default="", max_length=80),
    limit: int = Query(default=1000, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    query = select(Service)
    if collection_id:
        query = query.where(Service.collection_id == collection_id)
    if q:
        query = query.where(
            Service.name.icontains(q, autoescape=True) | Service.url.icontains(q, autoescape=True)
        )
    return db.scalars(
        query.order_by(Service.created_at, Service.id).offset(offset).limit(limit)
    ).all()


@router.get("/services/{identifier}", response_model=ServiceOut)
def service(identifier: str, db: Session = Depends(get_db)):
    return required(db, Service, identifier)


@router.post("/services", response_model=ServiceOut, status_code=201)
def create_service(body: ServiceInput, db: Session = Depends(get_db)):
    required(db, Collection, body.collection_id)
    if db.scalar(select(func.count()).select_from(Service)) >= get_settings().max_services:
        raise HTTPException(409, "The service limit has been reached.")
    obj = Service(**body.model_dump())
    db.add(obj)
    commit(db)
    return obj


@router.put("/services/{identifier}", response_model=ServiceOut)
def update_service(identifier: str, body: ServiceInput, db: Session = Depends(get_db)):
    edit_lock(db, identifier)
    obj = required(db, Service, identifier)
    required(db, Collection, body.collection_id)
    for key, value in body.model_dump().items():
        setattr(obj, key, value)
    obj.next_check_at = None
    commit(db)
    return obj


@router.delete("/services/{identifier}", status_code=204)
def delete_service(identifier: str, db: Session = Depends(get_db)):
    edit_lock(db, identifier)
    db.delete(required(db, Service, identifier))
    commit(db)
    return Response(status_code=204)


@router.get("/configuration", response_model=ConfigurationOut)
def configuration(db: Session = Depends(get_db)):
    return required(db, Configuration, 1)


@router.put("/configuration", response_model=ConfigurationOut)
def update_configuration(body: ConfigurationInput, db: Session = Depends(get_db)):
    obj = required(db, Configuration, 1)
    for key, value in body.model_dump().items():
        setattr(obj, key, value)
    commit(db)
    return obj


@router.get("/workspace")
def workspace(request: Request, db: Session = Depends(get_db)):
    return {
        "services": [
            ServiceOut.model_validate(s)
            for s in services(collection_id=None, q="", limit=1000, offset=0, db=db)
        ],
        "collections": [CollectionOut.model_validate(c) for c in collections(db=db)],
        "configuration": ConfigurationOut.model_validate(configuration(db=db)),
        "alerts": list_alerts(db),
        "unread_alert_count": db.scalar(
            select(func.count()).select_from(Alert).where(Alert.read_at.is_(None))
        ),
        "checks": checks(service_id=None, limit=100, offset=0, db=db),
        "incidents": incidents(service_id=None, state=None, limit=100, offset=0, db=db),
        "active_incident_count": db.scalar(
            select(func.count()).select_from(Incident).where(Incident.state != "resolved")
        ),
        "running_service_ids": sorted(request.app.state.monitor.running)
        if getattr(request.app.state, "monitor", None)
        else [],
        "monitoring_enabled": getattr(request.app.state, "monitor", None) is not None,
        "phase": 5,
        "version": "1.1.0",
    }


def database_error_handler(request, exc: SQLAlchemyError):
    # Do not expose SQL, connection URLs, bind parameters or driver exception strings.
    logger.error("Database operation failed (%s)", type(exc).__name__)
    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=503,
        content={
            "detail": "Database unavailable. Check the local database service and migrations."
        },
    )


def edit_lock(db, identifier):
    if not db.scalar(
        text("SELECT pg_try_advisory_xact_lock(hashtextextended(:id, 0))"), {"id": identifier}
    ):
        raise HTTPException(409, "A check is in progress. Wait for it to finish.")


@router.get("/checks", response_model=list[CheckOut])
def checks(
    service_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    query = select(Check, Service.name).join(Service, Check.service_id == Service.id)
    if service_id:
        query = query.where(Check.service_id == service_id)
    rows = db.execute(
        query.order_by(Check.checked_at.desc(), Check.id).offset(offset).limit(limit)
    ).all()
    return [
        CheckOut.model_validate(row).model_copy(update={"service_name": name}) for row, name in rows
    ]


def incident_out(row, name):
    return IncidentOut.model_validate(row).model_copy(
        update={
            "service_name": name,
            "duration_seconds": max(
                0, int(((row.resolved_at or now()) - row.started_at).total_seconds())
            ),
        }
    )


@router.get("/incidents", response_model=list[IncidentOut])
def incidents(
    service_id: str | None = None,
    state: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    query = select(Incident, Service.name).join(Service, Incident.service_id == Service.id)
    if service_id:
        query = query.where(Incident.service_id == service_id)
    if state:
        query = query.where(Incident.state == state)
    # Active incidents first so a long resolved history cannot hide an active outage.
    rows = db.execute(
        query.order_by((Incident.state == "resolved").asc(), Incident.started_at.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return [incident_out(row, name) for row, name in rows]


@router.put("/incidents/{identifier}", response_model=IncidentOut)
def change_incident(identifier: str, body: IncidentInput, db: Session = Depends(get_db)):
    obj = required(db, Incident, identifier)
    edit_lock(db, obj.service_id)
    db.refresh(obj)
    if obj.state == "resolved" and body.state != "resolved":
        raise HTTPException(
            409, "A resolved incident preserves its history and cannot be reopened."
        )
    obj.state = body.state
    obj.resolved_at = (obj.resolved_at or now()) if body.state == "resolved" else None
    commit(db)
    return incident_out(obj, required(db, Service, obj.service_id).name)


@router.put("/services/{identifier}/monitoring", response_model=ServiceOut)
def enable_service(identifier: str, body: EnabledInput, db: Session = Depends(get_db)):
    edit_lock(db, identifier)
    obj = required(db, Service, identifier)
    obj.enabled = body.enabled
    obj.next_check_at = None
    commit(db)
    return obj


@router.post("/services/{identifier}/check", status_code=202)
async def check_now(identifier: str, request: Request, db: Session = Depends(get_db)):
    required(db, Service, identifier)
    monitor = getattr(request.app.state, "monitor", None)
    if monitor is None:
        raise HTTPException(503, "The monitoring engine is not active.")
    if not monitor.enqueue(identifier, manual=True):
        raise HTTPException(409, "The service is already being checked or the engine is busy.")
    return {"service_id": identifier, "state": "queued"}


@router.post("/check-enabled", status_code=202)
async def check_enabled(request: Request, db: Session = Depends(get_db)):
    monitor = getattr(request.app.state, "monitor", None)
    if monitor is None:
        raise HTTPException(503, "The monitoring engine is not active.")
    identifiers = db.scalars(select(Service.id).where(Service.enabled.is_(True))).all()
    db.execute(update(Service).where(Service.enabled.is_(True)).values(next_check_at=now()))
    db.commit()
    accepted = [
        identifier for identifier in identifiers if monitor.enqueue(identifier, manual=True)
    ]
    return {"accepted": accepted, "pending": len(identifiers) - len(accepted)}
