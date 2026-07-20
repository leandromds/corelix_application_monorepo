"""
Shared fixtures for clients tests.

The key fixture here is `tenant_session`: a database session that has
RLS context already set to `test_professional.id`.

WHY a dedicated fixture:
  The clients table has FORCE ROW LEVEL SECURITY active (even in tests).
  Any SELECT on `clients` requires `app.current_tenant` to be set, or else
  the null-permissive policy returns 0 rows. Repository and service tests
  must always operate within a tenant context — this fixture encapsulates
  that setup so individual tests don't repeat the SET LOCAL boilerplate.

  It mirrors what TenantSession does in production (set_tenant_context()),
  but without the JWT layer — tests call the DB directly.
"""

import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from clients.models import Client
from clients.schemas import ClientCreate


@pytest_asyncio.fixture
async def tenant_session(
    db_session: AsyncSession,
    test_professional,
) -> AsyncSession:
    """
    Database session with RLS enforced for test_professional's tenant.

    Two settings are applied (both LOCAL = transaction-scoped, reverted on rollback):
      1. SET LOCAL ROLE test_rls_user  — switches to a role without BYPASSRLS so
         PostgreSQL's RLS policies are actually enforced. The 'postgres' superuser
         has BYPASSRLS and would silently skip all policies otherwise.
      2. SET LOCAL app.current_tenant  — sets the tenant context that the RLS
         policy reads via current_setting('app.current_tenant', TRUE).

    INSERTs performed by the test_professional fixture (via db_session, before
    this fixture switches the role) are still visible because they are in the
    same transaction. The role switch only affects privilege/RLS checks going
    forward in the transaction.

    Use this fixture in all repository and service tests that need to SELECT
    from the clients table with proper tenant isolation.
    """
    await db_session.execute(text("SET LOCAL ROLE test_rls_user"))
    await db_session.execute(text(f"SET LOCAL app.current_tenant = '{test_professional.id}'"))
    return db_session


@pytest_asyncio.fixture
async def test_client(
    tenant_session: AsyncSession,
    test_professional,
) -> Client:
    """
    Create and flush a real Client record for test_professional.

    Lives inside the test transaction — rolled back automatically.
    Use this in tests that need a pre-existing client to work with
    (e.g. get, update, delete).
    """
    client = Client(
        professional_id=test_professional.id,
        full_name="Test Client",
        phone="11999990001",
        email="testclient@example.com",
    )
    tenant_session.add(client)
    await tenant_session.flush()
    await tenant_session.refresh(client)
    return client


def make_client_create(
    *,
    full_name: str = "Test Client",
    phone: str | None = "11999990001",
    email: str | None = None,
    notes: str | None = None,
    whatsapp_opt_in: bool = False,
    email_opt_in: bool = False,
) -> ClientCreate:
    """
    Factory helper to build ClientCreate instances in tests.

    Defaults to a client with phone only (most common case).
    Centralises schema construction so test bodies stay readable.
    """
    return ClientCreate(
        full_name=full_name,
        phone=phone,
        email=email,
        notes=notes,
        whatsapp_opt_in=whatsapp_opt_in,
        email_opt_in=email_opt_in,
    )
