"""
Reports schemas — Pydantic models for billing report endpoint.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator


class BillingReportRequest(BaseModel):
    start_date: date
    end_date: date
    client_id: UUID | None = None
    status_filter: list[Literal["completed", "cancelled", "no_show", "scheduled"]] = ["completed"]

    @model_validator(mode="after")
    def validate_date_range(self) -> "BillingReportRequest":
        if self.end_date < self.start_date:
            raise ValueError("end_date must be >= start_date")
        if (self.end_date - self.start_date).days > 365:
            raise ValueError("Report range cannot exceed 365 days")
        return self


class SessionEntry(BaseModel):
    session_id: UUID
    client_id: UUID
    client_name: str
    scheduled_at: datetime
    duration_minutes: int
    price: Decimal
    status: str
    notes: str | None

    model_config = ConfigDict(from_attributes=True)


class ClientBillingEntry(BaseModel):
    client_id: UUID
    client_name: str
    session_count: int
    total_amount: Decimal
    sessions: list[SessionEntry]


class BillingReportResponse(BaseModel):
    period_start: date
    period_end: date
    total_sessions: int
    total_amount: Decimal
    clients: list[ClientBillingEntry]
    ai_insights: str | None
    generated_at: datetime
