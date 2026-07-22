"""Tests for TwilioSharedAccountProvider."""

import unittest.mock
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import httpx
import pytest
import respx

from whatsapp.providers.base import InvalidSignatureError, ProviderError
from whatsapp.providers.twilio_shared import TwilioSharedAccountProvider, _extract_tag

# ── Helpers ────────────────────────────────────────────────────────────────


def _make_provider(mock_session=None):
    """Cria provider com sessão mockada."""
    session = mock_session or AsyncMock()
    return TwilioSharedAccountProvider(session)


# ── Tests ──────────────────────────────────────────────────────────────────


class TestExtractTag:
    def test_extracts_tag_from_start(self):
        assert _extract_tag("DRANA-ABC123 oi") == "ABC123"

    def test_returns_none_if_no_tag(self):
        assert _extract_tag("Oi, quero agendar") is None

    def test_case_insensitive(self):
        assert _extract_tag("drana-XYZ789 olá") == "XYZ789"

    def test_tag_only_no_body(self):
        assert _extract_tag("DRANA-SLUG1") == "SLUG1"


class TestTwilioSharedProvider:
    def test_instantiates(self):
        p = _make_provider()
        assert p is not None

    async def test_parse_webhook_rejects_invalid_signature(self, monkeypatch):
        from core.config import settings

        monkeypatch.setattr(settings, "TWILIO_WEBHOOK_VALIDATION", True)
        monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "fake_token")

        p = _make_provider()
        raw = {"From": "whatsapp:+5511999999999", "Body": "oi", "MessageSid": "SM123"}
        with pytest.raises(InvalidSignatureError):
            await p.parse_webhook(raw_payload=raw, signature_header="invalid")

    async def test_parse_webhook_skips_validation_when_disabled(self, monkeypatch):
        from core.config import settings

        monkeypatch.setattr(settings, "TWILIO_WEBHOOK_VALIDATION", False)

        prof_id = uuid4()
        mock_binding = MagicMock()
        mock_binding.professional_id = prof_id

        mock_binding_repo = AsyncMock()
        mock_binding_repo.find_by_phone = AsyncMock(return_value=mock_binding)

        # Com validação desabilitada, qualquer signature_header deve ser aceito.
        # Se InvalidSignatureError for levantado, o teste falha — é o comportamento esperado.
        p = _make_provider()
        with unittest.mock.patch(
            "whatsapp.providers.twilio_shared.PhoneBindingRepository",
            return_value=mock_binding_repo,
        ):
            result = await p.parse_webhook(
                raw_payload={"From": "whatsapp:+5511999999999", "Body": "oi", "MessageSid": "SM1"},
                signature_header="qualquer_coisa",
            )
        # Se chegou aqui sem InvalidSignatureError, o teste passou
        assert result is not None
        assert result.professional_id == prof_id

    async def test_parse_webhook_returns_none_for_empty_body(self, monkeypatch):
        from core.config import settings

        monkeypatch.setattr(settings, "TWILIO_WEBHOOK_VALIDATION", False)

        mock_binding_repo = AsyncMock()
        mock_binding_repo.find_by_phone = AsyncMock(return_value=None)
        mock_account_repo = AsyncMock()
        mock_account_repo.find_by_routing_tag = AsyncMock(return_value=None)

        p = _make_provider()
        with (
            unittest.mock.patch(
                "whatsapp.providers.twilio_shared.PhoneBindingRepository",
                return_value=mock_binding_repo,
            ),
            unittest.mock.patch(
                "whatsapp.providers.twilio_shared.WhatsAppAccountRepository",
                return_value=mock_account_repo,
            ),
        ):
            result = await p.parse_webhook(
                raw_payload={"From": "whatsapp:+5511999999999", "Body": "", "MessageSid": "SM1"},
                signature_header=None,
            )
        assert result is None

    async def test_parse_webhook_resolves_professional_via_binding(self, monkeypatch):
        from core.config import settings

        monkeypatch.setattr(settings, "TWILIO_WEBHOOK_VALIDATION", False)

        prof_id = uuid4()
        mock_binding = MagicMock()
        mock_binding.professional_id = prof_id

        mock_binding_repo = AsyncMock()
        mock_binding_repo.find_by_phone = AsyncMock(return_value=mock_binding)

        p = _make_provider()
        with unittest.mock.patch(
            "whatsapp.providers.twilio_shared.PhoneBindingRepository",
            return_value=mock_binding_repo,
        ):
            result = await p.parse_webhook(
                raw_payload={"From": "whatsapp:+5511999999999", "Body": "oi", "MessageSid": "SM1"},
                signature_header=None,
            )

        assert result is not None
        assert result.professional_id == prof_id
        assert result.provider_type == "twilio_shared"

    async def test_parse_webhook_creates_binding_for_new_number_with_tag(self, monkeypatch):
        from core.config import settings

        monkeypatch.setattr(settings, "TWILIO_WEBHOOK_VALIDATION", False)

        prof_id = uuid4()
        mock_account = MagicMock()
        mock_account.professional_id = prof_id

        mock_new_binding = MagicMock()
        mock_new_binding.professional_id = prof_id

        mock_binding_repo = AsyncMock()
        mock_binding_repo.find_by_phone = AsyncMock(return_value=None)
        mock_binding_repo.create = AsyncMock(return_value=mock_new_binding)

        mock_account_repo = AsyncMock()
        mock_account_repo.find_by_routing_tag = AsyncMock(return_value=mock_account)

        p = _make_provider()
        with (
            unittest.mock.patch(
                "whatsapp.providers.twilio_shared.PhoneBindingRepository",
                return_value=mock_binding_repo,
            ),
            unittest.mock.patch(
                "whatsapp.providers.twilio_shared.WhatsAppAccountRepository",
                return_value=mock_account_repo,
            ),
        ):
            result = await p.parse_webhook(
                raw_payload={
                    "From": "whatsapp:+5511999999999",
                    "Body": "DRANA-XYZ123 oi tudo bem",
                    "MessageSid": "SM2",
                },
                signature_header=None,
            )

        assert result is not None
        assert result.professional_id == prof_id
        mock_binding_repo.create.assert_awaited_once()
        call_kwargs = mock_binding_repo.create.call_args.kwargs
        assert call_kwargs["bound_via"] == "tag"

    @respx.mock
    async def test_send_text_calls_twilio_api(self, monkeypatch):
        from core.config import settings

        monkeypatch.setattr(settings, "TWILIO_ACCOUNT_SID", "ACtest123")
        monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "auth_token_test")
        monkeypatch.setattr(settings, "TWILIO_SHARED_PHONE_NUMBER", "+5511000000000")
        monkeypatch.setattr(settings, "TWILIO_MESSAGING_SERVICE_SID", None)

        respx.post("https://api.twilio.com/2010-04-01/Accounts/ACtest123/Messages.json").mock(
            return_value=httpx.Response(201, json={"sid": "SM_RESULT_123"})
        )

        p = _make_provider()
        result = await p.send_text(
            professional_id=uuid4(),
            to="+5511999999999",
            body="Lembrete de consulta",
        )
        assert result.provider_message_id == "SM_RESULT_123"
        assert result.status == "queued"

    @respx.mock
    async def test_send_text_raises_provider_error_on_http_error(self, monkeypatch):
        from core.config import settings

        monkeypatch.setattr(settings, "TWILIO_ACCOUNT_SID", "ACtest123")
        monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "auth_token_test")
        monkeypatch.setattr(settings, "TWILIO_SHARED_PHONE_NUMBER", "+5511000000000")

        respx.post("https://api.twilio.com/2010-04-01/Accounts/ACtest123/Messages.json").mock(
            return_value=httpx.Response(401, json={"code": 20003, "message": "Authenticate"})
        )

        p = _make_provider()
        with pytest.raises(ProviderError) as exc_info:
            await p.send_text(professional_id=uuid4(), to="+5511999999999", body="msg")
        assert exc_info.value.status_code == 401

    async def test_verify_webhook_challenge_returns_none(self):
        p = _make_provider()
        result = await p.verify_webhook_challenge(params={"hub.challenge": "12345"})
        assert result is None
