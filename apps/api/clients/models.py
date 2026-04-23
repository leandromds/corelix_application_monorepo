"""SQLAlchemy model for the clients table."""

from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import UUID as SQLUUID

from core.database import Base
from core.mixins import TimestampMixin


class Client(TimestampMixin, Base):
    """
    Cliente de um profissional (tenant-isolated via RLS).

    ON DELETE RESTRICT: clientes têm valor histórico — não podem ser
    deletados se houver sessões vinculadas.

    whatsapp_opt_in e email_opt_in são obrigatórios pela LGPD e pelas
    políticas da Meta para uso do WhatsApp Business.
    """

    __tablename__ = "clients"

    __table_args__ = (
        Index("idx_clients_professional_id", "professional_id"),
        Index("idx_clients_phone", "professional_id", "phone"),
    )

    professional_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("professionals.id", ondelete="RESTRICT"),
        nullable=False,
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)
    whatsapp_opt_in: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    email_opt_in: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
