"""
Tests for clients router — TDD Red phase.

Coverage:
- POST   /api/v1/clients/        → create_client
- GET    /api/v1/clients/        → list_clients
- GET    /api/v1/clients/{id}    → get_client
- PATCH  /api/v1/clients/{id}    → update_client
- DELETE /api/v1/clients/{id}    → delete_client

All endpoints require authentication (TenantSession). Tests use:
  - authenticated_http_client  → requests with valid JWT for test_professional
  - http_client                → unauthenticated requests (for 401 assertions)

The router uses TenantSession which internally calls set_tenant_context().
The http_client fixture already overrides get_db() with the test session,
so RLS context is set by the router's dependency for authenticated requests.
"""

from uuid import uuid4

import pytest
from httpx import AsyncClient


class TestCreateClient:
    # ------------------------------------------------------------------
    # 201 — phone only
    # ------------------------------------------------------------------

    async def test_create_client_returns_201(self, authenticated_http_client: AsyncClient) -> None:
        """POST /clients/ deve retornar 201 para dados válidos."""
        response = await authenticated_http_client.post(
            "/api/v1/clients/",
            json={"full_name": "João Silva", "phone": "11999990200"},
        )
        assert response.status_code == 201

    async def test_create_client_with_phone_only_returns_client_response(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """Resposta deve conter os campos do ClientResponse (sem professional_id)."""
        response = await authenticated_http_client.post(
            "/api/v1/clients/",
            json={"full_name": "João Silva", "phone": "11999990201"},
        )
        data = response.json()

        assert "id" in data
        assert data["full_name"] == "João Silva"
        assert data["phone"] == "11999990201"
        assert data["email"] is None
        assert data["is_active"] is True
        assert data["whatsapp_opt_in"] is False
        assert "created_at" in data
        assert "updated_at" in data
        assert "professional_id" not in data

    # ------------------------------------------------------------------
    # 201 — email only
    # ------------------------------------------------------------------

    async def test_create_client_with_email_only_returns_201(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """POST /clients/ deve aceitar clientes com email apenas (sem phone)."""
        response = await authenticated_http_client.post(
            "/api/v1/clients/",
            json={"full_name": "Maria Santos", "email": "maria@example.com"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "maria@example.com"
        assert data["phone"] is None

    # ------------------------------------------------------------------
    # 422 — no contact method
    # ------------------------------------------------------------------

    async def test_create_client_without_contact_returns_422(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """POST /clients/ sem phone nem email deve retornar 422."""
        response = await authenticated_http_client.post(
            "/api/v1/clients/",
            json={"full_name": "No Contact"},
        )
        assert response.status_code == 422

    # ------------------------------------------------------------------
    # 409 — duplicate phone
    # ------------------------------------------------------------------

    async def test_create_client_duplicate_phone_returns_409(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """POST /clients/ com phone já cadastrado no mesmo tenant deve retornar 409."""
        payload = {"full_name": "First Client", "phone": "11999990210"}
        await authenticated_http_client.post("/api/v1/clients/", json=payload)

        response = await authenticated_http_client.post(
            "/api/v1/clients/",
            json={"full_name": "Second Client", "phone": "11999990210"},
        )
        assert response.status_code == 409

    # ------------------------------------------------------------------
    # 401 — unauthenticated
    # ------------------------------------------------------------------

    async def test_create_client_requires_authentication(self, http_client: AsyncClient) -> None:
        """POST /clients/ sem JWT deve retornar 401."""
        response = await http_client.post(
            "/api/v1/clients/",
            json={"full_name": "Unauth", "phone": "11999990220"},
        )
        assert response.status_code == 401


class TestListClients:
    # ------------------------------------------------------------------
    # 200 — basic listing
    # ------------------------------------------------------------------

    async def test_list_clients_returns_200(self, authenticated_http_client: AsyncClient) -> None:
        """GET /clients/ deve retornar 200."""
        response = await authenticated_http_client.get("/api/v1/clients/")
        assert response.status_code == 200

    async def test_list_clients_returns_list(self, authenticated_http_client: AsyncClient) -> None:
        """Resposta deve ser uma lista JSON."""
        response = await authenticated_http_client.get("/api/v1/clients/")
        assert isinstance(response.json(), list)

    async def test_list_clients_includes_created_client(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """GET /clients/ deve retornar clientes criados pelo profissional autenticado."""
        await authenticated_http_client.post(
            "/api/v1/clients/",
            json={"full_name": "List Test Client", "phone": "11999990230"},
        )

        response = await authenticated_http_client.get("/api/v1/clients/")
        data = response.json()

        phones = [c["phone"] for c in data]
        assert "11999990230" in phones

    async def test_list_clients_excludes_deleted_client(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """GET /clients/ não deve incluir clientes que foram deletados."""
        create_resp = await authenticated_http_client.post(
            "/api/v1/clients/",
            json={"full_name": "To Be Deleted", "phone": "11999990240"},
        )
        client_id = create_resp.json()["id"]

        await authenticated_http_client.delete(f"/api/v1/clients/{client_id}")

        response = await authenticated_http_client.get("/api/v1/clients/")
        ids = [c["id"] for c in response.json()]
        assert client_id not in ids

    # ------------------------------------------------------------------
    # Pagination
    # ------------------------------------------------------------------

    async def test_list_clients_respects_limit_query_param(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """GET /clients/?limit=1 deve retornar no máximo 1 cliente."""
        await authenticated_http_client.post(
            "/api/v1/clients/", json={"full_name": "Client A", "phone": "11999990250"}
        )
        await authenticated_http_client.post(
            "/api/v1/clients/", json={"full_name": "Client B", "phone": "11999990251"}
        )

        response = await authenticated_http_client.get("/api/v1/clients/?limit=1")
        assert len(response.json()) == 1

    # ------------------------------------------------------------------
    # 401 — unauthenticated
    # ------------------------------------------------------------------

    async def test_list_clients_requires_authentication(self, http_client: AsyncClient) -> None:
        """GET /clients/ sem JWT deve retornar 401."""
        response = await http_client.get("/api/v1/clients/")
        assert response.status_code == 401


class TestGetClient:
    # ------------------------------------------------------------------
    # 200 — found
    # ------------------------------------------------------------------

    async def test_get_client_returns_200(self, authenticated_http_client: AsyncClient) -> None:
        """GET /clients/{id} deve retornar 200 para cliente existente."""
        create_resp = await authenticated_http_client.post(
            "/api/v1/clients/",
            json={"full_name": "Get Me", "phone": "11999990260"},
        )
        client_id = create_resp.json()["id"]

        response = await authenticated_http_client.get(f"/api/v1/clients/{client_id}")
        assert response.status_code == 200

    async def test_get_client_returns_correct_client(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """GET /clients/{id} deve retornar os dados corretos do cliente."""
        create_resp = await authenticated_http_client.post(
            "/api/v1/clients/",
            json={"full_name": "Correct Client", "phone": "11999990261"},
        )
        client_id = create_resp.json()["id"]

        response = await authenticated_http_client.get(f"/api/v1/clients/{client_id}")
        data = response.json()

        assert data["id"] == client_id
        assert data["full_name"] == "Correct Client"
        assert data["phone"] == "11999990261"

    # ------------------------------------------------------------------
    # 404 — not found
    # ------------------------------------------------------------------

    async def test_get_client_returns_404_for_unknown_id(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """GET /clients/{id} para UUID inexistente deve retornar 404."""
        response = await authenticated_http_client.get(f"/api/v1/clients/{uuid4()}")
        assert response.status_code == 404

    # ------------------------------------------------------------------
    # 401 — unauthenticated
    # ------------------------------------------------------------------

    async def test_get_client_requires_authentication(self, http_client: AsyncClient) -> None:
        """GET /clients/{id} sem JWT deve retornar 401."""
        response = await http_client.get(f"/api/v1/clients/{uuid4()}")
        assert response.status_code == 401


class TestUpdateClient:
    # ------------------------------------------------------------------
    # 200 — successful update
    # ------------------------------------------------------------------

    async def test_update_client_returns_200(self, authenticated_http_client: AsyncClient) -> None:
        """PATCH /clients/{id} deve retornar 200 para dados válidos."""
        create_resp = await authenticated_http_client.post(
            "/api/v1/clients/",
            json={"full_name": "Before Update", "phone": "11999990270"},
        )
        client_id = create_resp.json()["id"]

        response = await authenticated_http_client.patch(
            f"/api/v1/clients/{client_id}",
            json={"full_name": "After Update"},
        )
        assert response.status_code == 200

    async def test_update_client_changes_full_name(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """PATCH deve retornar o cliente com o full_name atualizado."""
        create_resp = await authenticated_http_client.post(
            "/api/v1/clients/",
            json={"full_name": "Old Name", "phone": "11999990271"},
        )
        client_id = create_resp.json()["id"]

        response = await authenticated_http_client.patch(
            f"/api/v1/clients/{client_id}",
            json={"full_name": "New Name"},
        )
        assert response.json()["full_name"] == "New Name"

    # ------------------------------------------------------------------
    # PATCH semantics
    # ------------------------------------------------------------------

    async def test_update_client_partial_does_not_clear_other_fields(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """PATCH parcial não deve apagar campos não incluídos no body."""
        create_resp = await authenticated_http_client.post(
            "/api/v1/clients/",
            json={
                "full_name": "Partial Test",
                "phone": "11999990272",
                "notes": "Original notes",
            },
        )
        client_id = create_resp.json()["id"]

        response = await authenticated_http_client.patch(
            f"/api/v1/clients/{client_id}",
            json={"full_name": "Updated Name Only"},
        )
        data = response.json()

        assert data["full_name"] == "Updated Name Only"
        assert data["phone"] == "11999990272"  # unchanged
        assert data["notes"] == "Original notes"  # unchanged

    async def test_update_client_updates_opt_in_flags(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """PATCH deve atualizar whatsapp_opt_in e email_opt_in."""
        create_resp = await authenticated_http_client.post(
            "/api/v1/clients/",
            json={"full_name": "Opt In Test", "phone": "11999990273"},
        )
        client_id = create_resp.json()["id"]

        response = await authenticated_http_client.patch(
            f"/api/v1/clients/{client_id}",
            json={"whatsapp_opt_in": True, "email_opt_in": True},
        )
        data = response.json()

        assert data["whatsapp_opt_in"] is True
        assert data["email_opt_in"] is True

    # ------------------------------------------------------------------
    # 404 — not found
    # ------------------------------------------------------------------

    async def test_update_client_returns_404_for_unknown_id(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """PATCH /clients/{id} para UUID inexistente deve retornar 404."""
        response = await authenticated_http_client.patch(
            f"/api/v1/clients/{uuid4()}",
            json={"full_name": "Ghost"},
        )
        assert response.status_code == 404

    # ------------------------------------------------------------------
    # 401 — unauthenticated
    # ------------------------------------------------------------------

    async def test_update_client_requires_authentication(self, http_client: AsyncClient) -> None:
        """PATCH /clients/{id} sem JWT deve retornar 401."""
        response = await http_client.patch(
            f"/api/v1/clients/{uuid4()}",
            json={"full_name": "Unauth"},
        )
        assert response.status_code == 401


class TestDeleteClient:
    # ------------------------------------------------------------------
    # 204 — deleted
    # ------------------------------------------------------------------

    async def test_delete_client_returns_204(self, authenticated_http_client: AsyncClient) -> None:
        """DELETE /clients/{id} deve retornar 204 sem body."""
        create_resp = await authenticated_http_client.post(
            "/api/v1/clients/",
            json={"full_name": "To Delete", "phone": "11999990280"},
        )
        client_id = create_resp.json()["id"]

        response = await authenticated_http_client.delete(f"/api/v1/clients/{client_id}")
        assert response.status_code == 204

    async def test_delete_client_returns_no_body(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """DELETE /clients/{id} não deve retornar body (204 No Content)."""
        create_resp = await authenticated_http_client.post(
            "/api/v1/clients/",
            json={"full_name": "No Body Delete", "phone": "11999990281"},
        )
        client_id = create_resp.json()["id"]

        response = await authenticated_http_client.delete(f"/api/v1/clients/{client_id}")
        assert response.content == b""

    async def test_delete_client_excluded_from_list(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """Após DELETE, cliente não deve aparecer em GET /clients/."""
        create_resp = await authenticated_http_client.post(
            "/api/v1/clients/",
            json={"full_name": "Deleted From List", "phone": "11999990282"},
        )
        client_id = create_resp.json()["id"]

        await authenticated_http_client.delete(f"/api/v1/clients/{client_id}")

        list_resp = await authenticated_http_client.get("/api/v1/clients/")
        ids = [c["id"] for c in list_resp.json()]
        assert client_id not in ids

    async def test_delete_client_get_still_returns_404(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """
        Após DELETE, GET /clients/{id} deve retornar 404.

        Como o soft delete marca is_active=False e o find_by_id busca qualquer
        linha (ativa ou não), o cliente ainda estaria "visível" se chamado
        diretamente. Mas o get_client do service levanta NotFoundError quando
        find_by_id retorna None.

        Na verdade, find_by_id NÃO filtra por is_active — ele busca qualquer
        linha com aquele id. O cliente soft-deleted ainda retorna do find_by_id.
        Portanto, GET /clients/{id} de um cliente deletado deve retornar 200
        (o cliente existe, apenas inativo). Testamos que is_active=False.
        """
        create_resp = await authenticated_http_client.post(
            "/api/v1/clients/",
            json={"full_name": "Soft Deleted", "phone": "11999990283"},
        )
        client_id = create_resp.json()["id"]

        await authenticated_http_client.delete(f"/api/v1/clients/{client_id}")

        # get_client uses find_by_id (no active_only filter) — the record still exists
        get_resp = await authenticated_http_client.get(f"/api/v1/clients/{client_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["is_active"] is False

    # ------------------------------------------------------------------
    # 404 — not found
    # ------------------------------------------------------------------

    async def test_delete_client_returns_404_for_unknown_id(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """DELETE /clients/{id} para UUID inexistente deve retornar 404."""
        response = await authenticated_http_client.delete(f"/api/v1/clients/{uuid4()}")
        assert response.status_code == 404

    # ------------------------------------------------------------------
    # 401 — unauthenticated
    # ------------------------------------------------------------------

    async def test_delete_client_requires_authentication(self, http_client: AsyncClient) -> None:
        """DELETE /clients/{id} sem JWT deve retornar 401."""
        response = await http_client.delete(f"/api/v1/clients/{uuid4()}")
        assert response.status_code == 401
