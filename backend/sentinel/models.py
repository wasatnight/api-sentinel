from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def uid():
    return str(uuid4())


def now():
    return datetime.now(timezone.utc)


class Collection(Base):
    __tablename__ = "collections"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    name_key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    services: Mapped[list["Service"]] = relationship(back_populates="collection")


class Service(Base):
    __tablename__ = "services"
    __table_args__ = (
        CheckConstraint("interval_seconds BETWEEN 10 AND 86400", name="ck_service_interval"),
        CheckConstraint("timeout_seconds BETWEEN 1 AND 60", name="ck_service_timeout"),
        CheckConstraint(
            "method IN ('GET','HEAD')",
            name="ck_service_method",
        ),
        CheckConstraint(
            "status IN ('unknown','healthy','degraded','down')", name="ck_service_status"
        ),
        Index("ix_services_collection_created", "collection_id", "created_at"),
        Index("ix_services_due", "enabled", "next_check_at"),
        CheckConstraint(
            "expected_status_min BETWEEN 100 AND 599 AND expected_status_max BETWEEN expected_status_min AND 599",
            name="ck_expected_status",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    method: Mapped[str] = mapped_column(String(8), default="GET")
    interval_seconds: Mapped[int] = mapped_column(Integer, default=60)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=10)
    collection_id: Mapped[str] = mapped_column(ForeignKey("collections.id", ondelete="RESTRICT"))
    status: Mapped[str] = mapped_column(String(16), default="unknown")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    expected_status_min: Mapped[int] = mapped_column(Integer, default=200, server_default="200")
    expected_status_max: Mapped[int] = mapped_column(Integer, default=299, server_default="299")
    next_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_latency_ms: Mapped[float | None] = mapped_column(Float)
    collection: Mapped[Collection] = relationship(back_populates="services")


class Check(Base):
    __tablename__ = "checks"
    __table_args__ = (
        Index("ix_checks_service_time", "service_id", "checked_at"),
        Index("ix_checks_time_service", "checked_at", "service_id"),
        CheckConstraint("attempts BETWEEN 1 AND 2", name="ck_check_attempts"),
        CheckConstraint(
            "status IN ('unknown','healthy','degraded','down')", name="ck_check_status"
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    service_id: Mapped[str] = mapped_column(ForeignKey("services.id", ondelete="CASCADE"))
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    status_code: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[float | None] = mapped_column(Float)
    success: Mapped[bool] = mapped_column(Boolean)
    error: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="unknown", server_default="unknown")
    attempts: Mapped[int] = mapped_column(Integer, default=1, server_default="1")


class Incident(Base):
    __tablename__ = "incidents"
    __table_args__ = (
        CheckConstraint(
            "state IN ('investigating','monitoring','resolved')", name="ck_incident_state"
        ),
        Index("ix_incidents_service_started", "service_id", "started_at"),
        Index(
            "uq_incidents_open_service",
            "service_id",
            unique=True,
            postgresql_where=text("state != 'resolved'"),
            sqlite_where=text("state != 'resolved'"),
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    service_id: Mapped[str] = mapped_column(ForeignKey("services.id", ondelete="CASCADE"))
    state: Mapped[str] = mapped_column(String(20), default="investigating")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cause: Mapped[str | None] = mapped_column(Text)


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (
        Index("ix_alerts_service_created", "service_id", "created_at"),
        Index("ix_alerts_created", "created_at"),
        Index(
            "ix_alerts_unread",
            "created_at",
            postgresql_where=text("read_at IS NULL"),
            sqlite_where=text("read_at IS NULL"),
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    service_id: Mapped[str] = mapped_column(ForeignKey("services.id", ondelete="CASCADE"))
    incident_id: Mapped[str | None] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(24))
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Configuration(Base):
    __tablename__ = "configuration"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_configuration_singleton"),
        CheckConstraint("latency_threshold BETWEEN 1 AND 60000", name="ck_threshold"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    failure_alerts: Mapped[bool] = mapped_column(Boolean, default=True)
    recovery_alerts: Mapped[bool] = mapped_column(Boolean, default=True)
    latency_threshold: Mapped[int] = mapped_column(Integer, default=400)
