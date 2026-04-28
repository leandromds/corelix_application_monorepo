"""
Security utilities: password hashing, JWT tokens, and refresh token management.

Design decisions:
- bcrypt for password hashing (slow by design — prevents brute force)
- HS256 JWT for access tokens (stateless, 15-minute expiry)
- SHA-256 for refresh token hashing (fast, deterministic — stored in DB)
- secrets.token_urlsafe for raw refresh token generation (cryptographically secure)
"""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from jose import jwt
from passlib.context import CryptContext

from core.config import settings

# Password hashing context — bcrypt with automatic upgrade of deprecated schemes
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ============================================================================
# Password Utilities
# ============================================================================


def hash_password(password: str) -> str:
    """
    Hash a plain-text password using bcrypt.

    bcrypt automatically generates a unique salt for each hash,
    so the same password will produce different hashes every time.
    This is intentional and required for security.

    Args:
        password: Plain-text password to hash

    Returns:
        bcrypt hash string (includes salt, cost factor, and hash)
    """
    return cast(str, pwd_context.hash(password))


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain-text password against a bcrypt hash.

    This function is timing-safe — it always takes the same amount
    of time regardless of whether the password is correct or not.
    This prevents timing attacks.

    Args:
        plain_password: Password to verify
        hashed_password: Stored bcrypt hash

    Returns:
        True if password matches, False otherwise (never raises)
    """
    try:
        return cast(bool, pwd_context.verify(plain_password, hashed_password))
    except Exception:
        # Never raise — always return False for invalid hashes
        return False


# ============================================================================
# JWT Access Token
# ============================================================================


def create_access_token(
    subject: str,
    expires_delta: timedelta | None = None,
) -> str:
    """
    Create a signed JWT access token.

    The token contains:
    - sub: subject (professional_id as string)
    - type: "access" (to distinguish from refresh tokens)
    - exp: expiration timestamp

    Args:
        subject: The professional UUID as a string
        expires_delta: Custom expiry. Defaults to ACCESS_TOKEN_EXPIRE_MINUTES

    Returns:
        Signed JWT string
    """
    expire = datetime.now(tz=UTC) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    payload: dict[str, Any] = {
        "sub": subject,
        "type": "access",
        "exp": expire,
    }

    return cast(str, jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM))


def decode_access_token(token: str) -> dict[str, Any]:
    """
    Decode and validate a JWT access token.

    Validates:
    - Signature (using SECRET_KEY)
    - Expiration (raises if token is expired)
    - Algorithm (must match ALGORITHM setting)

    Args:
        token: JWT string to decode

    Returns:
        Decoded payload dictionary

    Raises:
        jose.JWTError: If token is invalid, expired, or tampered
    """
    return cast(
        dict[str, Any], jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    )


# ============================================================================
# Refresh Token
# ============================================================================


def generate_refresh_token() -> tuple[str, str]:
    """
    Generate a secure refresh token and its SHA-256 hash.

    We store the HASH in the database, not the raw token.
    This way, even if the database is compromised, the attacker
    cannot use the stolen hashes to authenticate.

    This is the same approach used for API keys by GitHub, etc.

    Returns:
        Tuple of (raw_token, hashed_token)
        - raw_token: sent to the client (in HttpOnly cookie)
        - hashed_token: stored in the database
    """
    raw_token = secrets.token_urlsafe(64)
    hashed_token = hash_refresh_token(raw_token)
    return raw_token, hashed_token


def hash_refresh_token(raw_token: str) -> str:
    """
    Hash a refresh token using SHA-256.

    Unlike bcrypt (used for passwords), SHA-256 is:
    - Fast (we need to look up tokens quickly on every refresh)
    - Deterministic (same input always produces same output — required for DB lookup)
    - Not suitable for passwords (too fast — brute-forceable)
      but fine for random tokens (128 bytes of entropy from secrets.token_urlsafe)

    Args:
        raw_token: Raw refresh token string

    Returns:
        SHA-256 hex digest string
    """
    return hashlib.sha256(raw_token.encode()).hexdigest()
