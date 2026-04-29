"""
Tests for the recurring sessions job.

Dois grupos de testes:
1. TestCalculateDates — testa a função pura calculate_dates() sem banco.
   Estes são os testes mais importantes: cobrem toda a lógica de calendário.

2. TestGenerateRecurringSessions — testa o job async com repository mockado.
   Verifica integração: tenant context, idempotência, error isolation.
"""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from jobs.tasks.recurrences import calculate_dates, generate_recurring_sessions

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_recurrence(
    *,
    frequency: str = "weekly",
    interval: int = 1,
    day_of_week: int | None = 0,  # Monday
    start_date: date = date(2025, 1, 6),  # Uma segunda-feira (weekday=0)
    end_date: date | None = None,
    professional_id=None,
    client_id=None,
    session_duration: int = 60,
    session_price: Decimal = Decimal("150.00"),
) -> MagicMock:
    rec = MagicMock()
    rec.id = uuid4()
    rec.professional_id = professional_id or uuid4()
    rec.client_id = client_id or uuid4()
    rec.frequency = frequency
    rec.interval = interval
    rec.day_of_week = day_of_week
    rec.start_date = start_date
    rec.end_date = end_date
    rec.session_duration = session_duration
    rec.session_price = session_price
    rec.is_active = True
    return rec


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    return session


# ---------------------------------------------------------------------------
# TestCalculateDates — pure function tests (sem banco, sem mock)
# ---------------------------------------------------------------------------


class TestCalculateDates:
    # Usamos 2025-07-14 (Monday) como "hoje" para todos os testes
    TODAY = date(2025, 7, 14)
    HORIZON = 30  # dias

    def test_weekly_preserves_series_alignment(self) -> None:
        """
        Série semanal começou em 2025-01-06 (Monday).
        Hoje é 2025-07-14 (Monday). Deve retornar 2025-07-14, 2025-07-21, …
        e NÃO datas fora da série (ex: 2025-07-15 seria errado).
        """
        rec = make_recurrence(frequency="weekly", start_date=date(2025, 1, 6), day_of_week=0)
        dates = calculate_dates(rec, self.TODAY, self.HORIZON)

        # Todos devem ser segunda-feira (weekday=0)
        assert all(d.weekday() == 0 for d in dates), "Todas as datas devem ser segunda-feira"
        assert date(2025, 7, 14) in dates
        assert date(2025, 7, 21) in dates

    def test_weekly_respects_day_of_week(self) -> None:
        """day_of_week=4 → apenas sextas-feiras."""
        rec = make_recurrence(
            frequency="weekly",
            day_of_week=4,  # Friday
            start_date=date(2025, 1, 3),  # Uma sexta
        )
        dates = calculate_dates(rec, self.TODAY, self.HORIZON)
        assert len(dates) > 0
        assert all(d.weekday() == 4 for d in dates)

    def test_weekly_does_not_generate_before_start_date(self) -> None:
        """start_date no futuro → nenhuma data antes de start_date."""
        future_start = date(2025, 7, 28)  # Monday, 2 semanas no futuro
        rec = make_recurrence(frequency="weekly", start_date=future_start, day_of_week=0)
        dates = calculate_dates(rec, self.TODAY, self.HORIZON)
        assert all(d >= future_start for d in dates)

    def test_weekly_does_not_generate_after_end_date(self) -> None:
        """end_date limita as datas geradas."""
        end = date(2025, 7, 21)
        rec = make_recurrence(
            frequency="weekly",
            start_date=date(2025, 1, 6),
            end_date=end,
            day_of_week=0,
        )
        dates = calculate_dates(rec, self.TODAY, self.HORIZON)
        assert all(d <= end for d in dates)
        assert date(2025, 7, 28) not in dates

    def test_returns_empty_when_end_date_before_today(self) -> None:
        """end_date no passado → lista vazia."""
        rec = make_recurrence(
            frequency="weekly",
            start_date=date(2025, 1, 6),
            end_date=date(2025, 7, 10),  # antes de TODAY=7/14
            day_of_week=0,
        )
        assert calculate_dates(rec, self.TODAY, self.HORIZON) == []

    def test_biweekly_has_14_day_spacing(self) -> None:
        """biweekly interval=1 → espaçamento de 14 dias entre datas consecutivas."""
        rec = make_recurrence(
            frequency="biweekly",
            interval=1,
            start_date=date(2025, 1, 6),
            day_of_week=0,
        )
        dates = calculate_dates(rec, self.TODAY, self.HORIZON)
        if len(dates) >= 2:
            diffs = [(dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)]
            assert all(d == 14 for d in diffs)

    def test_biweekly_interval_2_has_28_day_spacing(self) -> None:
        """biweekly interval=2 → espaçamento de 28 dias."""
        rec = make_recurrence(
            frequency="biweekly",
            interval=2,
            start_date=date(2025, 1, 6),
            day_of_week=0,
        )
        dates = calculate_dates(rec, self.TODAY, self.HORIZON)
        if len(dates) >= 2:
            diffs = [(dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)]
            assert all(d == 28 for d in diffs)

    def test_weekly_interval_2_every_14_days(self) -> None:
        """weekly interval=2 → espaçamento de 14 dias (a cada 2 semanas)."""
        rec = make_recurrence(
            frequency="weekly",
            interval=2,
            start_date=date(2025, 1, 6),
            day_of_week=0,
        )
        dates = calculate_dates(rec, self.TODAY, self.HORIZON)
        if len(dates) >= 2:
            diffs = [(dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)]
            assert all(d == 14 for d in diffs)

    def test_monthly_generates_same_day_each_month(self) -> None:
        """monthly com start_date=2025-01-14 → dia 14 de cada mês."""
        rec = make_recurrence(
            frequency="monthly",
            interval=1,
            day_of_week=None,
            start_date=date(2025, 1, 14),
        )
        # Usa horizon_days=31 para que 2025-08-14 (hoje + 31 dias) também seja incluído.
        # Com HORIZON=30, o limite seria 2025-08-13 e 8/14 ficaria fora da janela.
        dates = calculate_dates(rec, self.TODAY, 31)
        assert date(2025, 7, 14) in dates
        assert date(2025, 8, 14) in dates

    def test_monthly_without_end_date_stops_at_horizon(self) -> None:
        """Sem end_date, monthly não ultrapassa hoje+horizon_days."""
        rec = make_recurrence(
            frequency="monthly",
            interval=1,
            day_of_week=None,
            start_date=date(2025, 1, 14),
        )
        horizon_end = self.TODAY + timedelta(days=self.HORIZON)
        dates = calculate_dates(rec, self.TODAY, self.HORIZON)
        assert all(d <= horizon_end for d in dates)

    def test_monthly_with_end_date_stops_at_end_date(self) -> None:
        """end_date limita a geração mensal."""
        rec = make_recurrence(
            frequency="monthly",
            interval=1,
            day_of_week=None,
            start_date=date(2025, 1, 14),
            end_date=date(2025, 7, 20),
        )
        dates = calculate_dates(rec, self.TODAY, self.HORIZON)
        assert date(2025, 7, 14) in dates  # dentro do end_date
        assert date(2025, 8, 14) not in dates  # > end_date


# ---------------------------------------------------------------------------
# TestGenerateRecurringSessions — job async com mocks
# ---------------------------------------------------------------------------


class TestGenerateRecurringSessions:
    def _mock_execute_result(self, rows: list) -> MagicMock:
        """Simula session.execute(...).scalars().all() retornando rows."""
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = rows
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        return mock_result

    async def test_creates_session_for_each_calculated_date(self, mock_session) -> None:
        """Para cada data retornada por calculate_dates, sessions_repo.create é chamado."""
        prof_id = uuid4()
        rec = make_recurrence(professional_id=prof_id)

        mock_session.execute = AsyncMock(return_value=self._mock_execute_result([rec]))
        mock_sessions_repo = AsyncMock()
        mock_sessions_repo.find_by_exact.return_value = None  # slot livre

        with (
            patch("jobs.tasks.recurrences.async_session_maker", return_value=mock_session),
            patch("jobs.tasks.recurrences.set_tenant_context", new_callable=AsyncMock),
            patch("jobs.tasks.recurrences.SessionsRepository", return_value=mock_sessions_repo),
            patch("jobs.tasks.recurrences.calculate_dates", return_value=[date(2025, 7, 14)]),
        ):
            await generate_recurring_sessions()

        mock_sessions_repo.create.assert_called_once()

    async def test_skips_already_existing_session(self, mock_session) -> None:
        """Se find_by_exact retorna uma sessão existente, create NÃO é chamado."""
        rec = make_recurrence()
        mock_session.execute = AsyncMock(return_value=self._mock_execute_result([rec]))
        mock_sessions_repo = AsyncMock()
        existing_session = MagicMock()
        mock_sessions_repo.find_by_exact.return_value = existing_session  # já existe

        with (
            patch("jobs.tasks.recurrences.async_session_maker", return_value=mock_session),
            patch("jobs.tasks.recurrences.set_tenant_context", new_callable=AsyncMock),
            patch("jobs.tasks.recurrences.SessionsRepository", return_value=mock_sessions_repo),
            patch("jobs.tasks.recurrences.calculate_dates", return_value=[date(2025, 7, 14)]),
        ):
            await generate_recurring_sessions()

        mock_sessions_repo.create.assert_not_called()

    async def test_set_tenant_context_called_with_professional_id(self, mock_session) -> None:
        """set_tenant_context é chamado com o professional_id da recorrência."""
        prof_id = uuid4()
        rec = make_recurrence(professional_id=prof_id)
        mock_session.execute = AsyncMock(return_value=self._mock_execute_result([rec]))
        mock_sessions_repo = AsyncMock()
        mock_sessions_repo.find_by_exact.return_value = None

        mock_set_tenant = AsyncMock()

        with (
            patch("jobs.tasks.recurrences.async_session_maker", return_value=mock_session),
            patch("jobs.tasks.recurrences.set_tenant_context", mock_set_tenant),
            patch("jobs.tasks.recurrences.SessionsRepository", return_value=mock_sessions_repo),
            patch("jobs.tasks.recurrences.calculate_dates", return_value=[date(2025, 7, 14)]),
        ):
            await generate_recurring_sessions()

        # Verifica que foi chamado com a sessão e o professional_id correto
        mock_set_tenant.assert_called_once_with(mock_session, prof_id)

    async def test_error_in_one_professional_does_not_stop_others(self, mock_session) -> None:
        """Exceção num profissional é capturada; o loop continua para os demais."""
        prof_id_a = uuid4()
        prof_id_b = uuid4()
        rec_a = make_recurrence(professional_id=prof_id_a)
        rec_b = make_recurrence(professional_id=prof_id_b)

        mock_session.execute = AsyncMock(return_value=self._mock_execute_result([rec_a, rec_b]))

        call_count = 0

        async def fake_set_tenant(session, pid):
            nonlocal call_count
            call_count += 1
            if pid == prof_id_a:
                raise RuntimeError("Simulated DB error")

        mock_sessions_repo = AsyncMock()
        mock_sessions_repo.find_by_exact.return_value = None

        with (
            patch("jobs.tasks.recurrences.async_session_maker", return_value=mock_session),
            patch("jobs.tasks.recurrences.set_tenant_context", side_effect=fake_set_tenant),
            patch("jobs.tasks.recurrences.SessionsRepository", return_value=mock_sessions_repo),
            patch("jobs.tasks.recurrences.calculate_dates", return_value=[date(2025, 7, 14)]),
        ):
            await generate_recurring_sessions()

        # prof_b deve ter sido processado mesmo com erro em prof_a
        assert call_count == 2

    async def test_no_recurrences_returns_early(self, mock_session) -> None:
        """Sem recorrências ativas, commit não é chamado e set_tenant_context não é chamado."""
        mock_session.execute = AsyncMock(return_value=self._mock_execute_result([]))

        with (
            patch("jobs.tasks.recurrences.async_session_maker", return_value=mock_session),
            patch(
                "jobs.tasks.recurrences.set_tenant_context", new_callable=AsyncMock
            ) as mock_set_tenant,
        ):
            await generate_recurring_sessions()

        mock_set_tenant.assert_not_called()
        mock_session.commit.assert_not_called()
