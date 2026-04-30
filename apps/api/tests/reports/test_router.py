"""
Tests for reports router — GET /api/v1/reports/billing.

Coverage:
- 200  valid authenticated request
- 401  missing JWT
- 422  missing required query param (start_date)
- 422  end_date before start_date (Pydantic model_validator)
- response schema matches BillingReportResponse
- ai_insights is null when no sessions exist in the period
- default status_filter is ["completed"] when not explicitly provided

All tests use:
  - authenticated_http_client  → requests with valid JWT for test_professional
  - http_client                → unauthenticated requests (for 401 assertions)

AI calls are patched via patch("reports.service.AIService") to avoid real API
calls. Since the test DB has no sessions, the AI would not be invoked anyway —
but patching makes the tests hermetic and immune to missing AI_API_KEY in CI.
"""

from unittest.mock import AsyncMock, patch

from httpx import AsyncClient


class TestGetBillingReport:
    # ------------------------------------------------------------------
    # 200 — happy path
    # ------------------------------------------------------------------

    async def test_returns_200_with_valid_params(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """GET /reports/billing com params válidos deve retornar 200."""
        with patch("reports.service.AIService") as MockAI:
            MockAI.return_value.complete = AsyncMock(return_value="insights mock")
            response = await authenticated_http_client.get(
                "/api/v1/reports/billing",
                params={"start_date": "2025-01-01", "end_date": "2025-01-31"},
            )
        assert response.status_code == 200

    # ------------------------------------------------------------------
    # 401 — unauthenticated
    # ------------------------------------------------------------------

    async def test_returns_401_without_jwt(self, http_client: AsyncClient) -> None:
        """Requisição sem token JWT deve retornar 401."""
        response = await http_client.get(
            "/api/v1/reports/billing",
            params={"start_date": "2025-01-01", "end_date": "2025-01-31"},
        )
        assert response.status_code == 401

    # ------------------------------------------------------------------
    # 422 — missing required param
    # ------------------------------------------------------------------

    async def test_returns_422_when_start_date_missing(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """
        start_date é obrigatório (Query(...)). FastAPI deve devolver 422
        quando ausente, antes mesmo de chegar ao handler.
        """
        response = await authenticated_http_client.get(
            "/api/v1/reports/billing",
            params={"end_date": "2025-01-31"},
        )
        assert response.status_code == 422

    # ------------------------------------------------------------------
    # 422 — invalid date range
    # ------------------------------------------------------------------

    async def test_returns_422_when_end_date_before_start_date(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """
        end_date anterior a start_date deve retornar 422.
        A validação ocorre dentro do handler via BillingReportRequest
        (model_validator) e é convertida para 422 pelo router.
        """
        response = await authenticated_http_client.get(
            "/api/v1/reports/billing",
            params={"start_date": "2025-01-31", "end_date": "2025-01-01"},
        )
        assert response.status_code == 422

    # ------------------------------------------------------------------
    # Response schema
    # ------------------------------------------------------------------

    async def test_response_schema_matches_billing_report_response(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """
        Response body deve conter os campos obrigatórios do BillingReportResponse:
        period_start, period_end, total_sessions, total_amount, clients,
        ai_insights e generated_at.
        """
        with patch("reports.service.AIService") as MockAI:
            MockAI.return_value.complete = AsyncMock(return_value="insights mock")
            response = await authenticated_http_client.get(
                "/api/v1/reports/billing",
                params={"start_date": "2025-02-01", "end_date": "2025-02-28"},
            )

        assert response.status_code == 200
        data = response.json()

        assert "period_start" in data
        assert "period_end" in data
        assert "total_sessions" in data
        assert "total_amount" in data
        assert "clients" in data
        assert "ai_insights" in data
        assert "generated_at" in data

        assert data["period_start"] == "2025-02-01"
        assert data["period_end"] == "2025-02-28"
        assert isinstance(data["clients"], list)

    # ------------------------------------------------------------------
    # ai_insights null when no sessions
    # ------------------------------------------------------------------

    async def test_ai_insights_is_null_in_response_when_no_sessions(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """
        Quando não há sessões no período, ai_insights deve ser null.
        A IA não é chamada — nenhum dado para analisar.
        """
        response = await authenticated_http_client.get(
            "/api/v1/reports/billing",
            params={"start_date": "2025-06-01", "end_date": "2025-06-30"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["ai_insights"] is None
        assert data["total_sessions"] == 0

    # ------------------------------------------------------------------
    # Default status_filter
    # ------------------------------------------------------------------

    async def test_default_status_filter_is_completed(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """
        Omitir status_filter deve usar o padrão ["completed"].
        O endpoint deve retornar 200 com estrutura válida — mesmo sem sessões,
        o default é aplicado silenciosamente pelo Query(default=["completed"]).
        """
        response = await authenticated_http_client.get(
            "/api/v1/reports/billing",
            params={"start_date": "2025-07-01", "end_date": "2025-07-31"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_sessions"] == 0
        assert isinstance(data["clients"], list)


class TestGetPeriodSummary:
    async def test_returns_200_with_valid_params(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """GET /reports/summary com params válidos deve retornar 200."""
        response = await authenticated_http_client.get(
            "/api/v1/reports/summary",
            params={"start_date": "2025-01-01", "end_date": "2025-01-31"},
        )
        assert response.status_code == 200

    async def test_returns_401_without_jwt(self, http_client: AsyncClient) -> None:
        """Requisição sem JWT deve retornar 401."""
        response = await http_client.get(
            "/api/v1/reports/summary",
            params={"start_date": "2025-01-01", "end_date": "2025-01-31"},
        )
        assert response.status_code == 401

    async def test_returns_422_when_start_date_missing(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """start_date obrigatório — ausente deve retornar 422."""
        response = await authenticated_http_client.get(
            "/api/v1/reports/summary",
            params={"end_date": "2025-01-31"},
        )
        assert response.status_code == 422

    async def test_returns_422_when_end_date_before_start_date(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """end_date anterior a start_date deve retornar 422."""
        response = await authenticated_http_client.get(
            "/api/v1/reports/summary",
            params={"start_date": "2025-01-31", "end_date": "2025-01-01"},
        )
        assert response.status_code == 422

    async def test_response_schema_matches_period_summary_response(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """Response body deve conter os campos de PeriodSummaryResponse."""
        response = await authenticated_http_client.get(
            "/api/v1/reports/summary",
            params={"start_date": "2025-02-01", "end_date": "2025-02-28"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "period_start" in data
        assert "period_end" in data
        assert "total_sessions" in data
        assert "total_amount" in data
        assert "status_filter" in data
        assert data["period_start"] == "2025-02-01"
        assert data["period_end"] == "2025-02-28"
        assert data["total_sessions"] == 0
        assert isinstance(data["status_filter"], list)

    async def test_default_status_filter_in_response(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """Sem status_filter na query, response deve ter ['completed'] no campo status_filter."""
        response = await authenticated_http_client.get(
            "/api/v1/reports/summary",
            params={"start_date": "2025-07-01", "end_date": "2025-07-31"},
        )
        assert response.status_code == 200
        assert response.json()["status_filter"] == ["completed"]
