"""
Agenda repository — database layer for scheduling tables.

Covers: availability_slots, blocked_periods, sessions, recurrences.
All tables are RLS-protected.
"""

from sqlalchemy.ext.asyncio import AsyncSession


class AgendaRepository:
    """Data access layer for scheduling tables (RLS-protected)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # TODO: Implement after models are created
