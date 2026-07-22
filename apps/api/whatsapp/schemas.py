"""WhatsApp schemas — Pydantic models for webhook and messaging endpoints."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

# ============================================================================
# Webhook Verification (GET /whatsapp/webhook)
# ============================================================================


class WebhookVerificationRequest(BaseModel):
    """
    Query parameters for the Meta webhook verification handshake.

    Meta sends a GET request with these params when you register a webhook URL.
    The app must respond with hub.challenge to confirm ownership.

    All three fields use dotted aliases because FastAPI/Pydantic will receive
    them as query string params: hub.mode, hub.challenge, hub.verify_token.
    """

    hub_mode: str = Field(alias="hub.mode")
    hub_challenge: str = Field(alias="hub.challenge")
    hub_verify_token: str = Field(alias="hub.verify_token")

    model_config = {"populate_by_name": True}


# ============================================================================
# Meta Webhook Payload (POST /whatsapp/webhook)
# ============================================================================


class WebhookTextContent(BaseModel):
    """Text body of a WhatsApp text message."""

    body: str


class WebhookMessage(BaseModel):
    """
    Individual message object within a webhook notification.

    'from' is a Python keyword, so we alias it to from_.
    populate_by_name=True allows both 'from_' and 'from' to be used
    in tests and internal code.
    """

    from_: str = Field(alias="from")
    id: str
    timestamp: str
    type: str
    text: WebhookTextContent | None = None  # only present when type == 'text'

    model_config = {"populate_by_name": True}


class WebhookContact(BaseModel):
    """Contact entry in the webhook payload (sender info)."""

    wa_id: str


class WebhookMetadata(BaseModel):
    """
    Metadata for the receiving WhatsApp Business Account phone.

    phone_number_id is the key used to look up which professional
    owns this phone number — it is stable across token refreshes.
    """

    display_phone_number: str
    phone_number_id: str


class WebhookValue(BaseModel):
    """
    The 'value' object inside a webhook change entry.

    Contains the actual message(s), sender contacts, and metadata
    identifying the receiving business phone.
    """

    messaging_product: str
    metadata: WebhookMetadata
    contacts: list[WebhookContact] = []
    messages: list[WebhookMessage] = []


class WebhookChange(BaseModel):
    """A single change entry within a webhook event."""

    value: WebhookValue
    field: str


class WebhookEntry(BaseModel):
    """
    A single entry in the webhook payload.

    Meta may batch multiple entries in one request, but in practice
    each POST typically contains one entry with one message.
    """

    id: str
    changes: list[WebhookChange]


class WebhookPayload(BaseModel):
    """
    Root structure of the Meta Cloud API webhook POST body.

    object will be 'whatsapp_business_account' for WhatsApp events.
    entry contains one or more event entries.
    """

    object: str
    entry: list[WebhookEntry]


# ============================================================================
# API Requests
# ============================================================================


class SendMessageRequest(BaseModel):
    """Request body for manually sending a message to a client phone number."""

    client_phone: str
    message: str = Field(min_length=1, max_length=4096)


# ============================================================================
# API Responses
# ============================================================================


class ConversationResponse(BaseModel):
    """
    Response schema for a single WhatsApp conversation.

    Excludes professional_id — callers already know their own tenant context.
    client_id is nullable because the client may not be registered yet.
    """

    id: UUID
    client_phone: str
    client_id: UUID | None
    status: str
    mode: str
    started_at: datetime
    last_message_at: datetime
    ended_at: datetime | None

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    """Response schema for a single WhatsApp message."""

    id: UUID
    direction: str
    sender_type: str
    content: str
    sent_at: datetime

    model_config = {"from_attributes": True}


class ConversationWithMessagesResponse(BaseModel):
    """
    Full conversation detail response: metadata + message history.

    Used by GET /whatsapp/conversations/{id} to avoid a round-trip
    from the frontend — a single request fetches both.
    """

    conversation: ConversationResponse
    messages: list[MessageResponse]


class HandoffResponse(BaseModel):
    """
    Response after switching a conversation from AI mode to professional mode.

    Returns only the fields that changed so the frontend can update
    its local state without re-fetching the full conversation.
    """

    id: UUID
    mode: str  # will always be 'handoff' after the operation
    status: str  # will be 'waiting_professional'

    model_config = {"from_attributes": True}


# ============================================================================
# Provider-agnostic canonical types (ADR-028)
# ============================================================================


class InboundMessage(BaseModel):
    """Mensagem recebida, normalizada — independente do provider."""

    professional_id: UUID
    from_phone: str = Field(pattern=r"^\+\d{10,15}$")  # E.164
    body: str
    provider_message_id: str
    received_at: datetime
    provider_type: str = "unknown"  # 'meta', 'twilio_shared', 'terminal'


class TemplateMessage(BaseModel):
    """Template aprovado a ser enviado."""

    name: str
    language_code: str = "pt_BR"
    params: dict[str, str] = Field(default_factory=dict)


class SendResult(BaseModel):
    """Resultado de envio de mensagem por um provider."""

    provider_message_id: str
    status: Literal["sent", "queued", "failed"]
    error: str | None = None
