"""Shared fixtures for reports tests."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from agenda.models import Session as AgendaSession
from clients.models import Client


@pytest_asyncio.fixture
async def tenant_session(
    db_session: AsyncSession,
    test_professional,
) -> AsyncSession:
    """DB session with RLS enforced for test_professional (same pattern as agenda/clients)."""
    await db_session.execute(text("SET LOCAL ROLE test_rls_user"))
    await db_session.execute(text(f"SET LOCAL app.current_tenant = '{test_professional.id}'"))
    return db_session


@pytest_asyncio.fixture
async def test_client(
    tenant_session: AsyncSession,
    test_professional,
) -> Client:
    """A real Client record for test_professional, inside the test transaction."""
    client = Client(
        professional_id=test_professional.id,
        full_name="Reports Test Client",
        phone="11977770001",
    )
    tenant_session.add(client)
    await tenant_session.flush()
    await tenant_session.refresh(client)
    return client


async def make_session(
    db: AsyncSession,
    *,
    professional_id: UUID,
    client_id: UUID,
    scheduled_at: datetime,
    status: str = "completed",
    price: Decimal = Decimal("150.00"),
    duration_minutes: int = 60,
    notes: str | None = None,
) -> AgendaSession:
    """Helper: create and flush a Session directly (no service layer needed)."""
    s = AgendaSession(
        professional_id=professional_id,
        client_id=client_id,
        scheduled_at=scheduled_at,
        duration_minutes=duration_minutes,
        price=price,
        status=status,
        notes=notes,
    )
    db.add(s)
    await db.flush()
    await db.refresh(s)
    return s
