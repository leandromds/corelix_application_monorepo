"""
Professionals repository — database layer for professionals table.
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession


class ProfessionalsRepository:
    """Data access layer for professionals table."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # TODO: Implement after models are created
    # Methods to implement:
    # - create(data: dict) -> Professional
    # - find_by_id(id: UUID) -> Professional | None
    # - find_by_email(email: str) -> Professional | None
    # - update(id: UUID, data: dict) -> Professional
    # - deactivate(id: UUID) -> None
