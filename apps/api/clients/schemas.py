"""
Clients schemas — Pydantic models for request/response validation.

Design decisions:
- ClientCreate: phone AND email are both optional, but at least one is required
  (validated via model_validator). This supports clients that only use WhatsApp
  (phone only) or email-only communication.
- ClientUpdate: all fields are optional (PATCH semantics). Uses exclude_unset=True
  in the service layer so explicitly sending null clears the field, while omitting
  a field preserves the current value.
- ClientResponse: exposes created_at and updated_at for the frontend to display
  "client since" and "last updated" information. Never exposes professional_id
  (internal FK, not relevant to the API consumer).
"""

from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, model_validator


class ClientCreate(BaseModel):
    """
    Request body for POST /clients.

    Validation rule: at least one contact method (phone or email) must be provided.
    This is enforced both here (Pydantic layer) and conceptually in the service layer
    — defense in depth without duplication of business logic.
    """

    full_name: str = Field(min_length=2, max_length=255)
    phone: str | None = Field(default=None, min_length=10, max_length=20)
    email: EmailStr | None = None
    notes: str | None = None
    whatsapp_opt_in: bool = False
    email_opt_in: bool = False

    @model_validator(mode="after")
    def require_at_least_one_contact(self) -> Self:
        """Enforce that at least phone or email is provided."""
        if not self.phone and not self.email:
            raise ValueError(
                "At least one contact method is required: provide phone, email, or both."
            )
        return self


class ClientUpdate(BaseModel):
    """
    Request body for PATCH /clients/{id}.

    All fields are optional — only provided fields are updated (PATCH semantics).
    The service layer uses model_dump(exclude_unset=True) so:
      - Field omitted from body  → not included in update → existing value preserved
      - Field explicitly set to null → included as None → field cleared in DB
    """

    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    phone: str | None = Field(default=None, min_length=10, max_length=20)
    email: EmailStr | None = None
    notes: str | None = None
    whatsapp_opt_in: bool | None = None
    email_opt_in: bool | None = None


class ClientResponse(BaseModel):
    """
    Response body for all client endpoints.

    Intentionally excludes professional_id (internal FK — not useful to the API
    consumer, and exposing it would leak tenant structure).

    Includes created_at and updated_at so the frontend can display "client since"
    and "last modified" metadata without additional requests.
    """

    id: UUID
    full_name: str
    phone: str | None
    email: str | None
    notes: str | None
    whatsapp_opt_in: bool
    email_opt_in: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
