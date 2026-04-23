"""
WhatsApp service — business logic for Meta Cloud API integration.

Responsibilities:
- Process incoming webhook messages
- Route messages to AI or professional
- Send messages via Meta Cloud API
- Manage conversation state (ai/handoff mode)
"""

from sqlalchemy.ext.asyncio import AsyncSession


class WhatsAppService:
    """Handles WhatsApp business logic."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # TODO: Implement after repository layer is ready
    # Methods to implement:
    # - handle_incoming_message(payload: dict) -> None
    # - send_message(phone: str, message: str, access_token: str, phone_id: str) -> None
    # - get_conversations(professional_id: UUID) -> list[Conversation]
    # - handoff_to_professional(conversation_id: UUID) -> None
