"""
Auth router — HTTP layer for authentication endpoints.

Endpoints:
- POST /auth/register     → create account, return ProfessionalResponse (201)
- POST /auth/login        → authenticate, return access_token + set HttpOnly cookie
- POST /auth/refresh      → read cookie, return new access_token
- POST /auth/logout       → revoke cookie token, clear cookie
- POST /auth/logout-all   → revoke all tokens (protected), clear cookie

Cookie design:
- Name: "refresh_token"
- HttpOnly: True (not accessible by JavaScript)
- Secure: True em produção, False em desenvolvimento (controlado por settings.is_production)
- SameSite: "strict" (prevents CSRF)
- Max-Age: 30 days
- The raw token is NEVER returned in the response body
"""

from uuid import UUID

from fastapi import APIRouter, Cookie, Request, Response, status

from auth.schemas import AccessTokenResponse, LoginRequest, ProfessionalResponse, RegisterRequest
from auth.service import AuthService
from core.config import settings
from core.deps import CurrentProfessionalId, DbSession, TenantSession
from professionals.service import ProfessionalsService

router = APIRouter()

_COOKIE_NAME = "refresh_token"
_COOKIE_MAX_AGE = 30 * 24 * 60 * 60  # 30 days in seconds


@router.post(
    "/register",
    response_model=ProfessionalResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    data: RegisterRequest,
    session: DbSession,
) -> ProfessionalResponse:
    """
    Create a new professional account.

    Public endpoint — no authentication required.
    Returns ProfessionalResponse (never exposes password_hash).
    """
    service = ProfessionalsService(session)
    professional = await service.register(data)
    return ProfessionalResponse.model_validate(professional)


@router.post("/login", response_model=AccessTokenResponse)
async def login(
    data: LoginRequest,
    response: Response,
    request: Request,
    session: DbSession,
) -> AccessTokenResponse:
    """
    Authenticate with email + password.

    Response body: access_token (JWT, 15 min)
    Response cookie: refresh_token (HttpOnly, 30 days)

    The refresh token is intentionally NOT in the body — it must only
    travel via HttpOnly cookie to prevent XSS token theft.
    """
    device_info = request.headers.get("user-agent")
    service = AuthService(session)
    tokens = await service.login(data.email, data.password, device_info)

    response.set_cookie(
        key=_COOKIE_NAME,
        value=tokens["refresh_token"],
        httponly=True,
        secure=settings.is_production,  # False em dev (HTTP), True em produção (HTTPS)
        samesite="strict",
        max_age=_COOKIE_MAX_AGE,
    )

    return AccessTokenResponse(access_token=tokens["access_token"])


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(
    session: DbSession,
    raw_token: str | None = Cookie(default=None, alias=_COOKIE_NAME),
) -> AccessTokenResponse:
    """
    Exchange refresh token cookie for a new access token.

    Reads the HttpOnly cookie — no request body needed.
    Returns 401 if the cookie is missing or invalid.
    """
    if raw_token is None:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing",
        )

    service = AuthService(session)
    result = await service.refresh_access_token(raw_token)
    return AccessTokenResponse(access_token=result["access_token"])


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    session: DbSession,
    raw_token: str | None = Cookie(default=None, alias=_COOKIE_NAME),
) -> None:
    """
    Revoke the current refresh token and clear the cookie.

    Public endpoint (no JWT required) — the cookie itself is the credential.
    Safe to call even if the cookie is missing (idempotent).
    """
    if raw_token is not None:
        service = AuthService(session)
        await service.logout(raw_token)

    response.delete_cookie(_COOKIE_NAME)


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
async def logout_all(
    response: Response,
    session: TenantSession,
    professional_id: CurrentProfessionalId,
) -> None:
    """
    Revoke ALL refresh tokens for the authenticated professional.

    Protected endpoint — requires valid JWT.
    Logs the user out from every device simultaneously.
    """
    service = AuthService(session)
    await service.logout_all(UUID(professional_id))
    response.delete_cookie(_COOKIE_NAME)
