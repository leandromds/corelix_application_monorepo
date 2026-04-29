"""
Tests for WhatsApp router — HTTP layer for Meta Cloud API integration.

Coverage:
- GET  /api/v1/whatsapp/webhook    → verification handshake (public)
- POST /api/v1/whatsapp/webhook    → incoming messages (HMAC-authenticated)
- GET  /api/v1/whatsapp/conversations        → list (TenantSession)
- GET  /api/v1/whatsapp/conversations/{id}   → detail (TenantSession)
- POST /api/v1/whatsapp/conversations/{id}/handoff → handoff (TenantSession)

Test classes:
  TestWebhookVerification  (3 tests) — GET /webhook
  TestWebhookIncoming      (5 tests) — POST /webhook
  TestListConversations    (2 tests) — GET /conversations
  TestGetConversationDetail(2 tests) — GET /conversations/{id}
  TestHandoff              (2 tests) — POST /conversations/{id}/handoff

Design notes:
- HMAC signatures are computed with settings.WHATSAPP_APP_SECRET so tests stay
  in sync with the router's _verify_hmac() function automatically.
- Background task (_process_webhook_background) is patched globally to prevent
  it from opening a real DB session pointing at the dev database. With httpx
  ASGITransport, background tasks ARE executed before the client receives the
  response — so patching is required for tests 6 and to keep test DB isolated.
- WhatsAppRepository is patched at its definition site
  (whatsapp.repository.WhatsAppRepository) so the inline `from whatsapp.repository
  import WhatsAppRepository` inside receive_webhook picks up the mock.
"""

import copy
import hashlib
import hmac as _hmac
import json
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from httpx import AsyncClient

from core.config import settings

# ---------------------------------------------------------------------------
# HMAC helper (mirrors _verify_hmac in the router)
# ---------------------------------------------------------------------------


def make_signature(body: bytes) -> str:
    """Compute a valid X-Hub-Signature-256 header value for the given body."""
    sig = _hmac.new(
        settings.WHATSAPP_APP_SECRET.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
    return f"sha256={sig}"


# ===========================================================================
# TestWebhookVerification
# GET /api/v1/whatsapp/webhook
# ===========================================================================


class TestWebhookVerification:
    async def test_valid_token_returns_challenge(self, http_client: AsyncClient) -> None:
        """
        Correct hub.verify_token → 200 with hub.challenge value as plain-text body.

        Meta sends this GET request when a webhook URL is first registered.
        The server must echo hub.challenge verbatim to confirm ownership.
        """
        response = await http_client.get(
            "/api/v1/whatsapp/webhook",
            params={
                "hub.mode": "subscribe",
                "hub.challenge": "challenge_token_abc123",
                "hub.verify_token": settings.WHATSAPP_VERIFY_TOKEN,
            },
        )

        assert response.status_code == 200
        assert response.text == "challenge_token_abc123"

    async def test_invalid_token_returns_403(self, http_client: AsyncClient) -> None:
        """
        Wrong hub.verify_token → 403 Forbidden.

        Any other status code (e.g. 200) would allow an attacker to register
        a fake webhook endpoint for our URL.
        """
        response = await http_client.get(
            "/api/v1/whatsapp/webhook",
            params={
                "hub.mode": "subscribe",
                "hub.challenge": "challenge_xyz",
                "hub.verify_token": "WRONG_TOKEN_DEFINITELY_NOT_VALID",
            },
        )

        assert response.status_code == 403

    async def test_missing_hub_mode_returns_422(self, http_client: AsyncClient) -> None:
        """
        Missing required query parameter hub.mode → 422 Unprocessable Entity.

        FastAPI validates query parameters at the HTTP layer before the handler
        is called, so this tests that the endpoint signature is correctly
        declared as requiring all three hub.* parameters.
        """
        response = await http_client.get(
            "/api/v1/whatsapp/webhook",
            params={
                # hub.mode intentionally omitted
                "hub.challenge": "challenge_xyz",
                "hub.verify_token": settings.WHATSAPP_VERIFY_TOKEN,
            },
        )

        assert response.status_code == 422


# ===========================================================================
# TestWebhookIncoming
# POST /api/v1/whatsapp/webhook
# ===========================================================================


class TestWebhookIncoming:
    async def test_missing_signature_returns_400(
        self,
        http_client: AsyncClient,
        mock_whatsapp_webhook_payload: dict,
    ) -> None:
        """
        POST without X-Hub-Signature-256 header → 400 Bad Request.

        We must reject unsigned requests immediately — without HMAC verification
        anyone can send fake webhooks to trigger AI replies and conversation creation.
        """
        body = json.dumps(mock_whatsapp_webhook_payload).encode()

        response = await http_client.post(
            "/api/v1/whatsapp/webhook",
            content=body,
            headers={"Content-Type": "application/json"},
            # X-Hub-Signature-256 intentionally absent
        )

        assert response.status_code == 400

    async def test_invalid_signature_returns_400(
        self,
        http_client: AsyncClient,
        mock_whatsapp_webhook_payload: dict,
    ) -> None:
        """
        POST with a tampered (incorrect) HMAC signature → 400 Bad Request.

        Computed with a wrong key to simulate a spoofed request.
        """
        body = json.dumps(mock_whatsapp_webhook_payload).encode()
        wrong_sig = _hmac.new(
            b"wrong-secret-key",
            body,
            hashlib.sha256,
        ).hexdigest()

        response = await http_client.post(
            "/api/v1/whatsapp/webhook",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": f"sha256={wrong_sig}",
            },
        )

        assert response.status_code == 400

    async def test_valid_webhook_returns_200(
        self,
        http_client: AsyncClient,
        mock_whatsapp_webhook_payload: dict,
        test_professional,
    ) -> None:
        """
        Correctly signed POST with a text message and a known phone_number_id → 200.

        We mock:
        1. WhatsAppRepository so find_professional_by_phone_id returns test_professional.
        2. _process_webhook_background to prevent it from opening a real DB session
           (it creates its own async_session_maker() session pointing at the dev DB).
        """
        body = json.dumps(mock_whatsapp_webhook_payload).encode()
        sig = make_signature(body)

        with patch("whatsapp.repository.WhatsAppRepository") as MockRepo:
            mock_repo_instance = AsyncMock()
            mock_repo_instance.find_professional_by_phone_id.return_value = test_professional
            MockRepo.return_value = mock_repo_instance

            with patch(
                "whatsapp.router._process_webhook_background",
                new_callable=AsyncMock,
            ):
                response = await http_client.post(
                    "/api/v1/whatsapp/webhook",
                    content=body,
                    headers={
                        "Content-Type": "application/json",
                        "X-Hub-Signature-256": sig,
                    },
                )

        assert response.status_code == 200

    async def test_webhook_for_unknown_phone_id_returns_200(
        self,
        http_client: AsyncClient,
        mock_whatsapp_webhook_payload: dict,
    ) -> None:
        """
        Signed POST but phone_number_id belongs to no professional → still 200.

        Meta requires a 200 response for all webhooks, even if we don't recognize
        the phone_number_id. Returning 4xx would cause Meta to retry indefinitely.
        """
        body = json.dumps(mock_whatsapp_webhook_payload).encode()
        sig = make_signature(body)

        with patch("whatsapp.repository.WhatsAppRepository") as MockRepo:
            mock_repo_instance = AsyncMock()
            mock_repo_instance.find_professional_by_phone_id.return_value = None  # not found
            MockRepo.return_value = mock_repo_instance

            response = await http_client.post(
                "/api/v1/whatsapp/webhook",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Hub-Signature-256": sig,
                },
            )

        assert response.status_code == 200

    async def test_non_text_message_type_returns_200(
        self,
        http_client: AsyncClient,
        mock_whatsapp_webhook_payload: dict,
    ) -> None:
        """
        Signed POST with a non-text message (e.g. type='image') → 200.
        No background task should be added because we only handle text messages.

        The router filters for text-type messages before proceeding to find
        the professional and schedule the background task. An image-only payload
        is acknowledged with 200 but not processed.
        """
        # Deep copy to avoid mutating the shared fixture
        payload = copy.deepcopy(mock_whatsapp_webhook_payload)
        payload["entry"][0]["changes"][0]["value"]["messages"][0]["type"] = "image"
        body = json.dumps(payload).encode()
        sig = make_signature(body)

        with patch(
            "whatsapp.router._process_webhook_background",
            new_callable=AsyncMock,
        ) as mock_bg:
            response = await http_client.post(
                "/api/v1/whatsapp/webhook",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Hub-Signature-256": sig,
                },
            )
            mock_bg.assert_not_called()

        assert response.status_code == 200


# ===========================================================================
# TestListConversations
# GET /api/v1/whatsapp/conversations
# ===========================================================================


class TestListConversations:
    async def test_requires_auth_returns_401(self, http_client: AsyncClient) -> None:
        """
        GET /conversations without a JWT → 401 Unauthorized.

        list_conversations uses TenantSession which requires a valid Bearer token.
        """
        response = await http_client.get("/api/v1/whatsapp/conversations")

        assert response.status_code == 401

    async def test_returns_200_with_empty_list(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """
        GET /conversations with valid JWT and no conversations in the DB → 200 with [].

        authenticated_http_client injects the test DB session, so the query runs
        against the (empty) test transaction and returns an empty list.
        """
        response = await authenticated_http_client.get("/api/v1/whatsapp/conversations")

        assert response.status_code == 200
        assert response.json() == []


# ===========================================================================
# TestGetConversationDetail
# GET /api/v1/whatsapp/conversations/{conversation_id}
# ===========================================================================


class TestGetConversationDetail:
    async def test_requires_auth_returns_401(self, http_client: AsyncClient) -> None:
        """
        GET /conversations/{id} without a JWT → 401 Unauthorized.
        """
        response = await http_client.get(f"/api/v1/whatsapp/conversations/{uuid4()}")

        assert response.status_code == 401

    async def test_returns_404_for_unknown_conversation(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """
        GET /conversations/{id} with valid JWT but unknown UUID → 404.

        The service raises NotFoundError when get_conversation_by_id returns None,
        and the router converts it to 404. RLS makes cross-tenant UUIDs look the
        same as missing UUIDs — both return None from the repository.
        """
        response = await authenticated_http_client.get(f"/api/v1/whatsapp/conversations/{uuid4()}")

        assert response.status_code == 404


# ===========================================================================
# TestHandoff
# POST /api/v1/whatsapp/conversations/{conversation_id}/handoff
# ===========================================================================


class TestHandoff:
    async def test_requires_auth_returns_401(self, http_client: AsyncClient) -> None:
        """
        POST /conversations/{id}/handoff without a JWT → 401 Unauthorized.
        """
        response = await http_client.post(f"/api/v1/whatsapp/conversations/{uuid4()}/handoff")

        assert response.status_code == 401

    async def test_returns_404_for_unknown_conversation(
        self, authenticated_http_client: AsyncClient
    ) -> None:
        """
        POST /conversations/{id}/handoff with valid JWT but unknown UUID → 404.

        handoff_to_professional raises NotFoundError when the conversation
        is not found (or belongs to another tenant — RLS makes them the same).
        The router catches NotFoundError and returns 404.
        """
        response = await authenticated_http_client.post(
            f"/api/v1/whatsapp/conversations/{uuid4()}/handoff"
        )

        assert response.status_code == 404
