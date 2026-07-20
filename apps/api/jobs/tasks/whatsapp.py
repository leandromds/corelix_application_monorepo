"""Job 3: Renew WhatsApp access tokens approaching expiry."""

import logging
from datetime import UTC, datetime, timedelta

import httpx
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select

from core.config import settings
from core.database import async_session_maker
from professionals.models import Professional

logger = logging.getLogger(__name__)

RENEW_THRESHOLD_DAYS = 7


async def renew_whatsapp_tokens() -> None:
    """
    Refresh Meta access tokens that expire within RENEW_THRESHOLD_DAYS.

    Flow per professional:
    1. Decrypt current token with Fernet(ENCRYPTION_KEY)
    2. Exchange with Meta Graph API (fb_exchange_token grant)
    3. Encrypt new token and update DB fields

    Error isolation: failure for one professional is logged and skipped;
    others continue. This prevents a single bad token from blocking all renewals.
    """
    async with async_session_maker() as session:
        threshold = datetime.now(UTC) + timedelta(days=RENEW_THRESHOLD_DAYS)

        result = await session.execute(
            select(Professional).where(
                Professional.is_active.is_(True),
                Professional.whatsapp_access_token.is_not(None),
                Professional.whatsapp_token_expires_at < threshold,
            )
        )
        professionals = list(result.scalars().all())

        if not professionals:
            logger.info("renew_whatsapp_tokens: no tokens need renewal")
            return

        fernet = Fernet(settings.ENCRYPTION_KEY.encode())
        renewed = 0

        for prof in professionals:
            try:
                # Decrypt current token
                current_token = fernet.decrypt(prof.whatsapp_access_token.encode()).decode()  # type: ignore[union-attr]

                # Exchange with Meta
                new_token, expires_at = await _exchange_token(current_token)

                # Re-encrypt and save
                prof.whatsapp_access_token = fernet.encrypt(new_token.encode()).decode()
                prof.whatsapp_token_expires_at = expires_at
                await session.flush()
                renewed += 1

                logger.info("renew_whatsapp_tokens: renewed token for professional %s", prof.id)

            except InvalidToken:
                logger.warning(
                    "renew_whatsapp_tokens: could not decrypt token for professional %s — skipping",
                    prof.id,
                )
            except Exception:
                logger.exception("renew_whatsapp_tokens: failed for professional %s", prof.id)

        await session.commit()
        logger.info("renew_whatsapp_tokens: renewed %d / %d tokens", renewed, len(professionals))


async def _exchange_token(current_token: str) -> tuple[str, datetime]:
    """
    Call Meta Graph API to exchange a token for a long-lived one.

    Returns:
        (new_access_token, expires_at) — expires_at is UTC-aware.

    Raises:
        httpx.HTTPStatusError: on 4xx/5xx from Meta.
        httpx.HTTPError: on network/timeout errors.
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://graph.facebook.com/oauth/access_token",
            params={
                "grant_type": "fb_exchange_token",
                "client_id": settings.WHATSAPP_APP_ID,
                "client_secret": settings.WHATSAPP_APP_SECRET,
                "fb_exchange_token": current_token,
            },
            timeout=10.0,
        )
        response.raise_for_status()
        data = response.json()

        new_token: str = data["access_token"]
        expires_in: int = data.get("expires_in", 5184000)  # default: 60 days
        expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)

        return new_token, expires_at
