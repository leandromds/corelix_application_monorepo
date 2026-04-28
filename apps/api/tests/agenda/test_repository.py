"""
Tests for agenda repositories — TDD Red phase.

Coverage:
- AvailabilitySlotsRepository : create, find_by_id, find_all, find_by_day,
                                find_by_day_and_time, update, soft_delete
- BlockedPeriodsRepository    : create, find_by_id, find_all, find_overlapping,
                                delete
- RecurrencesRepository       : create, find_by_id, find_all, find_active_by_client,
                                update, deactivate
- SessionsRepository          : create, find_by_id, find_all, find_by_client,
                                find_scheduled_between, find_upcoming,
                                find_conflicting, update,
                                cancel_future_by_recurrence

RLS isolation pattern (same as tests/clients/test_repository.py):
  1. Create "other tenant" data WITHOUT setting tenant context.
     (null-permissive policy allows INSERT from postgres/BYPASSRLS)
  2. SET LOCAL ROLE test_rls_user  — activates RLS enforcement.
  3. SET LOCAL app.current_tenant = test_professional.id
  4. Query — RLS filters out the other tenant's rows → returns None / [].
"""

from datetime import UTC, date, datetime, time
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from agenda.models import AvailabilitySlot, BlockedPeriod, Recurrence
from agenda.models import Session as AgendaSession
from agenda.repository import (
    AvailabilitySlotsRepository,
    BlockedPeriodsRepository,
    RecurrencesRepository,
    SessionsRepository,
)
from agenda.schemas import (
    AvailabilitySlotCreate,
    BlockedPeriodCreate,
    RecurrenceCreate,
    SessionCreate,
)
from clients.models import Client
from professionals.models import Professional

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _slot_create(
    *,
    day_of_week: int = 1,
    start_time: time = time(9, 0),
    end_time: time = time(10, 0),
) -> AvailabilitySlotCreate:
    return AvailabilitySlotCreate(
        day_of_week=day_of_week,
        start_time=start_time,
        end_time=end_time,
    )


def _blocked_create(
    *,
    start: datetime = datetime(2030, 3, 1, 8, 0, tzinfo=UTC),
    end: datetime = datetime(2030, 3, 1, 18, 0, tzinfo=UTC),
    reason: str | None = "Test block",
) -> BlockedPeriodCreate:
    return BlockedPeriodCreate(
        start_datetime=start,
        end_datetime=end,
        reason=reason,
    )


def _recurrence_create(client_id, *, frequency: str = "weekly") -> RecurrenceCreate:
    kwargs: dict = {
        "client_id": client_id,
        "frequency": frequency,
        "start_date": date(2025, 1, 1),
        "session_duration": 60,
        "session_price": Decimal("150.00"),
    }
    if frequency in ("weekly", "biweekly"):
        kwargs["day_of_week"] = 1
    return RecurrenceCreate(**kwargs)


def _session_create(
    client_id,
    *,
    scheduled_at: datetime = datetime(2030, 6, 1, 10, 0, tzinfo=UTC),
    duration_minutes: int = 60,
    recurrence_id=None,
) -> SessionCreate:
    return SessionCreate(
        client_id=client_id,
        recurrence_id=recurrence_id,
        scheduled_at=scheduled_at,
        duration_minutes=duration_minutes,
        price=Decimal("150.00"),
    )


async def _make_prof(session: AsyncSession, email: str) -> Professional:
    p = Professional(email=email, password_hash="h", full_name="Repo Test Prof")
    session.add(p)
    await session.flush()
    return p


async def _make_client(session: AsyncSession, prof: Professional) -> Client:
    c = Client(
        professional_id=prof.id,
        full_name="Repo Test Client",
        phone=f"119{uuid4().int % 100_000_000:08d}",
    )
    session.add(c)
    await session.flush()
    return c


# ===========================================================================
# AvailabilitySlotsRepository
# ===========================================================================


class TestAvailabilitySlotsRepositoryCreate:
    async def test_create_returns_slot_with_id(
        self,
        tenant_session: AsyncSession,
        test_professional,
    ) -> None:
        """create() deve retornar AvailabilitySlot com id gerado pelo banco."""
        repo = AvailabilitySlotsRepository(tenant_session)

        slot = await repo.create(
            test_professional.id,
            _slot_create(day_of_week=1, start_time=time(9, 0), end_time=time(10, 0)),
        )

        assert slot.id is not None
        assert slot.day_of_week == 1
        assert slot.start_time == time(9, 0)
        assert slot.end_time == time(10, 0)

    async def test_create_defaults_is_active_true(
        self,
        tenant_session: AsyncSession,
        test_professional,
    ) -> None:
        """create() deve definir is_active=True por padrão."""
        repo = AvailabilitySlotsRepository(tenant_session)

        slot = await repo.create(
            test_professional.id,
            _slot_create(day_of_week=2, start_time=time(14, 0), end_time=time(16, 0)),
        )

        assert slot.is_active is True

    async def test_create_persists_professional_id(
        self,
        tenant_session: AsyncSession,
        test_professional,
    ) -> None:
        """create() deve vincular o slot ao professional_id informado."""
        repo = AvailabilitySlotsRepository(tenant_session)

        slot = await repo.create(
            test_professional.id,
            _slot_create(day_of_week=3),
        )

        assert slot.professional_id == test_professional.id


class TestAvailabilitySlotsRepositoryFindById:
    async def test_find_by_id_returns_slot(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_availability_slot: AvailabilitySlot,
    ) -> None:
        """find_by_id() deve retornar o slot quando existir."""
        repo = AvailabilitySlotsRepository(tenant_session)

        found = await repo.find_by_id(test_availability_slot.id)

        assert found is not None
        assert found.id == test_availability_slot.id

    async def test_find_by_id_returns_none_when_not_found(
        self,
        tenant_session: AsyncSession,
    ) -> None:
        """find_by_id() deve retornar None para UUID inexistente."""
        repo = AvailabilitySlotsRepository(tenant_session)

        found = await repo.find_by_id(uuid4())

        assert found is None

    async def test_find_by_id_returns_none_for_other_tenant(
        self,
        db_session: AsyncSession,
        test_professional,
    ) -> None:
        """find_by_id() deve retornar None para slot de outro tenant (RLS)."""
        # Criar slot para outro profissional SEM contexto de tenant
        other_prof = await _make_prof(db_session, "slot_other_tenant@example.com")
        other_slot = AvailabilitySlot(
            professional_id=other_prof.id,
            day_of_week=5,
            start_time=time(10, 0),
            end_time=time(11, 0),
        )
        db_session.add(other_slot)
        await db_session.flush()

        # Ativar RLS para test_professional
        await db_session.execute(text("SET LOCAL ROLE test_rls_user"))
        await db_session.execute(text(f"SET LOCAL app.current_tenant = '{test_professional.id}'"))

        repo = AvailabilitySlotsRepository(db_session)
        found = await repo.find_by_id(other_slot.id)

        assert found is None


class TestAvailabilitySlotsRepositoryFindAll:
    async def test_find_all_returns_active_slots(
        self,
        tenant_session: AsyncSession,
        test_professional,
    ) -> None:
        """find_all() deve retornar slots ativos do tenant."""
        repo = AvailabilitySlotsRepository(tenant_session)
        await repo.create(test_professional.id, _slot_create(day_of_week=1))
        await repo.create(
            test_professional.id,
            _slot_create(day_of_week=2, start_time=time(9, 0), end_time=time(10, 0)),
        )

        slots = await repo.find_all(active_only=True)

        assert len(slots) >= 2

    async def test_find_all_excludes_inactive_when_active_only_true(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_availability_slot: AvailabilitySlot,
    ) -> None:
        """find_all(active_only=True) não deve retornar slots com is_active=False."""
        repo = AvailabilitySlotsRepository(tenant_session)
        await repo.soft_delete(test_availability_slot)

        slots = await repo.find_all(active_only=True)
        ids = [s.id for s in slots]

        assert test_availability_slot.id not in ids

    async def test_find_all_includes_inactive_when_active_only_false(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_availability_slot: AvailabilitySlot,
    ) -> None:
        """find_all(active_only=False) deve incluir slots inativas."""
        repo = AvailabilitySlotsRepository(tenant_session)
        await repo.soft_delete(test_availability_slot)

        slots = await repo.find_all(active_only=False)
        ids = [s.id for s in slots]

        assert test_availability_slot.id in ids

    async def test_find_all_ordered_by_day_then_start_time(
        self,
        tenant_session: AsyncSession,
        test_professional,
    ) -> None:
        """find_all() deve ordenar por day_of_week, depois start_time."""
        repo = AvailabilitySlotsRepository(tenant_session)
        await repo.create(
            test_professional.id,
            _slot_create(day_of_week=3, start_time=time(14, 0), end_time=time(15, 0)),
        )
        await repo.create(
            test_professional.id,
            _slot_create(day_of_week=1, start_time=time(9, 0), end_time=time(10, 0)),
        )

        slots = await repo.find_all()

        # day_of_week=1 deve vir antes de day_of_week=3
        days = [s.day_of_week for s in slots]
        assert days == sorted(days)


class TestAvailabilitySlotsRepositoryFindByDay:
    async def test_find_by_day_returns_slots_for_day(
        self,
        tenant_session: AsyncSession,
        test_professional,
    ) -> None:
        """find_by_day() deve retornar slots ativos para o dia especificado."""
        repo = AvailabilitySlotsRepository(tenant_session)
        await repo.create(
            test_professional.id,
            _slot_create(day_of_week=1, start_time=time(9, 0), end_time=time(10, 0)),
        )
        await repo.create(
            test_professional.id,
            _slot_create(day_of_week=1, start_time=time(14, 0), end_time=time(16, 0)),
        )
        await repo.create(
            test_professional.id,
            _slot_create(day_of_week=2, start_time=time(9, 0), end_time=time(10, 0)),
        )

        slots = await repo.find_by_day(1)

        assert all(s.day_of_week == 1 for s in slots)
        assert len(slots) >= 2

    async def test_find_by_day_returns_empty_for_unknown_day(
        self,
        tenant_session: AsyncSession,
    ) -> None:
        """find_by_day() deve retornar lista vazia para dia sem slots."""
        repo = AvailabilitySlotsRepository(tenant_session)

        slots = await repo.find_by_day(6)

        assert slots == []


class TestAvailabilitySlotsRepositoryFindByDayAndTime:
    async def test_find_by_day_and_time_returns_slot(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_availability_slot: AvailabilitySlot,
    ) -> None:
        """find_by_day_and_time() deve retornar o slot correspondente."""
        repo = AvailabilitySlotsRepository(tenant_session)

        found = await repo.find_by_day_and_time(
            test_availability_slot.day_of_week,
            test_availability_slot.start_time,
        )

        assert found is not None
        assert found.id == test_availability_slot.id

    async def test_find_by_day_and_time_returns_none_when_not_found(
        self,
        tenant_session: AsyncSession,
    ) -> None:
        """find_by_day_and_time() deve retornar None quando não existe."""
        repo = AvailabilitySlotsRepository(tenant_session)

        found = await repo.find_by_day_and_time(6, time(23, 0))

        assert found is None

    async def test_find_by_day_and_time_returns_none_for_inactive_slot(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_availability_slot: AvailabilitySlot,
    ) -> None:
        """Slot com is_active=False não deve ser retornado (considera como disponível)."""
        repo = AvailabilitySlotsRepository(tenant_session)
        await repo.soft_delete(test_availability_slot)

        found = await repo.find_by_day_and_time(
            test_availability_slot.day_of_week,
            test_availability_slot.start_time,
        )

        assert found is None


class TestAvailabilitySlotsRepositoryUpdate:
    async def test_update_changes_end_time(
        self,
        tenant_session: AsyncSession,
        test_availability_slot: AvailabilitySlot,
    ) -> None:
        """update() deve atualizar os campos fornecidos."""
        repo = AvailabilitySlotsRepository(tenant_session)

        updated = await repo.update(test_availability_slot, {"end_time": time(18, 0)})

        assert updated.end_time == time(18, 0)

    async def test_update_does_not_change_unset_fields(
        self,
        tenant_session: AsyncSession,
        test_availability_slot: AvailabilitySlot,
    ) -> None:
        """update() não deve alterar campos não incluídos no dict."""
        repo = AvailabilitySlotsRepository(tenant_session)
        original_day = test_availability_slot.day_of_week

        await repo.update(test_availability_slot, {"is_active": False})

        assert test_availability_slot.day_of_week == original_day


class TestAvailabilitySlotsRepositorySoftDelete:
    async def test_soft_delete_sets_is_active_false(
        self,
        tenant_session: AsyncSession,
        test_availability_slot: AvailabilitySlot,
    ) -> None:
        """soft_delete() deve definir is_active=False."""
        repo = AvailabilitySlotsRepository(tenant_session)

        await repo.soft_delete(test_availability_slot)

        assert test_availability_slot.is_active is False

    async def test_soft_delete_excludes_from_active_list(
        self,
        tenant_session: AsyncSession,
        test_availability_slot: AvailabilitySlot,
    ) -> None:
        """Após soft_delete, slot não deve aparecer em find_all(active_only=True)."""
        repo = AvailabilitySlotsRepository(tenant_session)
        await repo.soft_delete(test_availability_slot)

        active = await repo.find_all(active_only=True)
        ids = [s.id for s in active]

        assert test_availability_slot.id not in ids

    async def test_soft_delete_preserves_record_in_db(
        self,
        tenant_session: AsyncSession,
        test_availability_slot: AvailabilitySlot,
    ) -> None:
        """Após soft_delete, o registro ainda deve existir (não hard delete)."""
        repo = AvailabilitySlotsRepository(tenant_session)
        await repo.soft_delete(test_availability_slot)

        all_slots = await repo.find_all(active_only=False)
        ids = [s.id for s in all_slots]

        assert test_availability_slot.id in ids


# ===========================================================================
# BlockedPeriodsRepository
# ===========================================================================


class TestBlockedPeriodsRepositoryCreate:
    async def test_create_returns_period_with_id(
        self,
        tenant_session: AsyncSession,
        test_professional,
    ) -> None:
        """create() deve retornar BlockedPeriod com id gerado pelo banco."""
        repo = BlockedPeriodsRepository(tenant_session)

        period = await repo.create(test_professional.id, _blocked_create())

        assert period.id is not None
        assert period.reason == "Test block"

    async def test_create_defaults_notify_clients_true(
        self,
        tenant_session: AsyncSession,
        test_professional,
    ) -> None:
        """create() deve manter o default notify_clients=True."""
        repo = BlockedPeriodsRepository(tenant_session)

        period = await repo.create(
            test_professional.id,
            BlockedPeriodCreate(
                start_datetime=datetime(2030, 4, 1, 8, 0, tzinfo=UTC),
                end_datetime=datetime(2030, 4, 1, 18, 0, tzinfo=UTC),
            ),
        )

        assert period.notify_clients is True


class TestBlockedPeriodsRepositoryFindById:
    async def test_find_by_id_returns_period(
        self,
        tenant_session: AsyncSession,
        test_blocked_period: BlockedPeriod,
    ) -> None:
        """find_by_id() deve retornar o período quando existir."""
        repo = BlockedPeriodsRepository(tenant_session)

        found = await repo.find_by_id(test_blocked_period.id)

        assert found is not None
        assert found.id == test_blocked_period.id

    async def test_find_by_id_returns_none_when_not_found(
        self,
        tenant_session: AsyncSession,
    ) -> None:
        """find_by_id() deve retornar None para UUID inexistente."""
        repo = BlockedPeriodsRepository(tenant_session)

        found = await repo.find_by_id(uuid4())

        assert found is None

    async def test_find_by_id_returns_none_for_other_tenant(
        self,
        db_session: AsyncSession,
        test_professional,
    ) -> None:
        """find_by_id() deve retornar None para período de outro tenant (RLS)."""
        other_prof = await _make_prof(db_session, "blocked_other_tenant@example.com")
        other_period = BlockedPeriod(
            professional_id=other_prof.id,
            start_datetime=datetime(2030, 5, 1, 8, 0, tzinfo=UTC),
            end_datetime=datetime(2030, 5, 1, 18, 0, tzinfo=UTC),
        )
        db_session.add(other_period)
        await db_session.flush()

        await db_session.execute(text("SET LOCAL ROLE test_rls_user"))
        await db_session.execute(text(f"SET LOCAL app.current_tenant = '{test_professional.id}'"))

        repo = BlockedPeriodsRepository(db_session)
        found = await repo.find_by_id(other_period.id)

        assert found is None


class TestBlockedPeriodsRepositoryFindAll:
    async def test_find_all_returns_periods(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_blocked_period: BlockedPeriod,
    ) -> None:
        """find_all() deve retornar todos os períodos do tenant."""
        repo = BlockedPeriodsRepository(tenant_session)

        periods = await repo.find_all()

        ids = [p.id for p in periods]
        assert test_blocked_period.id in ids

    async def test_find_all_ordered_by_start_datetime(
        self,
        tenant_session: AsyncSession,
        test_professional,
    ) -> None:
        """find_all() deve ordenar por start_datetime crescente."""
        repo = BlockedPeriodsRepository(tenant_session)
        await repo.create(
            test_professional.id,
            _blocked_create(
                start=datetime(2030, 8, 1, 8, 0, tzinfo=UTC),
                end=datetime(2030, 8, 1, 18, 0, tzinfo=UTC),
            ),
        )
        await repo.create(
            test_professional.id,
            _blocked_create(
                start=datetime(2030, 7, 1, 8, 0, tzinfo=UTC),
                end=datetime(2030, 7, 1, 18, 0, tzinfo=UTC),
            ),
        )

        periods = await repo.find_all()

        starts = [p.start_datetime for p in periods]
        assert starts == sorted(starts)


class TestBlockedPeriodsRepositoryFindOverlapping:
    async def test_find_overlapping_returns_overlapping_periods(
        self,
        tenant_session: AsyncSession,
        test_professional,
    ) -> None:
        """find_overlapping() deve retornar períodos que se sobrepõem."""
        repo = BlockedPeriodsRepository(tenant_session)

        # Bloqueia 10h-12h
        block = await repo.create(
            test_professional.id,
            _blocked_create(
                start=datetime(2030, 6, 15, 10, 0, tzinfo=UTC),
                end=datetime(2030, 6, 15, 12, 0, tzinfo=UTC),
            ),
        )

        # Consulta o intervalo 11h-13h — sobrepõe com 10h-12h
        overlapping = await repo.find_overlapping(
            datetime(2030, 6, 15, 11, 0, tzinfo=UTC),
            datetime(2030, 6, 15, 13, 0, tzinfo=UTC),
        )

        ids = [p.id for p in overlapping]
        assert block.id in ids

    async def test_find_overlapping_returns_empty_when_no_overlap(
        self,
        tenant_session: AsyncSession,
        test_professional,
    ) -> None:
        """find_overlapping() deve retornar [] quando não há sobreposição."""
        repo = BlockedPeriodsRepository(tenant_session)

        # Bloqueia 10h-11h
        await repo.create(
            test_professional.id,
            _blocked_create(
                start=datetime(2030, 6, 20, 10, 0, tzinfo=UTC),
                end=datetime(2030, 6, 20, 11, 0, tzinfo=UTC),
            ),
        )

        # Consulta 11h-12h — adjacente mas NÃO sobrepõe (start < end AND end > start)
        overlapping = await repo.find_overlapping(
            datetime(2030, 6, 20, 11, 0, tzinfo=UTC),
            datetime(2030, 6, 20, 12, 0, tzinfo=UTC),
        )

        assert overlapping == []

    async def test_find_overlapping_period_fully_inside_query_window(
        self,
        tenant_session: AsyncSession,
        test_professional,
    ) -> None:
        """Período completamente dentro da janela de consulta deve ser encontrado."""
        repo = BlockedPeriodsRepository(tenant_session)

        block = await repo.create(
            test_professional.id,
            _blocked_create(
                start=datetime(2030, 6, 25, 11, 0, tzinfo=UTC),
                end=datetime(2030, 6, 25, 12, 0, tzinfo=UTC),
            ),
        )

        # Janela 10h-13h contém completamente o bloco 11h-12h
        overlapping = await repo.find_overlapping(
            datetime(2030, 6, 25, 10, 0, tzinfo=UTC),
            datetime(2030, 6, 25, 13, 0, tzinfo=UTC),
        )

        ids = [p.id for p in overlapping]
        assert block.id in ids


class TestBlockedPeriodsRepositoryDelete:
    async def test_delete_removes_period(
        self,
        tenant_session: AsyncSession,
        test_blocked_period: BlockedPeriod,
    ) -> None:
        """delete() deve remover fisicamente o registro."""
        repo = BlockedPeriodsRepository(tenant_session)
        period_id = test_blocked_period.id

        await repo.delete(test_blocked_period)

        found = await repo.find_by_id(period_id)
        assert found is None

    async def test_delete_reduces_find_all_count(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_blocked_period: BlockedPeriod,
    ) -> None:
        """find_all() não deve retornar o período após delete()."""
        repo = BlockedPeriodsRepository(tenant_session)
        before = await repo.find_all()
        before_count = len(before)

        await repo.delete(test_blocked_period)

        after = await repo.find_all()
        assert len(after) == before_count - 1


# ===========================================================================
# RecurrencesRepository
# ===========================================================================


class TestRecurrencesRepositoryCreate:
    async def test_create_returns_recurrence_with_id(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_client: Client,
    ) -> None:
        """create() deve retornar Recurrence com id gerado pelo banco."""
        repo = RecurrencesRepository(tenant_session)

        rec = await repo.create(
            test_professional.id,
            _recurrence_create(test_client.id, frequency="weekly"),
        )

        assert rec.id is not None
        assert rec.frequency == "weekly"
        assert rec.session_duration == 60

    async def test_create_defaults_is_active_true(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_client: Client,
    ) -> None:
        """create() deve definir is_active=True por padrão."""
        repo = RecurrencesRepository(tenant_session)

        rec = await repo.create(
            test_professional.id,
            _recurrence_create(test_client.id, frequency="monthly"),
        )

        assert rec.is_active is True

    async def test_create_defaults_interval_one(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_client: Client,
    ) -> None:
        """create() deve manter interval=1 por padrão."""
        repo = RecurrencesRepository(tenant_session)

        rec = await repo.create(
            test_professional.id,
            _recurrence_create(test_client.id, frequency="monthly"),
        )

        assert rec.interval == 1


class TestRecurrencesRepositoryFindById:
    async def test_find_by_id_returns_recurrence(
        self,
        tenant_session: AsyncSession,
        test_recurrence: Recurrence,
    ) -> None:
        """find_by_id() deve retornar a recorrência quando existir."""
        repo = RecurrencesRepository(tenant_session)

        found = await repo.find_by_id(test_recurrence.id)

        assert found is not None
        assert found.id == test_recurrence.id

    async def test_find_by_id_returns_none_when_not_found(
        self,
        tenant_session: AsyncSession,
    ) -> None:
        """find_by_id() deve retornar None para UUID inexistente."""
        repo = RecurrencesRepository(tenant_session)

        found = await repo.find_by_id(uuid4())

        assert found is None

    async def test_find_by_id_returns_none_for_other_tenant(
        self,
        db_session: AsyncSession,
        test_professional,
    ) -> None:
        """find_by_id() deve retornar None para recorrência de outro tenant (RLS)."""
        other_prof = await _make_prof(db_session, "rec_other_tenant@example.com")
        other_client = await _make_client(db_session, other_prof)
        other_rec = Recurrence(
            professional_id=other_prof.id,
            client_id=other_client.id,
            frequency="monthly",
            start_date=date(2025, 1, 1),
            session_duration=60,
            session_price=Decimal("100.00"),
        )
        db_session.add(other_rec)
        await db_session.flush()

        await db_session.execute(text("SET LOCAL ROLE test_rls_user"))
        await db_session.execute(text(f"SET LOCAL app.current_tenant = '{test_professional.id}'"))

        repo = RecurrencesRepository(db_session)
        found = await repo.find_by_id(other_rec.id)

        assert found is None


class TestRecurrencesRepositoryFindAll:
    async def test_find_all_returns_active_recurrences(
        self,
        tenant_session: AsyncSession,
        test_recurrence: Recurrence,
    ) -> None:
        """find_all(active_only=True) deve retornar recorrências ativas."""
        repo = RecurrencesRepository(tenant_session)

        recs = await repo.find_all(active_only=True)
        ids = [r.id for r in recs]

        assert test_recurrence.id in ids

    async def test_find_all_excludes_inactive_by_default(
        self,
        tenant_session: AsyncSession,
        test_recurrence: Recurrence,
    ) -> None:
        """find_all() deve excluir recorrências inativas por padrão."""
        repo = RecurrencesRepository(tenant_session)
        await repo.deactivate(test_recurrence)

        recs = await repo.find_all(active_only=True)
        ids = [r.id for r in recs]

        assert test_recurrence.id not in ids

    async def test_find_all_includes_inactive_when_active_only_false(
        self,
        tenant_session: AsyncSession,
        test_recurrence: Recurrence,
    ) -> None:
        """find_all(active_only=False) deve incluir recorrências inativas."""
        repo = RecurrencesRepository(tenant_session)
        await repo.deactivate(test_recurrence)

        recs = await repo.find_all(active_only=False)
        ids = [r.id for r in recs]

        assert test_recurrence.id in ids


class TestRecurrencesRepositoryFindActiveByClient:
    async def test_find_active_by_client_returns_recurrences(
        self,
        tenant_session: AsyncSession,
        test_recurrence: Recurrence,
        test_client: Client,
    ) -> None:
        """find_active_by_client() deve retornar recorrências ativas do cliente."""
        repo = RecurrencesRepository(tenant_session)

        recs = await repo.find_active_by_client(test_client.id)
        ids = [r.id for r in recs]

        assert test_recurrence.id in ids

    async def test_find_active_by_client_excludes_inactive(
        self,
        tenant_session: AsyncSession,
        test_recurrence: Recurrence,
        test_client: Client,
    ) -> None:
        """find_active_by_client() não deve retornar recorrências inativas."""
        repo = RecurrencesRepository(tenant_session)
        await repo.deactivate(test_recurrence)

        recs = await repo.find_active_by_client(test_client.id)
        ids = [r.id for r in recs]

        assert test_recurrence.id not in ids

    async def test_find_active_by_client_returns_empty_for_unknown_client(
        self,
        tenant_session: AsyncSession,
    ) -> None:
        """find_active_by_client() deve retornar [] para client_id inexistente."""
        repo = RecurrencesRepository(tenant_session)

        recs = await repo.find_active_by_client(uuid4())

        assert recs == []


class TestRecurrencesRepositoryUpdate:
    async def test_update_changes_session_duration(
        self,
        tenant_session: AsyncSession,
        test_recurrence: Recurrence,
    ) -> None:
        """update() deve atualizar session_duration."""
        repo = RecurrencesRepository(tenant_session)

        updated = await repo.update(test_recurrence, {"session_duration": 90})

        assert updated.session_duration == 90

    async def test_update_does_not_change_unset_fields(
        self,
        tenant_session: AsyncSession,
        test_recurrence: Recurrence,
    ) -> None:
        """update() não deve alterar campos não incluídos no dict."""
        repo = RecurrencesRepository(tenant_session)
        original_frequency = test_recurrence.frequency

        await repo.update(test_recurrence, {"session_duration": 45})

        assert test_recurrence.frequency == original_frequency


class TestRecurrencesRepositoryDeactivate:
    async def test_deactivate_sets_is_active_false(
        self,
        tenant_session: AsyncSession,
        test_recurrence: Recurrence,
    ) -> None:
        """deactivate() deve definir is_active=False."""
        repo = RecurrencesRepository(tenant_session)

        await repo.deactivate(test_recurrence)

        assert test_recurrence.is_active is False

    async def test_deactivate_preserves_record_in_db(
        self,
        tenant_session: AsyncSession,
        test_recurrence: Recurrence,
    ) -> None:
        """deactivate() não deve excluir o registro (soft delete)."""
        repo = RecurrencesRepository(tenant_session)

        await repo.deactivate(test_recurrence)

        found = await repo.find_by_id(test_recurrence.id)
        assert found is not None
        assert found.is_active is False


# ===========================================================================
# SessionsRepository
# ===========================================================================


class TestSessionsRepositoryCreate:
    async def test_create_returns_session_with_id(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_client: Client,
    ) -> None:
        """create() deve retornar Session com id gerado pelo banco."""
        repo = SessionsRepository(tenant_session)

        sess = await repo.create(
            test_professional.id,
            _session_create(test_client.id),
        )

        assert sess.id is not None
        assert sess.client_id == test_client.id

    async def test_create_status_defaults_scheduled(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_client: Client,
    ) -> None:
        """create() deve definir status='scheduled' por padrão."""
        repo = SessionsRepository(tenant_session)

        sess = await repo.create(
            test_professional.id,
            _session_create(test_client.id),
        )

        assert sess.status == "scheduled"

    async def test_create_sets_professional_id(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_client: Client,
    ) -> None:
        """create() deve vincular a sessão ao professional_id informado."""
        repo = SessionsRepository(tenant_session)

        sess = await repo.create(
            test_professional.id,
            _session_create(test_client.id),
        )

        assert sess.professional_id == test_professional.id

    async def test_create_with_recurrence_id(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_client: Client,
        test_recurrence: Recurrence,
    ) -> None:
        """create() deve vincular a sessão à recorrência quando fornecida."""
        repo = SessionsRepository(tenant_session)

        sess = await repo.create(
            test_professional.id,
            _session_create(test_client.id, recurrence_id=test_recurrence.id),
        )

        assert sess.recurrence_id == test_recurrence.id

    async def test_create_without_recurrence_id_is_null(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_client: Client,
    ) -> None:
        """create() sem recurrence_id deve manter recurrence_id=None."""
        repo = SessionsRepository(tenant_session)

        sess = await repo.create(
            test_professional.id,
            _session_create(test_client.id, recurrence_id=None),
        )

        assert sess.recurrence_id is None


class TestSessionsRepositoryFindById:
    async def test_find_by_id_returns_session(
        self,
        tenant_session: AsyncSession,
        test_agenda_session: AgendaSession,
    ) -> None:
        """find_by_id() deve retornar a sessão quando existir."""
        repo = SessionsRepository(tenant_session)

        found = await repo.find_by_id(test_agenda_session.id)

        assert found is not None
        assert found.id == test_agenda_session.id

    async def test_find_by_id_returns_none_when_not_found(
        self,
        tenant_session: AsyncSession,
    ) -> None:
        """find_by_id() deve retornar None para UUID inexistente."""
        repo = SessionsRepository(tenant_session)

        found = await repo.find_by_id(uuid4())

        assert found is None

    async def test_find_by_id_returns_none_for_other_tenant(
        self,
        db_session: AsyncSession,
        test_professional,
    ) -> None:
        """find_by_id() deve retornar None para sessão de outro tenant (RLS)."""
        other_prof = await _make_prof(db_session, "sess_other_tenant@example.com")
        other_client = await _make_client(db_session, other_prof)
        other_sess = AgendaSession(
            professional_id=other_prof.id,
            client_id=other_client.id,
            scheduled_at=datetime(2030, 7, 1, 10, 0, tzinfo=UTC),
            duration_minutes=60,
            price=Decimal("100.00"),
        )
        db_session.add(other_sess)
        await db_session.flush()

        await db_session.execute(text("SET LOCAL ROLE test_rls_user"))
        await db_session.execute(text(f"SET LOCAL app.current_tenant = '{test_professional.id}'"))

        repo = SessionsRepository(db_session)
        found = await repo.find_by_id(other_sess.id)

        assert found is None


class TestSessionsRepositoryFindAll:
    async def test_find_all_returns_sessions(
        self,
        tenant_session: AsyncSession,
        test_agenda_session: AgendaSession,
    ) -> None:
        """find_all() deve retornar sessões do tenant."""
        repo = SessionsRepository(tenant_session)

        sessions = await repo.find_all()
        ids = [s.id for s in sessions]

        assert test_agenda_session.id in ids

    async def test_find_all_respects_limit(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_client: Client,
    ) -> None:
        """find_all(limit=1) deve retornar no máximo 1 registro."""
        repo = SessionsRepository(tenant_session)
        for i in range(3):
            await repo.create(
                test_professional.id,
                _session_create(
                    test_client.id,
                    scheduled_at=datetime(2030, 9, i + 1, 10, 0, tzinfo=UTC),
                ),
            )

        sessions = await repo.find_all(limit=1)

        assert len(sessions) == 1

    async def test_find_all_respects_skip(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_client: Client,
    ) -> None:
        """find_all(skip=N) deve pular os primeiros N registros."""
        repo = SessionsRepository(tenant_session)
        for i in range(3):
            await repo.create(
                test_professional.id,
                _session_create(
                    test_client.id,
                    scheduled_at=datetime(2030, 10, i + 1, 10, 0, tzinfo=UTC),
                ),
            )

        all_sessions = await repo.find_all()
        skipped = await repo.find_all(skip=1)

        assert len(skipped) == len(all_sessions) - 1

    async def test_find_all_ordered_by_scheduled_at_asc(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_client: Client,
    ) -> None:
        """find_all() deve ordenar por scheduled_at crescente."""
        repo = SessionsRepository(tenant_session)
        for hour in [15, 9, 12]:
            await repo.create(
                test_professional.id,
                _session_create(
                    test_client.id,
                    scheduled_at=datetime(2030, 11, 1, hour, 0, tzinfo=UTC),
                ),
            )

        sessions = await repo.find_all()
        times = [s.scheduled_at for s in sessions]
        assert times == sorted(times)


class TestSessionsRepositoryFindByClient:
    async def test_find_by_client_returns_sessions(
        self,
        tenant_session: AsyncSession,
        test_agenda_session: AgendaSession,
        test_client: Client,
    ) -> None:
        """find_by_client() deve retornar sessões do cliente especificado."""
        repo = SessionsRepository(tenant_session)

        sessions = await repo.find_by_client(test_client.id)
        ids = [s.id for s in sessions]

        assert test_agenda_session.id in ids

    async def test_find_by_client_returns_empty_for_unknown_client(
        self,
        tenant_session: AsyncSession,
    ) -> None:
        """find_by_client() deve retornar [] para client_id sem sessões."""
        repo = SessionsRepository(tenant_session)

        sessions = await repo.find_by_client(uuid4())

        assert sessions == []


class TestSessionsRepositoryFindScheduledBetween:
    async def test_find_scheduled_between_returns_sessions_in_window(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_client: Client,
    ) -> None:
        """find_scheduled_between() deve retornar sessões dentro da janela."""
        repo = SessionsRepository(tenant_session)
        sess = await repo.create(
            test_professional.id,
            _session_create(
                test_client.id,
                scheduled_at=datetime(2031, 1, 15, 10, 0, tzinfo=UTC),
            ),
        )

        found = await repo.find_scheduled_between(
            datetime(2031, 1, 15, 0, 0, tzinfo=UTC),
            datetime(2031, 1, 16, 0, 0, tzinfo=UTC),
        )

        ids = [s.id for s in found]
        assert sess.id in ids

    async def test_find_scheduled_between_excludes_sessions_outside_window(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_client: Client,
    ) -> None:
        """find_scheduled_between() não deve retornar sessões fora da janela."""
        repo = SessionsRepository(tenant_session)
        outside = await repo.create(
            test_professional.id,
            _session_create(
                test_client.id,
                scheduled_at=datetime(2031, 1, 20, 10, 0, tzinfo=UTC),
            ),
        )

        found = await repo.find_scheduled_between(
            datetime(2031, 1, 15, 0, 0, tzinfo=UTC),
            datetime(2031, 1, 16, 0, 0, tzinfo=UTC),
        )

        ids = [s.id for s in found]
        assert outside.id not in ids


class TestSessionsRepositoryFindConflicting:
    async def test_find_conflicting_returns_overlapping_session(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_client: Client,
    ) -> None:
        """find_conflicting() deve retornar sessões com sobreposição de horário."""
        repo = SessionsRepository(tenant_session)

        # Sessão existente: 10h00–11h00
        existing = await repo.create(
            test_professional.id,
            _session_create(
                test_client.id,
                scheduled_at=datetime(2031, 3, 1, 10, 0, tzinfo=UTC),
                duration_minutes=60,
            ),
        )

        # Nova proposta: 10h30–11h30 → sobrepõe com a existente
        conflicting = await repo.find_conflicting(
            scheduled_at=datetime(2031, 3, 1, 10, 30, tzinfo=UTC),
            duration_minutes=60,
        )

        ids = [s.id for s in conflicting]
        assert existing.id in ids

    async def test_find_conflicting_returns_empty_when_no_overlap(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_client: Client,
    ) -> None:
        """find_conflicting() deve retornar [] para horários não conflitantes."""
        repo = SessionsRepository(tenant_session)

        # Sessão existente: 10h00–11h00
        await repo.create(
            test_professional.id,
            _session_create(
                test_client.id,
                scheduled_at=datetime(2031, 4, 1, 10, 0, tzinfo=UTC),
                duration_minutes=60,
            ),
        )

        # Nova proposta: 11h00–12h00 → adjacente, NÃO sobrepõe
        conflicting = await repo.find_conflicting(
            scheduled_at=datetime(2031, 4, 1, 11, 0, tzinfo=UTC),
            duration_minutes=60,
        )

        assert conflicting == []

    async def test_find_conflicting_ignores_cancelled_sessions(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_client: Client,
    ) -> None:
        """find_conflicting() não deve considerar sessões canceladas ou concluídas."""
        repo = SessionsRepository(tenant_session)

        cancelled = await repo.create(
            test_professional.id,
            _session_create(
                test_client.id,
                scheduled_at=datetime(2031, 5, 1, 10, 0, tzinfo=UTC),
                duration_minutes=60,
            ),
        )
        # Marcar como cancelada
        await repo.update(cancelled, {"status": "cancelled"})

        # Mesma janela — não deve conflitar (sessão cancelada)
        conflicting = await repo.find_conflicting(
            scheduled_at=datetime(2031, 5, 1, 10, 0, tzinfo=UTC),
            duration_minutes=60,
        )

        assert conflicting == []

    async def test_find_conflicting_query_window_fully_contains_existing(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_client: Client,
    ) -> None:
        """Sessão existente completamente dentro da nova janela é conflito."""
        repo = SessionsRepository(tenant_session)

        # Sessão existente: 10h30–11h00
        existing = await repo.create(
            test_professional.id,
            _session_create(
                test_client.id,
                scheduled_at=datetime(2031, 6, 1, 10, 30, tzinfo=UTC),
                duration_minutes=30,
            ),
        )

        # Nova proposta: 10h00–12h00 — contém completamente a existente
        conflicting = await repo.find_conflicting(
            scheduled_at=datetime(2031, 6, 1, 10, 0, tzinfo=UTC),
            duration_minutes=120,
        )

        ids = [s.id for s in conflicting]
        assert existing.id in ids


class TestSessionsRepositoryUpdate:
    async def test_update_changes_status(
        self,
        tenant_session: AsyncSession,
        test_agenda_session: AgendaSession,
    ) -> None:
        """update() deve atualizar o status da sessão."""
        repo = SessionsRepository(tenant_session)

        updated = await repo.update(test_agenda_session, {"status": "completed"})

        assert updated.status == "completed"

    async def test_update_changes_notes(
        self,
        tenant_session: AsyncSession,
        test_agenda_session: AgendaSession,
    ) -> None:
        """update() deve atualizar as notas da sessão."""
        repo = SessionsRepository(tenant_session)

        updated = await repo.update(test_agenda_session, {"notes": "Sessão produtiva"})

        assert updated.notes == "Sessão produtiva"

    async def test_update_does_not_change_unset_fields(
        self,
        tenant_session: AsyncSession,
        test_agenda_session: AgendaSession,
    ) -> None:
        """update() não deve alterar campos não incluídos no dict."""
        repo = SessionsRepository(tenant_session)
        original_duration = test_agenda_session.duration_minutes

        await repo.update(test_agenda_session, {"notes": "New note"})

        assert test_agenda_session.duration_minutes == original_duration


class TestSessionsRepositoryCancelFutureByRecurrence:
    async def test_cancel_future_sessions_returns_count(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_client: Client,
        test_recurrence: Recurrence,
    ) -> None:
        """cancel_future_by_recurrence() deve retornar o número de sessões canceladas."""
        repo = SessionsRepository(tenant_session)

        # Criar 2 sessões futuras vinculadas à recorrência
        for month in [6, 7]:
            await repo.create(
                test_professional.id,
                _session_create(
                    test_client.id,
                    scheduled_at=datetime(2030, month, 15, 10, 0, tzinfo=UTC),
                    recurrence_id=test_recurrence.id,
                ),
            )

        count = await repo.cancel_future_by_recurrence(test_recurrence.id)

        assert count == 2

    async def test_cancel_future_sessions_changes_status_to_cancelled(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_client: Client,
        test_recurrence: Recurrence,
    ) -> None:
        """cancel_future_by_recurrence() deve mudar status para 'cancelled'."""
        repo = SessionsRepository(tenant_session)

        sess = await repo.create(
            test_professional.id,
            _session_create(
                test_client.id,
                scheduled_at=datetime(2030, 8, 1, 10, 0, tzinfo=UTC),
                recurrence_id=test_recurrence.id,
            ),
        )

        await repo.cancel_future_by_recurrence(test_recurrence.id)

        # Refresh necessário: bulk UPDATE não sincroniza o identity map
        await tenant_session.refresh(sess)
        assert sess.status == "cancelled"

    async def test_cancel_future_skips_past_sessions(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_client: Client,
        test_recurrence: Recurrence,
    ) -> None:
        """cancel_future_by_recurrence() não deve cancelar sessões passadas."""
        repo = SessionsRepository(tenant_session)

        # Sessão no passado — não deve ser cancelada
        past_sess = await repo.create(
            test_professional.id,
            _session_create(
                test_client.id,
                scheduled_at=datetime(2020, 1, 1, 10, 0, tzinfo=UTC),
                recurrence_id=test_recurrence.id,
            ),
        )

        count = await repo.cancel_future_by_recurrence(test_recurrence.id)

        assert count == 0
        await tenant_session.refresh(past_sess)
        assert past_sess.status == "scheduled"

    async def test_cancel_future_skips_already_completed_sessions(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_client: Client,
        test_recurrence: Recurrence,
    ) -> None:
        """cancel_future_by_recurrence() não deve alterar sessões já concluídas."""
        repo = SessionsRepository(tenant_session)

        # Sessão futura mas já marcada como concluída
        completed_sess = await repo.create(
            test_professional.id,
            _session_create(
                test_client.id,
                scheduled_at=datetime(2030, 9, 1, 10, 0, tzinfo=UTC),
                recurrence_id=test_recurrence.id,
            ),
        )
        await repo.update(completed_sess, {"status": "completed"})

        count = await repo.cancel_future_by_recurrence(test_recurrence.id)

        assert count == 0
        await tenant_session.refresh(completed_sess)
        assert completed_sess.status == "completed"

    async def test_cancel_future_only_affects_matching_recurrence(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_client: Client,
        test_recurrence: Recurrence,
    ) -> None:
        """cancel_future_by_recurrence() não deve afetar sessões de outra recorrência."""
        repo = SessionsRepository(tenant_session)

        # Sessão sem recorrência (avulsa)
        standalone = await repo.create(
            test_professional.id,
            _session_create(
                test_client.id,
                scheduled_at=datetime(2030, 9, 15, 10, 0, tzinfo=UTC),
                recurrence_id=None,
            ),
        )

        await repo.cancel_future_by_recurrence(test_recurrence.id)

        await tenant_session.refresh(standalone)
        assert standalone.status == "scheduled"

    async def test_cancel_future_returns_zero_when_no_sessions(
        self,
        tenant_session: AsyncSession,
        test_recurrence: Recurrence,
    ) -> None:
        """cancel_future_by_recurrence() deve retornar 0 quando não há sessões futuras."""
        repo = SessionsRepository(tenant_session)

        count = await repo.cancel_future_by_recurrence(test_recurrence.id)

        assert count == 0
