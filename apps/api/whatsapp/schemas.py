"""
WhatsApp schemas — Pydantic models for webhook and messaging endpoints.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class WebhookVerificationRequest(BaseModel):
    """Query params for GET /whatsapp/webhook (Meta verification handshake)."""

    hub_mode: str = Field(alias="hub.mode")
    hub_challenge: str = Field(alias="hub.challenge")
    hub_verify_token: str = Field(alias="hub.verify_token")

    model_config = {"populate_by_name": True}


class SendMessageRequest(BaseModel):
    """Request body for POST /whatsapp/send."""

    client_phone: str
    message: str = Field(min_length=1, max_length=4096)


class ConversationResponse(BaseModel):
    """Response for conversation endpoints."""

    id: UUID
    client_phone: str
    status: str
    mode: str
    last_message_at: datetime | None

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    """Response for individual message."""

    id: UUID
    direction: str
    sender_type: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}
