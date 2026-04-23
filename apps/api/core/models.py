"""SQLAlchemy model for the audit_logs table."""

from typing import Any
from uuid import UUID

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import UUID as SQLUUID

from core.database import Base
from core.mixins import CreatedAtMixin


class AuditLog(CreatedAtMixin, Base):
    """
    Registro imutável de cada alteração sensível no sistema.

    Sem RLS: acesso controlado pelo service layer (admin).
    Sem updated_at: logs de auditoria nunca são editados — é uma
    premissa de segurança, não uma conveniência.

    entity_id é UUID mas NOT FK — referencia qualquer tabela.
    old_data / new_data: snapshots JSONB antes e depois da alteração.
    ip_address VARCHAR(45): suporta IPv6 (máx 39 chars + zona).
    """

    __tablename__ = "audit_logs"

    professional_id: Mapped[UUID | None] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("professionals.id", ondelete="SET NULL"),
        index=True,
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_id: Mapped[UUID | None] = mapped_column(SQLUUID(as_uuid=True))
    old_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    new_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(Text)
