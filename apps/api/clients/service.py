"""
Clients service — business logic for client management.

Responsibilities:
- Validate unique phone per tenant before creating a client
- Delegate all persistence to ClientsRepository
- Map repository NotFoundError through get_client (single point of truth)
- Soft delete (is_active=False) instead of hard DELETE

Design notes:
- RLS is active at the session level (set by TenantSession in the router).
  The service never passes professional_id to read operations — the database
  handles tenant isolation transparently.
- professional_id IS passed to create() because we need to write the FK value
  into the new row before RLS can enforce isolation on it.
- PATCH semantics: update_client() uses model_dump(exclude_unset=True) so only
  fields explicitly included in the request body are updated. Fields omitted from
  the request body remain unchanged. This differs from exclude_none=True, which
  would also exclude fields that were explicitly set to null (clearing them).
- Never call session.commit() here — RLS uses SET LOCAL, valid only within the
  current transaction. The router's dependency lifecycle manages commit/rollback.
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from clients.models import Client
from clients.repository import ClientsRepository
from clients.schemas import ClientCreate, ClientUpdate
from core.exceptions import ConflictError, NotFoundError


class ClientsService:
    """Handles client management business logic."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = ClientsRepository(session)

    async def create_client(self, professional_id: UUID, data: ClientCreate) -> Client:
        """
        Register a new client for the given professional.

        Steps:
        1. If phone is provided, check for duplicates within the current tenant.
           RLS ensures find_by_phone() only searches the active tenant — the same
           phone number in a different tenant is invisible and not a conflict.
        2. Delegate creation to the repository.

        Note: The "at least one contact method" validation is enforced by the
        ClientCreate schema (model_validator). The service does not re-validate it —
        the Pydantic layer is the single source of truth for that rule.

        Args:
            professional_id: UUID of the owning professional.
            data: Validated ClientCreate schema.

        Returns:
            Newly created Client.

        Raises:
            ConflictError: if the phone number is already registered for an active
                           client in the current tenant.
        """
        if data.phone:
            existing = await self.repository.find_by_phone(data.phone)
            if existing is not None:
                raise ConflictError("Phone number already registered for this professional")

        return await self.repository.create(professional_id, data)

    async def get_client(self, client_id: UUID) -> Client:
        """
        Retrieve a client by ID within the current tenant.

        RLS makes clients from other tenants invisible — an unknown UUID and
        a cross-tenant UUID both return None from the repository, and both
        surface as NotFoundError here. This avoids leaking the existence of
        resources in other tenants (no oracle attack via 404 vs 403).

        Args:
            client_id: Client UUID.

        Returns:
            Client if found within the current tenant.

        Raises:
            NotFoundError: if no active or inactive client with this ID is visible.
        """
        client = await self.repository.find_by_id(client_id)
        if client is None:
            raise NotFoundError("Client not found")
        return client

    async def list_clients(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Client]:
        """
        List active clients for the current tenant (RLS-filtered).

        Args:
            skip: Number of records to skip (pagination offset).
            limit: Maximum number of records to return.

        Returns:
            List of active Client instances, ordered by created_at ascending.
        """
        return await self.repository.find_all(skip=skip, limit=limit, active_only=True)

    async def update_client(self, client_id: UUID, data: ClientUpdate) -> Client:
        """
        Partially update a client's fields (PATCH semantics).

        Only fields explicitly included in the request body are updated.
        Fields not present in the body (unset in Pydantic model) are excluded
        via model_dump(exclude_unset=True) and left unchanged in the database.

        Example:
            PATCH {"full_name": "New Name"}
            → full_name is updated, phone/email/notes remain unchanged.

        Args:
            client_id: Client UUID.
            data: ClientUpdate with fields to modify.

        Returns:
            Updated Client instance.

        Raises:
            NotFoundError: if the client doesn't exist or belongs to another tenant.
        """
        client = await self.get_client(client_id)
        # exclude_unset=True: only update fields the caller explicitly provided.
        # exclude_none=True would silently drop null values, preventing intentional clearing.
        update_data = data.model_dump(exclude_unset=True)
        return await self.repository.update(client, update_data)

    async def delete_client(self, client_id: UUID) -> None:
        """
        Soft delete a client (sets is_active=False).

        The client record is preserved for historical integrity — sessions,
        billing records, and audit logs reference the client by FK. Hard
        deleting would either cascade-destroy that history or violate RESTRICT
        constraints on the sessions table.

        After deletion, the client is excluded from list_clients() results
        and the phone number becomes available for re-registration.

        Args:
            client_id: Client UUID.

        Returns:
            None (maps to 204 No Content at the HTTP layer).

        Raises:
            NotFoundError: if the client doesn't exist or belongs to another tenant.
        """
        client = await self.get_client(client_id)
        await self.repository.soft_delete(client)
