"""SQLAlchemy model for the professionals table."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, Integer, Numeric, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TIMESTAMP, UUID as SQLUUID

from core.database import Base
from core.mixins import TimestampMixin


class Professional(TimestampMixin, Base):
    """
    Representa um profissional autônomo (tenant do sistema).

    É a raiz de toda a hierarquia de dados — todas as tabelas com RLS
    referenciam professional_id como FK.

    whatsapp_access_token é armazenado criptografado (Fernet).
    A descriptografia acontece no service layer quando necessário.
    """

    __tablename__ = "professionals"

    email: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    specialty: Mapped[str | None] = mapped_column(String(255))
    bio: Mapped[str | None] = mapped_column(Text)
    session_duration: Mapped[int] = mapped_column(
        Integer, nullable=False, default=60, server_default=text("60")
    )
    session_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    phone: Mapped[str | None] = mapped_column(String(20))

    # WhatsApp Business — preenchido após Embedded Signup
    whatsapp_phone_number: Mapped[str | None] = mapped_column(String(20))
    whatsapp_phone_id: Mapped[str | None] = mapped_column(String(100))
    whatsapp_access_token: Mapped[str | None] = mapped_column(Text)  # criptografado
    whatsapp_connected_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True)
    )
    whatsapp_token_expires_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True)
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
