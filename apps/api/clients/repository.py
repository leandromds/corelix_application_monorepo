"""
Clients repository — database layer for the clients table.

Design:
- RLS is already active on the clients table via TenantSession (SET LOCAL).
  Queries do NOT filter by professional_id — PostgreSQL handles that automatically.
  This keeps the repository simple and makes the security boundary explicit:
  isolation is the database's responsibility, not the application's.

- soft_delete() sets is_active=False instead of DELETE. Clients have historical
  value (linked to sessions, billing, reports) — hard deletes would break FKs.

- find_by_phone() only searches active clients. A soft-deleted client's phone
  number should be "available" again for a new registration.

- update() receives the already-fetched Client object (not just an ID). The
  service layer is responsible for finding the client first (raising NotFoundError
  if needed), then passing the object here. This avoids a redundant SELECT inside
  the repository and keeps transaction boundaries clear.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from clients.models import Client
from clients.schemas import ClientCreate


class ClientsRepository:
    """Data access layer for the clients table (RLS-protected)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, professional_id: UUID, data: ClientCreate) -> Client:
        """
        Persist a new Client record linked to professional_id.

        Args:
            professional_id: UUID of the owning professional (tenant).
            data: Validated ClientCreate schema.

        Returns:
            Client instance with server-generated id, timestamps, and defaults.

        Note:
            professional_id is passed explicitly (not derived from RLS context)
            because CREATE requires knowing who owns the row before the row exists.
            After creation, all subsequent reads are filtered by RLS automatically.
        """
        client = Client(
            professional_id=professional_id,
            full_name=data.full_name,
            phone=data.phone,
            email=str(data.email) if data.email else None,
            notes=data.notes,
            whatsapp_opt_in=data.whatsapp_opt_in,
            email_opt_in=data.email_opt_in,
        )
        self.session.add(client)
        await self.session.flush()
        await self.session.refresh(client)
        return client

    async def find_by_id(self, client_id: UUID) -> Client | None:
        """
        Lookup a client by UUID primary key.

        RLS ensures only the current tenant's clients are visible — a valid
        client_id from another tenant returns None, not a 403.

        Args:
            client_id: Client UUID.

        Returns:
            Client if found within the current tenant, None otherwise.
        """
        result = await self.session.execute(select(Client).where(Client.id == client_id))
        return result.scalar_one_or_none()

    async def find_all(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        active_only: bool = True,
    ) -> list[Client]:
        """
        List clients for the current tenant (RLS-filtered).

        Args:
            skip: Number of records to skip (for pagination).
            limit: Maximum number of records to return.
            active_only: If True, excludes soft-deleted clients.

        Returns:
            List of Client instances, ordered by created_at ascending.
        """
        query = select(Client)

        if active_only:
            query = query.where(Client.is_active.is_(True))

        query = query.order_by(Client.created_at.asc()).offset(skip).limit(limit)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def find_by_phone(self, phone: str) -> Client | None:
        """
        Lookup an active client by phone number within the current tenant.

        Used by the service layer to check for duplicate phone registrations
        before creating a new client. Only active clients are considered —
        a soft-deleted client's phone number is treated as available.

        RLS ensures the lookup is scoped to the current tenant automatically,
        so the same phone number can exist in different tenants without conflict.

        Args:
            phone: Phone number string (exact match).

        Returns:
            Active Client with this phone, or None.
        """
        result = await self.session.execute(
            select(Client).where(
                Client.phone == phone,
                Client.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def update(self, client: Client, data: dict) -> Client:
        """
        Apply partial updates to an existing Client.

        The caller (service layer) is responsible for fetching the client
        and handling NotFoundError before calling this method. Receiving
        the object avoids an extra SELECT inside the repository.

        Args:
            client: The Client instance to update (already fetched).
            data: Dict of fields to update. Only keys present in the dict
                  are modified — keys absent are left untouched.

        Returns:
            Updated Client instance with refreshed server values.
        """
        for field, value in data.items():
            setattr(client, field, value)

        await self.session.flush()
        await self.session.refresh(client)
        return client

    async def soft_delete(self, client: Client) -> Client:
        """
        Mark a client as inactive (soft delete).

        Does NOT remove the record from the database. The client's historical
        data (sessions, payments) must remain intact for reports and auditing.
        is_active=False hides the client from the active list in the UI.

        Args:
            client: The Client instance to deactivate (already fetched).

        Returns:
            Updated Client instance with is_active=False.
        """
        client.is_active = False
        await self.session.flush()
        return client
