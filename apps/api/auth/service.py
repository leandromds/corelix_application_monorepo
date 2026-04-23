"""
Auth service — business logic for authentication.

Responsibilities:
- Validate credentials (email + password)
- Issue JWT access tokens and refresh tokens
- Revoke refresh tokens on logout
- Validate refresh tokens on token refresh
"""

from sqlalchemy.ext.asyncio import AsyncSession


class AuthService:
    """Handles authentication business logic."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # TODO: Implement after repository layer is ready
    # Methods to implement:
    # - authenticate(email, password) -> Professional
    # - create_tokens(professional_id) -> tuple[access_token, refresh_token]
    # - refresh_access_token(raw_refresh_token) -> str
    # - revoke_refresh_token(raw_refresh_token) -> None
    # - revoke_all_refresh_tokens(professional_id) -> None
