"""
Professionals repository — data access layer for the professionals table.

Responsibilities:
- Raw CRUD against the professionals table
- No business logic — that lives in the service layer
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import NotFoundError
from professionals.models import Professional


class ProfessionalsRepository:
    """Data access layer for professionals table."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, data: dict) -> Professional:
        """
        Persist a new Professional record.

        Args:
            data: dict of column values (must include email, password_hash, full_name)

        Returns:
            Professional instance with id and server defaults populated.
        """
        professional = Professional(**data)
        self.session.add(professional)
        await self.session.flush()
        await self.session.refresh(professional)
        return professional

    async def find_by_email(self, email: str) -> Professional | None:
        """
        Lookup a professional by email address.

        Used by auth service to validate login credentials.

        Args:
            email: exact email string (case-sensitive per DB collation)

        Returns:
            Professional if found, None otherwise.
        """
        result = await self.session.execute(
            select(Professional).where(Professional.email == email)
        )
        return result.scalar_one_or_none()

    async def find_by_id(self, id: UUID) -> Professional | None:
        """
        Lookup a professional by UUID primary key.

        Args:
            id: Professional UUID

        Returns:
            Professional if found, None otherwise.
        """
        result = await self.session.execute(
            select(Professional).where(Professional.id == id)
        )
        return result.scalar_one_or_none()

    async def update(self, id: UUID, data: dict) -> Professional:
        """
        Apply partial updates to an existing Professional.

        Args:
            id: Professional UUID
            data: dict of fields to update (only non-None values should be passed)

        Returns:
            Updated Professional instance.

        Raises:
            NotFoundError: if no Professional with the given id exists.
        """
        professional = await self.find_by_id(id)
        if professional is None:
            raise NotFoundError(f"Professional {id} not found")

        for field, value in data.items():
            setattr(professional, field, value)

        await self.session.flush()
        await self.session.refresh(professional)
        return professional
