"""Tests for professionals router -- TDD Red phase."""

from httpx import AsyncClient


class TestGetMe:
    async def test_get_me_returns_200(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """GET /professionals/me deve retornar 200 para usuario autenticado."""
        response = await authenticated_http_client.get("/api/v1/professionals/me")
        assert response.status_code == 200

    async def test_get_me_returns_professional_response(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """Resposta deve conter os campos do ProfessionalResponse sem password_hash."""
        response = await authenticated_http_client.get("/api/v1/professionals/me")
        data = response.json()

        assert "id" in data
        assert "email" in data
        assert "full_name" in data
        assert "session_duration" in data
        assert "is_active" in data
        assert "created_at" in data
        assert "password_hash" not in data

    async def test_get_me_returns_correct_professional(
        self,
        authenticated_http_client: AsyncClient,
        test_professional,
    ) -> None:
        """Deve retornar os dados do profissional autenticado."""
        response = await authenticated_http_client.get("/api/v1/professionals/me")
        data = response.json()

        assert data["email"] == test_professional.email
        assert data["full_name"] == test_professional.full_name

    async def test_get_me_requires_authentication(
        self, http_client: AsyncClient
    ) -> None:
        """GET /professionals/me sem JWT deve retornar 401."""
        response = await http_client.get("/api/v1/professionals/me")
        assert response.status_code == 401


class TestPatchMe:
    async def test_patch_me_returns_200(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """PATCH /professionals/me deve retornar 200 para usuario autenticado."""
        response = await authenticated_http_client.patch(
            "/api/v1/professionals/me",
            json={"full_name": "Updated Name"},
        )
        assert response.status_code == 200

    async def test_patch_me_updates_full_name(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """PATCH deve atualizar o full_name e retornar o valor novo."""
        response = await authenticated_http_client.patch(
            "/api/v1/professionals/me",
            json={"full_name": "New Name After Patch"},
        )
        data = response.json()
        assert data["full_name"] == "New Name After Patch"

    async def test_patch_me_partial_update_does_not_clear_other_fields(
        self, authenticated_http_client: AsyncClient, test_professional
    ) -> None:
        """PATCH parcial nao deve apagar campos nao incluidos no body."""
        original_email = test_professional.email

        response = await authenticated_http_client.patch(
            "/api/v1/professionals/me",
            json={"full_name": "Partial Update"},
        )
        data = response.json()

        # Email should be unchanged
        assert data["email"] == original_email

    async def test_patch_me_returns_updated_professional_response(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """Resposta do PATCH deve ser um ProfessionalResponse valido sem password_hash."""
        response = await authenticated_http_client.patch(
            "/api/v1/professionals/me",
            json={"specialty": "Psicologia", "bio": "10 anos de experiencia"},
        )
        data = response.json()

        assert data["specialty"] == "Psicologia"
        assert data["bio"] == "10 anos de experiencia"
        assert "password_hash" not in data

    async def test_patch_me_requires_authentication(
        self, http_client: AsyncClient
    ) -> None:
        """PATCH /professionals/me sem JWT deve retornar 401."""
        response = await http_client.patch(
            "/api/v1/professionals/me",
            json={"full_name": "Unauthenticated"},
        )
        assert response.status_code == 401
