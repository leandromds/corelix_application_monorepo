"""SQLAlchemy models for the whatsapp module.

Tables: whatsapp_conversations, whatsapp_messages.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TIMESTAMP
from sqlalchemy.types import UUID as SQLUUID

from core.database import Base
from core.mixins import TimestampMixin


class WhatsAppConversation(TimestampMixin, Base):
    """
    Conversa WhatsApp entre um cliente e a secretária digital.

    mode='ai'     → IA responde automaticamente
    mode='handoff'→ profissional respondendo manualmente pelo app

    client_id usa SET NULL: contato pode ser de alguém não cadastrado ainda.
    Quando o cliente se cadastrar, pode-se vincular retroativamente.

    Índice parcial em status='active' acelera queries do dashboard
    (que só precisa mostrar conversas ativas).
    """

    __tablename__ = "whatsapp_conversations"

    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'resolved', 'waiting_professional')",
            name="chk_conversation_status",
        ),
        CheckConstraint(
            "mode IN ('ai', 'handoff')",
            name="chk_conversation_mode",
        ),
        Index("idx_conversations_professional_id", "professional_id"),
        Index("idx_conversations_client_phone", "professional_id", "client_phone"),
        Index(
            "idx_conversations_status",
            "professional_id",
            "status",
            postgresql_where=text("status = 'active'"),
        ),
    )

    professional_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("professionals.id", ondelete="RESTRICT"),
        nullable=False,
    )
    client_id: Mapped[UUID | None] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("clients.id", ondelete="SET NULL"),
    )
    client_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active", server_default=text("'active'")
    )
    mode: Mapped[str] = mapped_column(
        String(20), nullable=False, default="ai", server_default=text("'ai'")
    )
    started_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=text("NOW()"),
        nullable=False,
    )
    last_message_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=text("NOW()"),
        nullable=False,
    )
    ended_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))


class WhatsAppMessage(Base):
    """
    Mensagem individual de uma conversa WhatsApp.

    Sem TimestampMixin: usa sent_at em vez de created_at para refletir
    o momento real em que a mensagem foi enviada/recebida, não quando
    foi inserida no banco (pode haver delay no processamento do webhook).

    whatsapp_msg_id: ID único da Meta — usado para deduplicação de webhooks
    (Meta pode reenviar o mesmo webhook mais de uma vez).

    ON DELETE CASCADE: mensagens não têm valor sem a conversa.
    """

    __tablename__ = "whatsapp_messages"

    __table_args__ = (
        CheckConstraint(
            "direction IN ('inbound', 'outbound')",
            name="chk_message_direction",
        ),
        CheckConstraint(
            "sender_type IN ('client', 'ai', 'professional')",
            name="chk_message_sender_type",
        ),
        Index("idx_messages_conversation_id", "conversation_id"),
    )

    conversation_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("whatsapp_conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    sender_type: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    whatsapp_msg_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    sent_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=text("NOW()"),
        nullable=False,
    )
