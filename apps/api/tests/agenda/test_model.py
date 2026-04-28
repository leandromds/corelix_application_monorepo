"""Tests for agenda models + RLS isolation — TDD Red phase. Requer banco.

Coverage:
- AvailabilitySlot: defaults (is_active=True), CHECK chk_time_range,
                    CHECK chk_day_of_week, FK to professionals
- BlockedPeriod:    defaults (notify_clients=True), CHECK chk_blocked_period_range
- Recurrence:       defaults (is_active=True, interval=1), FK constraints
- Session:          defaults (status='scheduled'), CHECK chk_session_status,
                    CHECK chk_duration

RLS isolation tests follow the same pattern as tests/clients/test_model.py:
  1. Create records for two different professionals (postgres user, BYPASSRLS).
  2. SET LOCAL ROLE test_rls_user — activates RLS enforcement (postgres has
     BYPASSRLS and would ignore all policies otherwise).
  3. SET LOCAL app.current_tenant — sets the tenant UUID read by the policy.
  4. Query — RLS filters out the other tenant's rows.
"""

from datetime import UTC, date, datetime, time
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from agenda.models import AvailabilitySlot, BlockedPeriod, Recurrence
from agenda.models import Session as AgendaSession
from clients.models import Client
from professionals.models import Professional

# ---------------------------------------------------------------------------
# Helper factories (avoid repetition across test classes)
# ---------------------------------------------------------------------------


async def _make_prof(session: AsyncSession, email: str) -> Professional:
    """Create and flush a minimal Professional record."""
    p = Professional(email=email, password_hash="h", full_name="Test Pro")
    session.add(p)
    await session.flush()
    return p


async def _make_client(session: AsyncSession, prof: Professional) -> Client:
    """Create and flush a minimal Client record for the given professional."""
    c = Client(
        professional_id=prof.id,
        full_name="Test Client",
        phone=f"119{uuid4().int % 100_000_000:08d}",  # unique per call
    )
    session.add(c)
    await session.flush()
    return c


# ---------------------------------------------------------------------------
# AvailabilitySlot
# ---------------------------------------------------------------------------


class TestAvailabilitySlotModel:
    async def test_create_slot_persists_record(self, db_session: AsyncSession) -> None:
        """INSERT deve persistir o slot e gerar um UUID de id."""
        prof = await _make_prof(db_session, "slot_create@example.com")
        slot = AvailabilitySlot(
            professional_id=prof.id,
            day_of_week=1,
            start_time=time(9, 0),
            end_time=time(17, 0),
        )
        db_session.add(slot)
        await db_session.flush()

        assert slot.id is not None
        assert slot.day_of_week == 1
        assert slot.start_time == time(9, 0)
        assert slot.end_time == time(17, 0)

    async def test_slot_is_active_defaults_true(self, db_session: AsyncSession) -> None:
        """is_active deve ser True por padrão (server_default=true)."""
        prof = await _make_prof(db_session, "slot_active@example.com")
        slot = AvailabilitySlot(
            professional_id=prof.id,
            day_of_week=2,
            start_time=time(8, 0),
            end_time=time(12, 0),
        )
        db_session.add(slot)
        await db_session.flush()
        await db_session.refresh(slot)

        assert slot.is_active is True

    async def test_slot_created_at_and_updated_at_set_on_insert(
        self, db_session: AsyncSession
    ) -> None:
        """TimestampMixin: created_at e updated_at devem ser preenchidos no flush."""
        prof = await _make_prof(db_session, "slot_timestamps@example.com")
        slot = AvailabilitySlot(
            professional_id=prof.id,
            day_of_week=3,
            start_time=time(10, 0),
            end_time=time(11, 0),
        )
        db_session.add(slot)
        await db_session.flush()
        await db_session.refresh(slot)

        assert slot.created_at is not None
        assert slot.updated_at is not None

    async def test_slot_check_end_time_before_start_raises(self, db_session: AsyncSession) -> None:
        """CHECK chk_time_range: end_time <= start_time deve lançar IntegrityError."""
        prof = await _make_prof(db_session, "slot_range@example.com")
        slot = AvailabilitySlot(
            professional_id=prof.id,
            day_of_week=1,
            start_time=time(17, 0),
            end_time=time(9, 0),  # end < start — viola chk_time_range
        )
        db_session.add(slot)

        with pytest.raises(IntegrityError):
            await db_session.flush()

    async def test_slot_check_day_of_week_above_6_raises(self, db_session: AsyncSession) -> None:
        """CHECK chk_day_of_week: day_of_week=7 deve lançar IntegrityError."""
        prof = await _make_prof(db_session, "slot_day7@example.com")
        slot = AvailabilitySlot(
            professional_id=prof.id,
            day_of_week=7,  # viola chk_day_of_week (BETWEEN 0 AND 6)
            start_time=time(9, 0),
            end_time=time(17, 0),
        )
        db_session.add(slot)

        with pytest.raises(IntegrityError):
            await db_session.flush()

    async def test_slot_check_day_of_week_negative_raises(self, db_session: AsyncSession) -> None:
        """CHECK chk_day_of_week: day_of_week=-1 deve lançar IntegrityError."""
        prof = await _make_prof(db_session, "slot_dayneg@example.com")
        slot = AvailabilitySlot(
            professional_id=prof.id,
            day_of_week=-1,  # viola chk_day_of_week
            start_time=time(9, 0),
            end_time=time(17, 0),
        )
        db_session.add(slot)

        with pytest.raises(IntegrityError):
            await db_session.flush()

    async def test_slot_requires_valid_professional(self, db_session: AsyncSession) -> None:
        """FK ondelete=CASCADE: professional_id inválido deve lançar IntegrityError."""
        slot = AvailabilitySlot(
            professional_id=uuid4(),  # não existe na tabela professionals
            day_of_week=1,
            start_time=time(9, 0),
            end_time=time(17, 0),
        )
        db_session.add(slot)

        with pytest.raises(IntegrityError):
            await db_session.flush()


# ---------------------------------------------------------------------------
# BlockedPeriod
# ---------------------------------------------------------------------------


class TestBlockedPeriodModel:
    async def test_create_blocked_period_persists_record(self, db_session: AsyncSession) -> None:
        """INSERT deve persistir o período e gerar id."""
        prof = await _make_prof(db_session, "blocked_create@example.com")
        period = BlockedPeriod(
            professional_id=prof.id,
            start_datetime=datetime(2025, 6, 1, 8, 0, tzinfo=UTC),
            end_datetime=datetime(2025, 6, 1, 18, 0, tzinfo=UTC),
        )
        db_session.add(period)
        await db_session.flush()

        assert period.id is not None

    async def test_blocked_period_notify_clients_defaults_true(
        self, db_session: AsyncSession
    ) -> None:
        """notify_clients deve ser True por padrão (server_default=true)."""
        prof = await _make_prof(db_session, "blocked_notify@example.com")
        period = BlockedPeriod(
            professional_id=prof.id,
            start_datetime=datetime(2025, 6, 1, 8, 0, tzinfo=UTC),
            end_datetime=datetime(2025, 6, 1, 18, 0, tzinfo=UTC),
        )
        db_session.add(period)
        await db_session.flush()
        await db_session.refresh(period)

        assert period.notify_clients is True

    async def test_blocked_period_created_at_set_on_insert(self, db_session: AsyncSession) -> None:
        """CreatedAtMixin: created_at deve ser preenchido no flush."""
        prof = await _make_prof(db_session, "blocked_ts@example.com")
        period = BlockedPeriod(
            professional_id=prof.id,
            start_datetime=datetime(2025, 6, 1, 8, 0, tzinfo=UTC),
            end_datetime=datetime(2025, 6, 1, 18, 0, tzinfo=UTC),
        )
        db_session.add(period)
        await db_session.flush()
        await db_session.refresh(period)

        assert period.created_at is not None

    async def test_blocked_period_check_end_before_start_raises(
        self, db_session: AsyncSession
    ) -> None:
        """CHECK chk_blocked_period_range: end_datetime <= start_datetime deve lançar."""
        prof = await _make_prof(db_session, "blocked_range@example.com")
        period = BlockedPeriod(
            professional_id=prof.id,
            start_datetime=datetime(2025, 6, 1, 18, 0, tzinfo=UTC),
            end_datetime=datetime(2025, 6, 1, 8, 0, tzinfo=UTC),  # end < start
        )
        db_session.add(period)

        with pytest.raises(IntegrityError):
            await db_session.flush()

    async def test_blocked_period_reason_is_nullable(self, db_session: AsyncSession) -> None:
        """reason deve aceitar NULL (campo opcional)."""
        prof = await _make_prof(db_session, "blocked_reason@example.com")
        period = BlockedPeriod(
            professional_id=prof.id,
            start_datetime=datetime(2025, 6, 1, 8, 0, tzinfo=UTC),
            end_datetime=datetime(2025, 6, 1, 18, 0, tzinfo=UTC),
        )
        db_session.add(period)
        await db_session.flush()

        assert period.reason is None


# ---------------------------------------------------------------------------
# Recurrence
# ---------------------------------------------------------------------------


class TestRecurrenceModel:
    async def test_create_recurrence_persists_record(self, db_session: AsyncSession) -> None:
        """INSERT deve persistir a recorrência e gerar id."""
        prof = await _make_prof(db_session, "rec_create@example.com")
        client = await _make_client(db_session, prof)
        rec = Recurrence(
            professional_id=prof.id,
            client_id=client.id,
            frequency="weekly",
            day_of_week=1,
            start_date=date(2025, 1, 1),
            session_duration=60,
            session_price=Decimal("150.00"),
        )
        db_session.add(rec)
        await db_session.flush()

        assert rec.id is not None

    async def test_recurrence_is_active_defaults_true(self, db_session: AsyncSession) -> None:
        """is_active deve ser True por padrão."""
        prof = await _make_prof(db_session, "rec_active@example.com")
        client = await _make_client(db_session, prof)
        rec = Recurrence(
            professional_id=prof.id,
            client_id=client.id,
            frequency="monthly",
            start_date=date(2025, 1, 1),
            session_duration=60,
            session_price=Decimal("100.00"),
        )
        db_session.add(rec)
        await db_session.flush()
        await db_session.refresh(rec)

        assert rec.is_active is True

    async def test_recurrence_interval_defaults_one(self, db_session: AsyncSession) -> None:
        """interval deve ter default=1 (server_default='1')."""
        prof = await _make_prof(db_session, "rec_interval@example.com")
        client = await _make_client(db_session, prof)
        rec = Recurrence(
            professional_id=prof.id,
            client_id=client.id,
            frequency="monthly",
            start_date=date(2025, 1, 1),
            session_duration=60,
            session_price=Decimal("100.00"),
        )
        db_session.add(rec)
        await db_session.flush()
        await db_session.refresh(rec)

        assert rec.interval == 1

    async def test_recurrence_day_of_week_nullable_for_monthly(
        self, db_session: AsyncSession
    ) -> None:
        """day_of_week pode ser NULL para recorrências mensais."""
        prof = await _make_prof(db_session, "rec_dow_null@example.com")
        client = await _make_client(db_session, prof)
        rec = Recurrence(
            professional_id=prof.id,
            client_id=client.id,
            frequency="monthly",
            day_of_week=None,
            start_date=date(2025, 1, 1),
            session_duration=60,
            session_price=Decimal("100.00"),
        )
        db_session.add(rec)
        await db_session.flush()

        assert rec.day_of_week is None

    async def test_recurrence_requires_valid_client(self, db_session: AsyncSession) -> None:
        """FK ondelete=RESTRICT: client_id inválido deve lançar IntegrityError."""
        prof = await _make_prof(db_session, "rec_fk@example.com")
        rec = Recurrence(
            professional_id=prof.id,
            client_id=uuid4(),  # não existe
            frequency="monthly",
            start_date=date(2025, 1, 1),
            session_duration=60,
            session_price=Decimal("100.00"),
        )
        db_session.add(rec)

        with pytest.raises(IntegrityError):
            await db_session.flush()


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------


class TestSessionModel:
    async def test_create_session_persists_record(self, db_session: AsyncSession) -> None:
        """INSERT deve persistir a sessão e gerar id."""
        prof = await _make_prof(db_session, "sess_create@example.com")
        client = await _make_client(db_session, prof)
        sess = AgendaSession(
            professional_id=prof.id,
            client_id=client.id,
            scheduled_at=datetime(2025, 6, 1, 10, 0, tzinfo=UTC),
            duration_minutes=60,
            price=Decimal("150.00"),
        )
        db_session.add(sess)
        await db_session.flush()

        assert sess.id is not None

    async def test_session_status_defaults_scheduled(self, db_session: AsyncSession) -> None:
        """status deve ser 'scheduled' por padrão (server_default='scheduled')."""
        prof = await _make_prof(db_session, "sess_status@example.com")
        client = await _make_client(db_session, prof)
        sess = AgendaSession(
            professional_id=prof.id,
            client_id=client.id,
            scheduled_at=datetime(2025, 6, 1, 10, 0, tzinfo=UTC),
            duration_minutes=60,
            price=Decimal("150.00"),
        )
        db_session.add(sess)
        await db_session.flush()
        await db_session.refresh(sess)

        assert sess.status == "scheduled"

    async def test_session_recurrence_id_is_nullable(self, db_session: AsyncSession) -> None:
        """recurrence_id deve aceitar NULL (sessão avulsa)."""
        prof = await _make_prof(db_session, "sess_rec_null@example.com")
        client = await _make_client(db_session, prof)
        sess = AgendaSession(
            professional_id=prof.id,
            client_id=client.id,
            scheduled_at=datetime(2025, 6, 1, 10, 0, tzinfo=UTC),
            duration_minutes=60,
            price=Decimal("150.00"),
        )
        db_session.add(sess)
        await db_session.flush()

        assert sess.recurrence_id is None

    async def test_session_notes_is_nullable(self, db_session: AsyncSession) -> None:
        """notes deve aceitar NULL."""
        prof = await _make_prof(db_session, "sess_notes@example.com")
        client = await _make_client(db_session, prof)
        sess = AgendaSession(
            professional_id=prof.id,
            client_id=client.id,
            scheduled_at=datetime(2025, 6, 1, 10, 0, tzinfo=UTC),
            duration_minutes=60,
            price=Decimal("150.00"),
        )
        db_session.add(sess)
        await db_session.flush()

        assert sess.notes is None

    async def test_session_check_invalid_status_raises(self, db_session: AsyncSession) -> None:
        """CHECK chk_session_status: status inválido deve lançar IntegrityError."""
        prof = await _make_prof(db_session, "sess_badstatus@example.com")
        client = await _make_client(db_session, prof)
        sess = AgendaSession(
            professional_id=prof.id,
            client_id=client.id,
            scheduled_at=datetime(2025, 6, 1, 10, 0, tzinfo=UTC),
            duration_minutes=60,
            price=Decimal("150.00"),
            status="pending",  # viola chk_session_status
        )
        db_session.add(sess)

        with pytest.raises(IntegrityError):
            await db_session.flush()

    async def test_session_check_duration_zero_raises(self, db_session: AsyncSession) -> None:
        """CHECK chk_duration: duration_minutes=0 deve lançar IntegrityError."""
        prof = await _make_prof(db_session, "sess_dur0@example.com")
        client = await _make_client(db_session, prof)
        sess = AgendaSession(
            professional_id=prof.id,
            client_id=client.id,
            scheduled_at=datetime(2025, 6, 1, 10, 0, tzinfo=UTC),
            duration_minutes=0,  # viola chk_duration (> 0)
            price=Decimal("150.00"),
        )
        db_session.add(sess)

        with pytest.raises(IntegrityError):
            await db_session.flush()

    async def test_session_all_valid_statuses_accepted(self, db_session: AsyncSession) -> None:
        """Todos os valores do CHECK devem ser aceitos."""
        prof = await _make_prof(db_session, "sess_statuses@example.com")
        client = await _make_client(db_session, prof)

        for i, status in enumerate(["scheduled", "completed", "cancelled", "no_show"]):
            sess = AgendaSession(
                professional_id=prof.id,
                client_id=client.id,
                scheduled_at=datetime(2025, 6, i + 1, 10, 0, tzinfo=UTC),
                duration_minutes=60,
                price=Decimal("100.00"),
                status=status,
            )
            db_session.add(sess)

        # Should flush without any IntegrityError
        await db_session.flush()


# ---------------------------------------------------------------------------
# RLS isolation (cross-tenant)
# ---------------------------------------------------------------------------


class TestAgendaRLS:
    """
    Valida que o RLS isola corretamente os dados entre tenants em todas as tabelas
    do módulo agenda.

    Padrão:
      1. Criar dados para prof_a e prof_b usando postgres (BYPASSRLS — vê tudo).
      2. SET LOCAL ROLE test_rls_user (sem BYPASSRLS — RLS é aplicado).
      3. SET LOCAL app.current_tenant = prof_a.id.
      4. SELECT — apenas os dados de prof_a devem ser visíveis.
    """

    async def test_rls_isolates_availability_slots_between_tenants(
        self, db_session: AsyncSession
    ) -> None:
        """Prof A não deve ver slots de Prof B."""
        prof_a = await _make_prof(db_session, "slot_rls_a@example.com")
        prof_b = await _make_prof(db_session, "slot_rls_b@example.com")

        slot_a = AvailabilitySlot(
            professional_id=prof_a.id,
            day_of_week=1,
            start_time=time(9, 0),
            end_time=time(12, 0),
        )
        slot_b = AvailabilitySlot(
            professional_id=prof_b.id,
            day_of_week=2,
            start_time=time(9, 0),
            end_time=time(12, 0),
        )
        db_session.add_all([slot_a, slot_b])
        await db_session.flush()

        await db_session.execute(text("SET LOCAL ROLE test_rls_user"))
        await db_session.execute(text(f"SET LOCAL app.current_tenant = '{prof_a.id}'"))

        result = await db_session.execute(select(AvailabilitySlot))
        visible_ids = {s.id for s in result.scalars().all()}

        assert slot_a.id in visible_ids, "Slot de A deve ser visível para A"
        assert slot_b.id not in visible_ids, "Slot de B NÃO deve ser visível para A"

    async def test_rls_isolates_blocked_periods_between_tenants(
        self, db_session: AsyncSession
    ) -> None:
        """Prof A não deve ver períodos bloqueados de Prof B."""
        prof_a = await _make_prof(db_session, "blocked_rls_a@example.com")
        prof_b = await _make_prof(db_session, "blocked_rls_b@example.com")

        period_a = BlockedPeriod(
            professional_id=prof_a.id,
            start_datetime=datetime(2025, 8, 1, 8, 0, tzinfo=UTC),
            end_datetime=datetime(2025, 8, 1, 18, 0, tzinfo=UTC),
        )
        period_b = BlockedPeriod(
            professional_id=prof_b.id,
            start_datetime=datetime(2025, 8, 2, 8, 0, tzinfo=UTC),
            end_datetime=datetime(2025, 8, 2, 18, 0, tzinfo=UTC),
        )
        db_session.add_all([period_a, period_b])
        await db_session.flush()

        await db_session.execute(text("SET LOCAL ROLE test_rls_user"))
        await db_session.execute(text(f"SET LOCAL app.current_tenant = '{prof_a.id}'"))

        result = await db_session.execute(select(BlockedPeriod))
        visible_ids = {p.id for p in result.scalars().all()}

        assert period_a.id in visible_ids
        assert period_b.id not in visible_ids

    async def test_rls_isolates_sessions_between_tenants(self, db_session: AsyncSession) -> None:
        """Prof A não deve ver sessões de Prof B."""
        prof_a = await _make_prof(db_session, "sess_rls_a@example.com")
        prof_b = await _make_prof(db_session, "sess_rls_b@example.com")
        client_a = await _make_client(db_session, prof_a)
        client_b = await _make_client(db_session, prof_b)

        sess_a = AgendaSession(
            professional_id=prof_a.id,
            client_id=client_a.id,
            scheduled_at=datetime(2025, 6, 1, 10, 0, tzinfo=UTC),
            duration_minutes=60,
            price=Decimal("100.00"),
        )
        sess_b = AgendaSession(
            professional_id=prof_b.id,
            client_id=client_b.id,
            scheduled_at=datetime(2025, 6, 1, 14, 0, tzinfo=UTC),
            duration_minutes=60,
            price=Decimal("100.00"),
        )
        db_session.add_all([sess_a, sess_b])
        await db_session.flush()

        await db_session.execute(text("SET LOCAL ROLE test_rls_user"))
        await db_session.execute(text(f"SET LOCAL app.current_tenant = '{prof_a.id}'"))

        result = await db_session.execute(select(AgendaSession))
        visible_ids = {s.id for s in result.scalars().all()}

        assert sess_a.id in visible_ids, "Sessão de A deve ser visível para A"
        assert sess_b.id not in visible_ids, "Sessão de B NÃO deve ser visível para A"

    async def test_rls_isolates_recurrences_between_tenants(self, db_session: AsyncSession) -> None:
        """Prof A não deve ver recorrências de Prof B."""
        prof_a = await _make_prof(db_session, "rec_rls_a@example.com")
        prof_b = await _make_prof(db_session, "rec_rls_b@example.com")
        client_a = await _make_client(db_session, prof_a)
        client_b = await _make_client(db_session, prof_b)

        rec_a = Recurrence(
            professional_id=prof_a.id,
            client_id=client_a.id,
            frequency="weekly",
            day_of_week=1,
            start_date=date(2025, 1, 1),
            session_duration=60,
            session_price=Decimal("150.00"),
        )
        rec_b = Recurrence(
            professional_id=prof_b.id,
            client_id=client_b.id,
            frequency="monthly",
            start_date=date(2025, 1, 1),
            session_duration=45,
            session_price=Decimal("120.00"),
        )
        db_session.add_all([rec_a, rec_b])
        await db_session.flush()

        await db_session.execute(text("SET LOCAL ROLE test_rls_user"))
        await db_session.execute(text(f"SET LOCAL app.current_tenant = '{prof_a.id}'"))

        result = await db_session.execute(select(Recurrence))
        visible_ids = {r.id for r in result.scalars().all()}

        assert rec_a.id in visible_ids
        assert rec_b.id not in visible_ids
