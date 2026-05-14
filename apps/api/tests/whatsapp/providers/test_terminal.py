"""Tests for TerminalProvider."""

from uuid import uuid4

import pytest

from whatsapp.providers.terminal import TerminalProvider
from whatsapp.schemas import TemplateMessage


class TestTerminalProvider:
    def test_instantiates_in_development(self):
        """TerminalProvider deve instanciar normalmente fora de produção."""
        provider = TerminalProvider()
        assert provider is not None

    def test_blocked_in_production(self, monkeypatch):
        """Em produção, __init__ deve levantar RuntimeError com 'produção' no texto."""
        from core.config import settings

        monkeypatch.setattr(settings, "ENVIRONMENT", "production")
        with pytest.raises(RuntimeError, match="produção"):
            TerminalProvider()

    async def test_send_text_writes_to_stdout(self, capsys):
        provider = TerminalProvider()
        result = await provider.send_text(
            professional_id=uuid4(),
            to="+5511999999999",
            body="Olá, sua consulta é amanhã",
        )
        captured = capsys.readouterr()
        assert "+5511999999999" in captured.out
        assert "Olá, sua consulta é amanhã" in captured.out
        assert result.status == "sent"
        assert result.provider_message_id.startswith("terminal-")

    async def test_send_template_writes_to_stdout(self, capsys):
        provider = TerminalProvider()
        template = TemplateMessage(name="appointment_reminder", params={"name": "João"})
        result = await provider.send_template(
            professional_id=uuid4(),
            to="+5511888888888",
            template=template,
        )
        captured = capsys.readouterr()
        assert "appointment_reminder" in captured.out
        assert "+5511888888888" in captured.out
        assert result.status == "sent"

    async def test_parse_webhook_returns_inbound_message(self):
        provider = TerminalProvider()
        prof_id = uuid4()
        payload = {
            "professional_id": str(prof_id),
            "from_phone": "+5511999999999",
            "body": "Oi, quero remarcar",
            "message_id": "terminal-test-001",
        }
        result = await provider.parse_webhook(raw_payload=payload, signature_header=None)
        assert result is not None
        assert result.professional_id == prof_id
        assert result.from_phone == "+5511999999999"
        assert result.body == "Oi, quero remarcar"
        assert result.provider_type == "terminal"

    async def test_parse_webhook_returns_none_for_invalid_payload(self):
        provider = TerminalProvider()
        result = await provider.parse_webhook(raw_payload={}, signature_header=None)
        assert result is None

    async def test_verify_webhook_challenge_returns_none(self):
        provider = TerminalProvider()
        result = await provider.verify_webhook_challenge(params={"hub.challenge": "12345"})
        assert result is None

    async def test_send_text_each_call_has_unique_message_id(self):
        provider = TerminalProvider()
        r1 = await provider.send_text(professional_id=uuid4(), to="+5511999999999", body="msg1")
        r2 = await provider.send_text(professional_id=uuid4(), to="+5511999999999", body="msg2")
        assert r1.provider_message_id != r2.provider_message_id
