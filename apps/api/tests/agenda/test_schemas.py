"""
Tests for agenda schemas — model_validator rules.

Coverage:
- AvailabilitySlotCreate : end_time > start_time, day_of_week 0-6
- BlockedPeriodCreate    : end_datetime > start_datetime, defaults
- RecurrenceCreate       : day_of_week required for weekly/biweekly,
                           end_date > start_date, interval > 0
- SessionCreate          : basic field validation (gt=0 guards)

These are pure Pydantic tests — no database required.
"""

from datetime import UTC, date, datetime, time
from decimal import Decimal
from uuid import UUID

import pytest
from pydantic import ValidationError

from agenda.schemas import (
    AvailabilitySlotCreate,
    AvailabilitySlotUpdate,
    BlockedPeriodCreate,
    RecurrenceCreate,
    SessionCreate,
    SessionUpdate,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CLIENT_ID = UUID("00000000-0000-0000-0000-000000000001")


def _make_recurrence(**overrides) -> dict:
    base = {
        "client_id": _CLIENT_ID,
        "frequency": "monthly",
        "start_date": date(2025, 1, 1),
        "session_duration": 60,
        "session_price": Decimal("150.00"),
    }
    base.update(overrides)
    return base


# ===========================================================================
# AvailabilitySlotCreate
# ===========================================================================


class TestAvailabilitySlotCreate:
    # -----------------------------------------------------------------------
    # Happy path
    # -----------------------------------------------------------------------

    def test_valid_slot_is_accepted(self) -> None:
        """Slot com end_time > start_time e day_of_week válido deve ser aceito."""
        slot = AvailabilitySlotCreate(
            day_of_week=1,
            start_time=time(9, 0),
            end_time=time(17, 0),
        )
        assert slot.day_of_week == 1
        assert slot.start_time == time(9, 0)
        assert slot.end_time == time(17, 0)

    def test_boundary_days_are_accepted(self) -> None:
        """day_of_week 0 (domingo) e 6 (sábado) devem ser aceitos."""
        for day in (0, 6):
            slot = AvailabilitySlotCreate(
                day_of_week=day,
                start_time=time(8, 0),
                end_time=time(18, 0),
            )
            assert slot.day_of_week == day

    def test_all_days_of_week_are_accepted(self) -> None:
        """Todos os 7 dias (0-6) devem ser válidos."""
        for day in range(7):
            slot = AvailabilitySlotCreate(
                day_of_week=day,
                start_time=time(9, 0),
                end_time=time(10, 0),
            )
            assert slot.day_of_week == day

    def test_minute_level_precision_accepted(self) -> None:
        """Horários com minutos (ex: 09:30–17:30) devem ser aceitos."""
        slot = AvailabilitySlotCreate(
            day_of_week=3,
            start_time=time(9, 30),
            end_time=time(17, 30),
        )
        assert slot.start_time == time(9, 30)
        assert slot.end_time == time(17, 30)

    # -----------------------------------------------------------------------
    # end_time validator
    # -----------------------------------------------------------------------

    def test_end_time_before_start_time_raises(self) -> None:
        """end_time anterior a start_time deve lançar ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            AvailabilitySlotCreate(
                day_of_week=1,
                start_time=time(17, 0),
                end_time=time(9, 0),
            )
        errors = str(exc_info.value)
        assert "end_time must be after start_time" in errors

    def test_end_time_equal_to_start_time_raises(self) -> None:
        """end_time igual a start_time (janela de 0 minutos) deve falhar."""
        with pytest.raises(ValidationError):
            AvailabilitySlotCreate(
                day_of_week=1,
                start_time=time(9, 0),
                end_time=time(9, 0),
            )

    # -----------------------------------------------------------------------
    # day_of_week validator (Field ge=0, le=6)
    # -----------------------------------------------------------------------

    def test_day_of_week_negative_raises(self) -> None:
        """day_of_week < 0 deve lançar ValidationError."""
        with pytest.raises(ValidationError):
            AvailabilitySlotCreate(
                day_of_week=-1,
                start_time=time(9, 0),
                end_time=time(17, 0),
            )

    def test_day_of_week_above_6_raises(self) -> None:
        """day_of_week > 6 deve lançar ValidationError."""
        with pytest.raises(ValidationError):
            AvailabilitySlotCreate(
                day_of_week=7,
                start_time=time(9, 0),
                end_time=time(17, 0),
            )


# ===========================================================================
# AvailabilitySlotUpdate
# ===========================================================================


class TestAvailabilitySlotUpdate:
    def test_all_fields_optional(self) -> None:
        """AvailabilitySlotUpdate sem campos deve ser válido (PATCH semântico)."""
        update = AvailabilitySlotUpdate()
        assert update.start_time is None
        assert update.end_time is None
        assert update.is_active is None

    def test_partial_update_accepted(self) -> None:
        """Apenas is_active pode ser atualizado sem fornecer os outros campos."""
        update = AvailabilitySlotUpdate(is_active=False)
        assert update.is_active is False
        assert update.start_time is None


# ===========================================================================
# BlockedPeriodCreate
# ===========================================================================


class TestBlockedPeriodCreate:
    # -----------------------------------------------------------------------
    # Happy path
    # -----------------------------------------------------------------------

    def test_valid_blocked_period_is_accepted(self) -> None:
        """Período com end > start deve ser aceito."""
        period = BlockedPeriodCreate(
            start_datetime=datetime(2025, 1, 1, 8, 0, tzinfo=UTC),
            end_datetime=datetime(2025, 1, 1, 18, 0, tzinfo=UTC),
        )
        assert period.start_datetime < period.end_datetime

    def test_notify_clients_default_is_true(self) -> None:
        """notify_clients deve ser True por padrão — opt-out intencional."""
        period = BlockedPeriodCreate(
            start_datetime=datetime(2025, 1, 1, 8, 0, tzinfo=UTC),
            end_datetime=datetime(2025, 1, 1, 18, 0, tzinfo=UTC),
        )
        assert period.notify_clients is True

    def test_notify_clients_can_be_set_to_false(self) -> None:
        """Profissional pode optar por não notificar clientes."""
        period = BlockedPeriodCreate(
            start_datetime=datetime(2025, 1, 1, 8, 0, tzinfo=UTC),
            end_datetime=datetime(2025, 1, 1, 18, 0, tzinfo=UTC),
            notify_clients=False,
        )
        assert period.notify_clients is False

    def test_reason_is_optional(self) -> None:
        """reason deve ser None quando não fornecido."""
        period = BlockedPeriodCreate(
            start_datetime=datetime(2025, 1, 1, 8, 0, tzinfo=UTC),
            end_datetime=datetime(2025, 1, 1, 18, 0, tzinfo=UTC),
        )
        assert period.reason is None

    def test_multi_day_block_is_accepted(self) -> None:
        """Bloqueio de múltiplos dias (ex: férias) deve ser aceito."""
        period = BlockedPeriodCreate(
            start_datetime=datetime(2025, 7, 14, 0, 0, tzinfo=UTC),
            end_datetime=datetime(2025, 7, 28, 23, 59, tzinfo=UTC),
            reason="Férias de julho",
        )
        assert period.reason == "Férias de julho"

    # -----------------------------------------------------------------------
    # end_datetime validator
    # -----------------------------------------------------------------------

    def test_end_datetime_before_start_raises(self) -> None:
        """end_datetime anterior a start_datetime deve lançar ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            BlockedPeriodCreate(
                start_datetime=datetime(2025, 1, 1, 18, 0, tzinfo=UTC),
                end_datetime=datetime(2025, 1, 1, 8, 0, tzinfo=UTC),
            )
        assert "end_datetime must be after start_datetime" in str(exc_info.value)

    def test_end_datetime_equal_to_start_raises(self) -> None:
        """end_datetime igual a start_datetime (duração zero) deve falhar."""
        with pytest.raises(ValidationError):
            BlockedPeriodCreate(
                start_datetime=datetime(2025, 1, 1, 8, 0, tzinfo=UTC),
                end_datetime=datetime(2025, 1, 1, 8, 0, tzinfo=UTC),
            )

    def test_reason_max_length_255(self) -> None:
        """reason com mais de 255 caracteres deve falhar."""
        with pytest.raises(ValidationError):
            BlockedPeriodCreate(
                start_datetime=datetime(2025, 1, 1, 8, 0, tzinfo=UTC),
                end_datetime=datetime(2025, 1, 1, 18, 0, tzinfo=UTC),
                reason="x" * 256,
            )


# ===========================================================================
# RecurrenceCreate
# ===========================================================================


class TestRecurrenceCreate:
    # -----------------------------------------------------------------------
    # Happy path — frequencies
    # -----------------------------------------------------------------------

    def test_valid_weekly_with_day_of_week(self) -> None:
        """Recorrência semanal com day_of_week definido deve ser aceita."""
        rec = RecurrenceCreate(**_make_recurrence(frequency="weekly", day_of_week=1))
        assert rec.frequency == "weekly"
        assert rec.day_of_week == 1

    def test_valid_biweekly_with_day_of_week(self) -> None:
        """Recorrência quinzenal com day_of_week definido deve ser aceita."""
        rec = RecurrenceCreate(**_make_recurrence(frequency="biweekly", day_of_week=3))
        assert rec.frequency == "biweekly"
        assert rec.day_of_week == 3

    def test_valid_monthly_without_day_of_week(self) -> None:
        """Recorrência mensal sem day_of_week deve ser aceita."""
        rec = RecurrenceCreate(**_make_recurrence(frequency="monthly"))
        assert rec.frequency == "monthly"
        assert rec.day_of_week is None

    def test_valid_monthly_with_day_of_week(self) -> None:
        """Recorrência mensal com day_of_week também deve ser aceita."""
        rec = RecurrenceCreate(**_make_recurrence(frequency="monthly", day_of_week=0))
        assert rec.day_of_week == 0

    # -----------------------------------------------------------------------
    # day_of_week required validator
    # -----------------------------------------------------------------------

    def test_weekly_without_day_of_week_raises(self) -> None:
        """Recorrência semanal sem day_of_week deve lançar ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            RecurrenceCreate(**_make_recurrence(frequency="weekly"))
        assert "day_of_week is required" in str(exc_info.value)

    def test_biweekly_without_day_of_week_raises(self) -> None:
        """Recorrência quinzenal sem day_of_week deve lançar ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            RecurrenceCreate(**_make_recurrence(frequency="biweekly"))
        assert "day_of_week is required" in str(exc_info.value)

    # -----------------------------------------------------------------------
    # end_date validator
    # -----------------------------------------------------------------------

    def test_end_date_after_start_date_is_valid(self) -> None:
        """end_date posterior a start_date deve ser aceita."""
        rec = RecurrenceCreate(
            **_make_recurrence(
                start_date=date(2025, 1, 1),
                end_date=date(2025, 12, 31),
            )
        )
        assert rec.end_date == date(2025, 12, 31)

    def test_end_date_before_start_date_raises(self) -> None:
        """end_date anterior a start_date deve lançar ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            RecurrenceCreate(
                **_make_recurrence(
                    start_date=date(2025, 6, 1),
                    end_date=date(2025, 1, 1),
                )
            )
        assert "end_date must be after start_date" in str(exc_info.value)

    def test_end_date_equal_to_start_date_raises(self) -> None:
        """end_date igual a start_date (duração zero) deve falhar."""
        with pytest.raises(ValidationError):
            RecurrenceCreate(
                **_make_recurrence(
                    start_date=date(2025, 1, 1),
                    end_date=date(2025, 1, 1),
                )
            )

    def test_end_date_none_means_no_end(self) -> None:
        """end_date=None deve ser aceito (recorrência sem fim definido)."""
        rec = RecurrenceCreate(**_make_recurrence(end_date=None))
        assert rec.end_date is None

    # -----------------------------------------------------------------------
    # Other field constraints
    # -----------------------------------------------------------------------

    def test_interval_default_is_1(self) -> None:
        """interval deve ter valor padrão 1."""
        rec = RecurrenceCreate(**_make_recurrence())
        assert rec.interval == 1

    def test_interval_zero_raises(self) -> None:
        """interval=0 deve falhar (gt=0 constraint)."""
        with pytest.raises(ValidationError):
            RecurrenceCreate(**_make_recurrence(interval=0))

    def test_interval_negative_raises(self) -> None:
        """interval negativo deve falhar."""
        with pytest.raises(ValidationError):
            RecurrenceCreate(**_make_recurrence(interval=-1))

    def test_session_duration_zero_raises(self) -> None:
        """session_duration=0 deve falhar (gt=0)."""
        with pytest.raises(ValidationError):
            RecurrenceCreate(**_make_recurrence(session_duration=0))

    def test_session_price_zero_raises(self) -> None:
        """session_price=0 deve falhar (gt=0)."""
        with pytest.raises(ValidationError):
            RecurrenceCreate(**_make_recurrence(session_price=Decimal("0.00")))

    def test_invalid_frequency_raises(self) -> None:
        """Frequência fora de {weekly, biweekly, monthly} deve falhar."""
        with pytest.raises(ValidationError):
            RecurrenceCreate(**_make_recurrence(frequency="daily"))


# ===========================================================================
# SessionCreate
# ===========================================================================


class TestSessionCreate:
    def test_valid_session_is_accepted(self) -> None:
        """SessionCreate com todos os campos obrigatórios deve ser aceito."""
        session = SessionCreate(
            client_id=_CLIENT_ID,
            scheduled_at=datetime(2025, 6, 1, 10, 0, tzinfo=UTC),
            duration_minutes=60,
            price=Decimal("150.00"),
        )
        assert session.client_id == _CLIENT_ID
        assert session.recurrence_id is None
        assert session.notes is None

    def test_duration_minutes_zero_raises(self) -> None:
        """duration_minutes=0 deve falhar (gt=0)."""
        with pytest.raises(ValidationError):
            SessionCreate(
                client_id=_CLIENT_ID,
                scheduled_at=datetime(2025, 6, 1, 10, 0, tzinfo=UTC),
                duration_minutes=0,
                price=Decimal("150.00"),
            )

    def test_price_zero_raises(self) -> None:
        """price=0 deve falhar (gt=0)."""
        with pytest.raises(ValidationError):
            SessionCreate(
                client_id=_CLIENT_ID,
                scheduled_at=datetime(2025, 6, 1, 10, 0, tzinfo=UTC),
                duration_minutes=60,
                price=Decimal("0.00"),
            )


# ===========================================================================
# SessionUpdate
# ===========================================================================


class TestSessionUpdate:
    def test_all_fields_optional(self) -> None:
        """SessionUpdate sem campos deve ser válido (PATCH semântico)."""
        update = SessionUpdate()
        assert update.scheduled_at is None
        assert update.duration_minutes is None
        assert update.price is None
        assert update.status is None
        assert update.notes is None

    def test_valid_status_values(self) -> None:
        """Todos os status válidos devem ser aceitos."""
        for status in ("scheduled", "completed", "cancelled", "no_show"):
            update = SessionUpdate(status=status)
            assert update.status == status

    def test_invalid_status_raises(self) -> None:
        """Status fora do Literal deve lançar ValidationError."""
        with pytest.raises(ValidationError):
            SessionUpdate(status="pending")
