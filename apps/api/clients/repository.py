"""
Clients repository — database layer for clients table.

RLS is applied at the session level before any query.
The repository does NOT need to filter by professional_id manually —
PostgreSQL handles this automatically via RLS policies.
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession


class ClientsRepository:
    """Data access layer for clients table (RLS-protected)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # TODO: Implement after models are created
    # Methods to implement:
    # - find_all(skip: int, limit: int) -> list[Client]
    # - find_by_id(id: UUID) -> Client | None
    # - find_by_phone(phone: str) -> Client | None
    # - create(data: dict) -> Client
    # - update(id: UUID, data: dict) -> Client
    # - deactivate(id: UUID) -> None
