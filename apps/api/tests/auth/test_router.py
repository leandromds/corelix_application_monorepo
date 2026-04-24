"""Tests for auth router -- TDD Red phase."""

import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _register(client: AsyncClient, email: str = "router@example.com") -> None:
    """Register a professional via the API."""
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123", "full_name": "Router Test"},
    )


async def _login(client: AsyncClient, email: str = "router@example.com") -> dict:
    """Login and return the JSON body (access_token, token_type)."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "password123"},
    )
    return response.json()


# ---------------------------------------------------------------------------
# POST /auth/register
# ---------------------------------------------------------------------------


class TestRegister:
    async def test_register_returns_201(self, http_client: AsyncClient) -> None:
        """Registro bem-sucedido deve retornar 201 com ProfessionalResponse."""
        response = await http_client.post(
            "/api/v1/auth/register",
            json={
                "email": "new@example.com",
                "password": "password123",
                "full_name": "New User",
            },
        )
        assert response.status_code == 201

    async def test_register_returns_professional_response_fields(
        self, http_client: AsyncClient
    ) -> None:
        """Resposta deve conter os campos esperados e NUNCA password_hash."""
        response = await http_client.post(
            "/api/v1/auth/register",
            json={
                "email": "fields@example.com",
                "password": "password123",
                "full_name": "Fields Test",
            },
        )
        data = response.json()

        assert "id" in data
        assert "email" in data
        assert "full_name" in data
        assert "created_at" in data
        assert "password_hash" not in data

    async def test_register_conflict_returns_409(
        self, http_client: AsyncClient
    ) -> None:
        """Registrar email duplicado deve retornar 409 Conflict."""
        payload = {
            "email": "dup@example.com",
            "password": "password123",
            "full_name": "Dup User",
        }
        await http_client.post("/api/v1/auth/register", json=payload)
        response = await http_client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 409

    async def test_register_invalid_email_returns_422(
        self, http_client: AsyncClient
    ) -> None:
        """Email invalido deve retornar 422 Unprocessable Entity."""
        response = await http_client.post(
            "/api/v1/auth/register",
            json={
                "email": "not-an-email",
                "password": "password123",
                "full_name": "Invalid Email",
            },
        )
        assert response.status_code == 422

    async def test_register_with_optional_specialty_and_bio(
        self, http_client: AsyncClient
    ) -> None:
        """Registro com specialty e bio deve retornar 201."""
        response = await http_client.post(
            "/api/v1/auth/register",
            json={
                "email": "optional@example.com",
                "password": "password123",
                "full_name": "Optional Fields",
                "specialty": "Fisioterapia",
                "bio": "Professional bio text",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["specialty"] == "Fisioterapia"
        assert data["bio"] == "Professional bio text"


# ---------------------------------------------------------------------------
# POST /auth/login
# ---------------------------------------------------------------------------


class TestLogin:
    async def test_login_returns_access_token(
        self, http_client: AsyncClient
    ) -> None:
        """Login bem-sucedido deve retornar access_token no body."""
        await _register(http_client, "login@example.com")

        response = await http_client.post(
            "/api/v1/auth/login",
            json={"email": "login@example.com", "password": "password123"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_sets_httponly_cookie(
        self, http_client: AsyncClient
    ) -> None:
        """Login deve setar o cookie refresh_token."""
        await _register(http_client, "cookie@example.com")

        response = await http_client.post(
            "/api/v1/auth/login",
            json={"email": "cookie@example.com", "password": "password123"},
        )

        assert "refresh_token" in response.cookies

    async def test_login_wrong_email_returns_401(
        self, http_client: AsyncClient
    ) -> None:
        """Login com email inexistente deve retornar 401."""
        response = await http_client.post(
            "/api/v1/auth/login",
            json={"email": "ghost@example.com", "password": "password123"},
        )
        assert response.status_code == 401

    async def test_login_wrong_password_returns_401(
        self, http_client: AsyncClient
    ) -> None:
        """Login com senha errada deve retornar 401."""
        await _register(http_client, "wrongpw@example.com")

        response = await http_client.post(
            "/api/v1/auth/login",
            json={"email": "wrongpw@example.com", "password": "wrongpassword"},
        )
        assert response.status_code == 401

    async def test_login_does_not_return_refresh_token_in_body(
        self, http_client: AsyncClient
    ) -> None:
        """O refresh_token NUNCA deve aparecer no response body."""
        await _register(http_client, "nobodytoken@example.com")

        response = await http_client.post(
            "/api/v1/auth/login",
            json={"email": "nobodytoken@example.com", "password": "password123"},
        )

        data = response.json()
        assert "refresh_token" not in data


# ---------------------------------------------------------------------------
# POST /auth/refresh
# ---------------------------------------------------------------------------


class TestRefresh:
    async def test_refresh_returns_new_access_token(
        self, http_client: AsyncClient
    ) -> None:
        """Refresh com cookie valido deve retornar novo access_token."""
        await _register(http_client, "refresh@example.com")
        await http_client.post(
            "/api/v1/auth/login",
            json={"email": "refresh@example.com", "password": "password123"},
        )

        # Cookie is automatically included by the AsyncClient
        response = await http_client.post("/api/v1/auth/refresh")

        assert response.status_code == 200
        assert "access_token" in response.json()

    async def test_refresh_without_cookie_returns_401(
        self, http_client: AsyncClient
    ) -> None:
        """Refresh sem cookie deve retornar 401."""
        response = await http_client.post("/api/v1/auth/refresh")
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# POST /auth/logout
# ---------------------------------------------------------------------------


class TestLogout:
    async def test_logout_returns_204(self, http_client: AsyncClient) -> None:
        """Logout deve retornar 204 No Content."""
        await _register(http_client, "logout@example.com")
        await http_client.post(
            "/api/v1/auth/login",
            json={"email": "logout@example.com", "password": "password123"},
        )

        response = await http_client.post("/api/v1/auth/logout")
        assert response.status_code == 204

    async def test_logout_without_cookie_is_idempotent(
        self, http_client: AsyncClient
    ) -> None:
        """Logout sem cookie deve retornar 204 (idempotente)."""
        response = await http_client.post("/api/v1/auth/logout")
        assert response.status_code == 204

    async def test_logout_invalidates_refresh_token(
        self, http_client: AsyncClient
    ) -> None:
        """Apos logout, tentar refresh deve falhar com 401."""
        await _register(http_client, "logoutinval@example.com")
        await http_client.post(
            "/api/v1/auth/login",
            json={"email": "logoutinval@example.com", "password": "password123"},
        )
        await http_client.post("/api/v1/auth/logout")

        # Try to refresh after logout
        response = await http_client.post("/api/v1/auth/refresh")
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# POST /auth/logout-all
# ---------------------------------------------------------------------------


class TestLogoutAll:
    async def test_logout_all_returns_204(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """logout-all deve retornar 204 para usuario autenticado."""
        response = await authenticated_http_client.post("/api/v1/auth/logout-all")
        assert response.status_code == 204

    async def test_logout_all_requires_authentication(
        self, http_client: AsyncClient
    ) -> None:
        """logout-all sem JWT deve retornar 401."""
        response = await http_client.post("/api/v1/auth/logout-all")
        assert response.status_code == 401
