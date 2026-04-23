"""
Auth schemas — Pydantic models for request/response validation.
"""

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    """Request body for POST /auth/login."""

    email: EmailStr
    password: str = Field(min_length=8)


class TokenResponse(BaseModel):
    """Response body for successful authentication."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds until access token expires


class RefreshRequest(BaseModel):
    """Request body for POST /auth/refresh."""

    refresh_token: str


class LogoutRequest(BaseModel):
    """Request body for POST /auth/logout."""

    refresh_token: str
