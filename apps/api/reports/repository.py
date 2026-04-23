"""
Reports repository — database layer for report queries.

Complex aggregate queries live here.
"""

from sqlalchemy.ext.asyncio import AsyncSession


class ReportsRepository:
    """Data access layer for report aggregations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # TODO: Implement after models are created
