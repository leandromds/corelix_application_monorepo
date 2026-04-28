"""SQLAlchemy models for the agenda module.

Tables: availability_slots, blocked_periods, recurrences, sessions.

Nota sobre a ordem das classes neste arquivo: Session referencia Recurrence
via FK, então Recurrence deve ser definida antes de Session.
"""

from datetime import date, datetime, time
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    Time,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TIMESTAMP
from sqlalchemy.types import UUID as SQLUUID

from core.database import Base
from core.mixins import CreatedAtMixin, TimestampMixin


class AvailabilitySlot(TimestampMixin, Base):
    """
    Horário de disponibilidade semanal do profissional.

    day_of_week: 0=domingo, 6=sábado (convenção Python/JS).
    TIME (não TIMESTAMPTZ): representa um padrão semanal, não um instante.
    Múltiplos blocos por dia são permitidos (ex: 08:00-12:00 e 14:00-18:00).
    """

    __tablename__ = "availability_slots"

    __table_args__ = (
        CheckConstraint("end_time > start_time", name="chk_time_range"),
        CheckConstraint("day_of_week BETWEEN 0 AND 6", name="chk_day_of_week"),
        Index("idx_availability_slots_professional_id", "professional_id"),
    )

    professional_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("professionals.id", ondelete="CASCADE"),
        nullable=False,
    )
    day_of_week: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )


class BlockedPeriod(CreatedAtMixin, Base):
    """
    Período bloqueado na agenda (férias, feriados, indisponibilidade).

    Sem updated_at: bloqueios são criados ou deletados, nunca editados.
    notify_clients default TRUE: opt-out intencional — profissional precisa
    desmarcar explicitamente se não quiser notificar.

    Índice composto em (professional_id, start_datetime, end_datetime)
    acelera a verificação de conflito de agenda.
    """

    __tablename__ = "blocked_periods"

    __table_args__ = (
        CheckConstraint(
            "end_datetime > start_datetime", name="chk_blocked_period_range"
        ),
        Index("idx_blocked_periods_professional_id", "professional_id"),
        Index(
            "idx_blocked_periods_range",
            "professional_id",
            "start_datetime",
            "end_datetime",
        ),
    )

    professional_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("professionals.id", ondelete="CASCADE"),
        nullable=False,
    )
    start_datetime: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    end_datetime: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    reason: Mapped[str | None] = mapped_column(String(255))
    notify_clients: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )


class Recurrence(TimestampMixin, Base):
    """
    Padrão de sessões recorrentes para um cliente.

    Ao criar uma Recurrence, o AgendaService gera as Sessions futuras
    em janelas de tempo via pgqueuer.

    end_date=None significa recorrência sem fim definido.
    day_of_week é opcional para recorrências mensais (ex: todo dia 15).
    """

    __tablename__ = "recurrences"

    __table_args__ = (
        CheckConstraint(
            "frequency IN ('weekly', 'biweekly', 'monthly')",
            name="chk_recurrence_frequency",
        ),
        CheckConstraint("interval > 0", name="chk_recurrence_interval"),
        CheckConstraint(
            "day_of_week IS NULL OR day_of_week BETWEEN 0 AND 6",
            name="chk_recurrence_day_of_week",
        ),
        CheckConstraint(
            "end_date IS NULL OR end_date > start_date",
            name="chk_recurrence_end_date",
        ),
        Index("idx_recurrences_professional_id", "professional_id"),
        Index("idx_recurrences_client_id", "client_id"),
    )

    professional_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("professionals.id", ondelete="RESTRICT"),
        nullable=False,
    )
    client_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("clients.id", ondelete="RESTRICT"),
        nullable=False,
    )
    frequency: Mapped[str] = mapped_column(String(20), nullable=False)
    interval: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
    day_of_week: Mapped[int | None] = mapped_column(SmallInteger)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date)
    session_duration: Mapped[int] = mapped_column(Integer, nullable=False)
    session_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )


class Session(TimestampMixin, Base):
    """
    Sessão agendada entre profissional e cliente.

    price é congelado no momento do agendamento — não usa o preço atual
    do profissional. Isso garante que relatórios históricos sejam precisos
    mesmo após mudanças de preço.

    recurrence_id usa SET NULL: cancelar a recorrência não apaga as sessões
    já agendadas — elas continuam existindo de forma independente.

    Índice parcial WHERE status='scheduled' acelera verificação de conflito:
    só precisamos checar sessões futuras confirmadas.
    """

    __tablename__ = "sessions"

    __table_args__ = (
        CheckConstraint(
            "status IN ('scheduled', 'completed', 'cancelled', 'no_show')",
            name="chk_session_status",
        ),
        CheckConstraint("duration_minutes > 0", name="chk_duration"),
        Index("idx_sessions_professional_id", "professional_id"),
        Index("idx_sessions_client_id", "client_id"),
        Index("idx_sessions_scheduled_at", "professional_id", "scheduled_at"),
        Index(
            "idx_sessions_conflict_check",
            "professional_id",
            "scheduled_at",
            "status",
            postgresql_where=text("status = 'scheduled'"),
        ),
    )

    professional_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("professionals.id", ondelete="RESTRICT"),
        nullable=False,
    )
    client_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("clients.id", ondelete="RESTRICT"),
        nullable=False,
    )
    recurrence_id: Mapped[UUID | None] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("recurrences.id", ondelete="SET NULL"),
    )
    scheduled_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="scheduled", server_default=text("'scheduled'")
    )
    notes: Mapped[str | None] = mapped_column(Text)
