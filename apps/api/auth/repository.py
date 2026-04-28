"""
Auth repository — data access layer for refresh_tokens table.

Responsibilities:
- Store hashed refresh tokens
- Look up, revoke, and clean up tokens
- Never handles raw tokens — only receives/returns hashes
"""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from auth.models import RefreshToken


class RefreshTokenRepository:
    """Data access layer for refresh_tokens table."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        professional_id: UUID,
        token_hash: str,
        expires_at: datetime,
        device_info: str | None = None,
    ) -> RefreshToken:
        """
        Persist a new refresh token (hashed).

        The raw token is never passed here — the service layer hashes it
        before calling this method.

        Args:
            professional_id: Owner of this token
            token_hash: SHA-256 hash of the raw token
            expires_at: Absolute expiry timestamp (UTC)
            device_info: Optional User-Agent or device identifier

        Returns:
            Persisted RefreshToken with id and created_at populated.
        """
        token = RefreshToken(
            professional_id=professional_id,
            token_hash=token_hash,
            device_info=device_info,
            expires_at=expires_at,
        )
        self.session.add(token)
        await self.session.flush()
        await self.session.refresh(token)
        return token

    async def find_by_hash(self, token_hash: str) -> RefreshToken | None:
        """
        Look up a refresh token by its SHA-256 hash.

        Called on every /auth/refresh request to validate the cookie.

        Args:
            token_hash: SHA-256 hex digest of the raw token

        Returns:
            RefreshToken if found, None otherwise.
        """
        result = await self.session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def revoke(self, token_hash: str) -> None:
        """
        Mark a single token as revoked (soft delete).

        We keep the record for audit purposes instead of deleting it.
        The token is immediately invalid after this call.

        Args:
            token_hash: SHA-256 hex digest of the token to revoke
        """
        await self.session.execute(
            update(RefreshToken).where(RefreshToken.token_hash == token_hash).values(revoked=True)
        )

    async def revoke_all(self, professional_id: UUID) -> None:
        """
        Revoke all active tokens for a professional (logout-all).

        Called when the professional logs out from all devices or when
        a security event requires invalidating all sessions.

        Args:
            professional_id: UUID of the professional whose tokens to revoke
        """
        await self.session.execute(
            update(RefreshToken)
            .where(
                RefreshToken.professional_id == professional_id,
                RefreshToken.revoked == False,  # noqa: E712
            )
            .values(revoked=True)
        )

    async def delete_expired(self) -> int:
        """
        Permanently delete expired tokens (nightly cleanup job).

        Unlike revocation (soft delete), expired tokens have no audit value
        and can be hard-deleted to keep the table small.

        Returns:
            Number of rows deleted.
        """
        now = datetime.now(tz=timezone.utc)
        result = await self.session.execute(
            delete(RefreshToken).where(RefreshToken.expires_at < now)
        )
        return int(result.rowcount)  # type: ignore[attr-defined]
