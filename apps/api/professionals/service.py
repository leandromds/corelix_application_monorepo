"""
Professionals service — business logic for professional profile management.

Responsibilities:
- Register new professional (validate unique email, hash password)
- Retrieve and update profile
- Manage WhatsApp connection settings
"""

from sqlalchemy.ext.asyncio import AsyncSession


class ProfessionalsService:
    """Handles professional profile business logic."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # TODO: Implement after repository layer is ready
    # Methods to implement:
    # - register(data: RegisterRequest) -> Professional
    # - get_by_id(professional_id: UUID) -> Professional
    # - update(professional_id: UUID, data: UpdateProfileRequest) -> Professional
    # - deactivate(professional_id: UUID) -> None
