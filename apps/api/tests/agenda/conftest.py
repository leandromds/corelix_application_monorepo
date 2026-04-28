"""
Shared fixtures for agenda tests.

Follows the same pattern as tests/clients/conftest.py:
  - tenant_session: DB session with RLS set to test_professional's tenant.
  - test_client: a real Client record inside the test transaction.
  - Entity fixtures: one pre-existing record for each agenda model, used
    by tests that need an existing object to update/delete/query.

WHY tenant_session here:
  All agenda tables have RLS enabled.  Any SELECT requires
  app.current_tenant to be set, otherwise the null-permissive policy
  returns 0 rows.  Repository and service tests must always run inside a
  tenant context.  SET LOCAL ROLE test_rls_user activates RLS enforcement
  (the postgres superuser has BYPASSRLS and would skip all policies).
"""

from datetime import UTC, date, datetime, time
from decimal import Decimal

import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from agenda.models import AvailabilitySlot, BlockedPeriod, Recurrence
from agenda.models import Session as AgendaSession
from clients.models import Client

# ---------------------------------------------------------------------------
# Tenant-scoped session
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def tenant_session(
    db_session: AsyncSession,
    test_professional,
) -> AsyncSession:
    """
    Database session with RLS enforced for test_professional's tenant.

    Two SET LOCAL calls (both transaction-scoped, reverted on rollback):
      1. SET LOCAL ROLE test_rls_user — switches away from the postgres
         superuser so RLS policies are actually applied (postgres has
         BYPASSRLS and ignores all policies otherwise).
      2. SET LOCAL app.current_tenant — sets the UUID that RLS policies
         read via current_setting('app.current_tenant', TRUE).

    INSERTs made by test_professional (via db_session, before this fixture
    switches the role) remain visible because they are in the same
    transaction.
    """
    await db_session.execute(text("SET LOCAL ROLE test_rls_user"))
    await db_session.execute(text(f"SET LOCAL app.current_tenant = '{test_professional.id}'"))
    return db_session


# ---------------------------------------------------------------------------
# Client fixture (agenda tests need a client to attach sessions/recurrences)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def test_client(
    tenant_session: AsyncSession,
    test_professional,
) -> Client:
    """
    Create and flush a real Client record for test_professional.

    Lives inside the test transaction — rolled back automatically.
    Used as the client_id FK for Session and Recurrence fixtures.
    """
    client = Client(
        professional_id=test_professional.id,
        full_name="Agenda Test Client",
        phone="11988880001",
    )
    tenant_session.add(client)
    await tenant_session.flush()
    await tenant_session.refresh(client)
    return client


# ---------------------------------------------------------------------------
# AvailabilitySlot fixture
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def test_availability_slot(
    tenant_session: AsyncSession,
    test_professional,
) -> AvailabilitySlot:
    """
    Pre-existing AvailabilitySlot for test_professional.

    day_of_week=1 (Monday), 09:00–12:00.
    Used by update/delete/get tests that need an existing record.
    """
    slot = AvailabilitySlot(
        professional_id=test_professional.id,
        day_of_week=1,
        start_time=time(9, 0),
        end_time=time(12, 0),
    )
    tenant_session.add(slot)
    await tenant_session.flush()
    await tenant_session.refresh(slot)
    return slot


# ---------------------------------------------------------------------------
# BlockedPeriod fixture
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def test_blocked_period(
    tenant_session: AsyncSession,
    test_professional,
) -> BlockedPeriod:
    """
    Pre-existing BlockedPeriod for test_professional.

    Far in the future (2030-01-10) so it does not interfere with
    session-conflict tests that also use 2030 dates.
    """
    period = BlockedPeriod(
        professional_id=test_professional.id,
        start_datetime=datetime(2030, 1, 10, 8, 0, tzinfo=UTC),
        end_datetime=datetime(2030, 1, 10, 18, 0, tzinfo=UTC),
        reason="Test block",
    )
    tenant_session.add(period)
    await tenant_session.flush()
    await tenant_session.refresh(period)
    return period


# ---------------------------------------------------------------------------
# Recurrence fixture
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def test_recurrence(
    tenant_session: AsyncSession,
    test_professional,
    test_client,
) -> Recurrence:
    """
    Pre-existing weekly Recurrence for test_professional / test_client.

    Used by service tests that cancel a recurrence and by repository tests
    for cancel_future_by_recurrence.
    """
    recurrence = Recurrence(
        professional_id=test_professional.id,
        client_id=test_client.id,
        frequency="weekly",
        interval=1,
        day_of_week=1,
        start_date=date(2025, 1, 1),
        session_duration=60,
        session_price=Decimal("150.00"),
    )
    tenant_session.add(recurrence)
    await tenant_session.flush()
    await tenant_session.refresh(recurrence)
    return recurrence


# ---------------------------------------------------------------------------
# Session fixture
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def test_agenda_session(
    tenant_session: AsyncSession,
    test_professional,
    test_client,
) -> AgendaSession:
    """
    Pre-existing scheduled Session for test_professional / test_client.

    Scheduled in 2030 so it counts as a "future" session in conflict
    and cancel tests.  Named test_agenda_session to avoid shadowing
    pytest's own `session` fixture.
    """
    agenda_session = AgendaSession(
        professional_id=test_professional.id,
        client_id=test_client.id,
        scheduled_at=datetime(2030, 6, 1, 10, 0, tzinfo=UTC),
        duration_minutes=60,
        price=Decimal("150.00"),
    )
    tenant_session.add(agenda_session)
    await tenant_session.flush()
    await tenant_session.refresh(agenda_session)
    return agenda_session
