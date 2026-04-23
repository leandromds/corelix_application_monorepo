"""
Agenda service — business logic for scheduling.

Responsibilities:
- Validate session availability (no conflicts)
- Create and manage recurring sessions
- Block periods and validate against existing sessions
- Handle session status transitions
"""

from sqlalchemy.ext.asyncio import AsyncSession


class AgendaService:
    """Handles scheduling business logic."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # TODO: Implement after repository layer is ready
    # Methods to implement:
    # - get_availability(professional_id) -> list[AvailabilitySlot]
    # - create_availability_slot(professional_id, data) -> AvailabilitySlot
    # - create_session(professional_id, data) -> Session  (validates conflicts)
    # - update_session_status(professional_id, session_id, status) -> Session
    # - create_recurrence(professional_id, data) -> tuple[Recurrence, list[Session]]
    # - cancel_recurrence(professional_id, recurrence_id) -> None
