"""
Tests for the /health endpoint.

TDD — Red -> Green -> Refactor.
The endpoint must return 200 without authentication.
"""

from httpx import AsyncClient


class TestHealthCheck:
    """Tests for GET /health."""

    async def test_health_returns_200(self, http_client: AsyncClient) -> None:
        """Health endpoint must return 200 without any auth header."""
        response = await http_client.get("/health")
        assert response.status_code == 200

    async def test_health_response_has_status_field(self, http_client: AsyncClient) -> None:
        """Response body must contain a 'status' key."""
        response = await http_client.get("/health")
        data = response.json()
        assert "status" in data

    async def test_health_no_auth_required(self, http_client: AsyncClient) -> None:
        """Health endpoint must not require Authorization header."""
        response = await http_client.get("/health")
        # Must not be 401 or 403
        assert response.status_code not in (401, 403)
