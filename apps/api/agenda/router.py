"""
Agenda router — HTTP layer for scheduling management.

Endpoints:
  Availability Slots:
    POST   /agenda/slots/         → 201 AvailabilitySlotResponse
    GET    /agenda/slots/         → list[AvailabilitySlotResponse]
    GET    /agenda/slots/{id}     → AvailabilitySlotResponse
    PATCH  /agenda/slots/{id}     → AvailabilitySlotResponse
    DELETE /agenda/slots/{id}     → 204

  Blocked Periods:
    POST   /agenda/blocked/       → 201 BlockedPeriodResponse
    GET    /agenda/blocked/       → list[BlockedPeriodResponse]
    DELETE /agenda/blocked/{id}   → 204

  Recurrences:
    POST   /agenda/recurrences/       → 201 RecurrenceResponse
    GET    /agenda/recurrences/       → list[RecurrenceResponse]
    GET    /agenda/recurrences/{id}   → RecurrenceResponse
    DELETE /agenda/recurrences/{id}   → 200 {"cancelled_sessions": N}

  Sessions:
    POST   /agenda/sessions/         → 201 SessionResponse
    GET    /agenda/sessions/today    → list[SessionResponse]   ← before {id}!
    GET    /agenda/sessions/upcoming → list[SessionResponse]   ← before {id}!
    GET    /agenda/sessions/         → list[SessionResponse] (skip/limit)
    GET    /agenda/sessions/{id}     → SessionResponse
    PATCH  /agenda/sessions/{id}     → SessionResponse

Design:
- All endpoints use TenantSession: JWT validated + SET LOCAL app.current_tenant.
  The router never passes professional_id to read operations — RLS handles
  tenant isolation transparently at the database level.
- professional_id IS forwarded to create operations (the new row needs the FK
  value written before RLS can enforce isolation on it).
- Static paths (/today, /upcoming) are registered BEFORE the parameterized
  path (/{session_id}) so FastAPI matches them first. Although session_id is
  typed as UUID (which would reject "today"), being explicit about order is
  cleaner and avoids surprises.
- Query params for pagination (skip, limit) are declared in the function
  signature — FastAPI resolves them from the query string automatically.
"""

from uuid import UUID

from fastapi import APIRouter, Query, status

from agenda.schemas import (
    AvailabilitySlotCreate,
    AvailabilitySlotResponse,
    AvailabilitySlotUpdate,
    BlockedPeriodCreate,
    BlockedPeriodResponse,
    RecurrenceCreate,
    RecurrenceResponse,
    SessionCreate,
    SessionResponse,
    SessionUpdate,
)
from agenda.service import AgendaService
from core.deps import CurrentProfessionalId, TenantSession

router = APIRouter()


# =============================================================================
# Availability Slots
# =============================================================================


@router.post(
    "/slots/",
    response_model=AvailabilitySlotResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_availability_slot(
    data: AvailabilitySlotCreate,
    session: TenantSession,
    professional_id: CurrentProfessionalId,
) -> AvailabilitySlotResponse:
    """
    Create a new weekly availability window.

    Returns 409 if an active slot already exists for the same
    (day_of_week, start_time) pair in the current tenant.
    """
    service = AgendaService(session, UUID(professional_id))
    slot = await service.create_availability_slot(data)
    return AvailabilitySlotResponse.model_validate(slot)


@router.get("/slots/", response_model=list[AvailabilitySlotResponse])
async def list_availability_slots(
    session: TenantSession,
    professional_id: CurrentProfessionalId,
    active_only: bool = Query(default=True, description="Filter by is_active"),
) -> list[AvailabilitySlotResponse]:
    """
    List availability slots for the authenticated professional.

    By default returns only active slots (is_active=True).
    Pass active_only=false to include soft-deleted slots.
    """
    service = AgendaService(session, UUID(professional_id))
    slots = await service.list_slots(active_only=active_only)
    return [AvailabilitySlotResponse.model_validate(s) for s in slots]


@router.get("/slots/{slot_id}", response_model=AvailabilitySlotResponse)
async def get_availability_slot(
    slot_id: UUID,
    session: TenantSession,
    professional_id: CurrentProfessionalId,
) -> AvailabilitySlotResponse:
    """
    Retrieve a single availability slot by ID.

    RLS ensures slots from other tenants are invisible — a cross-tenant
    UUID returns 404, not 403.
    """
    service = AgendaService(session, UUID(professional_id))
    slot = await service.get_slot(slot_id)
    return AvailabilitySlotResponse.model_validate(slot)


@router.patch("/slots/{slot_id}", response_model=AvailabilitySlotResponse)
async def update_availability_slot(
    slot_id: UUID,
    data: AvailabilitySlotUpdate,
    session: TenantSession,
    professional_id: CurrentProfessionalId,
) -> AvailabilitySlotResponse:
    """
    Partially update an availability slot (PATCH semantics).

    Only fields included in the request body are applied.
    Fields absent from the body remain unchanged.
    """
    service = AgendaService(session, UUID(professional_id))
    slot = await service.update_slot(slot_id, data)
    return AvailabilitySlotResponse.model_validate(slot)


@router.delete("/slots/{slot_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_availability_slot(
    slot_id: UUID,
    session: TenantSession,
    professional_id: CurrentProfessionalId,
) -> None:
    """
    Soft delete an availability slot (sets is_active=False).

    The record is preserved for historical analysis.
    Returns 204 No Content on success.
    """
    service = AgendaService(session, UUID(professional_id))
    await service.delete_slot(slot_id)


# =============================================================================
# Blocked Periods
# =============================================================================


@router.post(
    "/blocked/",
    response_model=BlockedPeriodResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_blocked_period(
    data: BlockedPeriodCreate,
    session: TenantSession,
    professional_id: CurrentProfessionalId,
) -> BlockedPeriodResponse:
    """
    Register an explicit unavailability window (holiday, sick day, etc.).

    Overlapping blocked periods are allowed — professionals can stack them.
    Sessions cannot be created during blocked periods (conflict detection
    is enforced in create_session).
    """
    service = AgendaService(session, UUID(professional_id))
    period = await service.create_blocked_period(data)
    return BlockedPeriodResponse.model_validate(period)


@router.get("/blocked/", response_model=list[BlockedPeriodResponse])
async def list_blocked_periods(
    session: TenantSession,
    professional_id: CurrentProfessionalId,
) -> list[BlockedPeriodResponse]:
    """
    List all blocked periods for the authenticated professional.

    Returns periods ordered by start_datetime ascending.
    """
    service = AgendaService(session, UUID(professional_id))
    periods = await service.list_blocked_periods()
    return [BlockedPeriodResponse.model_validate(p) for p in periods]


@router.delete("/blocked/{period_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_blocked_period(
    period_id: UUID,
    session: TenantSession,
    professional_id: CurrentProfessionalId,
) -> None:
    """
    Hard delete a blocked period.

    Blocked periods have no historical value once elapsed.
    Returns 204 No Content on success.
    """
    service = AgendaService(session, UUID(professional_id))
    await service.delete_blocked_period(period_id)


# =============================================================================
# Recurrences
# =============================================================================


@router.post(
    "/recurrences/",
    response_model=RecurrenceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_recurrence(
    data: RecurrenceCreate,
    session: TenantSession,
    professional_id: CurrentProfessionalId,
) -> RecurrenceResponse:
    """
    Create a recurring session rule.

    Note: this only persists the rule — individual sessions are generated
    by a background job (pgqueuer) within the active window.
    """
    service = AgendaService(session, UUID(professional_id))
    recurrence = await service.create_recurrence(data)
    return RecurrenceResponse.model_validate(recurrence)


@router.get("/recurrences/", response_model=list[RecurrenceResponse])
async def list_recurrences(
    session: TenantSession,
    professional_id: CurrentProfessionalId,
    active_only: bool = Query(default=True, description="Filter by is_active"),
) -> list[RecurrenceResponse]:
    """
    List recurrence rules for the authenticated professional.

    By default returns only active recurrences.
    """
    service = AgendaService(session, UUID(professional_id))
    recurrences = await service.list_recurrences(active_only=active_only)
    return [RecurrenceResponse.model_validate(r) for r in recurrences]


@router.get("/recurrences/{recurrence_id}", response_model=RecurrenceResponse)
async def get_recurrence(
    recurrence_id: UUID,
    session: TenantSession,
    professional_id: CurrentProfessionalId,
) -> RecurrenceResponse:
    """
    Retrieve a single recurrence rule by ID.
    """
    service = AgendaService(session, UUID(professional_id))
    recurrence = await service.get_recurrence(recurrence_id)
    return RecurrenceResponse.model_validate(recurrence)


@router.delete("/recurrences/{recurrence_id}")
async def deactivate_recurrence(
    recurrence_id: UUID,
    session: TenantSession,
    professional_id: CurrentProfessionalId,
) -> dict:
    """
    Deactivate a recurrence and cancel all its future scheduled sessions.

    Returns 200 with {"cancelled_sessions": N} where N is the number of
    sessions that were cancelled as a result of this operation.
    Sessions already completed, cancelled, or in the past are not affected.
    """
    service = AgendaService(session, UUID(professional_id))
    cancelled_count = await service.deactivate_recurrence(recurrence_id)
    return {"cancelled_sessions": cancelled_count}


# =============================================================================
# Sessions
# =============================================================================
#
# IMPORTANT: /sessions/today and /sessions/upcoming MUST be registered before
# /sessions/{session_id}. Even though {session_id} is typed as UUID (which
# would reject "today"), FastAPI evaluates routes in registration order.
# Registering static paths first is cleaner and avoids any edge-case surprises.


@router.post(
    "/sessions/",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_session(
    data: SessionCreate,
    session: TenantSession,
    professional_id: CurrentProfessionalId,
) -> SessionResponse:
    """
    Schedule a new session.

    Conflict detection runs before creation:
    - Returns 409 if the proposed time window overlaps with an existing
      status='scheduled' session.
    - Returns 409 if the proposed time window falls within a blocked period.

    Sessions outside of availability_slots are allowed — professionals
    frequently make exceptions (emergency slots, one-off bookings).
    Sessions in the past are allowed — useful for retroactive onboarding.
    """
    service = AgendaService(session, UUID(professional_id))
    session_obj = await service.create_session(data)
    return SessionResponse.model_validate(session_obj)


@router.get("/sessions/today", response_model=list[SessionResponse])
async def list_today_sessions(
    session: TenantSession,
    professional_id: CurrentProfessionalId,
) -> list[SessionResponse]:
    """
    List all sessions scheduled for today (UTC).

    Returns sessions in any status — gives the professional a complete
    picture of the day, including cancelled or completed sessions.
    Ordered by scheduled_at ascending.
    """
    service = AgendaService(session, UUID(professional_id))
    sessions = await service.list_today_sessions()
    return [SessionResponse.model_validate(s) for s in sessions]


@router.get("/sessions/upcoming", response_model=list[SessionResponse])
async def list_upcoming_sessions(
    session: TenantSession,
    professional_id: CurrentProfessionalId,
    limit: int = Query(default=10, ge=1, le=100, description="Max sessions to return"),
) -> list[SessionResponse]:
    """
    List the next N upcoming scheduled sessions (status='scheduled').

    Used by the dashboard "next appointments" widget.
    Ordered by scheduled_at ascending.
    """
    service = AgendaService(session, UUID(professional_id))
    sessions = await service.list_upcoming_sessions(limit=limit)
    return [SessionResponse.model_validate(s) for s in sessions]


@router.get("/sessions/", response_model=list[SessionResponse])
async def list_sessions(
    session: TenantSession,
    professional_id: CurrentProfessionalId,
    skip: int = Query(default=0, ge=0, description="Number of records to skip"),
    limit: int = Query(default=50, ge=1, le=200, description="Maximum records to return"),
) -> list[SessionResponse]:
    """
    List sessions for the authenticated professional with pagination.

    Returns sessions in any status, ordered by scheduled_at ascending.
    Supports pagination via skip/limit query parameters.
    """
    service = AgendaService(session, UUID(professional_id))
    sessions = await service.list_sessions(skip=skip, limit=limit)
    return [SessionResponse.model_validate(s) for s in sessions]


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: UUID,
    session: TenantSession,
    professional_id: CurrentProfessionalId,
) -> SessionResponse:
    """
    Retrieve a single session by ID.

    RLS ensures sessions from other tenants are invisible — a cross-tenant
    UUID returns 404, not 403.
    """
    service = AgendaService(session, UUID(professional_id))
    session_obj = await service.get_session(session_id)
    return SessionResponse.model_validate(session_obj)


@router.patch("/sessions/{session_id}", response_model=SessionResponse)
async def update_session(
    session_id: UUID,
    data: SessionUpdate,
    session: TenantSession,
    professional_id: CurrentProfessionalId,
) -> SessionResponse:
    """
    Partially update a session (PATCH semantics).

    Only fields included in the request body are applied.

    If scheduled_at or duration_minutes are changed, conflict detection
    runs against the new time window (excluding the session being updated).

    Returns 409 if the new time window conflicts with another session or
    a blocked period.
    """
    service = AgendaService(session, UUID(professional_id))
    session_obj = await service.update_session(session_id, data)
    return SessionResponse.model_validate(session_obj)
