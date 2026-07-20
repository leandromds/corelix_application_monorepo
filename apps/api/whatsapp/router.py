"""
WhatsApp router — HTTP layer for Meta Cloud API integration.

Endpoints:
- GET  /webhook               → Meta verification handshake (public)
- POST /webhook               → receive incoming messages (public, HMAC verified)
- GET  /conversations         → list conversations (TenantSession)
- GET  /conversations/{id}    → detail with messages (TenantSession)
- POST /conversations/{id}/handoff → switch to handoff mode (TenantSession)

Design notes:
- The webhook endpoints are public (no JWT required) because Meta sends requests
  from its own infrastructure, not from authenticated users. Security is enforced
  via HMAC-SHA256 signature verification on POST requests.
- Background task (_process_webhook_background) creates its own DB session to
  avoid holding the request session open while the AI call is in progress.
  This means it commits independently — SET LOCAL tenant context must be re-set
  inside the background task before any RLS-protected queries.
- Only text-type messages are processed. Non-text messages (images, audio, etc.)
  are acknowledged with 200 OK but not queued for processing. This prevents
  unnecessary background task scheduling for unsupported message types.
- The inline `from whatsapp.repository import WhatsAppRepository` inside
  receive_webhook is intentional: it makes the import patchable in tests via
  `patch("whatsapp.repository.WhatsAppRepository")`.
"""

import hashlib
import hmac as _hmac
import json
import logging
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request, Response, status
from fastapi.responses import PlainTextResponse

from core.config import settings
from core.database import async_session_maker, set_tenant_context
from core.deps import DbSession, TenantSession
from core.exceptions import NotFoundError
from whatsapp.schemas import (
    ConversationResponse,
    ConversationWithMessagesResponse,
    HandoffResponse,
    MessageResponse,
)
from whatsapp.service import WhatsAppService

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================================
# HMAC verification helper
# ============================================================================


def _verify_hmac(body: bytes, signature_header: str) -> bool:
    """
    Verify the Meta webhook HMAC-SHA256 signature.

    Meta computes: HMAC-SHA256(app_secret, raw_request_body)
    and sends it as: X-Hub-Signature-256: sha256=<hexdigest>

    We use hmac.compare_digest (constant-time comparison) to prevent
    timing attacks that could leak information about the secret.

    Args:
        body: Raw request body bytes (must be the original bytes — NOT decoded).
        signature_header: Value of the X-Hub-Signature-256 request header.

    Returns:
        True if the signature is valid, False otherwise.
    """
    if not signature_header.startswith("sha256="):
        return False
    expected = signature_header.removeprefix("sha256=")
    computed = _hmac.new(
        settings.WHATSAPP_APP_SECRET.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
    return _hmac.compare_digest(computed, expected)


# ============================================================================
# Background task — runs after the 200 is already sent to Meta
# ============================================================================


async def _process_webhook_background(
    professional_id: UUID,
    messages_data: list[dict],
) -> None:
    """
    Process incoming webhook messages asynchronously after responding to Meta.

    Creates its own independent DB session (not the request session) so the
    200 response can be sent to Meta immediately without waiting for AI inference
    or database writes to complete.

    Steps:
    1. Open a new async session.
    2. Set the tenant context (SET LOCAL) so RLS is active for the professional.
    3. Re-fetch the Professional model (needed for AI context and token decryption).
    4. For each text message in the payload, call service.process_incoming_message().
    5. Commit on success, rollback on any exception.

    Args:
        professional_id: UUID of the professional who owns the receiving WABA phone.
        messages_data: List of raw message dicts (already filtered to text-only).
    """
    async with async_session_maker() as session:
        try:
            await set_tenant_context(session, professional_id)

            # Re-fetch professional in this new session context
            from professionals.repository import ProfessionalsRepository

            prof_repo = ProfessionalsRepository(session)
            professional = await prof_repo.find_by_id(professional_id)
            if not professional:
                logger.warning(
                    "Background task: professional %s not found — aborting", professional_id
                )
                return

            service = WhatsAppService(session)
            for msg_data in messages_data:
                # Double-check type (messages_data is already pre-filtered,
                # but be defensive in case this function is called directly)
                if msg_data.get("type") != "text":
                    continue
                text_content = msg_data.get("text") or {}
                body = text_content.get("body", "").strip()
                if not body:
                    continue
                await service.process_incoming_message(
                    professional=professional,
                    client_phone=msg_data["from"],
                    content=body,
                    whatsapp_msg_id=msg_data["id"],
                )

            await session.commit()
        except Exception as exc:  # noqa: BLE001
            await session.rollback()
            logger.error(
                "Background webhook processing failed for professional %s: %s",
                professional_id,
                exc,
                exc_info=True,
            )


# ============================================================================
# Webhook verification (GET)
# ============================================================================


@router.get("/webhook", response_class=PlainTextResponse)
async def verify_webhook(
    hub_mode: str = Query(alias="hub.mode"),
    hub_challenge: str = Query(alias="hub.challenge"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
) -> str:
    """
    Meta webhook verification handshake.

    Meta sends a GET request with these query parameters when a webhook URL is
    first registered (or re-verified). The server must respond with the plain-text
    value of hub.challenge — nothing else — to confirm it controls the endpoint.

    Returns 403 if the verify token does not match settings.WHATSAPP_VERIFY_TOKEN.
    This prevents other parties from registering our URL as their webhook.

    Args:
        hub_mode: Meta always sends 'subscribe' for webhook registration.
        hub_challenge: Random string Meta expects echoed back verbatim.
        hub_verify_token: Token that must match our configured WHATSAPP_VERIFY_TOKEN.

    Returns:
        hub_challenge as a plain-text response body (required by Meta).
    """
    if hub_verify_token != settings.WHATSAPP_VERIFY_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid verify token",
        )
    return hub_challenge


# ============================================================================
# Webhook incoming messages (POST)
# ============================================================================


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def receive_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    session: DbSession,
) -> Response:
    """
    Receive incoming WhatsApp messages from Meta Cloud API.

    Processing pipeline:
    1. Read raw body (must happen before any JSON parsing to compute HMAC).
    2. Verify HMAC-SHA256 signature — reject with 400 if invalid.
    3. Parse JSON payload, extract phone_number_id and text messages.
       Non-text messages are filtered out; if nothing remains, return 200 immediately.
    4. Look up the professional by phone_number_id. Unknown phone IDs → 200 (not 404).
       Meta must always receive 200 or it will retry the webhook indefinitely.
    5. Queue a background task to process the messages asynchronously.
    6. Return 200 immediately — the actual processing (AI call, DB writes) happens
       after this response is sent so Meta gets a fast acknowledgment.

    Security: HMAC verification (step 2) prevents spoofed webhook requests from
    triggering AI replies and creating conversations.

    Args:
        request: Raw FastAPI request (needed to read body before parsing).
        background_tasks: FastAPI BackgroundTasks for async post-response processing.
        session: Database session (DbSession — no RLS, used only for the
                 find_professional_by_phone_id lookup on the public professionals table).

    Returns:
        Empty 200 response.
    """
    # 1. Read raw body for HMAC computation BEFORE JSON parsing
    body = await request.body()

    # 2. Verify HMAC signature
    signature = request.headers.get("X-Hub-Signature-256", "")
    if not _verify_hmac(body, signature):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook signature",
        )

    # 3. Parse payload and extract text messages only
    payload = json.loads(body)

    phone_number_id: str | None = None
    all_messages: list[dict] = []

    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            meta = value.get("metadata", {})
            if phone_number_id is None and meta.get("phone_number_id"):
                phone_number_id = meta["phone_number_id"]
            all_messages.extend(value.get("messages", []))

    # Filter to text messages only — we don't process images, audio, etc. yet
    text_messages = [m for m in all_messages if m.get("type") == "text"]

    # Nothing to process — acknowledge Meta and return early
    if not phone_number_id or not text_messages:
        return Response(status_code=status.HTTP_200_OK)

    # 4. Resolve the professional by their WABA phone_number_id
    # Inline import so tests can patch whatsapp.repository.WhatsAppRepository
    from whatsapp.repository import WhatsAppRepository

    repo = WhatsAppRepository(session)
    professional = await repo.find_professional_by_phone_id(phone_number_id)

    if not professional:
        # Unknown phone_number_id — acknowledge Meta but do not process
        logger.info("Webhook received for unknown phone_number_id=%s — ignored", phone_number_id)
        return Response(status_code=status.HTTP_200_OK)

    # 5. Queue background task — actual processing happens after this 200 is sent
    background_tasks.add_task(
        _process_webhook_background,
        professional_id=professional.id,
        messages_data=text_messages,
    )

    # 6. Respond immediately (Meta requires a fast acknowledgment)
    return Response(status_code=status.HTTP_200_OK)


# ============================================================================
# Conversations (protected — TenantSession)
# ============================================================================


@router.get("/conversations", response_model=list[ConversationResponse])
async def list_conversations(
    session: TenantSession,
    status: str | None = Query(default=None, description="Filter by status"),
) -> list[ConversationResponse]:
    """
    List WhatsApp conversations for the authenticated professional.

    RLS is active on the session (via TenantSession) so the repository
    automatically returns only the current professional's conversations.

    Args:
        session: Tenant-scoped DB session (JWT validated + SET LOCAL active).
        status: Optional filter — 'active', 'resolved', or 'waiting_professional'.
                If omitted, all statuses are returned.

    Returns:
        List of ConversationResponse objects ordered by last_message_at DESC.
    """
    service = WhatsAppService(session)
    conversations = await service.list_conversations(status_filter=status)
    return [ConversationResponse.model_validate(c) for c in conversations]


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationWithMessagesResponse,
)
async def get_conversation(
    conversation_id: UUID,
    session: TenantSession,
) -> ConversationWithMessagesResponse:
    """
    Retrieve a conversation with its full message history.

    Combines the conversation metadata and its messages in a single request
    to avoid a round-trip from the frontend dashboard.

    Args:
        conversation_id: UUID of the conversation to retrieve.
        session: Tenant-scoped DB session.

    Returns:
        ConversationWithMessagesResponse with conversation + messages list.

    Raises:
        404: If the conversation does not exist or belongs to another tenant.
    """
    service = WhatsAppService(session)
    try:
        conversation, messages = await service.get_conversation_detail(conversation_id)
    except NotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        ) from err
    return ConversationWithMessagesResponse(
        conversation=ConversationResponse.model_validate(conversation),
        messages=[MessageResponse.model_validate(m) for m in messages],
    )


@router.post(
    "/conversations/{conversation_id}/handoff",
    response_model=HandoffResponse,
)
async def handoff_to_professional(
    conversation_id: UUID,
    session: TenantSession,
) -> HandoffResponse:
    """
    Switch a conversation from AI mode to professional (handoff) mode.

    After handoff:
    - The AI will stop auto-replying to incoming messages.
    - The conversation status changes to 'waiting_professional'.
    - The professional can see the conversation in their dashboard and reply manually.

    Args:
        conversation_id: UUID of the conversation to hand off.
        session: Tenant-scoped DB session.

    Returns:
        HandoffResponse with updated mode and status.

    Raises:
        404: If the conversation does not exist or belongs to another tenant.
    """
    service = WhatsAppService(session)
    try:
        conversation = await service.handoff_to_professional(conversation_id)
    except NotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        ) from err
    return HandoffResponse.model_validate(conversation)
