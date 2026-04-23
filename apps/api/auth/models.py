"""SQLAlchemy model for the refresh_tokens table."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TIMESTAMP, UUID as SQLUUID

from core.database import Base
from core.mixins import CreatedAtMixin


class RefreshToken(CreatedAtMixin, Base):
    """
    Refresh token armazenado no banco (com hash SHA-256).

    Design:
    - Sem updated_at — tokens são imutáveis (criados ou revogados)
    - token_hash armazena SHA-256 do token raw (nunca o token em si)
    - revoked=True invalida o token sem deletar o registro (auditoria)
    - CASCADE: tokens são deletados quando o professional é deletado
    """

    __tablename__ = "refresh_tokens"

    professional_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("professionals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True
    )
    device_info: Mapped[str | None] = mapped_column(String(255))
    expires_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    revoked: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
