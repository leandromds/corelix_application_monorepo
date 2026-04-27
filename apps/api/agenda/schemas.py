"""
Agenda schemas — Pydantic models for scheduling endpoints.

Organized by domain entity:
  - AvailabilitySlot  (weekly recurring availability windows)
  - BlockedPeriod     (explicit unavailability periods)
  - Recurrence        (recurring session rules)
  - Session           (individual appointments)

Validators here are limited to simple field-level checks (e.g. end > start).
Business-level conflict detection lives in agenda/service.py.
"""

from datetime import date, datetime, time
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

# ---------------------------------------------------------------------------
# AvailabilitySlot
# ---------------------------------------------------------------------------


class AvailabilitySlotCreate(BaseModel):
    """Payload to register a new weekly availability window."""

    day_of_week: int = Field(ge=0, le=6, description="0=Monday … 6=Sunday")
    start_time: time
    end_time: time

    @model_validator(mode="after")
    def validate_time_range(self) -> "AvailabilitySlotCreate":
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class AvailabilitySlotUpdate(BaseModel):
    """Partial update for an availability slot (PATCH semantics).

    All fields optional — only the fields sent by the client are applied.
    Typical use-case: toggle is_active or adjust the time window.
    """

    start_time: time | None = None
    end_time: time | None = None
    is_active: bool | None = None


class AvailabilitySlotResponse(BaseModel):
    """Serialised availability slot returned by the API."""

    id: UUID
    day_of_week: int
    start_time: time
    end_time: time
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# BlockedPeriod
# ---------------------------------------------------------------------------


class BlockedPeriodCreate(BaseModel):
    """Payload to register an explicit unavailability window.

    `professional_id` is injected by the service from the authenticated
    user — it is never accepted from the request body.
    """

    start_datetime: datetime
    end_datetime: datetime
    reason: str | None = Field(default=None, max_length=255)
    notify_clients: bool = True

    @model_validator(mode="after")
    def validate_date_range(self) -> "BlockedPeriodCreate":
        if self.end_datetime <= self.start_datetime:
            raise ValueError("end_datetime must be after start_datetime")
        return self


class BlockedPeriodResponse(BaseModel):
    """Serialised blocked period returned by the API."""

    id: UUID
    start_datetime: datetime
    end_datetime: datetime
    reason: str | None
    notify_clients: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Recurrence
# ---------------------------------------------------------------------------


class RecurrenceCreate(BaseModel):
    """Payload to create a recurring session rule.

    `day_of_week` is required for weekly/biweekly frequencies; optional for
    monthly (where the day is derived from `start_date`).
    """

    client_id: UUID
    frequency: Literal["weekly", "biweekly", "monthly"]
    interval: int = Field(default=1, gt=0)
    day_of_week: int | None = Field(default=None, ge=0, le=6)
    start_date: date
    end_date: date | None = None
    session_duration: int = Field(gt=0)
    session_price: Decimal = Field(gt=0, decimal_places=2)

    @model_validator(mode="after")
    def validate_recurrence(self) -> "RecurrenceCreate":
        if self.frequency in ("weekly", "biweekly") and self.day_of_week is None:
            raise ValueError("day_of_week is required for weekly and biweekly frequencies")
        if self.end_date and self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date")
        return self


class RecurrenceResponse(BaseModel):
    """Serialised recurrence rule returned by the API.

    `session_price` is exposed as a plain string because PostgreSQL NUMERIC
    is returned as a string by SQLAlchemy's asyncpg dialect — preserving
    exact decimal representation without float rounding.
    """

    id: UUID
    client_id: UUID
    frequency: str
    interval: int
    day_of_week: int | None
    start_date: date
    end_date: date | None
    session_duration: int
    session_price: Decimal  # asyncpg returns NUMERIC as Decimal
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------


class SessionCreate(BaseModel):
    """Payload to schedule a new individual session.

    `price` is required explicitly so the professional can override the
    recurrence default price (e.g. promotional sessions).
    """

    client_id: UUID
    recurrence_id: UUID | None = None
    scheduled_at: datetime
    duration_minutes: int = Field(gt=0)
    price: Decimal = Field(gt=0, decimal_places=2)
    notes: str | None = None


class SessionUpdate(BaseModel):
    """Partial update for a session (PATCH semantics).

    Allows rescheduling, price correction, status progression or note updates.
    Conflict detection for rescheduling is enforced in the service layer.
    """

    scheduled_at: datetime | None = None
    duration_minutes: int | None = Field(default=None, gt=0)
    price: Decimal | None = Field(default=None, gt=0, decimal_places=2)
    status: Literal["scheduled", "completed", "cancelled", "no_show"] | None = None
    notes: str | None = None


class SessionResponse(BaseModel):
    """Serialised session returned by the API.

    `price` is a string for the same reason as `RecurrenceResponse.session_price`.
    """

    id: UUID
    client_id: UUID
    recurrence_id: UUID | None
    scheduled_at: datetime
    duration_minutes: int
    price: Decimal  # asyncpg returns NUMERIC as Decimal
    status: str
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
