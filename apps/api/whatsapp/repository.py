"""
WhatsApp repository — database layer for conversations and messages.

Covers: whatsapp_conversations, whatsapp_messages tables.
All tables are RLS-protected.
"""

from sqlalchemy.ext.asyncio import AsyncSession


class WhatsAppRepository:
    """Data access layer for whatsapp tables (RLS-protected)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # TODO: Implement after models are created
