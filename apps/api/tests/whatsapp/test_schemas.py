"""Tests for WhatsApp canonical schema types (provider-agnostic dialect)."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from whatsapp.schemas import InboundMessage, SendResult, TemplateMessage


class TestInboundMessage:
    def test_valid_e164_phone_accepted(self):
        msg = InboundMessage(
            professional_id=uuid4(),
            from_phone="+5511999999999",
            body="oi",
            provider_message_id="m1",
            received_at=datetime.now(UTC),
        )
        assert msg.from_phone == "+5511999999999"

    def test_rejects_phone_without_plus(self):
        with pytest.raises(ValidationError):
            InboundMessage(
                professional_id=uuid4(),
                from_phone="5511999999999",  # sem +
                body="oi",
                provider_message_id="m1",
                received_at=datetime.now(UTC),
            )

    def test_rejects_non_e164_format(self):
        with pytest.raises(ValidationError):
            InboundMessage(
                professional_id=uuid4(),
                from_phone="11999999999",  # falta +55
                body="oi",
                provider_message_id="m1",
                received_at=datetime.now(UTC),
            )

    def test_provider_type_defaults_to_unknown(self):
        msg = InboundMessage(
            professional_id=uuid4(),
            from_phone="+5511999999999",
            body="oi",
            provider_message_id="m1",
            received_at=datetime.now(UTC),
        )
        assert msg.provider_type == "unknown"

    def test_provider_type_can_be_set(self):
        msg = InboundMessage(
            professional_id=uuid4(),
            from_phone="+5511999999999",
            body="oi",
            provider_message_id="m1",
            received_at=datetime.now(UTC),
            provider_type="twilio_shared",
        )
        assert msg.provider_type == "twilio_shared"


class TestSendResult:
    def test_sent_status(self):
        r = SendResult(provider_message_id="sm1", status="sent")
        assert r.status == "sent"
        assert r.error is None

    def test_failed_status_with_error(self):
        r = SendResult(provider_message_id="sm2", status="failed", error="timeout")
        assert r.status == "failed"
        assert r.error == "timeout"

    def test_invalid_status_raises(self):
        with pytest.raises(ValidationError):
            SendResult(provider_message_id="sm3", status="unknown_status")


class TestTemplateMessage:
    def test_defaults(self):
        t = TemplateMessage(name="appointment_reminder")
        assert t.language_code == "pt_BR"
        assert t.params == {}

    def test_with_params(self):
        t = TemplateMessage(
            name="appointment_reminder",
            language_code="pt_BR",
            params={"name": "João", "time": "14h"},
        )
        assert t.params["name"] == "João"
