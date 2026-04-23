"""
Clients schemas — Pydantic models for request/response validation.
"""

from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class CreateClientRequest(BaseModel):
    """Request body for POST /clients."""

    full_name: str = Field(min_length=2, max_length=200)
    phone: str = Field(min_length=10, max_length=20)
    email: EmailStr | None = None
    notes: str | None = None
    whatsapp_opt_in: bool = False
    email_opt_in: bool = False


class UpdateClientRequest(BaseModel):
    """Request body for PATCH /clients/{id} (all fields optional)."""

    full_name: str | None = Field(default=None, min_length=2, max_length=200)
    phone: str | None = Field(default=None, min_length=10, max_length=20)
    email: EmailStr | None = None
    notes: str | None = None
    whatsapp_opt_in: bool | None = None
    email_opt_in: bool | None = None


class ClientResponse(BaseModel):
    """Response body for client endpoints."""

    id: UUID
    full_name: str
    phone: str
    email: str | None
    notes: str | None
    whatsapp_opt_in: bool
    email_opt_in: bool
    is_active: bool

    model_config = {"from_attributes": True}


class ClientListResponse(BaseModel):
    """Paginated list of clients."""

    items: list[ClientResponse]
    total: int
    skip: int
    limit: int
