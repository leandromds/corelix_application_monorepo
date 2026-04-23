"""
Professionals schemas — Pydantic models for request/response validation.
"""

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """Request body for POST /professionals/register."""

    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=2, max_length=200)
    specialty: str = Field(min_length=2, max_length=100)
    phone: str = Field(min_length=10, max_length=20)


class UpdateProfileRequest(BaseModel):
    """Request body for PATCH /professionals/me (all fields optional)."""

    full_name: str | None = Field(default=None, min_length=2, max_length=200)
    specialty: str | None = Field(default=None, min_length=2, max_length=100)
    bio: str | None = None
    phone: str | None = Field(default=None, min_length=10, max_length=20)
    session_duration: int | None = Field(default=None, ge=15, le=480)  # minutes
    session_price: Decimal | None = Field(default=None, ge=0)


class ProfessionalResponse(BaseModel):
    """Response body for professional profile endpoints."""

    id: UUID
    email: str
    full_name: str
    specialty: str
    bio: str | None
    phone: str | None
    session_duration: int | None
    session_price: Decimal | None
    is_active: bool

    model_config = {"from_attributes": True}
