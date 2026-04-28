"""
Tests for agenda router — TDD Red phase.

Coverage:
- POST/GET/GET{id}/PATCH/DELETE for availability slots
- POST/GET/DELETE for blocked periods
- POST/GET/GET{id}/DELETE for recurrences
- POST/GET(list)/GET(today)/GET(upcoming)/GET{id}/PATCH for sessions

All endpoints require authentication (TenantSession). Tests use:
  - authenticated_http_client → requests with valid JWT for test_professional
  - http_client               → unauthenticated requests (for 401 assertions)

The router uses TenantSession. The http_client fixture overrides get_db()
with the test session, so RLS context is set by the router's dependency.
"""

from uuid import uuid4

from httpx import AsyncClient

# ---------------------------------------------------------------------------
# Payload factories
# ---------------------------------------------------------------------------


def _slot_payload(**overrides) -> dict:
    base = {
        "day_of_week": 1,
        "start_time": "09:00:00",
        "end_time": "10:00:00",
    }
    base.update(overrides)
    return base


def _blocked_payload(**overrides) -> dict:
    base = {
        "start_datetime": "2035-01-10T08:00:00Z",
        "end_datetime": "2035-01-10T18:00:00Z",
        "reason": "Test block",
    }
    base.update(overrides)
    return base


def _recurrence_payload(client_id: str, **overrides) -> dict:
    base = {
        "client_id": client_id,
        "frequency": "weekly",
        "day_of_week": 1,
        "start_date": "2025-01-01",
        "session_duration": 60,
        "session_price": "150.00",
    }
    base.update(overrides)
    return base


def _session_payload(client_id: str, **overrides) -> dict:
    base = {
        "client_id": client_id,
        "scheduled_at": "2035-06-01T10:00:00Z",
        "duration_minutes": 60,
        "price": "150.00",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Helpers to create dependent resources via the API
# ---------------------------------------------------------------------------


async def _api_create_client(client: AsyncClient, *, name: str = "Router Test Client") -> str:
    """Create a client via API and return its id."""
    resp = await client.post(
        "/api/v1/clients/",
        json={
            "full_name": name,
            "phone": f"119{uuid4().int % 100_000_000:08d}",
        },
    )
    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
    return resp.json()["id"]


async def _api_create_recurrence(client: AsyncClient, client_id: str, **overrides) -> str:
    """Create a recurrence via API and return its id."""
    resp = await client.post(
        "/api/v1/agenda/recurrences/",
        json=_recurrence_payload(client_id, **overrides),
    )
    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
    return resp.json()["id"]


async def _api_create_session(client: AsyncClient, client_id: str, scheduled_at: str) -> str:
    """Create a session via API and return its id."""
    resp = await client.post(
        "/api/v1/agenda/sessions/",
        json=_session_payload(client_id, scheduled_at=scheduled_at),
    )
    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
    return resp.json()["id"]


# =============================================================================
# Availability Slots
# =============================================================================


class TestCreateAvailabilitySlot:
    async def test_create_slot_returns_201(self, authenticated_http_client: AsyncClient) -> None:
        """POST /slots/ com payload válido deve retornar 201."""
        response = await authenticated_http_client.post(
            "/api/v1/agenda/slots/",
            json=_slot_payload(),
        )
        assert response.status_code == 201

    async def test_create_slot_response_fields(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """Resposta deve conter os campos do AvailabilitySlotResponse."""
        response = await authenticated_http_client.post(
            "/api/v1/agenda/slots/",
            json=_slot_payload(day_of_week=2, start_time="14:00:00", end_time="15:00:00"),
        )
        data = response.json()
        assert "id" in data
        assert data["day_of_week"] == 2
        assert data["start_time"] == "14:00:00"
        assert data["end_time"] == "15:00:00"
        assert data["is_active"] is True
        assert "created_at" in data
        assert "updated_at" in data

    async def test_create_slot_duplicate_returns_409(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """Segunda criação com mesmo (day_of_week, start_time) deve retornar 409."""
        payload = _slot_payload(day_of_week=3, start_time="09:00:00", end_time="10:00:00")
        first = await authenticated_http_client.post("/api/v1/agenda/slots/", json=payload)
        assert first.status_code == 201
        second = await authenticated_http_client.post("/api/v1/agenda/slots/", json=payload)
        assert second.status_code == 409

    async def test_create_slot_invalid_day_of_week_returns_422(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """day_of_week=7 deve retornar 422."""
        response = await authenticated_http_client.post(
            "/api/v1/agenda/slots/",
            json=_slot_payload(day_of_week=7),
        )
        assert response.status_code == 422

    async def test_create_slot_end_before_start_returns_422(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """end_time < start_time deve retornar 422."""
        response = await authenticated_http_client.post(
            "/api/v1/agenda/slots/",
            json=_slot_payload(start_time="17:00:00", end_time="09:00:00"),
        )
        assert response.status_code == 422

    async def test_create_slot_unauthenticated_returns_401(self, http_client: AsyncClient) -> None:
        """Requisição sem JWT deve retornar 401."""
        response = await http_client.post("/api/v1/agenda/slots/", json=_slot_payload())
        assert response.status_code == 401


class TestListAvailabilitySlots:
    async def test_list_slots_returns_200(self, authenticated_http_client: AsyncClient) -> None:
        """GET /slots/ deve retornar 200 com lista."""
        response = await authenticated_http_client.get("/api/v1/agenda/slots/")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    async def test_list_slots_includes_created_slot(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """Slot criado deve aparecer no GET /slots/."""
        create_resp = await authenticated_http_client.post(
            "/api/v1/agenda/slots/",
            json=_slot_payload(day_of_week=4, start_time="11:00:00", end_time="12:00:00"),
        )
        slot_id = create_resp.json()["id"]

        list_resp = await authenticated_http_client.get("/api/v1/agenda/slots/")
        ids = [s["id"] for s in list_resp.json()]
        assert slot_id in ids

    async def test_list_slots_unauthenticated_returns_401(self, http_client: AsyncClient) -> None:
        """GET /slots/ sem JWT deve retornar 401."""
        response = await http_client.get("/api/v1/agenda/slots/")
        assert response.status_code == 401


class TestGetAvailabilitySlot:
    async def test_get_slot_returns_200(self, authenticated_http_client: AsyncClient) -> None:
        """GET /slots/{id} deve retornar 200 para slot existente."""
        create_resp = await authenticated_http_client.post(
            "/api/v1/agenda/slots/",
            json=_slot_payload(day_of_week=5, start_time="08:00:00", end_time="09:00:00"),
        )
        slot_id = create_resp.json()["id"]

        response = await authenticated_http_client.get(f"/api/v1/agenda/slots/{slot_id}")
        assert response.status_code == 200
        assert response.json()["id"] == slot_id

    async def test_get_slot_not_found_returns_404(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """GET /slots/{id} com UUID inexistente deve retornar 404."""
        response = await authenticated_http_client.get(f"/api/v1/agenda/slots/{uuid4()}")
        assert response.status_code == 404

    async def test_get_slot_unauthenticated_returns_401(self, http_client: AsyncClient) -> None:
        response = await http_client.get(f"/api/v1/agenda/slots/{uuid4()}")
        assert response.status_code == 401


class TestUpdateAvailabilitySlot:
    async def test_update_slot_returns_200(self, authenticated_http_client: AsyncClient) -> None:
        """PATCH /slots/{id} deve retornar 200 e campo atualizado."""
        create_resp = await authenticated_http_client.post(
            "/api/v1/agenda/slots/",
            json=_slot_payload(day_of_week=6, start_time="10:00:00", end_time="11:00:00"),
        )
        slot_id = create_resp.json()["id"]

        response = await authenticated_http_client.patch(
            f"/api/v1/agenda/slots/{slot_id}",
            json={"end_time": "12:00:00"},
        )
        assert response.status_code == 200
        assert response.json()["end_time"] == "12:00:00"

    async def test_update_slot_patch_preserves_unset_fields(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """PATCH não deve alterar campos não incluídos no payload."""
        create_resp = await authenticated_http_client.post(
            "/api/v1/agenda/slots/",
            json=_slot_payload(day_of_week=0, start_time="16:00:00", end_time="17:00:00"),
        )
        slot = create_resp.json()
        slot_id = slot["id"]

        response = await authenticated_http_client.patch(
            f"/api/v1/agenda/slots/{slot_id}",
            json={"is_active": False},
        )
        assert response.json()["day_of_week"] == 0  # unchanged
        assert response.json()["start_time"] == "16:00:00"  # unchanged

    async def test_update_slot_not_found_returns_404(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        response = await authenticated_http_client.patch(
            f"/api/v1/agenda/slots/{uuid4()}",
            json={"is_active": False},
        )
        assert response.status_code == 404

    async def test_update_slot_unauthenticated_returns_401(self, http_client: AsyncClient) -> None:
        response = await http_client.patch(
            f"/api/v1/agenda/slots/{uuid4()}",
            json={"is_active": False},
        )
        assert response.status_code == 401


class TestDeleteAvailabilitySlot:
    async def test_delete_slot_returns_204(self, authenticated_http_client: AsyncClient) -> None:
        """DELETE /slots/{id} deve retornar 204."""
        create_resp = await authenticated_http_client.post(
            "/api/v1/agenda/slots/",
            json=_slot_payload(day_of_week=1, start_time="20:00:00", end_time="21:00:00"),
        )
        slot_id = create_resp.json()["id"]

        response = await authenticated_http_client.delete(f"/api/v1/agenda/slots/{slot_id}")
        assert response.status_code == 204

    async def test_delete_slot_is_soft_delete(self, authenticated_http_client: AsyncClient) -> None:
        """DELETE deve setar is_active=False, não remover o registro."""
        create_resp = await authenticated_http_client.post(
            "/api/v1/agenda/slots/",
            json=_slot_payload(day_of_week=2, start_time="20:00:00", end_time="21:00:00"),
        )
        slot_id = create_resp.json()["id"]
        await authenticated_http_client.delete(f"/api/v1/agenda/slots/{slot_id}")

        # GET ainda deve retornar o slot (soft delete preserva o registro)
        get_resp = await authenticated_http_client.get(f"/api/v1/agenda/slots/{slot_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["is_active"] is False

    async def test_delete_slot_not_found_returns_404(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        response = await authenticated_http_client.delete(f"/api/v1/agenda/slots/{uuid4()}")
        assert response.status_code == 404

    async def test_delete_slot_unauthenticated_returns_401(self, http_client: AsyncClient) -> None:
        response = await http_client.delete(f"/api/v1/agenda/slots/{uuid4()}")
        assert response.status_code == 401


# =============================================================================
# Blocked Periods
# =============================================================================


class TestCreateBlockedPeriod:
    async def test_create_blocked_period_returns_201(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """POST /blocked/ com payload válido deve retornar 201."""
        response = await authenticated_http_client.post(
            "/api/v1/agenda/blocked/",
            json=_blocked_payload(),
        )
        assert response.status_code == 201

    async def test_create_blocked_period_response_fields(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """Resposta deve conter os campos do BlockedPeriodResponse."""
        response = await authenticated_http_client.post(
            "/api/v1/agenda/blocked/",
            json=_blocked_payload(
                start_datetime="2035-02-01T08:00:00Z",
                end_datetime="2035-02-01T18:00:00Z",
                reason="Congresso",
            ),
        )
        data = response.json()
        assert "id" in data
        assert data["reason"] == "Congresso"
        assert data["notify_clients"] is True
        assert "created_at" in data

    async def test_create_blocked_period_without_reason_returns_201(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """reason é opcional — omitir deve funcionar."""
        response = await authenticated_http_client.post(
            "/api/v1/agenda/blocked/",
            json={
                "start_datetime": "2035-03-01T08:00:00Z",
                "end_datetime": "2035-03-01T18:00:00Z",
            },
        )
        assert response.status_code == 201
        assert response.json()["reason"] is None

    async def test_create_blocked_period_end_before_start_returns_422(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """end_datetime < start_datetime deve retornar 422."""
        response = await authenticated_http_client.post(
            "/api/v1/agenda/blocked/",
            json={
                "start_datetime": "2035-01-10T18:00:00Z",
                "end_datetime": "2035-01-10T08:00:00Z",
            },
        )
        assert response.status_code == 422

    async def test_create_blocked_period_unauthenticated_returns_401(
        self, http_client: AsyncClient
    ) -> None:
        response = await http_client.post("/api/v1/agenda/blocked/", json=_blocked_payload())
        assert response.status_code == 401


class TestListBlockedPeriods:
    async def test_list_blocked_periods_returns_200(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """GET /blocked/ deve retornar 200 com lista."""
        response = await authenticated_http_client.get("/api/v1/agenda/blocked/")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    async def test_list_blocked_periods_includes_created(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """Período criado deve aparecer no GET /blocked/."""
        create_resp = await authenticated_http_client.post(
            "/api/v1/agenda/blocked/",
            json=_blocked_payload(
                start_datetime="2035-04-01T08:00:00Z",
                end_datetime="2035-04-01T18:00:00Z",
            ),
        )
        period_id = create_resp.json()["id"]

        list_resp = await authenticated_http_client.get("/api/v1/agenda/blocked/")
        ids = [p["id"] for p in list_resp.json()]
        assert period_id in ids

    async def test_list_blocked_periods_unauthenticated_returns_401(
        self, http_client: AsyncClient
    ) -> None:
        response = await http_client.get("/api/v1/agenda/blocked/")
        assert response.status_code == 401


class TestDeleteBlockedPeriod:
    async def test_delete_blocked_period_returns_204(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """DELETE /blocked/{id} deve retornar 204."""
        create_resp = await authenticated_http_client.post(
            "/api/v1/agenda/blocked/",
            json=_blocked_payload(
                start_datetime="2035-05-01T08:00:00Z",
                end_datetime="2035-05-01T18:00:00Z",
            ),
        )
        period_id = create_resp.json()["id"]

        response = await authenticated_http_client.delete(f"/api/v1/agenda/blocked/{period_id}")
        assert response.status_code == 204

    async def test_delete_blocked_period_hard_deletes(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """Após DELETE, período não deve aparecer em GET /blocked/."""
        create_resp = await authenticated_http_client.post(
            "/api/v1/agenda/blocked/",
            json=_blocked_payload(
                start_datetime="2035-06-01T08:00:00Z",
                end_datetime="2035-06-01T18:00:00Z",
            ),
        )
        period_id = create_resp.json()["id"]
        await authenticated_http_client.delete(f"/api/v1/agenda/blocked/{period_id}")

        list_resp = await authenticated_http_client.get("/api/v1/agenda/blocked/")
        ids = [p["id"] for p in list_resp.json()]
        assert period_id not in ids

    async def test_delete_blocked_period_not_found_returns_404(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        response = await authenticated_http_client.delete(f"/api/v1/agenda/blocked/{uuid4()}")
        assert response.status_code == 404

    async def test_delete_blocked_period_unauthenticated_returns_401(
        self, http_client: AsyncClient
    ) -> None:
        response = await http_client.delete(f"/api/v1/agenda/blocked/{uuid4()}")
        assert response.status_code == 401


# =============================================================================
# Recurrences
# =============================================================================


class TestCreateRecurrence:
    async def test_create_recurrence_returns_201(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """POST /recurrences/ com payload válido deve retornar 201."""
        client_id = await _api_create_client(authenticated_http_client, name="Rec Create Client")
        response = await authenticated_http_client.post(
            "/api/v1/agenda/recurrences/",
            json=_recurrence_payload(client_id),
        )
        assert response.status_code == 201

    async def test_create_recurrence_response_fields(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """Resposta deve conter os campos do RecurrenceResponse."""
        client_id = await _api_create_client(authenticated_http_client, name="Rec Fields Client")
        response = await authenticated_http_client.post(
            "/api/v1/agenda/recurrences/",
            json=_recurrence_payload(client_id, frequency="biweekly", day_of_week=3),
        )
        data = response.json()
        assert "id" in data
        assert data["client_id"] == client_id
        assert data["frequency"] == "biweekly"
        assert data["day_of_week"] == 3
        assert data["is_active"] is True
        assert data["interval"] == 1
        assert "session_price" in data
        assert "created_at" in data
        assert "updated_at" in data

    async def test_create_recurrence_weekly_without_day_of_week_returns_422(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """weekly sem day_of_week deve retornar 422."""
        client_id = await _api_create_client(authenticated_http_client, name="Rec Val Client")
        response = await authenticated_http_client.post(
            "/api/v1/agenda/recurrences/",
            json={
                "client_id": client_id,
                "frequency": "weekly",
                # day_of_week ausente — obrigatório para weekly
                "start_date": "2025-01-01",
                "session_duration": 60,
                "session_price": "150.00",
            },
        )
        assert response.status_code == 422

    async def test_create_recurrence_monthly_without_day_of_week_returns_201(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """monthly sem day_of_week deve ser aceito."""
        client_id = await _api_create_client(authenticated_http_client, name="Rec Monthly Client")
        response = await authenticated_http_client.post(
            "/api/v1/agenda/recurrences/",
            json={
                "client_id": client_id,
                "frequency": "monthly",
                "start_date": "2025-01-01",
                "session_duration": 60,
                "session_price": "150.00",
            },
        )
        assert response.status_code == 201

    async def test_create_recurrence_unauthenticated_returns_401(
        self, http_client: AsyncClient
    ) -> None:
        response = await http_client.post(
            "/api/v1/agenda/recurrences/",
            json=_recurrence_payload(str(uuid4())),
        )
        assert response.status_code == 401


class TestListRecurrences:
    async def test_list_recurrences_returns_200(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """GET /recurrences/ deve retornar 200 com lista."""
        response = await authenticated_http_client.get("/api/v1/agenda/recurrences/")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    async def test_list_recurrences_includes_created(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """Recorrência criada deve aparecer no GET /recurrences/."""
        client_id = await _api_create_client(authenticated_http_client, name="List Rec Client")
        rec_id = await _api_create_recurrence(authenticated_http_client, client_id)

        list_resp = await authenticated_http_client.get("/api/v1/agenda/recurrences/")
        ids = [r["id"] for r in list_resp.json()]
        assert rec_id in ids

    async def test_list_recurrences_unauthenticated_returns_401(
        self, http_client: AsyncClient
    ) -> None:
        response = await http_client.get("/api/v1/agenda/recurrences/")
        assert response.status_code == 401


class TestGetRecurrence:
    async def test_get_recurrence_returns_200(self, authenticated_http_client: AsyncClient) -> None:
        """GET /recurrences/{id} deve retornar 200 para recorrência existente."""
        client_id = await _api_create_client(authenticated_http_client, name="Get Rec Client")
        rec_id = await _api_create_recurrence(authenticated_http_client, client_id)

        response = await authenticated_http_client.get(f"/api/v1/agenda/recurrences/{rec_id}")
        assert response.status_code == 200
        assert response.json()["id"] == rec_id

    async def test_get_recurrence_not_found_returns_404(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        response = await authenticated_http_client.get(f"/api/v1/agenda/recurrences/{uuid4()}")
        assert response.status_code == 404

    async def test_get_recurrence_unauthenticated_returns_401(
        self, http_client: AsyncClient
    ) -> None:
        response = await http_client.get(f"/api/v1/agenda/recurrences/{uuid4()}")
        assert response.status_code == 401


class TestDeactivateRecurrence:
    async def test_deactivate_recurrence_returns_200(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """DELETE /recurrences/{id} deve retornar 200."""
        client_id = await _api_create_client(
            authenticated_http_client, name="Deactivate Rec Client"
        )
        rec_id = await _api_create_recurrence(authenticated_http_client, client_id)

        response = await authenticated_http_client.delete(f"/api/v1/agenda/recurrences/{rec_id}")
        assert response.status_code == 200

    async def test_deactivate_recurrence_returns_cancelled_sessions_key(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """Resposta deve conter {'cancelled_sessions': N}."""
        client_id = await _api_create_client(authenticated_http_client, name="Cancel Count Client")
        rec_id = await _api_create_recurrence(authenticated_http_client, client_id)

        response = await authenticated_http_client.delete(f"/api/v1/agenda/recurrences/{rec_id}")
        data = response.json()
        assert "cancelled_sessions" in data
        assert isinstance(data["cancelled_sessions"], int)
        # No sessions were created for this recurrence
        assert data["cancelled_sessions"] == 0

    async def test_deactivate_recurrence_not_found_returns_404(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        response = await authenticated_http_client.delete(f"/api/v1/agenda/recurrences/{uuid4()}")
        assert response.status_code == 404

    async def test_deactivate_recurrence_unauthenticated_returns_401(
        self, http_client: AsyncClient
    ) -> None:
        response = await http_client.delete(f"/api/v1/agenda/recurrences/{uuid4()}")
        assert response.status_code == 401


# =============================================================================
# Sessions
# =============================================================================


class TestCreateSession:
    async def test_create_session_returns_201(self, authenticated_http_client: AsyncClient) -> None:
        """POST /sessions/ com payload válido deve retornar 201."""
        client_id = await _api_create_client(authenticated_http_client, name="Create Sess Client")
        response = await authenticated_http_client.post(
            "/api/v1/agenda/sessions/",
            json=_session_payload(client_id, scheduled_at="2036-01-01T10:00:00Z"),
        )
        assert response.status_code == 201

    async def test_create_session_response_fields(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """Resposta deve conter os campos do SessionResponse."""
        client_id = await _api_create_client(authenticated_http_client, name="Sess Fields Client")
        response = await authenticated_http_client.post(
            "/api/v1/agenda/sessions/",
            json=_session_payload(client_id, scheduled_at="2036-01-02T10:00:00Z"),
        )
        data = response.json()
        assert "id" in data
        assert data["client_id"] == client_id
        assert data["status"] == "scheduled"
        assert data["duration_minutes"] == 60
        assert "price" in data
        assert data["recurrence_id"] is None
        assert data["notes"] is None
        assert "created_at" in data
        assert "updated_at" in data

    async def test_create_session_conflict_returns_409(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """Sobreposição de horário deve retornar 409."""
        client_id = await _api_create_client(authenticated_http_client, name="Conflict Sess Client")
        payload = _session_payload(client_id, scheduled_at="2036-02-01T10:00:00Z")
        first = await authenticated_http_client.post("/api/v1/agenda/sessions/", json=payload)
        assert first.status_code == 201

        # Mesmo horário — conflito total
        second = await authenticated_http_client.post("/api/v1/agenda/sessions/", json=payload)
        assert second.status_code == 409

    async def test_create_session_duration_zero_returns_422(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """duration_minutes=0 deve retornar 422."""
        client_id = await _api_create_client(authenticated_http_client, name="Dur Zero Client")
        response = await authenticated_http_client.post(
            "/api/v1/agenda/sessions/",
            json=_session_payload(
                client_id,
                scheduled_at="2036-03-01T10:00:00Z",
                duration_minutes=0,
            ),
        )
        assert response.status_code == 422

    async def test_create_session_unauthenticated_returns_401(
        self, http_client: AsyncClient
    ) -> None:
        response = await http_client.post(
            "/api/v1/agenda/sessions/",
            json=_session_payload(str(uuid4())),
        )
        assert response.status_code == 401


class TestListSessions:
    async def test_list_sessions_returns_200(self, authenticated_http_client: AsyncClient) -> None:
        """GET /sessions/ deve retornar 200 com lista."""
        response = await authenticated_http_client.get("/api/v1/agenda/sessions/")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    async def test_list_sessions_includes_created_session(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """Sessão criada deve aparecer em GET /sessions/."""
        client_id = await _api_create_client(authenticated_http_client, name="List Sess Client")
        sess_id = await _api_create_session(
            authenticated_http_client, client_id, "2036-04-01T10:00:00Z"
        )

        response = await authenticated_http_client.get("/api/v1/agenda/sessions/")
        ids = [s["id"] for s in response.json()]
        assert sess_id in ids

    async def test_list_sessions_pagination(self, authenticated_http_client: AsyncClient) -> None:
        """skip e limit devem funcionar como query params."""
        response = await authenticated_http_client.get(
            "/api/v1/agenda/sessions/",
            params={"skip": 0, "limit": 5},
        )
        assert response.status_code == 200
        assert len(response.json()) <= 5

    async def test_list_sessions_unauthenticated_returns_401(
        self, http_client: AsyncClient
    ) -> None:
        response = await http_client.get("/api/v1/agenda/sessions/")
        assert response.status_code == 401


class TestListTodaySessions:
    async def test_list_today_sessions_returns_200(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """GET /sessions/today deve retornar 200 com lista."""
        response = await authenticated_http_client.get("/api/v1/agenda/sessions/today")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    async def test_list_today_sessions_does_not_include_far_future(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """Sessão em 2036 não deve aparecer em /sessions/today."""
        client_id = await _api_create_client(authenticated_http_client, name="Today Sess Client")
        sess_id = await _api_create_session(
            authenticated_http_client, client_id, "2036-05-01T10:00:00Z"
        )

        response = await authenticated_http_client.get("/api/v1/agenda/sessions/today")
        ids = [s["id"] for s in response.json()]
        assert sess_id not in ids

    async def test_list_today_sessions_unauthenticated_returns_401(
        self, http_client: AsyncClient
    ) -> None:
        response = await http_client.get("/api/v1/agenda/sessions/today")
        assert response.status_code == 401


class TestListUpcomingSessions:
    async def test_list_upcoming_sessions_returns_200(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """GET /sessions/upcoming deve retornar 200 com lista."""
        response = await authenticated_http_client.get("/api/v1/agenda/sessions/upcoming")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    async def test_list_upcoming_sessions_respects_limit(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """limit deve limitar o número de resultados."""
        response = await authenticated_http_client.get(
            "/api/v1/agenda/sessions/upcoming",
            params={"limit": 3},
        )
        assert response.status_code == 200
        assert len(response.json()) <= 3

    async def test_list_upcoming_sessions_unauthenticated_returns_401(
        self, http_client: AsyncClient
    ) -> None:
        response = await http_client.get("/api/v1/agenda/sessions/upcoming")
        assert response.status_code == 401


class TestGetSession:
    async def test_get_session_returns_200(self, authenticated_http_client: AsyncClient) -> None:
        """GET /sessions/{id} deve retornar 200 para sessão existente."""
        client_id = await _api_create_client(authenticated_http_client, name="Get Sess Client")
        sess_id = await _api_create_session(
            authenticated_http_client, client_id, "2036-06-01T10:00:00Z"
        )

        response = await authenticated_http_client.get(f"/api/v1/agenda/sessions/{sess_id}")
        assert response.status_code == 200
        assert response.json()["id"] == sess_id

    async def test_get_session_not_found_returns_404(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        response = await authenticated_http_client.get(f"/api/v1/agenda/sessions/{uuid4()}")
        assert response.status_code == 404

    async def test_get_session_unauthenticated_returns_401(self, http_client: AsyncClient) -> None:
        response = await http_client.get(f"/api/v1/agenda/sessions/{uuid4()}")
        assert response.status_code == 401


class TestUpdateSession:
    async def test_update_session_returns_200(self, authenticated_http_client: AsyncClient) -> None:
        """PATCH /sessions/{id} deve retornar 200 e campo atualizado."""
        client_id = await _api_create_client(authenticated_http_client, name="Update Sess Client 1")
        sess_id = await _api_create_session(
            authenticated_http_client, client_id, "2036-07-01T10:00:00Z"
        )

        response = await authenticated_http_client.patch(
            f"/api/v1/agenda/sessions/{sess_id}",
            json={"status": "completed"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "completed"

    async def test_update_session_notes(self, authenticated_http_client: AsyncClient) -> None:
        """PATCH com notes deve atualizar o campo."""
        client_id = await _api_create_client(authenticated_http_client, name="Update Sess Client 2")
        sess_id = await _api_create_session(
            authenticated_http_client, client_id, "2036-07-02T10:00:00Z"
        )

        response = await authenticated_http_client.patch(
            f"/api/v1/agenda/sessions/{sess_id}",
            json={"notes": "Boa sessão"},
        )
        assert response.status_code == 200
        assert response.json()["notes"] == "Boa sessão"

    async def test_update_session_patch_preserves_unset_fields(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """PATCH não deve alterar campos não enviados."""
        client_id = await _api_create_client(authenticated_http_client, name="Update Sess Client 3")
        sess_id = await _api_create_session(
            authenticated_http_client, client_id, "2036-07-03T10:00:00Z"
        )

        response = await authenticated_http_client.patch(
            f"/api/v1/agenda/sessions/{sess_id}",
            json={"notes": "Nota"},
        )
        assert response.json()["duration_minutes"] == 60  # unchanged
        assert response.json()["status"] == "scheduled"  # unchanged

    async def test_update_session_not_found_returns_404(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        response = await authenticated_http_client.patch(
            f"/api/v1/agenda/sessions/{uuid4()}",
            json={"status": "completed"},
        )
        assert response.status_code == 404

    async def test_update_session_invalid_status_returns_422(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """status fora do Literal deve retornar 422."""
        client_id = await _api_create_client(authenticated_http_client, name="Update Sess Client 4")
        sess_id = await _api_create_session(
            authenticated_http_client, client_id, "2036-07-04T10:00:00Z"
        )

        response = await authenticated_http_client.patch(
            f"/api/v1/agenda/sessions/{sess_id}",
            json={"status": "pending"},  # not in Literal
        )
        assert response.status_code == 422

    async def test_update_session_unauthenticated_returns_401(
        self, http_client: AsyncClient
    ) -> None:
        response = await http_client.patch(
            f"/api/v1/agenda/sessions/{uuid4()}",
            json={"status": "completed"},
        )
        assert response.status_code == 401
