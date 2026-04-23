"""
Auth repository — database layer for token management.

Responsibilities:
- Store and retrieve refresh tokens (hashed)
- Revoke individual or all tokens for a professional
- Clean up expired tokens
"""

from sqlalchemy.ext.asyncio import AsyncSession


class RefreshTokenRepository:
    """Data access layer for refresh_tokens table."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # TODO: Implement after models are created
    # Methods to implement:
    # - create(professional_id, token_hash, device_info, expires_at) -> RefreshToken
    # - find_by_hash(token_hash) -> RefreshToken | None
    # - revoke(token_hash) -> None
    # - revoke_all(professional_id) -> None
    # - delete_expired() -> int  (returns count of deleted tokens)
