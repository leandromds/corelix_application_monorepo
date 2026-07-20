"""
Auth service — business logic for authentication.

Responsibilities:
- Validate credentials (email + password)
- Issue JWT access tokens + refresh tokens
- Validate and rotate refresh tokens
- Revoke tokens on logout

Token lifecycle:
  login()              → creates access_token (JWT) + refresh_token (UUID raw, hash stored)
  refresh_access_token() → validates hash in DB, issues new access_token
  logout()             → revokes single token
  logout_all()         → revokes all tokens for professional
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from auth.repository import RefreshTokenRepository
from core.config import settings
from core.exceptions import AuthenticationError
from core.security import (
    create_access_token,
    generate_refresh_token,
    hash_refresh_token,
    verify_password,
)
from professionals.repository import ProfessionalsRepository


class AuthService:
    """Handles authentication business logic."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.token_repository = RefreshTokenRepository(session)
        self.professionals_repository = ProfessionalsRepository(session)

    async def login(
        self,
        email: str,
        password: str,
        device_info: str | None = None,
    ) -> dict[str, str]:
        """
        Authenticate a professional with email + password.

        Steps:
        1. Look up professional by email
        2. Verify password against stored bcrypt hash
        3. Generate JWT access token (15 min)
        4. Generate refresh token (UUID), store SHA-256 hash in DB
        5. Return both tokens

        Security note: we return the same generic error whether the email
        doesn't exist OR the password is wrong — prevents user enumeration.

        Args:
            email: Professional email
            password: Plain-text password
            device_info: Optional User-Agent string for token tracking

        Returns:
            dict with "access_token" (JWT string) and "refresh_token" (raw UUID string)

        Raises:
            AuthenticationError: if email not found or password doesn't match
        """
        professional = await self.professionals_repository.find_by_email(email)

        if professional is None or not verify_password(password, professional.password_hash):
            # Generic message — prevents user enumeration
            raise AuthenticationError("Invalid credentials")

        access_token = create_access_token(str(professional.id))
        raw_refresh, hashed_refresh = generate_refresh_token()

        expires_at = datetime.now(tz=UTC) + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )

        await self.token_repository.create(
            professional_id=professional.id,
            token_hash=hashed_refresh,
            expires_at=expires_at,
            device_info=device_info,
        )

        return {"access_token": access_token, "refresh_token": raw_refresh}

    async def refresh_access_token(self, raw_token: str) -> dict[str, str]:
        """
        Issue a new access token given a valid refresh token.

        Validates:
        - Token exists in the database
        - Token has not been revoked
        - Token has not expired

        Args:
            raw_token: The raw refresh token from the client cookie

        Returns:
            dict with "access_token" (new JWT string)

        Raises:
            AuthenticationError: if token is invalid, revoked, or expired
        """
        token_hash = hash_refresh_token(raw_token)
        token = await self.token_repository.find_by_hash(token_hash)

        if (
            token is None
            or token.revoked
            or token.expires_at < datetime.now(tz=UTC)
        ):
            raise AuthenticationError("Invalid or expired refresh token")

        access_token = create_access_token(str(token.professional_id))
        return {"access_token": access_token}

    async def logout(self, raw_token: str) -> None:
        """
        Revoke a single refresh token (logout from current device).

        Args:
            raw_token: The raw refresh token from the client cookie
        """
        token_hash = hash_refresh_token(raw_token)
        await self.token_repository.revoke(token_hash)

    async def logout_all(self, professional_id: UUID) -> None:
        """
        Revoke all refresh tokens for a professional (logout from all devices).

        Args:
            professional_id: UUID of the professional
        """
        await self.token_repository.revoke_all(professional_id)
