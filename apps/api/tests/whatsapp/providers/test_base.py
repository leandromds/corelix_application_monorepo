"""Tests for WhatsApp provider base classes and exceptions."""

import pytest

from whatsapp.providers.base import InvalidSignatureError, ProviderError, WhatsAppProvider


class TestProviderError:
    def test_str_representation(self):
        err = ProviderError(provider="twilio", message="rate limited", status_code=429)
        assert "twilio" in str(err)
        assert "rate limited" in str(err)

    def test_stores_attributes(self):
        err = ProviderError(provider="meta", message="invalid token", status_code=401)
        assert err.provider == "meta"
        assert err.status_code == 401


class TestInvalidSignatureError:
    def test_str_representation(self):
        err = InvalidSignatureError(provider="twilio")
        assert "twilio" in str(err)

    def test_stores_provider(self):
        err = InvalidSignatureError(provider="meta")
        assert err.provider == "meta"


class TestWhatsAppProvider:
    def test_cannot_instantiate_abc(self):
        """WhatsAppProvider is abstract — direct instantiation must fail."""
        with pytest.raises(TypeError):
            WhatsAppProvider()  # type: ignore[abstract]
