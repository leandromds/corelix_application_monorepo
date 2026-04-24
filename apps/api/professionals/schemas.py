"""
Professionals schemas — Pydantic models for request/response validation.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """Request body for POST /auth/register."""

    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=2, max_length=200)
    specialty: str | None = Field(default=None, min_length=2, max_length=100)
    bio: str | None = None


class UpdateProfileRequest(BaseModel):
    """Request body for PATCH /professionals/me (all fields optional)."""

    full_name: str | None = Field(default=None, min_length=2, max_length=200)
    specialty: str | None = Field(default=None, min_length=2, max_length=100)
    bio: str | None = None
    phone: str | None = Field(default=None, min_length=10, max_length=20)
    session_duration: int | None = Field(default=None, ge=15, le=480)  # minutes
    session_price: Decimal | None = Field(default=None, ge=0)


class ProfessionalResponse(BaseModel):
    """
    Response body for professional profile endpoints.

    NEVER includes password_hash — this is enforced by only selecting these fields.
    """

    id: UUID
    email: str
    full_name: str
    specialty: str | None
    bio: str | None
    phone: str | None
    session_duration: int
    session_price: Decimal | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
