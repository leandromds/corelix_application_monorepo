"""
Tests for AgendaService — TDD Red phase.

Coverage:
- create_availability_slot : happy path, ConflictError on duplicate (day, time)
- list_slots               : returns active, excludes inactive
- get_slot                 : found, NotFoundError
- update_slot              : PATCH semantics, NotFoundError
- delete_slot              : soft delete, NotFoundError

- create_blocked_period    : happy path
- list_blocked_periods     : returns all
- delete_blocked_period    : hard delete, NotFoundError

- create_session           : happy path, ConflictError on session overlap,
                             ConflictError on blocked period overlap
- list_sessions            : pagination
- get_session              : found, NotFoundError
- update_session           : PATCH semantics, reschedule triggers conflict check,
                             exclude_session_id prevents self-conflict
- list_today_sessions      : returns today only
- list_upcoming_sessions   : returns future scheduled only

- create_recurrence        : happy path
- list_recurrences         : active_only filter
- get_recurrence           : found, NotFoundError
- deactivate_recurrence    : soft-deletes rule + cancels future sessions,
                             returns count

All tests use tenant_session so RLS is active for all SELECT queries.
"""

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
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
    AvailabilitySlotUpdate,
    BlockedPeriodCreate,
    RecurrenceCreate,
    SessionCreate,
    SessionUpdate,
)
from agenda.service import AgendaService
from clients.models import Client
from core.exceptions import ConflictError, NotFoundError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_service(session: AsyncSession, professional_id) -> AgendaService:
    return AgendaService(session, professional_id)


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
    start: datetime = datetime(2030, 3, 1, 8, 0, tzinfo=timezone.utc),
    end: datetime = datetime(2030, 3, 1, 18, 0, tzinfo=timezone.utc),
    reason: str | None = "Test block",
) -> BlockedPeriodCreate:
    return BlockedPeriodCreate(
        start_datetime=start,
        end_datetime=end,
        reason=reason,
    )


def _session_create(
    client_id,
    *,
    scheduled_at: datetime = datetime(2030, 6, 1, 10, 0, tzinfo=timezone.utc),
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


def _recurrence_create(client_id, *, frequency: str = "weekly") -> RecurrenceCreate:
    kwargs: dict = dict(
        client_id=client_id,
        frequency=frequency,
        start_date=date(2025, 1, 1),
        session_duration=60,
        session_price=Decimal("150.00"),
    )
    if frequency in ("weekly", "biweekly"):
        kwargs["day_of_week"] = 1
    return RecurrenceCreate(**kwargs)


# ===========================================================================
# Availability Slots
# ===========================================================================


class TestAgendaServiceCreateAvailabilitySlot:
    async def test_create_slot_returns_slot(
        self,
        tenant_session: AsyncSession,
        test_professional,
    ) -> None:
        """create_availability_slot() deve retornar AvailabilitySlot persistido."""
        service = _make_service(tenant_session, test_professional.id)

        slot = await service.create_availability_slot(
            _slot_create(day_of_week=2, start_time=time(9, 0), end_time=time(10, 0))
        )

        assert slot.id is not None
        assert slot.day_of_week == 2
        assert slot.is_active is True

    async def test_create_slot_conflict_error_on_duplicate_day_and_time(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_availability_slot: AvailabilitySlot,
    ) -> None:
        """ConflictError deve ser lançado para (day_of_week, start_time) duplicado."""
        service = _make_service(tenant_session, test_professional.id)

        with pytest.raises(ConflictError):
            await service.create_availability_slot(
                _slot_create(
                    day_of_week=test_availability_slot.day_of_week,
                    start_time=test_availability_slot.start_time,
                    end_time=test_availability_slot.end_time,
                )
            )

    async def test_create_slot_same_day_different_start_time_allowed(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_availability_slot: AvailabilitySlot,
    ) -> None:
        """Dois blocos no mesmo dia com start_time diferentes devem ser aceitos."""
        service = _make_service(tenant_session, test_professional.id)

        # test_availability_slot starts at 09:00 — create at 14:00 on same day
        slot = await service.create_availability_slot(
            _slot_create(
                day_of_week=test_availability_slot.day_of_week,
                start_time=time(14, 0),
                end_time=time(16, 0),
            )
        )

        assert slot.id is not None

    async def test_create_slot_same_day_and_time_different_tenant_allowed(
        self,
        db_session: AsyncSession,
        test_professional,
    ) -> None:
        """Mesmo (day_of_week, start_time) em tenant diferente não é conflito (RLS)."""
        from professionals.models import Professional

        # Criar outro profissional e slot ANTES de ativar o contexto de tenant
        other_prof = Professional(
            email="other_slot_svc@example.com",
            password_hash="h",
            full_name="Other Pro",
        )
        db_session.add(other_prof)
        await db_session.flush()

        other_slot = AvailabilitySlot(
            professional_id=other_prof.id,
            day_of_week=3,
            start_time=time(9, 0),
            end_time=time(10, 0),
        )
        db_session.add(other_slot)
        await db_session.flush()

        # Ativar tenant de test_professional
        from sqlalchemy import text

        await db_session.execute(text("SET LOCAL ROLE test_rls_user"))
        await db_session.execute(text(f"SET LOCAL app.current_tenant = '{test_professional.id}'"))

        service = _make_service(db_session, test_professional.id)

        # Mesmo (day=3, start=09:00) — mas outro tenant não é visível via RLS
        slot = await service.create_availability_slot(
            _slot_create(day_of_week=3, start_time=time(9, 0), end_time=time(10, 0))
        )

        assert slot.id is not None


class TestAgendaServiceListSlots:
    async def test_list_slots_returns_active_slots(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_availability_slot: AvailabilitySlot,
    ) -> None:
        """list_slots() deve retornar slots ativos."""
        service = _make_service(tenant_session, test_professional.id)

        slots = await service.list_slots()
        ids = [s.id for s in slots]

        assert test_availability_slot.id in ids

    async def test_list_slots_excludes_inactive(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_availability_slot: AvailabilitySlot,
    ) -> None:
        """list_slots() deve excluir slots inativas por padrão."""
        service = _make_service(tenant_session, test_professional.id)
        await service.delete_slot(test_availability_slot.id)

        slots = await service.list_slots()
        ids = [s.id for s in slots]

        assert test_availability_slot.id not in ids


class TestAgendaServiceGetSlot:
    async def test_get_slot_returns_slot(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_availability_slot: AvailabilitySlot,
    ) -> None:
        """get_slot() deve retornar o slot pelo id."""
        service = _make_service(tenant_session, test_professional.id)

        slot = await service.get_slot(test_availability_slot.id)

        assert slot.id == test_availability_slot.id

    async def test_get_slot_not_found_raises(
        self,
        tenant_session: AsyncSession,
        test_professional,
    ) -> None:
        """get_slot() deve lançar NotFoundError para id inexistente."""
        service = _make_service(tenant_session, test_professional.id)

        with pytest.raises(NotFoundError):
            await service.get_slot(uuid4())


class TestAgendaServiceUpdateSlot:
    async def test_update_slot_changes_end_time(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_availability_slot: AvailabilitySlot,
    ) -> None:
        """update_slot() deve atualizar o campo fornecido."""
        service = _make_service(tenant_session, test_professional.id)

        updated = await service.update_slot(
            test_availability_slot.id,
            AvailabilitySlotUpdate(end_time=time(18, 0)),
        )

        assert updated.end_time == time(18, 0)

    async def test_update_slot_does_not_change_unset_fields(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_availability_slot: AvailabilitySlot,
    ) -> None:
        """update_slot() não deve alterar campos não incluídos no payload."""
        service = _make_service(tenant_session, test_professional.id)
        original_day = test_availability_slot.day_of_week

        await service.update_slot(
            test_availability_slot.id,
            AvailabilitySlotUpdate(is_active=False),
        )

        assert test_availability_slot.day_of_week == original_day

    async def test_update_slot_not_found_raises(
        self,
        tenant_session: AsyncSession,
        test_professional,
    ) -> None:
        """update_slot() deve lançar NotFoundError para id inexistente."""
        service = _make_service(tenant_session, test_professional.id)

        with pytest.raises(NotFoundError):
            await service.update_slot(uuid4(), AvailabilitySlotUpdate(is_active=False))


class TestAgendaServiceDeleteSlot:
    async def test_delete_slot_soft_deletes(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_availability_slot: AvailabilitySlot,
    ) -> None:
        """delete_slot() deve setar is_active=False (soft delete)."""
        service = _make_service(tenant_session, test_professional.id)

        await service.delete_slot(test_availability_slot.id)

        assert test_availability_slot.is_active is False

    async def test_delete_slot_excludes_from_active_list(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_availability_slot: AvailabilitySlot,
    ) -> None:
        """Após delete_slot(), slot não deve aparecer em list_slots()."""
        service = _make_service(tenant_session, test_professional.id)

        await service.delete_slot(test_availability_slot.id)
        slots = await service.list_slots()
        ids = [s.id for s in slots]

        assert test_availability_slot.id not in ids

    async def test_delete_slot_not_found_raises(
        self,
        tenant_session: AsyncSession,
        test_professional,
    ) -> None:
        """delete_slot() deve lançar NotFoundError para id inexistente."""
        service = _make_service(tenant_session, test_professional.id)

        with pytest.raises(NotFoundError):
            await service.delete_slot(uuid4())


# ===========================================================================
# Blocked Periods
# ===========================================================================


class TestAgendaServiceCreateBlockedPeriod:
    async def test_create_blocked_period_returns_period(
        self,
        tenant_session: AsyncSession,
        test_professional,
    ) -> None:
        """create_blocked_period() deve retornar BlockedPeriod persistido."""
        service = _make_service(tenant_session, test_professional.id)

        period = await service.create_blocked_period(_blocked_create())

        assert period.id is not None
        assert period.reason == "Test block"
        assert period.notify_clients is True

    async def test_create_blocked_period_sets_professional_id(
        self,
        tenant_session: AsyncSession,
        test_professional,
    ) -> None:
        """create_blocked_period() deve vincular ao professional_id do serviço."""
        service = _make_service(tenant_session, test_professional.id)

        period = await service.create_blocked_period(_blocked_create())

        assert period.professional_id == test_professional.id


class TestAgendaServiceListBlockedPeriods:
    async def test_list_blocked_periods_returns_periods(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_blocked_period: BlockedPeriod,
    ) -> None:
        """list_blocked_periods() deve retornar todos os períodos do tenant."""
        service = _make_service(tenant_session, test_professional.id)

        periods = await service.list_blocked_periods()
        ids = [p.id for p in periods]

        assert test_blocked_period.id in ids


class TestAgendaServiceDeleteBlockedPeriod:
    async def test_delete_blocked_period_removes_record(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_blocked_period: BlockedPeriod,
    ) -> None:
        """delete_blocked_period() deve remover fisicamente o registro."""
        service = _make_service(tenant_session, test_professional.id)
        period_id = test_blocked_period.id

        await service.delete_blocked_period(period_id)

        periods = await service.list_blocked_periods()
        ids = [p.id for p in periods]
        assert period_id not in ids

    async def test_delete_blocked_period_not_found_raises(
        self,
        tenant_session: AsyncSession,
        test_professional,
    ) -> None:
        """delete_blocked_period() deve lançar NotFoundError para id inexistente."""
        service = _make_service(tenant_session, test_professional.id)

        with pytest.raises(NotFoundError):
            await service.delete_blocked_period(uuid4())


# ===========================================================================
# Sessions
# ===========================================================================


class TestAgendaServiceCreateSession:
    async def test_create_session_returns_session(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_client: Client,
    ) -> None:
        """create_session() deve retornar Session persistida."""
        service = _make_service(tenant_session, test_professional.id)

        sess = await service.create_session(
            _session_create(
                test_client.id,
                scheduled_at=datetime(2031, 1, 1, 10, 0, tzinfo=timezone.utc),
            )
        )

        assert sess.id is not None
        assert sess.status == "scheduled"
        assert sess.professional_id == test_professional.id

    async def test_create_session_conflict_with_existing_session_raises(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_client: Client,
    ) -> None:
        """ConflictError deve ser lançado quando há sobreposição com sessão existente."""
        service = _make_service(tenant_session, test_professional.id)

        # Criar sessão existente: 10h00–11h00
        await service.create_session(
            _session_create(
                test_client.id,
                scheduled_at=datetime(2031, 2, 1, 10, 0, tzinfo=timezone.utc),
                duration_minutes=60,
            )
        )

        # Tentar criar no mesmo horário (sobreposição total)
        with pytest.raises(ConflictError):
            await service.create_session(
                _session_create(
                    test_client.id,
                    scheduled_at=datetime(2031, 2, 1, 10, 0, tzinfo=timezone.utc),
                    duration_minutes=60,
                )
            )

    async def test_create_session_conflict_with_blocked_period_raises(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_client: Client,
    ) -> None:
        """ConflictError deve ser lançado quando sessão cai dentro de período bloqueado."""
        service = _make_service(tenant_session, test_professional.id)

        # Bloquear 08h–18h do dia 2031-03-01
        await service.create_blocked_period(
            BlockedPeriodCreate(
                start_datetime=datetime(2031, 3, 1, 8, 0, tzinfo=timezone.utc),
                end_datetime=datetime(2031, 3, 1, 18, 0, tzinfo=timezone.utc),
                reason="Bloqueio de teste",
            )
        )

        # Tentar criar sessão dentro do bloqueio: 10h–11h
        with pytest.raises(ConflictError):
            await service.create_session(
                _session_create(
                    test_client.id,
                    scheduled_at=datetime(2031, 3, 1, 10, 0, tzinfo=timezone.utc),
                    duration_minutes=60,
                )
            )

    async def test_create_session_adjacent_to_existing_is_allowed(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_client: Client,
    ) -> None:
        """Sessão que começa exatamente quando outra termina não é conflito."""
        service = _make_service(tenant_session, test_professional.id)

        # Sessão existente: 10h00–11h00
        await service.create_session(
            _session_create(
                test_client.id,
                scheduled_at=datetime(2031, 4, 1, 10, 0, tzinfo=timezone.utc),
                duration_minutes=60,
            )
        )

        # Sessão adjacente: 11h00–12h00 — deve ser aceita
        sess = await service.create_session(
            _session_create(
                test_client.id,
                scheduled_at=datetime(2031, 4, 1, 11, 0, tzinfo=timezone.utc),
                duration_minutes=60,
            )
        )

        assert sess.id is not None

    async def test_create_session_past_date_is_allowed(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_client: Client,
    ) -> None:
        """Sessão no passado deve ser permitida (registro retroativo no onboarding)."""
        service = _make_service(tenant_session, test_professional.id)

        sess = await service.create_session(
            _session_create(
                test_client.id,
                scheduled_at=datetime(2020, 1, 1, 10, 0, tzinfo=timezone.utc),
            )
        )

        assert sess.id is not None


class TestAgendaServiceListSessions:
    async def test_list_sessions_returns_sessions(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_agenda_session: AgendaSession,
    ) -> None:
        """list_sessions() deve retornar sessões do tenant."""
        service = _make_service(tenant_session, test_professional.id)

        sessions = await service.list_sessions()
        ids = [s.id for s in sessions]

        assert test_agenda_session.id in ids

    async def test_list_sessions_respects_limit(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_client: Client,
    ) -> None:
        """list_sessions(limit=1) deve retornar no máximo 1 resultado."""
        service = _make_service(tenant_session, test_professional.id)
        for i in range(3):
            await service.create_session(
                _session_create(
                    test_client.id,
                    scheduled_at=datetime(2031, 5, i + 1, 10, 0, tzinfo=timezone.utc),
                )
            )

        sessions = await service.list_sessions(limit=1)

        assert len(sessions) == 1


class TestAgendaServiceGetSession:
    async def test_get_session_returns_session(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_agenda_session: AgendaSession,
    ) -> None:
        """get_session() deve retornar a sessão pelo id."""
        service = _make_service(tenant_session, test_professional.id)

        sess = await service.get_session(test_agenda_session.id)

        assert sess.id == test_agenda_session.id

    async def test_get_session_not_found_raises(
        self,
        tenant_session: AsyncSession,
        test_professional,
    ) -> None:
        """get_session() deve lançar NotFoundError para id inexistente."""
        service = _make_service(tenant_session, test_professional.id)

        with pytest.raises(NotFoundError):
            await service.get_session(uuid4())


class TestAgendaServiceUpdateSession:
    async def test_update_session_changes_status(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_agenda_session: AgendaSession,
    ) -> None:
        """update_session() deve atualizar o status quando fornecido."""
        service = _make_service(tenant_session, test_professional.id)

        updated = await service.update_session(
            test_agenda_session.id,
            SessionUpdate(status="completed"),
        )

        assert updated.status == "completed"

    async def test_update_session_patch_semantics_preserves_unset_fields(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_agenda_session: AgendaSession,
    ) -> None:
        """update_session() não deve alterar campos não enviados no payload."""
        service = _make_service(tenant_session, test_professional.id)
        original_duration = test_agenda_session.duration_minutes

        await service.update_session(
            test_agenda_session.id,
            SessionUpdate(notes="Nova nota"),
        )

        assert test_agenda_session.duration_minutes == original_duration

    async def test_update_session_not_found_raises(
        self,
        tenant_session: AsyncSession,
        test_professional,
    ) -> None:
        """update_session() deve lançar NotFoundError para id inexistente."""
        service = _make_service(tenant_session, test_professional.id)

        with pytest.raises(NotFoundError):
            await service.update_session(uuid4(), SessionUpdate(status="completed"))

    async def test_update_session_reschedule_triggers_conflict_check(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_client: Client,
    ) -> None:
        """Reagendar para horário conflitante deve lançar ConflictError."""
        service = _make_service(tenant_session, test_professional.id)

        # Criar sessão A: 10h–11h
        sess_a = await service.create_session(
            _session_create(
                test_client.id,
                scheduled_at=datetime(2031, 6, 1, 10, 0, tzinfo=timezone.utc),
                duration_minutes=60,
            )
        )

        # Criar sessão B: 14h–15h
        sess_b = await service.create_session(
            _session_create(
                test_client.id,
                scheduled_at=datetime(2031, 6, 1, 14, 0, tzinfo=timezone.utc),
                duration_minutes=60,
            )
        )

        # Tentar mover sessão B para 10h30 (conflita com A)
        with pytest.raises(ConflictError):
            await service.update_session(
                sess_b.id,
                SessionUpdate(scheduled_at=datetime(2031, 6, 1, 10, 30, tzinfo=timezone.utc)),
            )

    async def test_update_session_reschedule_same_slot_no_conflict(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_client: Client,
    ) -> None:
        """Reagendar sem mudar o horário não deve conflitar com a própria sessão."""
        service = _make_service(tenant_session, test_professional.id)

        sess = await service.create_session(
            _session_create(
                test_client.id,
                scheduled_at=datetime(2031, 7, 1, 10, 0, tzinfo=timezone.utc),
                duration_minutes=60,
            )
        )

        # Atualizar apenas as notas — sem mudar o horário
        updated = await service.update_session(
            sess.id,
            SessionUpdate(notes="Sem conflito"),
        )

        assert updated.notes == "Sem conflito"


class TestAgendaServiceTodayAndUpcoming:
    async def test_list_today_sessions_returns_empty_for_far_future(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_agenda_session: AgendaSession,
    ) -> None:
        """list_today_sessions() não deve retornar sessões agendadas para 2030."""
        service = _make_service(tenant_session, test_professional.id)

        # test_agenda_session está em 2030-06-01, claramente não é hoje
        sessions = await service.list_today_sessions()
        ids = [s.id for s in sessions]

        assert test_agenda_session.id not in ids

    async def test_list_upcoming_sessions_returns_future_scheduled(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_agenda_session: AgendaSession,
    ) -> None:
        """list_upcoming_sessions() deve retornar sessão futura com status='scheduled'."""
        service = _make_service(tenant_session, test_professional.id)

        # test_agenda_session está em 2030, que é futuro
        sessions = await service.list_upcoming_sessions(limit=50)
        ids = [s.id for s in sessions]

        assert test_agenda_session.id in ids

    async def test_list_upcoming_sessions_respects_limit(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_client: Client,
    ) -> None:
        """list_upcoming_sessions(limit=2) deve retornar no máximo 2 resultados."""
        service = _make_service(tenant_session, test_professional.id)

        # Criar 3 sessões futuras sem conflito
        for i in range(3):
            await service.create_session(
                _session_create(
                    test_client.id,
                    scheduled_at=datetime(2032, i + 1, 1, 10, 0, tzinfo=timezone.utc),
                )
            )

        sessions = await service.list_upcoming_sessions(limit=2)

        assert len(sessions) <= 2


# ===========================================================================
# Recurrences
# ===========================================================================


class TestAgendaServiceCreateRecurrence:
    async def test_create_recurrence_returns_recurrence(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_client: Client,
    ) -> None:
        """create_recurrence() deve retornar Recurrence persistida."""
        service = _make_service(tenant_session, test_professional.id)

        rec = await service.create_recurrence(
            _recurrence_create(test_client.id, frequency="weekly")
        )

        assert rec.id is not None
        assert rec.frequency == "weekly"
        assert rec.is_active is True

    async def test_create_recurrence_sets_professional_id(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_client: Client,
    ) -> None:
        """create_recurrence() deve vincular ao professional_id do serviço."""
        service = _make_service(tenant_session, test_professional.id)

        rec = await service.create_recurrence(
            _recurrence_create(test_client.id, frequency="monthly")
        )

        assert rec.professional_id == test_professional.id


class TestAgendaServiceListRecurrences:
    async def test_list_recurrences_returns_active(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_recurrence: Recurrence,
    ) -> None:
        """list_recurrences() deve retornar recorrências ativas."""
        service = _make_service(tenant_session, test_professional.id)

        recs = await service.list_recurrences()
        ids = [r.id for r in recs]

        assert test_recurrence.id in ids

    async def test_list_recurrences_excludes_inactive(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_recurrence: Recurrence,
    ) -> None:
        """list_recurrences() não deve retornar recorrências desativadas."""
        service = _make_service(tenant_session, test_professional.id)
        await service.deactivate_recurrence(test_recurrence.id)

        recs = await service.list_recurrences()
        ids = [r.id for r in recs]

        assert test_recurrence.id not in ids


class TestAgendaServiceGetRecurrence:
    async def test_get_recurrence_returns_recurrence(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_recurrence: Recurrence,
    ) -> None:
        """get_recurrence() deve retornar a recorrência pelo id."""
        service = _make_service(tenant_session, test_professional.id)

        rec = await service.get_recurrence(test_recurrence.id)

        assert rec.id == test_recurrence.id

    async def test_get_recurrence_not_found_raises(
        self,
        tenant_session: AsyncSession,
        test_professional,
    ) -> None:
        """get_recurrence() deve lançar NotFoundError para id inexistente."""
        service = _make_service(tenant_session, test_professional.id)

        with pytest.raises(NotFoundError):
            await service.get_recurrence(uuid4())


class TestAgendaServiceDeactivateRecurrence:
    async def test_deactivate_recurrence_sets_is_active_false(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_recurrence: Recurrence,
    ) -> None:
        """deactivate_recurrence() deve marcar a recorrência como inativa."""
        service = _make_service(tenant_session, test_professional.id)

        await service.deactivate_recurrence(test_recurrence.id)

        assert test_recurrence.is_active is False

    async def test_deactivate_recurrence_cancels_future_sessions(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_client: Client,
        test_recurrence: Recurrence,
    ) -> None:
        """deactivate_recurrence() deve cancelar sessões futuras da recorrência."""
        service = _make_service(tenant_session, test_professional.id)

        # Criar 2 sessões futuras vinculadas à recorrência
        sess_repo = SessionsRepository(tenant_session)
        sess1 = await sess_repo.create(
            test_professional.id,
            SessionCreate(
                client_id=test_client.id,
                recurrence_id=test_recurrence.id,
                scheduled_at=datetime(2030, 8, 1, 10, 0, tzinfo=timezone.utc),
                duration_minutes=60,
                price=Decimal("150.00"),
            ),
        )
        sess2 = await sess_repo.create(
            test_professional.id,
            SessionCreate(
                client_id=test_client.id,
                recurrence_id=test_recurrence.id,
                scheduled_at=datetime(2030, 9, 1, 10, 0, tzinfo=timezone.utc),
                duration_minutes=60,
                price=Decimal("150.00"),
            ),
        )

        await service.deactivate_recurrence(test_recurrence.id)

        await tenant_session.refresh(sess1)
        await tenant_session.refresh(sess2)
        assert sess1.status == "cancelled"
        assert sess2.status == "cancelled"

    async def test_deactivate_recurrence_returns_cancelled_count(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_client: Client,
        test_recurrence: Recurrence,
    ) -> None:
        """deactivate_recurrence() deve retornar o número de sessões canceladas."""
        service = _make_service(tenant_session, test_professional.id)

        # Criar 3 sessões futuras
        sess_repo = SessionsRepository(tenant_session)
        for month in [7, 8, 9]:
            await sess_repo.create(
                test_professional.id,
                SessionCreate(
                    client_id=test_client.id,
                    recurrence_id=test_recurrence.id,
                    scheduled_at=datetime(2030, month, 1, 10, 0, tzinfo=timezone.utc),
                    duration_minutes=60,
                    price=Decimal("150.00"),
                ),
            )

        count = await service.deactivate_recurrence(test_recurrence.id)

        assert count == 3

    async def test_deactivate_recurrence_does_not_cancel_past_sessions(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_client: Client,
        test_recurrence: Recurrence,
    ) -> None:
        """deactivate_recurrence() não deve cancelar sessões passadas."""
        service = _make_service(tenant_session, test_professional.id)

        sess_repo = SessionsRepository(tenant_session)
        past_sess = await sess_repo.create(
            test_professional.id,
            SessionCreate(
                client_id=test_client.id,
                recurrence_id=test_recurrence.id,
                scheduled_at=datetime(2020, 1, 1, 10, 0, tzinfo=timezone.utc),
                duration_minutes=60,
                price=Decimal("150.00"),
            ),
        )

        count = await service.deactivate_recurrence(test_recurrence.id)

        assert count == 0
        await tenant_session.refresh(past_sess)
        assert past_sess.status == "scheduled"

    async def test_deactivate_recurrence_not_found_raises(
        self,
        tenant_session: AsyncSession,
        test_professional,
    ) -> None:
        """deactivate_recurrence() deve lançar NotFoundError para id inexistente."""
        service = _make_service(tenant_session, test_professional.id)

        with pytest.raises(NotFoundError):
            await service.deactivate_recurrence(uuid4())
