"""Tests for cleanup_expired_refresh_tokens job."""

from unittest.mock import AsyncMock, patch

import pytest

from jobs.tasks.cleanup import cleanup_expired_refresh_tokens


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    return session


class TestCleanupExpiredRefreshTokens:
    async def test_calls_delete_expired_once(self, mock_session) -> None:
        """delete_expired() deve ser chamado exatamente uma vez."""
        mock_repo = AsyncMock()
        mock_repo.delete_expired.return_value = 3

        with (
            patch("jobs.tasks.cleanup.async_session_maker", return_value=mock_session),
            patch("jobs.tasks.cleanup.RefreshTokenRepository", return_value=mock_repo),
        ):
            await cleanup_expired_refresh_tokens()

        mock_repo.delete_expired.assert_called_once()

    async def test_commits_after_delete(self, mock_session) -> None:
        """session.commit() deve ser chamado após delete_expired()."""
        mock_repo = AsyncMock()
        mock_repo.delete_expired.return_value = 0

        with (
            patch("jobs.tasks.cleanup.async_session_maker", return_value=mock_session),
            patch("jobs.tasks.cleanup.RefreshTokenRepository", return_value=mock_repo),
        ):
            await cleanup_expired_refresh_tokens()

        mock_session.commit.assert_called_once()

    async def test_delete_is_called_before_commit(self, mock_session) -> None:
        """Ordem: delete_expired primeiro, depois commit."""
        call_order = []
        mock_repo = AsyncMock()
        mock_repo.delete_expired.side_effect = lambda: call_order.append("delete") or 5
        mock_session.commit.side_effect = lambda: call_order.append("commit")

        with (
            patch("jobs.tasks.cleanup.async_session_maker", return_value=mock_session),
            patch("jobs.tasks.cleanup.RefreshTokenRepository", return_value=mock_repo),
        ):
            await cleanup_expired_refresh_tokens()

        assert call_order == ["delete", "commit"]

    async def test_zero_deleted_does_not_raise(self, mock_session) -> None:
        """count=0 é resultado normal — não deve levantar exceção."""
        mock_repo = AsyncMock()
        mock_repo.delete_expired.return_value = 0

        with (
            patch("jobs.tasks.cleanup.async_session_maker", return_value=mock_session),
            patch("jobs.tasks.cleanup.RefreshTokenRepository", return_value=mock_repo),
        ):
            # Não deve levantar exceção
            await cleanup_expired_refresh_tokens()
