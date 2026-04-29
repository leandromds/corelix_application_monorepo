"""
Job 2: Generate sessions for active recurrences — nightly scheduling.

Design decisions:
- calculate_dates() is a pure synchronous function — no DB access, fully testable
  in isolation without any async machinery or fixtures.
- generate_recurring_sessions() does a cross-tenant READ of all active recurrences,
  then groups by professional_id to minimise SET LOCAL calls within the transaction.
- Idempotency is enforced at application level via find_by_exact() — no UNIQUE
  constraint on the table because sessions can be legitimately duplicated across
  different recurrences (edge case: client has two overlapping recurrences).
- A single commit at the end keeps all insertions atomic per run. If the process
  crashes mid-way, the next run will skip already-created sessions thanks to
  find_by_exact() and pick up from where it left off.
"""

import logging
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal  # noqa: F401 — available for callers / type checkers
from uuid import UUID

from dateutil.relativedelta import relativedelta

from agenda.models import Recurrence, Session  # noqa: F401
from agenda.repository import SessionsRepository
from agenda.schemas import SessionCreate
from core.database import async_session_maker, set_tenant_context

logger = logging.getLogger(__name__)

HORIZON_DAYS = 30
DEFAULT_SESSION_TIME = time(9, 0)  # 09:00 UTC


# ---------------------------------------------------------------------------
# Pure helper — no DB access, easily unit-tested
# ---------------------------------------------------------------------------


def calculate_dates(
    recurrence: Recurrence,
    today: date,
    horizon_days: int = HORIZON_DAYS,
) -> list[date]:
    """
    Return all dates within [today, today + horizon_days] that belong to this
    recurrence series.

    Rules:
    - Never before recurrence.start_date
    - Never after recurrence.end_date (when defined)
    - weekly / biweekly: advances with a fixed step from start_date, preserving
      the original series alignment regardless of what `today` is.
      (If we calculated from `today` we'd drift the series on every run.)
    - monthly: uses relativedelta(months=interval) to correctly handle
      month-end edge cases (e.g. Jan 31 → Feb 28, not Feb 31).

    Args:
        recurrence: Active Recurrence ORM object.
        today:      Reference date (usually date.today(); injectable for tests).
        horizon_days: How many days ahead to look.

    Returns:
        Sorted list of dates (may be empty).
    """
    horizon_end = today + timedelta(days=horizon_days)
    range_start = max(today, recurrence.start_date)
    range_end = min(horizon_end, recurrence.end_date) if recurrence.end_date else horizon_end

    if range_start > range_end:
        return []

    result: list[date] = []

    if recurrence.frequency in ("weekly", "biweekly"):
        step_days = (
            7 * recurrence.interval
            if recurrence.frequency == "weekly"
            else 14 * recurrence.interval
        )
        step = timedelta(days=step_days)

        # Fast-forward from start_date to near range_start while preserving the
        # original cadence alignment — integer division gives us the largest
        # multiple of step that still keeps current < range_start.
        current = recurrence.start_date
        if current < range_start:
            days_diff = (range_start - current).days
            steps_to_skip = days_diff // step_days
            current = current + step * steps_to_skip
            # One extra step may be needed if integer division landed us behind
            while current < range_start:
                current += step

        while current <= range_end:
            result.append(current)
            current += step

    elif recurrence.frequency == "monthly":
        current = recurrence.start_date
        while current <= range_end:
            if current >= range_start:
                result.append(current)
            current = current + relativedelta(months=recurrence.interval)

    return result


# ---------------------------------------------------------------------------
# Async job
# ---------------------------------------------------------------------------


async def generate_recurring_sessions() -> None:
    """
    Generate sessions for all active recurrences within the next HORIZON_DAYS days.

    Cross-tenant design:
    - READ recurrences without tenant context (app user has BYPASSRLS in production;
      tests mock the entire session).
    - WRITE sessions with set_tenant_context(session, professional_id) per professional
      (required because the sessions table has RLS WITH CHECK).

    Idempotency: checks for an existing session with (client_id, scheduled_at)
    before inserting. No UNIQUE constraint on the table — this is enforced at the
    application level.

    Error isolation: an exception in one professional is logged and skipped; the
    loop continues with the remaining professionals. The final commit only includes
    professionals that succeeded.

    Commit once at the end: SET LOCAL is valid for the entire transaction duration.
    Calling set_tenant_context() again within the same open transaction updates the
    GUC for subsequent queries — no need to open a new session per professional.
    """
    from sqlalchemy import select

    async with async_session_maker() as session:
        today = date.today()

        # Cross-tenant read — no SET LOCAL here
        result = await session.execute(select(Recurrence).where(Recurrence.is_active.is_(True)))
        recurrences = list(result.scalars().all())

        if not recurrences:
            logger.info("generate_recurring_sessions: no active recurrences found")
            return

        # Group by professional_id to minimise context-switch calls
        by_professional: dict[UUID, list[Recurrence]] = {}
        for rec in recurrences:
            by_professional.setdefault(rec.professional_id, []).append(rec)

        sessions_created = 0

        for professional_id, prof_recurrences in by_professional.items():
            try:
                await set_tenant_context(session, professional_id)
                sessions_repo = SessionsRepository(session)

                for recurrence in prof_recurrences:
                    dates = calculate_dates(recurrence, today)

                    for d in dates:
                        scheduled_at = datetime.combine(d, DEFAULT_SESSION_TIME, tzinfo=UTC)

                        # Idempotency guard — skip if session already exists
                        existing = await sessions_repo.find_by_exact(
                            recurrence.client_id, scheduled_at
                        )
                        if existing is not None:
                            continue

                        data = SessionCreate(
                            client_id=recurrence.client_id,
                            recurrence_id=recurrence.id,
                            scheduled_at=scheduled_at,
                            duration_minutes=recurrence.session_duration,
                            price=recurrence.session_price,
                        )
                        await sessions_repo.create(professional_id, data)
                        sessions_created += 1

            except Exception:
                logger.exception(
                    "generate_recurring_sessions: error processing professional %s",
                    professional_id,
                )

        await session.commit()
        logger.info(
            "generate_recurring_sessions: created %d sessions for %d professionals",
            sessions_created,
            len(by_professional),
        )
