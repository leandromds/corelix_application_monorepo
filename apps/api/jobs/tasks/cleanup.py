"""Job 1: Delete expired refresh tokens — nightly purge."""

import logging

from auth.repository import RefreshTokenRepository
from core.database import async_session_maker

logger = logging.getLogger(__name__)


async def cleanup_expired_refresh_tokens() -> None:
    """
    Delete all refresh tokens where expires_at < NOW().

    Hard delete (not soft): expired tokens have no audit value.
    Keeps the refresh_tokens table small.

    Typical result: a few tokens per professional per month.
    """
    async with async_session_maker() as session:
        repo = RefreshTokenRepository(session)
        count = await repo.delete_expired()
        await session.commit()
        logger.info("cleanup_expired_refresh_tokens: deleted %d tokens", count)
