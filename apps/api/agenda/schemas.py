"""
Agenda schemas — Pydantic models for scheduling endpoints.
"""

from datetime import date, datetime, time
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class AvailabilitySlotRequest(BaseModel):
    """Request to create an availability slot."""

    day_of_week: int = Field(ge=0, le=6, description="0=Monday, 6=Sunday")
    start_time: time
    end_time: time


class AvailabilitySlotResponse(BaseModel):
    """Response for availability slot."""

    id: UUID
    day_of_week: int
    start_time: time
    end_time: time

    model_config = {"from_attributes": True}


class CreateSessionRequest(BaseModel):
    """Request to schedule a new session."""

    client_id: UUID
    scheduled_at: datetime
    duration_minutes: int = Field(ge=15, le=480)
    price: Decimal = Field(ge=0)
    notes: str | None = None


class UpdateSessionStatusRequest(BaseModel):
    """Request to update session status."""

    status: str = Field(pattern="^(scheduled|completed|cancelled|no_show)$")
    notes: str | None = None


class SessionResponse(BaseModel):
    """Response for session endpoints."""

    id: UUID
    client_id: UUID
    scheduled_at: datetime
    duration_minutes: int
    price: Decimal
    status: str
    notes: str | None

    model_config = {"from_attributes": True}
