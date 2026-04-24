"""
Professionals service — business logic for professional profile management.

Responsibilities:
- Validate unique email on registration
- Hash password before persisting (NEVER store plain text)
- Retrieve and update profile

Design: service holds a repository instance. This makes it easy to mock
the repository in unit tests without touching the database.
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import ConflictError, NotFoundError
from core.security import hash_password
from professionals.models import Professional
from professionals.repository import ProfessionalsRepository
from professionals.schemas import RegisterRequest, UpdateProfileRequest


class ProfessionalsService:
    """Handles professional profile business logic."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = ProfessionalsRepository(session)

    async def register(self, data: RegisterRequest) -> Professional:
        """
        Register a new professional account.

        Steps:
        1. Check email uniqueness (ConflictError if taken)
        2. Hash the plain-text password
        3. Persist via repository

        The caller (router) is responsible for converting the returned
        Professional model to ProfessionalResponse (which excludes password_hash).

        Args:
            data: RegisterRequest with email, password, full_name, and optional fields

        Returns:
            Newly created Professional model.

        Raises:
            ConflictError: if email is already registered.
        """
        existing = await self.repository.find_by_email(data.email)
        if existing is not None:
            raise ConflictError("Email already registered")

        professional = await self.repository.create(
            {
                "email": data.email,
                "password_hash": hash_password(data.password),
                "full_name": data.full_name,
                "specialty": data.specialty,
                "bio": data.bio,
            }
        )
        return professional

    async def get_by_id(self, professional_id: UUID) -> Professional:
        """
        Retrieve a professional by ID.

        Args:
            professional_id: UUID of the professional

        Returns:
            Professional model.

        Raises:
            NotFoundError: if no professional with this ID exists.
        """
        professional = await self.repository.find_by_id(professional_id)
        if professional is None:
            raise NotFoundError("Professional not found")
        return professional

    async def update_profile(
        self, professional_id: UUID, data: UpdateProfileRequest
    ) -> Professional:
        """
        Apply a partial profile update (PATCH semantics).

        Only fields explicitly set in the request are updated.
        None values are excluded so existing data is not overwritten.

        Args:
            professional_id: UUID of the professional to update
            data: UpdateProfileRequest with optional fields

        Returns:
            Updated Professional model.

        Raises:
            NotFoundError: if professional does not exist.
        """
        # exclude_none=True ensures we only update fields explicitly provided
        update_data = data.model_dump(exclude_none=True)
        return await self.repository.update(professional_id, update_data)
