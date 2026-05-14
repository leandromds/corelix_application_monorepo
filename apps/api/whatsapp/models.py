"""SQLAlchemy models for the whatsapp module.

Tables: whatsapp_conversations, whatsapp_messages.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TIMESTAMP
from sqlalchemy.types import UUID as SQLUUID

from core.database import Base
from core.mixins import CreatedAtMixin, TimestampMixin


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


# ============================================================================
# Provider architecture models (ADR-028)
# ============================================================================


class WhatsAppAccount(TimestampMixin, Base):
    """
    Vincula um profissional a um provider WhatsApp com número dedicado.

    provider_type='meta': número próprio via Embedded Signup
    provider_type='twilio_shared': número Corelix compartilhado

    access_token_encrypted é cifrado com Fernet (providers/crypto.py).
    Descriptografar apenas no momento de uso — não manter plaintext em memória.
    routing_tag: slug curto único para roteamento Twilio (ex: 'CMcm6').
    """

    __tablename__ = "whatsapp_accounts"
    __table_args__ = (
        CheckConstraint(
            "provider_type IN ('meta', 'twilio_shared')",
            name="chk_wa_account_provider_type",
        ),
    )

    professional_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("professionals.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    provider_type: Mapped[str] = mapped_column(Text, nullable=False)
    phone_number: Mapped[str] = mapped_column(Text, nullable=False)  # E.164
    phone_number_id: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # Meta phone_number_id ou Twilio MSGSVC SID
    access_token_encrypted: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    routing_tag: Mapped[str | None] = mapped_column(
        Text, unique=True
    )  # usado no modo Twilio Shared
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )


class WhatsAppPhoneBinding(CreatedAtMixin, Base):
    """
    Mapeia número de telefone do cliente final para um profissional.

    Usado exclusivamente pelo TwilioSharedAccountProvider para resolver
    de qual profissional é cada mensagem entrante no número compartilhado.

    bound_via:
      'tag'    — cliente enviou mensagem com tag DRANA-{slug} na primeira mensagem
      'qr'     — cliente escaneou QR code único do profissional
      'manual' — profissional iniciou conversa pelo dashboard (template outbound)

    Índice em phone_number para lookup rápido em cada webhook entrante.
    """

    __tablename__ = "whatsapp_phone_bindings"
    __table_args__ = (
        UniqueConstraint("phone_number", "professional_id", name="uq_phone_binding"),
        Index("ix_phone_bindings_phone", "phone_number"),
        CheckConstraint("bound_via IN ('tag', 'qr', 'manual')", name="chk_bound_via"),
    )

    professional_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("professionals.id", ondelete="CASCADE"),
        nullable=False,
    )
    phone_number: Mapped[str] = mapped_column(Text, nullable=False)  # E.164
    bound_via: Mapped[str] = mapped_column(Text, nullable=False)
    bound_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=text("NOW()"),
        nullable=False,
    )


class WhatsAppProviderMessage(CreatedAtMixin, Base):
    """
    Log de idempotência para mensagens processadas por providers.

    Garante que cada mensagem (identificada por professional_id + provider_message_id)
    seja processada exatamente uma vez, mesmo que o provider reenvie o webhook.

    Twilio e Meta têm semântica at-least-once — sem este log, um lembrete de
    consulta pode ser disparado em duplicidade para o cliente final.

    Separada da WhatsAppMessage (conversation-based) por ser uma preocupação
    transversal do provider layer, não da lógica de conversa.
    """

    __tablename__ = "whatsapp_provider_messages"
    __table_args__ = (
        UniqueConstraint("professional_id", "provider_message_id", name="uq_provider_msg"),
        CheckConstraint("direction IN ('inbound', 'outbound')", name="chk_provider_msg_direction"),
    )

    professional_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("professionals.id", ondelete="RESTRICT"),
        nullable=False,
    )
    provider_message_id: Mapped[str] = mapped_column(Text, nullable=False)
    direction: Mapped[str] = mapped_column(Text, nullable=False)
    from_phone: Mapped[str] = mapped_column(Text, nullable=False)  # E.164
    to_phone: Mapped[str] = mapped_column(Text, nullable=False)  # E.164
    body: Mapped[str] = mapped_column(Text, nullable=False)
    provider_type: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # 'meta', 'twilio_shared', 'terminal'
