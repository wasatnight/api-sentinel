import ipaddress
from datetime import datetime, timezone
from typing import Literal
from urllib.parse import parse_qsl, urlsplit, urlunsplit

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)


class CollectionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=50)


class CollectionOut(CollectionInput):
    model_config = ConfigDict(from_attributes=True)
    id: str
    created_at: datetime


class ServiceInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=80)
    url: str = Field(min_length=1, max_length=2048)
    method: Literal["GET", "HEAD"] = "GET"
    interval_seconds: int = Field(default=60, ge=10, le=86400, strict=True)
    timeout_seconds: int = Field(default=10, ge=1, le=60, strict=True)
    collection_id: str = Field(min_length=1, max_length=36)

    enabled: bool = Field(default=True, strict=True)
    expected_status_min: int = Field(default=200, ge=100, le=599, strict=True)
    expected_status_max: int = Field(default=299, ge=100, le=599, strict=True)

    @model_validator(mode="after")
    def expected_range(self):
        if self.expected_status_max < self.expected_status_min:
            raise ValueError("The maximum HTTP status code must be greater than or equal to the minimum.")
        return self

    @field_validator("url")
    @classmethod
    def validate_url(cls, value):
        try:
            parsed = urlsplit(value)
            host = parsed.hostname
            if (
                parsed.scheme not in {"http", "https"}
                or not host
                or parsed.username
                or parsed.password
                or parsed.fragment
                or any(ord(c) < 33 for c in value)
                or "\\" in value
                or "%" in host
            ):
                raise ValueError
            if parsed.port is not None and not 1 <= parsed.port <= 65535:
                raise ValueError
            secret_keys = {
                "token",
                "access_token",
                "api_key",
                "apikey",
                "password",
                "secret",
                "authorization",
                "signature",
            }
            if any(
                key.lower() in secret_keys
                for key, _ in parse_qsl(parsed.query, keep_blank_values=True)
            ):
                raise ValueError
            normalized = host.rstrip(".").lower().encode("idna").decode()
            if normalized == "localhost" or normalized.endswith(
                (".localhost", ".local", ".internal")
            ):
                raise ValueError
            try:
                address = ipaddress.ip_address(normalized)
            except ValueError:
                # Reject ambiguous IP encodings and numeric hostnames.
                if (
                    "." not in normalized
                    or normalized.replace(".", "").isdigit()
                    or normalized.startswith("0x")
                ):
                    raise ValueError
            else:
                if not address.is_global or (
                    getattr(address, "ipv4_mapped", None) and not address.ipv4_mapped.is_global
                ):
                    raise ValueError
            return urlunsplit(parsed)
        except (ValueError, UnicodeError):
            raise ValueError(
                "Use HTTP/HTTPS with a public destination and no credentials or fragments."
            ) from None


class ServiceOut(ServiceInput):
    model_config = ConfigDict(from_attributes=True)
    id: str
    status: str
    created_at: datetime
    last_checked_at: datetime | None
    next_check_at: datetime | None
    last_latency_ms: float | None


class ConfigurationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    failure_alerts: bool = Field(strict=True)
    recovery_alerts: bool = Field(strict=True)
    latency_threshold: int = Field(ge=1, le=60000, strict=True)


class ConfigurationOut(ConfigurationInput):
    model_config = ConfigDict(from_attributes=True)


class CheckOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    service_id: str
    service_name: str = ""
    checked_at: datetime
    status_code: int | None
    latency_ms: float | None
    success: bool
    status: str
    error: str | None
    attempts: int


class IncidentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    service_id: str
    service_name: str = ""
    state: str
    started_at: datetime
    resolved_at: datetime | None
    cause: str | None
    duration_seconds: int = 0


class IncidentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    state: Literal["investigating", "monitoring", "resolved"]


class EnabledInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = Field(strict=True)


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    service_id: str
    service_name: str = ""
    incident_id: str | None
    kind: str
    message: str
    created_at: datetime
    read_at: datetime | None

    @field_serializer("created_at", "read_at")
    def serialize_utc(self, value):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z") if value else None
