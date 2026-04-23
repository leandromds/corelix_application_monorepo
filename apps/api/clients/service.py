"""
Clients service — business logic for client management.

Responsibilities:
- CRUD operations for clients (tenant-isolated)
- Validate unique phone per professional
- Soft delete (set is_active = False)
"""

from sqlalchemy.ext.asyncio import AsyncSession


class ClientsService:
    """Handles client management business logic."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # TODO: Implement after repository layer is ready
    # Methods to implement:
    # - list_all(professional_id: UUID, skip: int, limit: int) -> list[Client]
    # - get_by_id(professional_id: UUID, client_id: UUID) -> Client
    # - create(professional_id: UUID, data: CreateClientRequest) -> Client
    # - update(professional_id: UUID, client_id: UUID, data: UpdateClientRequest) -> Client
    # - deactivate(professional_id: UUID, client_id: UUID) -> None
