"""
Tests for ReportsService.

Testa a lógica de agregação em Python e a integração com AIService.
O banco não é necessário para testes de service — mockamos o repository.
"""

from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from core.exceptions import ExternalServiceError
from reports.schemas import BillingReportRequest, BillingReportResponse
from reports.service import ReportsService

# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture
def service() -> ReportsService:
    """
    ReportsService com repository e AI completamente mockados.

    Substituímos self.repository e self.ai após a instância ser criada
    para evitar dependência de banco ou de chave de API nos testes unitários.
    """
    mock_db = AsyncMock()
    svc = ReportsService(mock_db)
    svc.repository = AsyncMock()
    svc.ai = AsyncMock()
    return svc


@pytest.fixture
def default_request() -> BillingReportRequest:
    """Request padrão para Janeiro 2025."""
    return BillingReportRequest(
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 31),
    )


@pytest.fixture
def mock_repo_rows_one_session() -> list:
    """Uma Row simulando o retorno de find_sessions_in_period."""
    row = MagicMock()
    row.id = uuid4()
    row.client_id = uuid4()
    row.client_name = "Alice"
    row.scheduled_at = datetime(2025, 1, 15, 10, 0, tzinfo=UTC)
    row.duration_minutes = 60
    row.price = Decimal("150.00")
    row.status = "completed"
    row.notes = None
    return [row]


def _make_row(
    *,
    client_id=None,
    client_name: str = "Alice",
    price: Decimal = Decimal("150.00"),
    status: str = "completed",
) -> MagicMock:
    """Fábrica de Row mocks para reduzir boilerplate nos testes."""
    row = MagicMock()
    row.id = uuid4()
    row.client_id = client_id or uuid4()
    row.client_name = client_name
    row.scheduled_at = datetime(2025, 1, 10, 10, 0, tzinfo=UTC)
    row.duration_minutes = 60
    row.price = price
    row.status = status
    row.notes = None
    return row


# ===========================================================================
# TestReportsServiceGenerateBillingReport
# ===========================================================================


class TestReportsServiceGenerateBillingReport:
    # -----------------------------------------------------------------------
    # 1. Empty report
    # -----------------------------------------------------------------------

    async def test_returns_empty_report_when_no_sessions(
        self,
        service: ReportsService,
        default_request: BillingReportRequest,
    ) -> None:
        """
        Sem sessões no período: total_sessions=0, clients=[], ai_insights=None.
        A IA NÃO deve ser chamada — não há dados para analisar.
        """
        service.repository.find_sessions_in_period.return_value = []

        result = await service.generate_billing_report(
            professional_name="Dr. Test",
            professional_specialty="Fisioterapia",
            request=default_request,
        )

        assert isinstance(result, BillingReportResponse)
        assert result.total_sessions == 0
        assert result.clients == []
        assert result.ai_insights is None
        service.ai.complete.assert_not_called()

    # -----------------------------------------------------------------------
    # 2. Aggregation by client
    # -----------------------------------------------------------------------

    async def test_aggregates_sessions_by_client(
        self,
        service: ReportsService,
        default_request: BillingReportRequest,
    ) -> None:
        """
        Duas sessões do mesmo cliente devem gerar um único ClientBillingEntry
        com session_count=2.
        """
        client_id = uuid4()
        rows = [
            _make_row(client_id=client_id, client_name="Alice"),
            _make_row(client_id=client_id, client_name="Alice"),
        ]
        service.repository.find_sessions_in_period.return_value = rows
        service.ai.complete.return_value = "Insights"

        result = await service.generate_billing_report(
            professional_name="Dr. Test",
            professional_specialty="Fisioterapia",
            request=default_request,
        )

        assert len(result.clients) == 1
        assert result.clients[0].session_count == 2

    # -----------------------------------------------------------------------
    # 3. Total amount (global)
    # -----------------------------------------------------------------------

    async def test_total_amount_is_sum_of_all_session_prices(
        self,
        service: ReportsService,
        default_request: BillingReportRequest,
    ) -> None:
        """total_amount deve ser a soma dos preços de todas as sessões."""
        rows = [
            _make_row(price=Decimal("100.00")),
            _make_row(price=Decimal("200.00")),
            _make_row(price=Decimal("50.00")),
        ]
        service.repository.find_sessions_in_period.return_value = rows
        service.ai.complete.return_value = "Insights"

        result = await service.generate_billing_report(
            professional_name="Dr. Test",
            professional_specialty="Fisioterapia",
            request=default_request,
        )

        assert result.total_amount == Decimal("350.00")

    # -----------------------------------------------------------------------
    # 4. Per-client total amount
    # -----------------------------------------------------------------------

    async def test_client_billing_total_amount_is_sum_of_client_sessions(
        self,
        service: ReportsService,
        default_request: BillingReportRequest,
    ) -> None:
        """
        ClientBillingEntry.total_amount deve somar apenas as sessões daquele
        cliente — não de todos os clientes do período.
        """
        client_id = uuid4()
        rows = [
            _make_row(client_id=client_id, client_name="Carol", price=Decimal("100.00")),
            _make_row(client_id=client_id, client_name="Carol", price=Decimal("200.00")),
        ]
        service.repository.find_sessions_in_period.return_value = rows
        service.ai.complete.return_value = "Insights"

        result = await service.generate_billing_report(
            professional_name="Dr. Test",
            professional_specialty="Fisioterapia",
            request=default_request,
        )

        assert result.clients[0].total_amount == Decimal("300.00")

    # -----------------------------------------------------------------------
    # 5. AI insights — success path
    # -----------------------------------------------------------------------

    async def test_ai_insights_populated_when_ai_succeeds(
        self,
        service: ReportsService,
        mock_repo_rows_one_session: list,
        default_request: BillingReportRequest,
    ) -> None:
        """
        Quando a IA retorna com sucesso, ai_insights deve conter exatamente
        a string devolvida pelo mock.
        """
        service.repository.find_sessions_in_period.return_value = mock_repo_rows_one_session
        service.ai.complete.return_value = "Insights gerados com sucesso"

        result = await service.generate_billing_report(
            professional_name="Dr. Test",
            professional_specialty="Fisioterapia",
            request=default_request,
        )

        assert result.ai_insights == "Insights gerados com sucesso"

    # -----------------------------------------------------------------------
    # 6. AI insights — graceful degradation
    # -----------------------------------------------------------------------

    async def test_ai_insights_is_none_when_ai_raises_external_service_error(
        self,
        service: ReportsService,
        mock_repo_rows_one_session: list,
        default_request: BillingReportRequest,
    ) -> None:
        """
        Falha na API de IA (ExternalServiceError) deve resultar em
        ai_insights=None sem propagar a exceção para o caller.

        Degradação graciosa: o relatório financeiro não deve falhar
        por indisponibilidade do serviço de IA.
        """
        service.repository.find_sessions_in_period.return_value = mock_repo_rows_one_session
        service.ai.complete.side_effect = ExternalServiceError(
            message="AI API unavailable",
            service_name="ai",
        )

        result = await service.generate_billing_report(
            professional_name="Dr. Test",
            professional_specialty="Fisioterapia",
            request=default_request,
        )

        assert result.ai_insights is None

    # -----------------------------------------------------------------------
    # 7. AI not called when empty
    # -----------------------------------------------------------------------

    async def test_ai_not_called_when_sessions_empty(
        self,
        service: ReportsService,
        default_request: BillingReportRequest,
    ) -> None:
        """
        Sem sessões no período, complete() não deve ser invocado.
        Evita custo de token e latência desnecessários.
        """
        service.repository.find_sessions_in_period.return_value = []

        await service.generate_billing_report(
            professional_name="Dr. Test",
            professional_specialty="Fisioterapia",
            request=default_request,
        )

        service.ai.complete.assert_not_called()

    # -----------------------------------------------------------------------
    # 8. Two distinct clients
    # -----------------------------------------------------------------------

    async def test_two_clients_generate_two_entries(
        self,
        service: ReportsService,
        default_request: BillingReportRequest,
    ) -> None:
        """Dois clientes distintos devem gerar dois ClientBillingEntry separados."""
        rows = [
            _make_row(client_name="Alice"),
            _make_row(client_name="Bob"),
        ]
        service.repository.find_sessions_in_period.return_value = rows
        service.ai.complete.return_value = "Insights"

        result = await service.generate_billing_report(
            professional_name="Dr. Test",
            professional_specialty="Fisioterapia",
            request=default_request,
        )

        assert len(result.clients) == 2

    # -----------------------------------------------------------------------
    # 9. Period dates propagated correctly
    # -----------------------------------------------------------------------

    async def test_response_has_correct_period_dates(
        self,
        service: ReportsService,
    ) -> None:
        """
        period_start e period_end na resposta devem refletir exatamente
        as datas do BillingReportRequest, independente dos dados retornados.
        """
        request = BillingReportRequest(
            start_date=date(2025, 3, 1),
            end_date=date(2025, 3, 31),
        )
        service.repository.find_sessions_in_period.return_value = []

        result = await service.generate_billing_report(
            professional_name="Dr. Test",
            professional_specialty="Fisioterapia",
            request=request,
        )

        assert result.period_start == date(2025, 3, 1)
        assert result.period_end == date(2025, 3, 31)
