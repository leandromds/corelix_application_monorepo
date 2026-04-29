"""
Reports repository — aggregate queries for billing reports.

Queries sessions joined with clients (explicit join — ADR-006, no relationship()).
RLS on the sessions table guarantees tenant isolation automatically.

Design notes:
  - datetime.combine(..., tzinfo=UTC) produces timezone-aware bounds required by
    asyncpg when comparing against TIMESTAMPTZ columns. Passing a naive datetime
    raises ValueError at the driver level.
  - coalesce(sum(price), 0) ensures total_amount is always Decimal, never None,
    so callers don't need null-checks.
  - Results are ordered by (client_id, scheduled_at) so the service layer can
    aggregate per-client in a single O(n) pass without re-sorting.
"""

from datetime import UTC, date, datetime, time
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Row, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from agenda.models import Session
from clients.models import Client


class ReportsRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def find_sessions_in_period(
        self,
        start_date: date,
        end_date: date,
        client_id: UUID | None = None,
        status_filter: list[str] | None = None,
    ) -> list[Row]:
        """
        Return sessions in [start_date, end_date] joined with client name.

        Bounds are inclusive on both ends:
          - start  = start_date at 00:00:00.000000 UTC
          - end    = end_date   at 23:59:59.999999 UTC

        Ordered by (client_id, scheduled_at) so the service can aggregate
        by client in a single pass without re-sorting.
        RLS on sessions guarantees only the current tenant's rows are returned.
        """
        start_bound = datetime.combine(start_date, time.min, tzinfo=UTC)
        end_bound = datetime.combine(end_date, time.max, tzinfo=UTC)

        query = (
            select(
                Session.id,
                Session.client_id,
                Client.full_name.label("client_name"),
                Session.scheduled_at,
                Session.duration_minutes,
                Session.price,
                Session.status,
                Session.notes,
            )
            .join(Client, Session.client_id == Client.id)
            .where(
                Session.scheduled_at >= start_bound,
                Session.scheduled_at <= end_bound,
            )
            .order_by(Session.client_id, Session.scheduled_at)
        )

        if client_id is not None:
            query = query.where(Session.client_id == client_id)

        if status_filter:
            query = query.where(Session.status.in_(status_filter))

        result = await self.db.execute(query)
        return list(result.all())

    async def get_period_summary(
        self,
        start_date: date,
        end_date: date,
        status_filter: list[str] | None = None,
    ) -> Row:
        """
        Return (total_sessions, total_amount) for the period.

        coalesce(sum(price), 0) ensures total_amount is Decimal('0') (not None)
        when no sessions exist in the period — callers can use the value directly
        without null-checks.
        """
        start_bound = datetime.combine(start_date, time.min, tzinfo=UTC)
        end_bound = datetime.combine(end_date, time.max, tzinfo=UTC)

        query = select(
            func.count(Session.id).label("total_sessions"),
            func.coalesce(func.sum(Session.price), Decimal("0")).label("total_amount"),
        ).where(
            Session.scheduled_at >= start_bound,
            Session.scheduled_at <= end_bound,
        )

        if status_filter:
            query = query.where(Session.status.in_(status_filter))

        result = await self.db.execute(query)
        return result.one()
