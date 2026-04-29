"""
WhatsApp repository — database layer for conversations and messages.

Design:
- RLS is active on whatsapp_conversations. Queries do NOT filter by
  professional_id — PostgreSQL enforces tenant isolation automatically via
  SET LOCAL app.current_tenant (set by TenantSession in the router).
  The only exception is create_conversation(), which must write the FK value
  into the new row before RLS can enforce isolation on it.

- whatsapp_messages has NO RLS. All message queries filter explicitly by
  conversation_id. Because conversations are already RLS-isolated, a valid
  conversation_id implicitly scopes messages to the correct tenant.

- find_message_by_whatsapp_id() queries whatsapp_messages WITHOUT any
  additional filter. This is intentional: the whatsapp_msg_id has a global
  UNIQUE constraint, and idempotency checks must work even if (by a bug)
  the same Meta message_id were delivered to two different tenants' webhooks.
  No sensitive data is exposed — only the existence of the row is checked.

- find_professional_by_phone_id() imports Professional inline to avoid a
  circular import: whatsapp.repository → professionals.models →
  (nothing in professionals imports whatsapp, but keeping it inline is the
  established pattern for cross-module model access in this codebase).
"""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from whatsapp.models import WhatsAppConversation, WhatsAppMessage


class WhatsAppRepository:
    """Data access layer for whatsapp_conversations and whatsapp_messages tables."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # =========================================================================
    # Conversations
    # =========================================================================

    async def create_conversation(
        self,
        professional_id: UUID,
        client_phone: str,
    ) -> WhatsAppConversation:
        """
        Open a new conversation for the given professional and client phone.

        professional_id is passed explicitly because the row does not exist yet
        — RLS cannot enforce tenant isolation until after the row is created.
        started_at and last_message_at are set in Python (not deferred to
        server_default) so the returned object has populated datetime fields
        immediately after flush, without requiring an extra round-trip.

        Args:
            professional_id: UUID of the owning professional (tenant).
            client_phone: Normalized phone number of the client (E.164 recommended).

        Returns:
            Persisted WhatsAppConversation with server-generated id and timestamps.
        """
        now = datetime.now(UTC)
        conversation = WhatsAppConversation(
            professional_id=professional_id,
            client_phone=client_phone,
            status="active",
            mode="ai",
            started_at=now,
            last_message_at=now,
        )
        self.session.add(conversation)
        await self.session.flush()
        await self.session.refresh(conversation)
        return conversation

    async def find_active_conversation_by_phone(
        self,
        client_phone: str,
    ) -> WhatsAppConversation | None:
        """
        Find an open (status='active') conversation for this phone number.

        RLS filters by the current tenant automatically — no WHERE professional_id
        clause needed. If the professional has no active conversation with this
        phone, returns None so the caller can create one.

        Args:
            client_phone: Client phone number to look up.

        Returns:
            Active WhatsAppConversation for this tenant and phone, or None.
        """
        result = await self.session.execute(
            select(WhatsAppConversation).where(
                WhatsAppConversation.client_phone == client_phone,
                WhatsAppConversation.status == "active",
            )
        )
        return result.scalar_one_or_none()

    async def get_conversation_by_id(
        self,
        conversation_id: UUID,
    ) -> WhatsAppConversation | None:
        """
        Fetch a conversation by primary key.

        RLS ensures conversations from other tenants are invisible — a
        cross-tenant UUID returns None, not a 403 (no oracle attack surface).

        Args:
            conversation_id: UUID of the conversation.

        Returns:
            WhatsAppConversation if found within the current tenant, else None.
        """
        result = await self.session.execute(
            select(WhatsAppConversation).where(
                WhatsAppConversation.id == conversation_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_conversations(
        self,
        status: str | None = None,
    ) -> list[WhatsAppConversation]:
        """
        List all conversations for the current tenant (RLS-filtered).

        Ordered by last_message_at DESC so the most recently active
        conversation appears first — matches the expected dashboard order.

        Args:
            status: Optional status filter ('active', 'resolved',
                    'waiting_professional'). If None, returns all statuses.

        Returns:
            List of WhatsAppConversation instances for the current tenant.
        """
        query = select(WhatsAppConversation)

        if status is not None:
            query = query.where(WhatsAppConversation.status == status)

        query = query.order_by(WhatsAppConversation.last_message_at.desc())

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update_conversation(
        self,
        conversation: WhatsAppConversation,
        data: dict,
    ) -> WhatsAppConversation:
        """
        Apply partial updates to an existing conversation.

        The caller is responsible for fetching the conversation first (and
        raising NotFoundError if needed) before passing the object here.
        Receiving the already-fetched object avoids a redundant SELECT inside
        the repository and keeps transaction boundaries clear.

        Args:
            conversation: The WhatsAppConversation instance to update.
            data: Dict of fields to update (e.g. {"mode": "handoff", "status": "waiting_professional"}).

        Returns:
            Updated WhatsAppConversation with refreshed server values.
        """
        for field, value in data.items():
            setattr(conversation, field, value)

        await self.session.flush()
        await self.session.refresh(conversation)
        return conversation

    # =========================================================================
    # Messages
    # =========================================================================

    async def create_message(
        self,
        conversation_id: UUID,
        direction: str,
        sender_type: str,
        content: str,
        whatsapp_msg_id: str | None = None,
    ) -> WhatsAppMessage:
        """
        Persist a new message linked to the given conversation.

        whatsapp_msg_id is Meta's unique identifier for inbound messages.
        It is stored to enable idempotency checks (Meta may re-deliver the same
        webhook). For outbound AI/professional messages it will be None until
        we get a response from the Meta send API (stored separately if needed).

        Args:
            conversation_id: UUID of the parent conversation.
            direction: 'inbound' (client → system) or 'outbound' (system → client).
            sender_type: 'client', 'ai', or 'professional'.
            content: Plain-text message body.
            whatsapp_msg_id: Meta's message ID (only present for inbound messages).

        Returns:
            Persisted WhatsAppMessage with server-generated id and sent_at.
        """
        message = WhatsAppMessage(
            conversation_id=conversation_id,
            direction=direction,
            sender_type=sender_type,
            content=content,
            whatsapp_msg_id=whatsapp_msg_id,
        )
        self.session.add(message)
        await self.session.flush()
        await self.session.refresh(message)
        return message

    async def find_message_by_whatsapp_id(
        self,
        whatsapp_msg_id: str,
    ) -> WhatsAppMessage | None:
        """
        Look up a message by Meta's unique message ID.

        Used for idempotency: Meta's webhook delivery has at-least-once
        semantics, meaning the same message can arrive more than once.
        Checking for an existing row with this ID before processing prevents
        duplicate conversations and AI replies.

        No RLS restriction here — whatsapp_messages has no RLS, and
        whatsapp_msg_id has a global UNIQUE constraint. The check is
        purely "has this message been processed before?", regardless of tenant.

        Args:
            whatsapp_msg_id: Meta's message identifier string.

        Returns:
            WhatsAppMessage if this ID was already processed, else None.
        """
        result = await self.session.execute(
            select(WhatsAppMessage).where(
                WhatsAppMessage.whatsapp_msg_id == whatsapp_msg_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_messages_for_conversation(
        self,
        conversation_id: UUID,
        limit: int = 50,
    ) -> list[WhatsAppMessage]:
        """
        Fetch messages for a conversation, oldest first.

        Ordered by sent_at ASC so the list reads chronologically — the last
        item in the returned list is the most recent message, which matches
        the expected shape for building an AI history array (user, assistant,
        user, assistant, ...).

        Args:
            conversation_id: UUID of the parent conversation.
            limit: Maximum number of messages to return (default 50).
                   Pass a smaller value (e.g. 20) when building AI context
                   to stay within token budgets.

        Returns:
            List of WhatsAppMessage instances, ordered by sent_at ASC.
        """
        result = await self.session.execute(
            select(WhatsAppMessage)
            .where(WhatsAppMessage.conversation_id == conversation_id)
            .order_by(WhatsAppMessage.sent_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    # =========================================================================
    # Professionals (cross-module, webhook only)
    # =========================================================================

    async def find_professional_by_phone_id(
        self,
        phone_number_id: str,
    ) -> "Professional | None":  # type: ignore[name-defined]  # noqa: F821
        """
        Find an active professional by their WhatsApp Business phone_number_id.

        This is the entry point for the webhook flow: Meta sends the
        phone_number_id in every webhook payload, and we use it to resolve
        which professional (tenant) owns the receiving phone number.

        Professional is imported inline to avoid a circular import:
          whatsapp.repository imports professionals.models
          professionals does not import whatsapp — but keeping this inline
          is the established pattern in this codebase for cross-module access.

        No RLS needed — professionals table has no RLS policy, and we need to
        find the professional *before* we can set the tenant context.

        Args:
            phone_number_id: Meta's stable phone_number_id for the WABA phone.

        Returns:
            Active Professional whose whatsapp_phone_id matches, or None.
        """
        # Inline import to avoid circular dependency:
        # whatsapp.repository → professionals.models is fine at import time,
        # but keeping it local makes the cross-module dependency explicit.
        from professionals.models import Professional

        result = await self.session.execute(
            select(Professional).where(
                Professional.whatsapp_phone_id == phone_number_id,
                Professional.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()
