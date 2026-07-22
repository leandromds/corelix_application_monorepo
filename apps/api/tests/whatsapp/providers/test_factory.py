"""Tests for WhatsApp provider factory."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from whatsapp.providers.factory import get_provider_for_professional
from whatsapp.providers.meta import MetaCloudProvider
from whatsapp.providers.terminal import TerminalProvider
from whatsapp.providers.twilio_shared import TwilioSharedAccountProvider


class TestProviderFactory:
    async def test_returns_terminal_when_force_flag_is_set(self, monkeypatch):
        from core.config import settings

        monkeypatch.setattr(settings, "WHATSAPP_FORCE_TERMINAL", True)

        session = AsyncMock()
        provider = await get_provider_for_professional(
            professional_id=uuid4(),
            session=session,
        )
        assert isinstance(provider, TerminalProvider)

    async def test_returns_meta_when_professional_has_meta_account(self, monkeypatch):
        from core.config import settings

        monkeypatch.setattr(settings, "WHATSAPP_FORCE_TERMINAL", False)

        prof_id = uuid4()
        mock_account = MagicMock()
        mock_account.provider_type = "meta"

        session = AsyncMock()
        mock_repo = AsyncMock()
        mock_repo.find_by_professional_id = AsyncMock(return_value=mock_account)

        with patch("whatsapp.providers.factory.WhatsAppAccountRepository", return_value=mock_repo):
            provider = await get_provider_for_professional(
                professional_id=prof_id,
                session=session,
            )
        assert isinstance(provider, MetaCloudProvider)

    async def test_returns_twilio_when_no_meta_account(self, monkeypatch):
        from core.config import settings

        monkeypatch.setattr(settings, "WHATSAPP_FORCE_TERMINAL", False)

        session = AsyncMock()
        mock_repo = AsyncMock()
        mock_repo.find_by_professional_id = AsyncMock(return_value=None)

        with patch("whatsapp.providers.factory.WhatsAppAccountRepository", return_value=mock_repo):
            provider = await get_provider_for_professional(
                professional_id=uuid4(),
                session=session,
            )
        assert isinstance(provider, TwilioSharedAccountProvider)

    async def test_returns_twilio_when_account_is_twilio_shared(self, monkeypatch):
        from core.config import settings

        monkeypatch.setattr(settings, "WHATSAPP_FORCE_TERMINAL", False)

        mock_account = MagicMock()
        mock_account.provider_type = "twilio_shared"

        session = AsyncMock()
        mock_repo = AsyncMock()
        mock_repo.find_by_professional_id = AsyncMock(return_value=mock_account)

        with patch("whatsapp.providers.factory.WhatsAppAccountRepository", return_value=mock_repo):
            provider = await get_provider_for_professional(
                professional_id=uuid4(),
                session=session,
            )
        assert isinstance(provider, TwilioSharedAccountProvider)

    async def test_force_terminal_overrides_meta_account(self, monkeypatch):
        """WHATSAPP_FORCE_TERMINAL=True deve prevalecer mesmo com conta Meta ativa."""
        from core.config import settings

        monkeypatch.setattr(settings, "WHATSAPP_FORCE_TERMINAL", True)

        mock_account = MagicMock()
        mock_account.provider_type = "meta"

        session = AsyncMock()
        mock_repo = AsyncMock()
        mock_repo.find_by_professional_id = AsyncMock(return_value=mock_account)

        with patch("whatsapp.providers.factory.WhatsAppAccountRepository", return_value=mock_repo):
            provider = await get_provider_for_professional(
                professional_id=uuid4(),
                session=session,
            )
        assert isinstance(provider, TerminalProvider)
