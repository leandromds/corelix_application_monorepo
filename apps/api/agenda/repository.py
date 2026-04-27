"""
Agenda repository — database layer for scheduling tables.

Four repository classes, one per domain entity:
  - AvailabilitySlotsRepository  (weekly availability windows)
  - BlockedPeriodsRepository     (explicit unavailability periods)
  - RecurrencesRepository        (recurring session rules)
  - SessionsRepository           (individual appointments)

All tables are RLS-protected. Queries do NOT filter by professional_id —
PostgreSQL handles tenant isolation automatically via SET LOCAL app.current_tenant.
professional_id IS passed to create() methods because the new row needs the FK
value written before RLS can enforce isolation on it.

Design mirrors clients/repository.py — see that module for extended commentary
on the RLS pattern and the "service fetches, repository acts" convention.
"""

from datetime import datetime, time, timedelta
from uuid import UUID

from sqlalchemy import cast, func, literal, select, update
from sqlalchemy.dialects.postgresql import INTERVAL
from sqlalchemy.ext.asyncio import AsyncSession

from agenda.models import AvailabilitySlot, BlockedPeriod, Recurrence, Session
from agenda.schemas import (
    AvailabilitySlotCreate,
    BlockedPeriodCreate,
    RecurrenceCreate,
    SessionCreate,
)

# ---------------------------------------------------------------------------
# AvailabilitySlotsRepository
# ---------------------------------------------------------------------------


class AvailabilitySlotsRepository:
    """Data access layer for the availability_slots table (RLS-protected)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, professional_id: UUID, data: AvailabilitySlotCreate) -> AvailabilitySlot:
        """
        Persist a new weekly availability window.

        professional_id is written explicitly into the new row so that RLS
        can enforce tenant isolation on subsequent reads.
        """
        slot = AvailabilitySlot(
            professional_id=professional_id,
            day_of_week=data.day_of_week,
            start_time=data.start_time,
            end_time=data.end_time,
        )
        self.session.add(slot)
        await self.session.flush()
        await self.session.refresh(slot)
        return slot

    async def find_by_id(self, slot_id: UUID) -> AvailabilitySlot | None:
        """Return a slot by primary key, or None if not visible to the current tenant."""
        result = await self.session.execute(
            select(AvailabilitySlot).where(AvailabilitySlot.id == slot_id)
        )
        return result.scalar_one_or_none()

    async def find_all(self, *, active_only: bool = True) -> list[AvailabilitySlot]:
        """
        List availability slots for the current tenant (RLS-filtered).

        Ordered by day_of_week then start_time to present a predictable
        weekly schedule view.
        """
        query = select(AvailabilitySlot)
        if active_only:
            query = query.where(AvailabilitySlot.is_active.is_(True))
        query = query.order_by(
            AvailabilitySlot.day_of_week.asc(),
            AvailabilitySlot.start_time.asc(),
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def find_by_day(self, day_of_week: int) -> list[AvailabilitySlot]:
        """Return active slots for a specific day of the week."""
        result = await self.session.execute(
            select(AvailabilitySlot)
            .where(
                AvailabilitySlot.day_of_week == day_of_week,
                AvailabilitySlot.is_active.is_(True),
            )
            .order_by(AvailabilitySlot.start_time.asc())
        )
        return list(result.scalars().all())

    async def find_by_day_and_time(
        self, day_of_week: int, start_time: time
    ) -> AvailabilitySlot | None:
        """
        Check whether an active slot already exists for (day_of_week, start_time).

        Used by the service layer to detect UNIQUE-equivalent violations before
        INSERT. Checking here (rather than relying on a DB UNIQUE constraint)
        lets us raise a descriptive ConflictError instead of catching IntegrityError.

        Only active slots are considered — a soft-deleted slot's time window
        is available for a new registration.
        """
        result = await self.session.execute(
            select(AvailabilitySlot).where(
                AvailabilitySlot.day_of_week == day_of_week,
                AvailabilitySlot.start_time == start_time,
                AvailabilitySlot.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def update(self, slot: AvailabilitySlot, data: dict) -> AvailabilitySlot:
        """
        Apply partial updates to an existing slot.

        The caller (service layer) is responsible for fetching the slot first.
        Only keys present in `data` are modified.
        """
        for field, value in data.items():
            setattr(slot, field, value)
        await self.session.flush()
        await self.session.refresh(slot)
        return slot

    async def soft_delete(self, slot: AvailabilitySlot) -> None:
        """
        Mark a slot as inactive (soft delete).

        Preserves the historical record — the time window configuration has
        analytical value even after it's no longer in use.
        """
        slot.is_active = False
        await self.session.flush()


# ---------------------------------------------------------------------------
# BlockedPeriodsRepository
# ---------------------------------------------------------------------------


class BlockedPeriodsRepository:
    """Data access layer for the blocked_periods table (RLS-protected)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, professional_id: UUID, data: BlockedPeriodCreate) -> BlockedPeriod:
        """Persist a new blocked period for the given professional."""
        period = BlockedPeriod(
            professional_id=professional_id,
            start_datetime=data.start_datetime,
            end_datetime=data.end_datetime,
            reason=data.reason,
            notify_clients=data.notify_clients,
        )
        self.session.add(period)
        await self.session.flush()
        await self.session.refresh(period)
        return period

    async def find_by_id(self, period_id: UUID) -> BlockedPeriod | None:
        """Return a blocked period by primary key, or None."""
        result = await self.session.execute(
            select(BlockedPeriod).where(BlockedPeriod.id == period_id)
        )
        return result.scalar_one_or_none()

    async def find_all(self) -> list[BlockedPeriod]:
        """List all blocked periods for the current tenant, ordered by start_datetime."""
        result = await self.session.execute(
            select(BlockedPeriod).order_by(BlockedPeriod.start_datetime.asc())
        )
        return list(result.scalars().all())

    async def find_overlapping(self, start: datetime, end: datetime) -> list[BlockedPeriod]:
        """
        Return blocked periods that overlap with [start, end).

        Overlap condition (standard interval intersection):
            period.start < end  AND  period.end > start

        This is called by the service layer to check whether a proposed session
        falls within a blocked period before creating it.
        """
        result = await self.session.execute(
            select(BlockedPeriod).where(
                BlockedPeriod.start_datetime < end,
                BlockedPeriod.end_datetime > start,
            )
        )
        return list(result.scalars().all())

    async def delete(self, period: BlockedPeriod) -> None:
        """
        Hard delete a blocked period.

        Blocked periods have no historical value once they have passed —
        they are created and deleted, never edited (no updated_at on the model).
        """
        await self.session.delete(period)
        await self.session.flush()


# ---------------------------------------------------------------------------
# RecurrencesRepository
# ---------------------------------------------------------------------------


class RecurrencesRepository:
    """Data access layer for the recurrences table (RLS-protected)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, professional_id: UUID, data: RecurrenceCreate) -> Recurrence:
        """Persist a new recurrence rule."""
        recurrence = Recurrence(
            professional_id=professional_id,
            client_id=data.client_id,
            frequency=data.frequency,
            interval=data.interval,
            day_of_week=data.day_of_week,
            start_date=data.start_date,
            end_date=data.end_date,
            session_duration=data.session_duration,
            session_price=data.session_price,
        )
        self.session.add(recurrence)
        await self.session.flush()
        await self.session.refresh(recurrence)
        return recurrence

    async def find_by_id(self, recurrence_id: UUID) -> Recurrence | None:
        """Return a recurrence by primary key, or None."""
        result = await self.session.execute(
            select(Recurrence).where(Recurrence.id == recurrence_id)
        )
        return result.scalar_one_or_none()

    async def find_all(self, *, active_only: bool = True) -> list[Recurrence]:
        """List recurrences for the current tenant, ordered by created_at."""
        query = select(Recurrence)
        if active_only:
            query = query.where(Recurrence.is_active.is_(True))
        query = query.order_by(Recurrence.created_at.asc())
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def find_active_by_client(self, client_id: UUID) -> list[Recurrence]:
        """Return active recurrences for a specific client."""
        result = await self.session.execute(
            select(Recurrence).where(
                Recurrence.client_id == client_id,
                Recurrence.is_active.is_(True),
            )
        )
        return list(result.scalars().all())

    async def update(self, recurrence: Recurrence, data: dict) -> Recurrence:
        """Apply partial updates to an existing recurrence."""
        for field, value in data.items():
            setattr(recurrence, field, value)
        await self.session.flush()
        await self.session.refresh(recurrence)
        return recurrence

    async def deactivate(self, recurrence: Recurrence) -> None:
        """
        Mark a recurrence as inactive (soft delete).

        The series history has analytical value — keeping the record allows
        reports to show the full lifetime of a client's recurring appointments.
        """
        recurrence.is_active = False
        await self.session.flush()


# ---------------------------------------------------------------------------
# SessionsRepository
# ---------------------------------------------------------------------------


class SessionsRepository:
    """Data access layer for the sessions table (RLS-protected)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, professional_id: UUID, data: SessionCreate) -> Session:
        """
        Persist a new session.

        price is taken from the request payload (not from the professional's
        current rate) — it is frozen at booking time for financial integrity.
        """
        session_obj = Session(
            professional_id=professional_id,
            client_id=data.client_id,
            recurrence_id=data.recurrence_id,
            scheduled_at=data.scheduled_at,
            duration_minutes=data.duration_minutes,
            price=data.price,
            notes=data.notes,
        )
        self.session.add(session_obj)
        await self.session.flush()
        await self.session.refresh(session_obj)
        return session_obj

    async def find_by_id(self, session_id: UUID) -> Session | None:
        """Return a session by primary key, or None."""
        result = await self.session.execute(select(Session).where(Session.id == session_id))
        return result.scalar_one_or_none()

    async def find_all(self, *, skip: int = 0, limit: int = 50) -> list[Session]:
        """
        List sessions for the current tenant, ordered by scheduled_at ascending.

        Supports pagination via skip/limit.
        """
        result = await self.session.execute(
            select(Session).order_by(Session.scheduled_at.asc()).offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def find_by_client(self, client_id: UUID) -> list[Session]:
        """Return all sessions for a specific client, ordered by scheduled_at."""
        result = await self.session.execute(
            select(Session)
            .where(Session.client_id == client_id)
            .order_by(Session.scheduled_at.asc())
        )
        return list(result.scalars().all())

    async def find_scheduled_between(self, start: datetime, end: datetime) -> list[Session]:
        """
        Return sessions whose scheduled_at falls in [start, end).

        Used by list_today_sessions. Does not filter by status — returns
        sessions in any status within the window.
        """
        result = await self.session.execute(
            select(Session)
            .where(
                Session.scheduled_at >= start,
                Session.scheduled_at < end,
            )
            .order_by(Session.scheduled_at.asc())
        )
        return list(result.scalars().all())

    async def find_upcoming(self, *, limit: int = 10) -> list[Session]:
        """
        Return the next N upcoming scheduled sessions (status='scheduled').

        Uses func.now() so the cutoff is evaluated by the database, not
        the application server — avoids clock skew issues.
        """
        result = await self.session.execute(
            select(Session)
            .where(
                Session.status == "scheduled",
                Session.scheduled_at > func.now(),
            )
            .order_by(Session.scheduled_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def find_conflicting(
        self, scheduled_at: datetime, duration_minutes: int
    ) -> list[Session]:
        """
        Return sessions whose time window overlaps with [scheduled_at, scheduled_at + duration).

        Only considers sessions with status='scheduled' — this exploits the
        partial index idx_sessions_conflict_check (WHERE status = 'scheduled')
        defined on the model, keeping conflict checks fast even with large tables.

        Overlap condition — A conflicts with B when:
            A.start < B.end  AND  A.end > B.start

        Where:
            new.end      = scheduled_at + duration_minutes
            existing.end = existing.scheduled_at + existing.duration_minutes

        The existing session's end time is computed in SQL using PostgreSQL's
        make_interval(years, months, weeks, days, hours, mins) so the comparison
        is done entirely in the database with timezone-aware TIMESTAMPTZ arithmetic.
        """
        new_end = scheduled_at + timedelta(minutes=duration_minutes)

        # PostgreSQL: make_interval(0, 0, 0, 0, 0, duration_minutes)
        # → interval of `duration_minutes` minutes
        existing_end = Session.scheduled_at + func.make_interval(
            0, 0, 0, 0, 0, Session.duration_minutes
        )

        result = await self.session.execute(
            select(Session).where(
                Session.status == "scheduled",
                Session.scheduled_at < new_end,  # existing starts before new ends
                existing_end > scheduled_at,  # existing ends after new starts
            )
        )
        return list(result.scalars().all())

    async def update(self, session_obj: Session, data: dict) -> Session:
        """Apply partial updates to an existing session."""
        for field, value in data.items():
            setattr(session_obj, field, value)
        await self.session.flush()
        await self.session.refresh(session_obj)
        return session_obj

    async def cancel_future_by_recurrence(self, recurrence_id: UUID) -> int:
        """
        Bulk-cancel all future scheduled sessions for a recurrence.

        Conditions:
          - recurrence_id matches
          - scheduled_at > NOW() (future only — past sessions are not affected)
          - status = 'scheduled' (completed/cancelled/no_show sessions are left intact)

        Uses a bulk UPDATE (not ORM object iteration) for efficiency.
        synchronize_session=False because we're returning a count and not
        reading the affected objects back within the same transaction.

        Returns:
            Count of sessions that were cancelled.
        """
        stmt = (
            update(Session)
            .where(
                Session.recurrence_id == recurrence_id,
                Session.scheduled_at > func.now(),
                Session.status == "scheduled",
            )
            .values(status="cancelled")
            .execution_options(synchronize_session=False)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount
