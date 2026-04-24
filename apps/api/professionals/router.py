"""
Professionals router — HTTP layer for professional profile management.

Endpoints:
- GET  /professionals/me   → get own profile (protected)
- PATCH /professionals/me  → partial profile update (protected)

Design:
- Both endpoints use TenantSession (JWT validated + RLS active)
- Service layer does the business logic, router only handles HTTP concerns
- ProfessionalResponse is the public shape — never exposes password_hash
"""

from uuid import UUID

from fastapi import APIRouter

from core.deps import CurrentProfessionalId, TenantSession
from professionals.schemas import ProfessionalResponse, UpdateProfileRequest
from professionals.service import ProfessionalsService

router = APIRouter()


@router.get("/me", response_model=ProfessionalResponse)
async def get_me(
    session: TenantSession,
    professional_id: CurrentProfessionalId,
) -> ProfessionalResponse:
    """
    Return the authenticated professional's own profile.

    Uses TenantSession so RLS is active — the professional can only
    access their own row (belt-and-suspenders with the JWT check).
    """
    service = ProfessionalsService(session)
    professional = await service.get_by_id(UUID(professional_id))
    return ProfessionalResponse.model_validate(professional)


@router.patch("/me", response_model=ProfessionalResponse)
async def update_me(
    data: UpdateProfileRequest,
    session: TenantSession,
    professional_id: CurrentProfessionalId,
) -> ProfessionalResponse:
    """
    Partially update the authenticated professional's profile.

    Only fields included in the request body are updated (PATCH semantics).
    Email and password are NOT updatable through this endpoint.
    """
    service = ProfessionalsService(session)
    professional = await service.update_profile(UUID(professional_id), data)
    return ProfessionalResponse.model_validate(professional)
