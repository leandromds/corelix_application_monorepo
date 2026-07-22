"""Tests for Meta webhook endpoints."""

import hashlib
import hmac
import json

import pytest
from httpx import AsyncClient


def _make_meta_signature(body: bytes, secret: str) -> str:
    computed = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={computed}"


class TestMetaWebhookChallenge:
    async def test_returns_hub_challenge_for_valid_token(
        self, http_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """GET com token válido deve retornar hub.challenge como texto."""
        from core.config import settings

        monkeypatch.setattr(settings, "META_WEBHOOK_VERIFY_TOKEN", "test_verify_token")
        monkeypatch.setattr(settings, "WHATSAPP_VERIFY_TOKEN", "test_verify_token")

        response = await http_client.get(
            "/api/v1/webhooks/whatsapp/meta",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "test_verify_token",
                "hub.challenge": "12345",
            },
        )
        assert response.status_code == 200
        assert response.text == "12345"

    async def test_returns_403_for_wrong_token(
        self, http_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """GET com token errado deve retornar 403."""
        from core.config import settings

        monkeypatch.setattr(settings, "META_WEBHOOK_VERIFY_TOKEN", "correct_token")
        monkeypatch.setattr(settings, "WHATSAPP_VERIFY_TOKEN", "correct_token")

        response = await http_client.get(
            "/api/v1/webhooks/whatsapp/meta",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "wrong_token",
                "hub.challenge": "12345",
            },
        )
        assert response.status_code == 403


class TestMetaWebhookPost:
    async def test_returns_200_for_valid_payload(
        self, http_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """POST com payload válido e assinatura correta deve retornar 200."""
        from core.config import settings

        secret = "test_app_secret"
        monkeypatch.setattr(settings, "META_APP_SECRET", secret)
        monkeypatch.setattr(settings, "WHATSAPP_APP_SECRET", secret)

        payload = {"object": "whatsapp_business_account", "entry": []}
        body = json.dumps(payload).encode()
        sig = _make_meta_signature(body, secret)

        response = await http_client.post(
            "/api/v1/webhooks/whatsapp/meta",
            content=body,
            headers={"Content-Type": "application/json", "X-Hub-Signature-256": sig},
        )
        assert response.status_code == 200

    async def test_returns_200_even_for_invalid_json(self, http_client: AsyncClient) -> None:
        """POST com JSON inválido deve retornar 200 (idempotente, sem crash)."""
        response = await http_client.post(
            "/api/v1/webhooks/whatsapp/meta",
            content=b"invalid json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 200
