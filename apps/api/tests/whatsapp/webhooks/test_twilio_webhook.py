"""Tests for Twilio webhook endpoints."""

import pytest
from httpx import AsyncClient


class TestTwilioWebhook:
    async def test_returns_200_immediately(
        self, http_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """POST com payload válido deve retornar 200 imediatamente."""
        from core.config import settings

        monkeypatch.setattr(settings, "TWILIO_WEBHOOK_VALIDATION", False)

        response = await http_client.post(
            "/api/v1/webhooks/whatsapp/twilio",
            data={
                "From": "whatsapp:+5511999999999",
                "Body": "Oi",
                "MessageSid": "SM_TEST_001",
            },
        )
        assert response.status_code == 200

    async def test_returns_200_for_empty_payload(self, http_client: AsyncClient) -> None:
        """POST com payload vazio deve retornar 200 (background task silencioso)."""
        response = await http_client.post(
            "/api/v1/webhooks/whatsapp/twilio",
            data={},
        )
        assert response.status_code == 200
