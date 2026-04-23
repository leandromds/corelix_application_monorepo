"""
Auth router — HTTP layer for authentication endpoints.

Endpoints to implement:
- POST /auth/login           -> authenticate and return tokens
- POST /auth/refresh         -> exchange refresh token for new access token
- POST /auth/logout          -> revoke refresh token
- POST /auth/logout-all      -> revoke all refresh tokens for the professional
"""

from fastapi import APIRouter

router = APIRouter()

# TODO: Implement endpoints after service layer is ready
# Follow TDD: write test_router.py first
