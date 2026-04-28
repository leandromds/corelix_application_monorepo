"""
Agenda service — business logic for scheduling.

Responsibilities:
- Validate unique (day_of_week, start_time) before creating availability slots
- Detect session time conflicts with other sessions AND blocked periods
- Soft delete slots and recurrences (preserve historical data)
- Hard delete blocked periods (no historical value)
- Cascade-cancel future sessions when a recurrence is deactivated

Design notes:
- RLS is active at the session level (set by TenantSession in the router).
  Read operations never pass professional_id — the database handles tenant
  isolation transparently via SET LOCAL app.current_tenant.
- professional_id IS forwarded to create() calls because new rows need the FK
  value written before RLS can enforce isolation on them.
- PATCH semantics: update methods use model_dump(exclude_unset=True) so only
  fields explicitly included in the request body are applied. Fields omitted
  from the body remain unchanged in the database.
- Never call session.commit() here — RLS uses SET LOCAL, which is valid only
  within the current transaction. The router's dependency lifecycle manages
  commit/rollback (ADR-007).
- _check_session_conflict checks two independent sources:
    1. Scheduled sessions (overlap with existing status='scheduled' sessions)
    2. Blocked periods (overlap with any active blocked period)
  A ConflictError is raised if either source returns results.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from agenda.models import AvailabilitySlot, BlockedPeriod, Recurrence, Session
from agenda.repository import (
    AvailabilitySlotsRepository,
    BlockedPeriodsRepository,
    RecurrencesRepository,
    SessionsRepository,
)
from agenda.schemas import (
    AvailabilitySlotCreate,
    AvailabilitySlotUpdate,
    BlockedPeriodCreate,
    RecurrenceCreate,
    SessionCreate,
    SessionUpdate,
)
from core.exceptions import ConflictError, NotFoundError


class AgendaService:
    """Handles scheduling business logic for a single authenticated professional."""

    def __init__(self, session: AsyncSession, professional_id: UUID) -> None:
        self.slots_repo = AvailabilitySlotsRepository(session)
        self.blocked_repo = BlockedPeriodsRepository(session)
        self.recurrences_repo = RecurrencesRepository(session)
        self.sessions_repo = SessionsRepository(session)
        self.professional_id = professional_id

    # ──────────────────────────────────────────────────────────────────────────
    # Availability Slots
    # ──────────────────────────────────────────────────────────────────────────

    async def create_availability_slot(self, data: AvailabilitySlotCreate) -> AvailabilitySlot:
        """
        Register a new weekly availability window.

        Checks for an existing active slot at the same (day_of_week, start_time)
        before inserting. This prevents logical duplicates without relying on a
        DB UNIQUE constraint (which would raise a cryptic IntegrityError).

        Args:
            data: Validated AvailabilitySlotCreate schema.

        Returns:
            Newly created AvailabilitySlot.

        Raises:
            ConflictError: if an active slot already exists for this
                           (day_of_week, start_time) pair in the current tenant.
        """
        existing = await self.slots_repo.find_by_day_and_time(data.day_of_week, data.start_time)
        if existing is not None:
            raise ConflictError(
                "An active availability slot already exists for this day and start time"
            )
        return await self.slots_repo.create(self.professional_id, data)

    async def list_slots(self, *, active_only: bool = True) -> list[AvailabilitySlot]:
        """
        List availability slots for the current tenant.

        Args:
            active_only: If True (default), excludes soft-deleted slots.

        Returns:
            List of AvailabilitySlot instances ordered by day_of_week, start_time.
        """
        return await self.slots_repo.find_all(active_only=active_only)

    async def get_slot(self, slot_id: UUID) -> AvailabilitySlot:
        """
        Retrieve a single availability slot by ID.

        RLS makes slots from other tenants invisible — a cross-tenant UUID
        returns None from the repository and surfaces as NotFoundError here.

        Args:
            slot_id: AvailabilitySlot UUID.

        Returns:
            AvailabilitySlot if found within the current tenant.

        Raises:
            NotFoundError: if the slot does not exist or belongs to another tenant.
        """
        slot = await self.slots_repo.find_by_id(slot_id)
        if slot is None:
            raise NotFoundError("Availability slot not found")
        return slot

    async def update_slot(self, slot_id: UUID, data: AvailabilitySlotUpdate) -> AvailabilitySlot:
        """
        Partially update an availability slot (PATCH semantics).

        Only fields explicitly included in the request body are updated.
        Fields absent from the body (unset in Pydantic model) are excluded
        via model_dump(exclude_unset=True) and left unchanged.

        Args:
            slot_id: AvailabilitySlot UUID.
            data: AvailabilitySlotUpdate with fields to modify.

        Returns:
            Updated AvailabilitySlot instance.

        Raises:
            NotFoundError: if the slot doesn't exist or belongs to another tenant.
        """
        slot = await self.get_slot(slot_id)
        update_data = data.model_dump(exclude_unset=True)
        return await self.slots_repo.update(slot, update_data)

    async def delete_slot(self, slot_id: UUID) -> None:
        """
        Soft delete an availability slot (sets is_active=False).

        The slot record is preserved for historical analysis (e.g. reports
        correlating schedule configuration changes with booking patterns).
        After soft deletion the slot is excluded from the active list and its
        (day_of_week, start_time) becomes available for a new registration.

        Args:
            slot_id: AvailabilitySlot UUID.

        Returns:
            None (maps to 204 No Content at the HTTP layer).

        Raises:
            NotFoundError: if the slot doesn't exist or belongs to another tenant.
        """
        slot = await self.get_slot(slot_id)
        await self.slots_repo.soft_delete(slot)

    # ──────────────────────────────────────────────────────────────────────────
    # Blocked Periods
    # ──────────────────────────────────────────────────────────────────────────

    async def create_blocked_period(self, data: BlockedPeriodCreate) -> BlockedPeriod:
        """
        Register an explicit unavailability period.

        No uniqueness check is performed — overlapping blocked periods are allowed
        (e.g. a weekly holiday and a sick day can both cover the same window).

        Args:
            data: Validated BlockedPeriodCreate schema.

        Returns:
            Newly created BlockedPeriod.
        """
        return await self.blocked_repo.create(self.professional_id, data)

    async def list_blocked_periods(self) -> list[BlockedPeriod]:
        """
        List all blocked periods for the current tenant.

        Returns:
            List of BlockedPeriod instances ordered by start_datetime.
        """
        return await self.blocked_repo.find_all()

    async def get_blocked_period(self, period_id: UUID) -> BlockedPeriod:
        """
        Retrieve a single blocked period by ID.

        Args:
            period_id: BlockedPeriod UUID.

        Returns:
            BlockedPeriod if found within the current tenant.

        Raises:
            NotFoundError: if the period doesn't exist or belongs to another tenant.
        """
        period = await self.blocked_repo.find_by_id(period_id)
        if period is None:
            raise NotFoundError("Blocked period not found")
        return period

    async def delete_blocked_period(self, period_id: UUID) -> None:
        """
        Hard delete a blocked period.

        Blocked periods have no historical value once elapsed — deleting them
        keeps the database clean and avoids stale conflict checks for future
        sessions. Hard delete is safe here because no other table references
        blocked_periods via FK.

        Args:
            period_id: BlockedPeriod UUID.

        Returns:
            None (maps to 204 No Content at the HTTP layer).

        Raises:
            NotFoundError: if the period doesn't exist or belongs to another tenant.
        """
        period = await self.get_blocked_period(period_id)
        await self.blocked_repo.delete(period)

    # ──────────────────────────────────────────────────────────────────────────
    # Sessions
    # ──────────────────────────────────────────────────────────────────────────

    async def create_session(self, data: SessionCreate) -> Session:
        """
        Schedule a new session, checking for time conflicts first.

        Conflict detection considers:
          1. Other scheduled sessions that overlap with the proposed window.
          2. Blocked periods that overlap with the proposed window.

        Decision: sessions are NOT required to fall within an availability_slot
        window. Professionals frequently make exceptions (emergency slots, etc.).
        The availability_slot data is used by the AI bot to suggest times, not
        as a hard gate.

        Decision: sessions in the past are permitted. Professionals need to
        retroactively register sessions when onboarding historical data.

        Args:
            data: Validated SessionCreate schema.

        Returns:
            Newly created Session with status='scheduled'.

        Raises:
            ConflictError: if the proposed time window overlaps with an existing
                           scheduled session or a blocked period.
        """
        await self._check_session_conflict(data.scheduled_at, data.duration_minutes)
        return await self.sessions_repo.create(self.professional_id, data)

    async def list_sessions(self, *, skip: int = 0, limit: int = 50) -> list[Session]:
        """
        List sessions for the current tenant with pagination.

        Args:
            skip: Number of records to skip.
            limit: Maximum number of records to return.

        Returns:
            List of Session instances ordered by scheduled_at ascending.
        """
        return await self.sessions_repo.find_all(skip=skip, limit=limit)

    async def get_session(self, session_id: UUID) -> Session:
        """
        Retrieve a single session by ID.

        Args:
            session_id: Session UUID.

        Returns:
            Session if found within the current tenant.

        Raises:
            NotFoundError: if the session doesn't exist or belongs to another tenant.
        """
        session_obj = await self.sessions_repo.find_by_id(session_id)
        if session_obj is None:
            raise NotFoundError("Session not found")
        return session_obj

    async def update_session(self, session_id: UUID, data: SessionUpdate) -> Session:
        """
        Partially update a session (PATCH semantics).

        If scheduled_at or duration_minutes are being changed, conflict detection
        is re-run for the new time window — excluding the session being updated
        (a session cannot conflict with itself).

        Args:
            session_id: Session UUID.
            data: SessionUpdate with fields to modify.

        Returns:
            Updated Session instance.

        Raises:
            NotFoundError: if the session doesn't exist or belongs to another tenant.
            ConflictError: if the new time window overlaps with another session
                           or a blocked period.
        """
        session_obj = await self.get_session(session_id)
        update_data = data.model_dump(exclude_unset=True)

        # Re-check conflict only when the time window is changing.
        # Use the updated value if provided; fall back to the current value.
        if "scheduled_at" in update_data or "duration_minutes" in update_data:
            new_scheduled_at = update_data.get("scheduled_at", session_obj.scheduled_at)
            new_duration = update_data.get("duration_minutes", session_obj.duration_minutes)
            await self._check_session_conflict(
                new_scheduled_at,
                new_duration,
                exclude_session_id=session_obj.id,
            )

        return await self.sessions_repo.update(session_obj, update_data)

    async def list_today_sessions(self) -> list[Session]:
        """
        Return all sessions scheduled for today (UTC).

        Does not filter by status — returns sessions in any status for today,
        giving the professional a complete picture of the day.

        Returns:
            List of Session instances for the current UTC day, ordered by
            scheduled_at ascending.
        """

        today = datetime.now(UTC).date()
        start = datetime(today.year, today.month, today.day, tzinfo=UTC)
        end = start + timedelta(days=1)
        return await self.sessions_repo.find_scheduled_between(start, end)

    async def list_upcoming_sessions(self, *, limit: int = 10) -> list[Session]:
        """
        Return the next N upcoming scheduled sessions.

        Only returns sessions with status='scheduled' and scheduled_at in the
        future. Used by the dashboard "next appointments" widget.

        Args:
            limit: Maximum number of sessions to return (default 10).

        Returns:
            List of upcoming Session instances ordered by scheduled_at ascending.
        """
        return await self.sessions_repo.find_upcoming(limit=limit)

    # ──────────────────────────────────────────────────────────────────────────
    # Recurrences
    # ──────────────────────────────────────────────────────────────────────────

    async def create_recurrence(self, data: RecurrenceCreate) -> Recurrence:
        """
        Create a new recurring session rule.

        Does not generate individual sessions — that responsibility belongs to a
        background job (pgqueuer). The recurrence record describes the rule; the
        job materialises the sessions within the active window.

        Args:
            data: Validated RecurrenceCreate schema.

        Returns:
            Newly created Recurrence with is_active=True.
        """
        return await self.recurrences_repo.create(self.professional_id, data)

    async def list_recurrences(self, *, active_only: bool = True) -> list[Recurrence]:
        """
        List recurrence rules for the current tenant.

        Args:
            active_only: If True (default), excludes deactivated recurrences.

        Returns:
            List of Recurrence instances ordered by created_at ascending.
        """
        return await self.recurrences_repo.find_all(active_only=active_only)

    async def get_recurrence(self, recurrence_id: UUID) -> Recurrence:
        """
        Retrieve a single recurrence by ID.

        Args:
            recurrence_id: Recurrence UUID.

        Returns:
            Recurrence if found within the current tenant.

        Raises:
            NotFoundError: if the recurrence doesn't exist or belongs to another tenant.
        """
        recurrence = await self.recurrences_repo.find_by_id(recurrence_id)
        if recurrence is None:
            raise NotFoundError("Recurrence not found")
        return recurrence

    async def deactivate_recurrence(self, recurrence_id: UUID) -> int:
        """
        Deactivate a recurrence rule and cancel all its future scheduled sessions.

        Steps:
          1. Set recurrence.is_active = False.
          2. Bulk-UPDATE sessions: status='scheduled' → 'cancelled' WHERE
             recurrence_id = ? AND scheduled_at > NOW().
          3. Return the count of cancelled sessions.

        Design:
          - Past sessions (scheduled_at <= NOW()) are NOT affected — they
            represent historical events or sessions already in progress.
          - Sessions with status != 'scheduled' (completed, cancelled, no_show)
            are NOT touched — cancelling a completed session makes no sense.
          - The count is returned so the HTTP layer can include it in the
            response body ({"cancelled_sessions": N}).

        Args:
            recurrence_id: Recurrence UUID.

        Returns:
            Count of sessions that were cancelled as a result of this operation.

        Raises:
            NotFoundError: if the recurrence doesn't exist or belongs to another tenant.
        """
        recurrence = await self.get_recurrence(recurrence_id)
        await self.recurrences_repo.deactivate(recurrence)
        cancelled_count = await self.sessions_repo.cancel_future_by_recurrence(recurrence_id)
        return cancelled_count

    # ──────────────────────────────────────────────────────────────────────────
    # Private helpers
    # ──────────────────────────────────────────────────────────────────────────

    async def _check_session_conflict(
        self,
        scheduled_at: datetime,
        duration_minutes: int,
        exclude_session_id: UUID | None = None,
    ) -> None:
        """
        Verify that the proposed time window does not overlap with existing data.

        Two independent checks are performed:

        1. Session conflicts:
           Any status='scheduled' session whose time window intersects with
           [scheduled_at, scheduled_at + duration_minutes). The partial index
           idx_sessions_conflict_check makes this query fast even on large tables.
           When rescheduling, pass exclude_session_id to prevent the session from
           conflicting with its own current slot.

        2. Blocked period conflicts:
           Any blocked period whose [start_datetime, end_datetime) range intersects
           with the proposed session window. A session cannot be created or moved
           to a time the professional has explicitly blocked.

        Args:
            scheduled_at: Proposed start time of the session.
            duration_minutes: Duration of the proposed session in minutes.
            exclude_session_id: When rescheduling, the ID of the session being
                                updated — excluded from conflict detection so it
                                cannot conflict with its own current time slot.

        Raises:
            ConflictError: if any conflict is detected (either sessions or
                           blocked periods).
        """
        # ── Check 1: existing scheduled sessions ──────────────────────────
        conflicting = await self.sessions_repo.find_conflicting(scheduled_at, duration_minutes)

        if exclude_session_id is not None:
            # Filter out the session being updated — it cannot conflict with itself.
            conflicting = [s for s in conflicting if s.id != exclude_session_id]

        if conflicting:
            raise ConflictError("Session overlaps with an existing scheduled session")

        # ── Check 2: blocked periods ───────────────────────────────────────
        session_end = scheduled_at + timedelta(minutes=duration_minutes)
        overlapping = await self.blocked_repo.find_overlapping(scheduled_at, session_end)

        if overlapping:
            raise ConflictError("Session falls within a blocked period")
