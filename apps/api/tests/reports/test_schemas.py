"""
Tests for reports schemas — BillingReportRequest and BillingReportResponse.

Coverage:
- BillingReportRequest  : date range validation, default fields, optional fields
- BillingReportResponse : correct structure, optional ai_insights, Decimal types

These are pure Pydantic tests — no database required.
"""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from reports.schemas import (
    BillingReportRequest,
    BillingReportResponse,
    ClientBillingEntry,
    SessionEntry,
)

# ===========================================================================
# BillingReportRequest
# ===========================================================================


class TestBillingReportRequest:
    # -----------------------------------------------------------------------
    # Happy path
    # -----------------------------------------------------------------------

    def test_valid_request_accepted(self) -> None:
        """Request com start_date e end_date válidos deve ser aceito."""
        req = BillingReportRequest(
            start_date=date(2025, 1, 1),
            end_date=date(2025, 3, 31),
        )
        assert req.start_date == date(2025, 1, 1)
        assert req.end_date == date(2025, 3, 31)

    def test_default_status_filter_is_completed(self) -> None:
        """Sem status_filter explícito, o padrão deve ser ['completed']."""
        req = BillingReportRequest(
            start_date=date(2025, 1, 1),
            end_date=date(2025, 3, 31),
        )
        assert req.status_filter == ["completed"]

    def test_client_id_is_optional_defaults_to_none(self) -> None:
        """client_id não fornecido deve resultar em None."""
        req = BillingReportRequest(
            start_date=date(2025, 1, 1),
            end_date=date(2025, 3, 31),
        )
        assert req.client_id is None

    # -----------------------------------------------------------------------
    # Date range validation
    # -----------------------------------------------------------------------

    def test_end_date_before_start_date_raises_validation_error(self) -> None:
        """end_date anterior a start_date deve levantar ValidationError."""
        with pytest.raises(ValidationError):
            BillingReportRequest(
                start_date=date(2025, 3, 31),
                end_date=date(2025, 1, 1),
            )

    def test_same_start_and_end_date_is_valid(self) -> None:
        """start_date == end_date (range de 0 dias) deve ser aceito."""
        req = BillingReportRequest(
            start_date=date(2025, 6, 15),
            end_date=date(2025, 6, 15),
        )
        assert req.start_date == req.end_date

    def test_range_of_366_days_raises_validation_error(self) -> None:
        """Range de 366 dias deve levantar ValidationError (excede o limite de 365)."""
        with pytest.raises(ValidationError):
            BillingReportRequest(
                start_date=date(2025, 1, 1),
                end_date=date(2026, 1, 2),  # 366 dias
            )

    def test_range_of_365_days_is_valid(self) -> None:
        """Range de exatamente 365 dias deve ser aceito."""
        req = BillingReportRequest(
            start_date=date(2025, 1, 1),
            end_date=date(2026, 1, 1),  # 365 dias
        )
        assert req.start_date == date(2025, 1, 1)
        assert req.end_date == date(2026, 1, 1)


# ===========================================================================
# BillingReportResponse
# ===========================================================================


class TestBillingReportResponse:
    # -----------------------------------------------------------------------
    # Full structure
    # -----------------------------------------------------------------------

    def test_response_built_correctly_with_clients_and_insights(self) -> None:
        """Response com clients e ai_insights deve ser construída corretamente."""
        session_id = uuid4()
        client_id = uuid4()
        now = datetime.now(UTC)

        entry = SessionEntry(
            session_id=session_id,
            client_id=client_id,
            client_name="Ana Lima",
            scheduled_at=now,
            duration_minutes=60,
            price=Decimal("200.00"),
            status="completed",
            notes=None,
        )

        client_billing = ClientBillingEntry(
            client_id=client_id,
            client_name="Ana Lima",
            session_count=1,
            total_amount=Decimal("200.00"),
            sessions=[entry],
        )

        response = BillingReportResponse(
            period_start=date(2025, 1, 1),
            period_end=date(2025, 3, 31),
            total_sessions=1,
            total_amount=Decimal("200.00"),
            clients=[client_billing],
            ai_insights="Boa performance no trimestre.",
            generated_at=now,
        )

        assert response.total_sessions == 1
        assert response.total_amount == Decimal("200.00")
        assert len(response.clients) == 1
        assert response.clients[0].client_name == "Ana Lima"
        assert response.ai_insights == "Boa performance no trimestre."
        assert response.period_start == date(2025, 1, 1)
        assert response.period_end == date(2025, 3, 31)

    def test_response_ai_insights_can_be_none(self) -> None:
        """ai_insights pode ser None quando a análise IA não foi solicitada."""
        now = datetime.now(UTC)
        response = BillingReportResponse(
            period_start=date(2025, 1, 1),
            period_end=date(2025, 3, 31),
            total_sessions=0,
            total_amount=Decimal("0.00"),
            clients=[],
            ai_insights=None,
            generated_at=now,
        )
        assert response.ai_insights is None

    # -----------------------------------------------------------------------
    # Decimal types
    # -----------------------------------------------------------------------

    def test_session_entry_price_is_decimal(self) -> None:
        """SessionEntry.price deve ser do tipo Decimal."""
        entry = SessionEntry(
            session_id=uuid4(),
            client_id=uuid4(),
            client_name="Beatriz Santos",
            scheduled_at=datetime.now(UTC),
            duration_minutes=50,
            price=Decimal("150.00"),
            status="completed",
            notes=None,
        )
        assert isinstance(entry.price, Decimal)

    def test_client_billing_total_amount_is_decimal(self) -> None:
        """ClientBillingEntry.total_amount deve ser do tipo Decimal."""
        entry = SessionEntry(
            session_id=uuid4(),
            client_id=uuid4(),
            client_name="Carlos Pereira",
            scheduled_at=datetime.now(UTC),
            duration_minutes=60,
            price=Decimal("300.00"),
            status="completed",
            notes=None,
        )
        billing = ClientBillingEntry(
            client_id=uuid4(),
            client_name="Carlos Pereira",
            session_count=1,
            total_amount=Decimal("300.00"),
            sessions=[entry],
        )
        assert isinstance(billing.total_amount, Decimal)
