"""
WhatsApp service — business logic for Meta Cloud API integration.

Responsibilities:
- Process incoming webhook messages (idempotent via whatsapp_msg_id)
- Route messages to AI or hold for professional (handoff mode)
- Send messages via Meta Cloud API using per-professional credentials
- Manage conversation state transitions (ai → handoff → resolved)
- Decrypt per-professional Fernet-encrypted access tokens at call time

Design notes:
- process_incoming_message() assumes tenant context (SET LOCAL) is already
  active on the session. The webhook router sets it after resolving the
  professional from phone_number_id — before delegating here.
- Never call session.commit() here. SET LOCAL is valid only for the current
  transaction; committing mid-request silently drops the RLS context.
- Graceful degradation: AI and Meta API failures are caught and logged.
  The inbound message is always persisted regardless of downstream failures.
  A broken AI reply is worse than no reply.
- Fernet decryption happens at call time (not at __init__) to avoid holding
  plaintext tokens in memory longer than necessary.
"""

import logging
from datetime import UTC, datetime
from uuid import UUID

import httpx

from ai.prompts import PROMPTS
from ai.service import AIService
from core.exceptions import ExternalServiceError, NotFoundError
from whatsapp.models import WhatsAppConversation, WhatsAppMessage
from whatsapp.repository import WhatsAppRepository

logger = logging.getLogger(__name__)


class WhatsAppService:
    """Handles WhatsApp business logic: message routing, AI replies, Meta API calls."""

    def __init__(self, session) -> None:
        self.session = session
        self.repository = WhatsAppRepository(session)
        self.ai = AIService()

    # =========================================================================
    # Incoming message processing
    # =========================================================================

    async def process_incoming_message(
        self,
        professional,  # professionals.models.Professional instance
        client_phone: str,
        content: str,
        whatsapp_msg_id: str,
    ) -> None:
        """
        Process an inbound WhatsApp message end-to-end.

        Steps:
        1. Idempotency check — skip if whatsapp_msg_id already processed.
           Meta's webhook delivery has at-least-once semantics.
        2. Get or create an active conversation for this phone number.
        3. Persist the inbound message.
        4. Update last_message_at on the conversation.
        5. If mode == 'ai': build conversation history, call AI, persist AI
           reply, and attempt to deliver it via Meta Cloud API.
        6. If mode == 'handoff': do nothing — professional handles it manually.

        AI and Meta API failures are caught here and logged. The inbound
        message is always saved to the database regardless of what happens
        downstream — losing the message is worse than a delayed reply.

        Args:
            professional: The Professional model instance that owns the WABA phone.
            client_phone: Sender's phone number (E.164 format from Meta).
            content: Plain-text message body.
            whatsapp_msg_id: Meta's unique message ID (for idempotency).
        """
        # 1. Idempotency — Meta may re-deliver the same webhook
        existing = await self.repository.find_message_by_whatsapp_id(whatsapp_msg_id)
        if existing is not None:
            logger.info(
                "Duplicate webhook ignored (whatsapp_msg_id=%s already processed)",
                whatsapp_msg_id,
            )
            return

        # 2. Get or create conversation
        conversation = await self.repository.find_active_conversation_by_phone(client_phone)
        if conversation is None:
            conversation = await self.repository.create_conversation(professional.id, client_phone)
            logger.info(
                "New conversation created (professional_id=%s, phone=%s, conversation_id=%s)",
                professional.id,
                client_phone,
                conversation.id,
            )

        # 3. Persist inbound message
        await self.repository.create_message(
            conversation_id=conversation.id,
            direction="inbound",
            sender_type="client",
            content=content,
            whatsapp_msg_id=whatsapp_msg_id,
        )

        # 4. Update last_message_at to reflect this new activity
        await self.repository.update_conversation(
            conversation, {"last_message_at": datetime.now(UTC)}
        )

        # 5. Only auto-reply when the conversation is in AI mode
        if conversation.mode != "ai":
            logger.debug(
                "Conversation %s is in '%s' mode — skipping AI reply",
                conversation.id,
                conversation.mode,
            )
            return

        # 6. Build conversation history for AI context (last 20 messages)
        # Fetching after inserting the inbound message ensures the new message
        # is included in the history the AI sees.
        recent_messages = await self.repository.get_messages_for_conversation(
            conversation.id, limit=20
        )
        history = [
            {
                "role": "user" if msg.direction == "inbound" else "assistant",
                "content": msg.content,
            }
            for msg in recent_messages
        ]

        # 7. Generate AI response — graceful degradation on failure
        try:
            system_prompt = PROMPTS["whatsapp_secretary"].format(
                professional_name=professional.full_name,
                professional_specialty=professional.specialty or "Profissional de saúde",
                session_duration=professional.session_duration,
                session_price=str(professional.session_price or "a consultar"),
            )
            ai_response = await self.ai.complete_with_history(system_prompt, history)
        except ExternalServiceError as exc:
            logger.error(
                "AI service unavailable for conversation %s — skipping reply: %s",
                conversation.id,
                exc,
            )
            return  # Inbound message is already saved; just don't reply

        # 8. Persist AI outbound message before attempting delivery.
        # Saving first ensures we have a record even if Meta API fails.
        await self.repository.create_message(
            conversation_id=conversation.id,
            direction="outbound",
            sender_type="ai",
            content=ai_response,
        )

        # 9. Attempt delivery via Meta Cloud API
        access_token = self._decrypt_access_token(professional.whatsapp_access_token)
        if not access_token:
            logger.warning(
                "No decryptable access token for professional %s — message saved but not delivered",
                professional.id,
            )
            return

        if not professional.whatsapp_phone_id:
            logger.warning(
                "No whatsapp_phone_id for professional %s — message saved but not delivered",
                professional.id,
            )
            return

        try:
            meta_msg_id = await self.send_message_via_meta(
                phone=client_phone,
                message=ai_response,
                access_token=access_token,
                phone_number_id=professional.whatsapp_phone_id,
            )
            logger.info(
                "AI reply delivered via Meta (conversation=%s, meta_msg_id=%s)",
                conversation.id,
                meta_msg_id,
            )
        except Exception as exc:  # noqa: BLE001
            # Meta API failure — the AI message is already persisted locally.
            # Log and continue; the professional can resend manually if needed.
            logger.error(
                "Meta API delivery failed for conversation %s: %s",
                conversation.id,
                exc,
            )

    # =========================================================================
    # Meta Cloud API
    # =========================================================================

    async def send_message_via_meta(
        self,
        phone: str,
        message: str,
        access_token: str,
        phone_number_id: str,
    ) -> str | None:
        """
        Send a text message via the Meta Cloud API.

        Uses the v18.0 messages endpoint. The access_token is the
        per-professional token obtained via Embedded Signup, stored
        encrypted in the database and decrypted at call time.

        Args:
            phone: Recipient phone number in E.164 format (e.g. '5511999998888').
            message: Plain-text message body (max 4096 chars per Meta limits).
            access_token: Decrypted WABA access token for this professional.
            phone_number_id: Meta's stable phone_number_id for the sending number.

        Returns:
            Meta's message ID string on success, or None if the response
            contained no message IDs (shouldn't happen on 200 OK, but defensive).

        Raises:
            ExternalServiceError: If the Meta API returns an HTTP error.
                The caller (process_incoming_message) catches this and logs it.
        """
        url = f"https://graph.facebook.com/v18.0/{phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": phone,
            "type": "text",
            "text": {"preview_url": False, "body": message},
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    url,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                    },
                    timeout=10.0,
                )
                response.raise_for_status()
                data = response.json()
                messages = data.get("messages", [])
                return messages[0].get("id") if messages else None
            except httpx.HTTPStatusError as exc:
                raise ExternalServiceError(
                    message=f"Meta API HTTP error {exc.response.status_code}: {exc.response.text}",
                    service_name="whatsapp",
                ) from exc
            except httpx.HTTPError as exc:
                raise ExternalServiceError(
                    message=f"Meta API connection error: {exc}",
                    service_name="whatsapp",
                ) from exc

    # =========================================================================
    # Token decryption
    # =========================================================================

    def _decrypt_access_token(self, encrypted_token: str | None) -> str | None:
        """
        Decrypt the Fernet-encrypted WhatsApp access token stored in the database.

        Fails silently and returns None on any error (missing token, wrong key,
        corrupted ciphertext, token rotation, etc.). The caller must handle None
        by skipping Meta API delivery rather than raising — a failed decryption
        should never crash the request that was saving an inbound message.

        Args:
            encrypted_token: Fernet-encrypted token bytes encoded as a string,
                             as stored in Professional.whatsapp_access_token.

        Returns:
            Decrypted access token string, or None on any failure.
        """
        if not encrypted_token:
            return None
        try:
            from cryptography.fernet import Fernet, InvalidToken  # noqa: F401

            from core.config import settings

            fernet = Fernet(settings.ENCRYPTION_KEY.encode())
            return fernet.decrypt(encrypted_token.encode()).decode()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to decrypt WhatsApp access token: %s", exc)
            return None

    # =========================================================================
    # Conversation management
    # =========================================================================

    async def handoff_to_professional(
        self,
        conversation_id: UUID,
    ) -> WhatsAppConversation:
        """
        Switch a conversation from AI mode to professional (handoff) mode.

        After handoff:
        - mode='handoff'  → AI will no longer auto-reply
        - status='waiting_professional' → signals the professional that action is needed

        The professional can switch back to AI mode manually (e.g. when going
        on holiday) via a future endpoint — that transition is not implemented
        in the MVP.

        Args:
            conversation_id: UUID of the conversation to hand off.

        Returns:
            Updated WhatsAppConversation with mode='handoff'.

        Raises:
            NotFoundError: If no conversation with this ID is visible to the
                           current tenant (RLS-filtered lookup returns None).
        """
        conversation = await self.repository.get_conversation_by_id(conversation_id)
        if conversation is None:
            raise NotFoundError("Conversation not found")

        return await self.repository.update_conversation(
            conversation,
            {"mode": "handoff", "status": "waiting_professional"},
        )

    async def list_conversations(
        self,
        status_filter: str | None = None,
    ) -> list[WhatsAppConversation]:
        """
        List conversations for the current tenant (RLS-filtered).

        Delegates entirely to the repository. The RLS context must already
        be set on the session (via TenantSession in the router).

        Args:
            status_filter: Optional status to filter by ('active', 'resolved',
                           'waiting_professional'). None returns all statuses.

        Returns:
            List of WhatsAppConversation instances ordered by last_message_at DESC.
        """
        return await self.repository.list_conversations(status=status_filter)

    async def get_conversation_detail(
        self,
        conversation_id: UUID,
    ) -> tuple[WhatsAppConversation, list[WhatsAppMessage]]:
        """
        Fetch a conversation and its message history in one service call.

        Combining both queries here (rather than making the router call
        two service methods) keeps the controller thin and ensures both
        pieces of data are fetched within the same RLS-active transaction.

        Args:
            conversation_id: UUID of the conversation to retrieve.

        Returns:
            Tuple of (WhatsAppConversation, list[WhatsAppMessage]) where
            messages are ordered by sent_at ASC (chronological).

        Raises:
            NotFoundError: If the conversation doesn't exist or belongs to
                           another tenant (RLS makes them indistinguishable).
        """
        conversation = await self.repository.get_conversation_by_id(conversation_id)
        if conversation is None:
            raise NotFoundError("Conversation not found")

        messages = await self.repository.get_messages_for_conversation(conversation_id)
        return conversation, messages
