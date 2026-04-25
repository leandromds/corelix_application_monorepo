"""
Clients router — HTTP layer for client management.

Endpoints:
- POST   /clients/          → create_client  (201, ClientResponse)
- GET    /clients/          → list_clients   (200, list[ClientResponse])
- GET    /clients/{id}      → get_client     (200, ClientResponse)
- PATCH  /clients/{id}      → update_client  (200, ClientResponse)
- DELETE /clients/{id}      → delete_client  (204, no body)

Design:
- All endpoints use TenantSession: JWT validated + SET LOCAL app.current_tenant
  active. The router never passes professional_id to read operations — RLS
  handles tenant isolation transparently at the database level.
- professional_id IS forwarded to create_client() because the new row needs
  the FK value written before RLS can enforce isolation on it.
- Query params for pagination (skip, limit) are declared directly in the
  function signature — FastAPI resolves them from the query string automatically.
- DELETE returns 204 No Content (no response_model needed).
"""

from uuid import UUID

from fastapi import APIRouter, Query, status

from clients.schemas import ClientCreate, ClientResponse, ClientUpdate
from clients.service import ClientsService
from core.deps import CurrentProfessionalId, TenantSession

router = APIRouter()


@router.post("/", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
async def create_client(
    data: ClientCreate,
    session: TenantSession,
    professional_id: CurrentProfessionalId,
) -> ClientResponse:
    """
    Create a new client for the authenticated professional.

    At least one contact method (phone or email) must be provided.
    Phone numbers are unique per tenant — duplicate phone returns 409.
    """
    service = ClientsService(session)
    client = await service.create_client(UUID(professional_id), data)
    return ClientResponse.model_validate(client)


@router.get("/", response_model=list[ClientResponse])
async def list_clients(
    session: TenantSession,
    skip: int = Query(default=0, ge=0, description="Number of records to skip"),
    limit: int = Query(default=100, ge=1, le=500, description="Maximum records to return"),
) -> list[ClientResponse]:
    """
    List active clients for the authenticated professional.

    Returns only is_active=True clients, ordered by created_at ascending.
    Supports pagination via skip/limit query parameters.
    """
    service = ClientsService(session)
    clients = await service.list_clients(skip=skip, limit=limit)
    return [ClientResponse.model_validate(c) for c in clients]


@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(
    client_id: UUID,
    session: TenantSession,
) -> ClientResponse:
    """
    Retrieve a single client by ID.

    RLS ensures clients from other tenants are invisible — a cross-tenant
    UUID returns 404, not 403 (no oracle attack surface).
    Returns both active and inactive (soft-deleted) clients — the caller
    can check is_active to determine the client's status.
    """
    service = ClientsService(session)
    client = await service.get_client(client_id)
    return ClientResponse.model_validate(client)


@router.patch("/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: UUID,
    data: ClientUpdate,
    session: TenantSession,
) -> ClientResponse:
    """
    Partially update a client's fields (PATCH semantics).

    Only fields included in the request body are updated.
    Fields absent from the body are left unchanged.
    """
    service = ClientsService(session)
    client = await service.update_client(client_id, data)
    return ClientResponse.model_validate(client)


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_client(
    client_id: UUID,
    session: TenantSession,
) -> None:
    """
    Soft delete a client (sets is_active=False).

    The client record is preserved for historical integrity (sessions,
    billing, reports). Returns 204 No Content on success.
    """
    service = ClientsService(session)
    await service.delete_client(client_id)
