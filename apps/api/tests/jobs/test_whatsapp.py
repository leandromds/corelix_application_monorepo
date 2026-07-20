"""Tests for renew_whatsapp_tokens job."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet

from jobs.tasks.whatsapp import renew_whatsapp_tokens

# Gera uma chave Fernet válida para os testes
_TEST_FERNET_KEY = Fernet.generate_key().decode()
_FERNET = Fernet(_TEST_FERNET_KEY.encode())


def _encrypt(token: str) -> str:
    return _FERNET.encrypt(token.encode()).decode()


def make_professional(*, token: str = "valid-meta-token", days_until_expiry: int = 3) -> MagicMock:
    prof = MagicMock()
    prof.id = uuid4()
    prof.whatsapp_access_token = _encrypt(token)
    prof.whatsapp_token_expires_at = datetime.now(UTC) + timedelta(days=days_until_expiry)
    return prof


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    return session


def _mock_execute_result(rows: list) -> MagicMock:
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = rows
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    return mock_result


class TestRenewWhatsappTokens:
    async def test_no_professionals_skips_api_calls(self, mock_session) -> None:
        """Nenhum profissional com token expirando → não chama _exchange_token."""
        mock_session.execute = AsyncMock(return_value=_mock_execute_result([]))

        with (
            patch("jobs.tasks.whatsapp.async_session_maker", return_value=mock_session),
            patch("jobs.tasks.whatsapp.settings") as mock_settings,
            patch("jobs.tasks.whatsapp._exchange_token", new_callable=AsyncMock) as mock_exchange,
        ):
            mock_settings.ENCRYPTION_KEY = _TEST_FERNET_KEY
            await renew_whatsapp_tokens()

        mock_exchange.assert_not_called()
        mock_session.commit.assert_not_called()

    async def test_new_token_is_encrypted_before_saving(self, mock_session) -> None:
        """O novo token retornado pela Meta API deve ser re-encriptado com Fernet."""
        prof = make_professional()
        mock_session.execute = AsyncMock(return_value=_mock_execute_result([prof]))

        new_token = "new-meta-token-xyz"
        new_expires_at = datetime.now(UTC) + timedelta(days=60)

        with (
            patch("jobs.tasks.whatsapp.async_session_maker", return_value=mock_session),
            patch("jobs.tasks.whatsapp.settings") as mock_settings,
            patch("jobs.tasks.whatsapp._exchange_token", new_callable=AsyncMock) as mock_exchange,
        ):
            mock_settings.ENCRYPTION_KEY = _TEST_FERNET_KEY
            mock_exchange.return_value = (new_token, new_expires_at)

            await renew_whatsapp_tokens()

        # O token salvo deve ser decifrável e igual ao new_token
        saved_encrypted = prof.whatsapp_access_token
        fernet = Fernet(_TEST_FERNET_KEY.encode())
        decrypted = fernet.decrypt(saved_encrypted.encode()).decode()
        assert decrypted == new_token

    async def test_token_expires_at_is_updated(self, mock_session) -> None:
        """whatsapp_token_expires_at deve ser atualizado com o novo prazo."""
        prof = make_professional()
        mock_session.execute = AsyncMock(return_value=_mock_execute_result([prof]))

        new_expires_at = datetime.now(UTC) + timedelta(days=60)

        with (
            patch("jobs.tasks.whatsapp.async_session_maker", return_value=mock_session),
            patch("jobs.tasks.whatsapp.settings") as mock_settings,
            patch("jobs.tasks.whatsapp._exchange_token", new_callable=AsyncMock) as mock_exchange,
        ):
            mock_settings.ENCRYPTION_KEY = _TEST_FERNET_KEY
            mock_exchange.return_value = ("new-token", new_expires_at)

            await renew_whatsapp_tokens()

        assert prof.whatsapp_token_expires_at == new_expires_at

    async def test_meta_api_failure_does_not_stop_other_professionals(self, mock_session) -> None:
        """httpx.HTTPError numa renovação → logado, próximo profissional processado."""
        import httpx

        prof_a = make_professional(token="token-a")
        prof_b = make_professional(token="token-b")
        mock_session.execute = AsyncMock(return_value=_mock_execute_result([prof_a, prof_b]))

        new_expires_at = datetime.now(UTC) + timedelta(days=60)
        call_count = 0

        async def side_effect(token: str):
            nonlocal call_count
            call_count += 1
            if token == "token-a":
                raise httpx.HTTPError("Meta API down")
            return ("new-token-b", new_expires_at)

        with (
            patch("jobs.tasks.whatsapp.async_session_maker", return_value=mock_session),
            patch("jobs.tasks.whatsapp.settings") as mock_settings,
            patch("jobs.tasks.whatsapp._exchange_token", side_effect=side_effect),
        ):
            mock_settings.ENCRYPTION_KEY = _TEST_FERNET_KEY

            await renew_whatsapp_tokens()

        # Ambos foram tentados
        assert call_count == 2
        # prof_b foi atualizado mesmo com prof_a falhando
        assert prof_b.whatsapp_token_expires_at == new_expires_at

    async def test_invalid_fernet_token_is_skipped(self, mock_session) -> None:
        """Token corrompido (InvalidToken) → profissional pulado sem propagar erro."""
        prof = MagicMock()
        prof.id = uuid4()
        prof.whatsapp_access_token = "not-valid-fernet-data"
        prof.whatsapp_token_expires_at = datetime.now(UTC) + timedelta(days=1)

        mock_session.execute = AsyncMock(return_value=_mock_execute_result([prof]))

        with (
            patch("jobs.tasks.whatsapp.async_session_maker", return_value=mock_session),
            patch("jobs.tasks.whatsapp.settings") as mock_settings,
            patch("jobs.tasks.whatsapp._exchange_token", new_callable=AsyncMock) as mock_exchange,
        ):
            mock_settings.ENCRYPTION_KEY = _TEST_FERNET_KEY

            # Não deve levantar exceção
            await renew_whatsapp_tokens()

        # _exchange_token não foi chamado (falhou na decriptação antes)
        mock_exchange.assert_not_called()

    async def test_commits_after_processing_all_professionals(self, mock_session) -> None:
        """session.commit() é chamado uma vez ao final, mesmo com múltiplos profissionais."""
        prof_a = make_professional(token="token-a")
        prof_b = make_professional(token="token-b")
        mock_session.execute = AsyncMock(return_value=_mock_execute_result([prof_a, prof_b]))

        new_expires_at = datetime.now(UTC) + timedelta(days=60)

        with (
            patch("jobs.tasks.whatsapp.async_session_maker", return_value=mock_session),
            patch("jobs.tasks.whatsapp.settings") as mock_settings,
            patch("jobs.tasks.whatsapp._exchange_token", new_callable=AsyncMock) as mock_exchange,
        ):
            mock_settings.ENCRYPTION_KEY = _TEST_FERNET_KEY
            mock_exchange.return_value = ("new-token", new_expires_at)

            await renew_whatsapp_tokens()

        mock_session.commit.assert_called_once()
