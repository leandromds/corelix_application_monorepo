"""
Auth schemas — Pydantic models for authentication request/response validation.

RegisterRequest and ProfessionalResponse are re-exported from professionals.schemas
to keep the source of truth in one place (professionals module owns the Professional entity).
"""

from pydantic import BaseModel, EmailStr

# Re-export from professionals so auth router can use a single import
from professionals.schemas import ProfessionalResponse, RegisterRequest

__all__ = [
    "LoginRequest",
    "AccessTokenResponse",
    "RegisterRequest",
    "ProfessionalResponse",
]


class LoginRequest(BaseModel):
    """Request body for POST /auth/login."""

    email: EmailStr
    password: str


class AccessTokenResponse(BaseModel):
    """
    Response body for successful authentication or token refresh.

    access_token: JWT (15 minutes)
    token_type: always "bearer"

    The refresh_token is NOT in the body — it travels only via HttpOnly cookie.
    """

    access_token: str
    token_type: str = "bearer"
