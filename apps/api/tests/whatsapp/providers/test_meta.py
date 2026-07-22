"""Tests for MetaCloudProvider."""

import hashlib
import hmac
import json
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import httpx
import pytest
import respx

from whatsapp.providers.base import InvalidSignatureError, ProviderError
from whatsapp.providers.meta import MetaCloudProvider


def _make_provider(mock_session=None):
    session = mock_session or AsyncMock()
    return MetaCloudProvider(session)


def _make_valid_signature(body_bytes: bytes, secret: str) -> str:
    """Gera assinatura HMAC-SHA256 válida para testes."""
    computed = hmac.new(secret.encode(), body_bytes, hashlib.sha256).hexdigest()
    return f"sha256={computed}"


class TestMetaCloudProvider:
    def test_instantiates(self):
        p = _make_provider()
        assert p is not None

    async def test_verify_webhook_challenge_returns_challenge_for_valid_token(self, monkeypatch):
        from core.config import settings

        monkeypatch.setattr(settings, "META_WEBHOOK_VERIFY_TOKEN", "my_verify_token")

        p = _make_provider()
        result = await p.verify_webhook_challenge(
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "my_verify_token",
                "hub.challenge": "12345",
            }
        )
        assert result == "12345"

    async def test_verify_webhook_challenge_returns_none_for_wrong_token(self, monkeypatch):
        from core.config import settings

        monkeypatch.setattr(settings, "META_WEBHOOK_VERIFY_TOKEN", "correct_token")

        p = _make_provider()
        result = await p.verify_webhook_challenge(
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "wrong_token",
                "hub.challenge": "12345",
            }
        )
        assert result is None

    async def test_verify_webhook_challenge_falls_back_to_legacy_token(self, monkeypatch):
        from core.config import settings

        monkeypatch.setattr(settings, "META_WEBHOOK_VERIFY_TOKEN", None)
        monkeypatch.setattr(settings, "WHATSAPP_VERIFY_TOKEN", "legacy_token")

        p = _make_provider()
        result = await p.verify_webhook_challenge(
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "legacy_token",
                "hub.challenge": "abc123",
            }
        )
        assert result == "abc123"

    async def test_parse_webhook_rejects_invalid_signature(self, monkeypatch):
        from core.config import settings

        monkeypatch.setattr(settings, "META_APP_SECRET", "real_secret")

        p = _make_provider()
        payload = {"object": "whatsapp_business_account", "entry": []}
        with pytest.raises(InvalidSignatureError):
            await p.parse_webhook(raw_payload=payload, signature_header="sha256=invalid")

    async def test_parse_webhook_returns_none_for_non_text_message(self, monkeypatch):
        from core.config import settings

        secret = "test_app_secret"
        monkeypatch.setattr(settings, "META_APP_SECRET", secret)

        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "WBA_ID",
                    "changes": [
                        {
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {"phone_number_id": "PHONE_ID_123"},
                                "messages": [
                                    {"type": "image", "from": "5511999999999", "id": "WAMID1"}
                                ],
                            },
                            "field": "messages",
                        }
                    ],
                }
            ],
        }
        body_bytes = json.dumps(payload, separators=(",", ":")).encode()
        sig = _make_valid_signature(body_bytes, secret)

        p = _make_provider()
        result = await p.parse_webhook(raw_payload=payload, signature_header=sig)
        assert result is None

    async def test_parse_webhook_returns_inbound_for_valid_text(self, monkeypatch):
        from core.config import settings

        secret = "test_app_secret"
        monkeypatch.setattr(settings, "META_APP_SECRET", secret)

        prof_id = uuid4()
        mock_account = MagicMock()
        mock_account.professional_id = prof_id

        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "WBA_ID",
                    "changes": [
                        {
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {"phone_number_id": "PHONE_ID_123"},
                                "contacts": [{"wa_id": "5511999999999"}],
                                "messages": [
                                    {
                                        "type": "text",
                                        "from": "5511999999999",
                                        "id": "WAMID1",
                                        "text": {"body": "Oi quero agendar"},
                                    }
                                ],
                            },
                            "field": "messages",
                        }
                    ],
                }
            ],
        }
        body_bytes = json.dumps(payload, separators=(",", ":")).encode()
        sig = _make_valid_signature(body_bytes, secret)

        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_account
        session.execute = AsyncMock(return_value=mock_result)

        p = MetaCloudProvider(session)
        result = await p.parse_webhook(raw_payload=payload, signature_header=sig)
        assert result is not None
        assert result.professional_id == prof_id
        assert result.from_phone == "+5511999999999"
        assert result.provider_type == "meta"

    @respx.mock
    async def test_send_text_calls_meta_api(self, monkeypatch):
        from whatsapp.providers.crypto import encrypt_credentials

        prof_id = uuid4()

        mock_account = MagicMock()
        mock_account.provider_type = "meta"
        mock_account.phone_number_id = "PHONE_ID_123"
        mock_account.access_token_encrypted = encrypt_credentials("test_access_token")

        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_account
        session.execute = AsyncMock(return_value=mock_result)

        respx.post("https://graph.facebook.com/v18.0/PHONE_ID_123/messages").mock(
            return_value=httpx.Response(200, json={"messages": [{"id": "wamid.TEST123"}]})
        )

        p = MetaCloudProvider(session)
        result = await p.send_text(
            professional_id=prof_id,
            to="+5511999999999",
            body="Lembrete de consulta",
        )
        assert result.provider_message_id == "wamid.TEST123"
        assert result.status == "sent"

    async def test_send_text_raises_when_no_meta_account(self):
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_result)

        p = MetaCloudProvider(session)
        with pytest.raises(ProviderError) as exc_info:
            await p.send_text(professional_id=uuid4(), to="+5511999999999", body="msg")
        assert "meta" in str(exc_info.value).lower() or exc_info.value.provider == "meta"
