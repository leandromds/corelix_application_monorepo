"""
Shared pytest fixtures for testing.

This module provides:
- Database fixtures (isolated test database with per-test transaction rollback)
- HTTP client fixtures (AsyncClient with test database injection)
- Authentication fixtures (test professionals, tokens)
"""

import asyncio
from typing import AsyncGenerator, Generator
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from core.config import settings
from core.database import Base
from core.security import create_access_token, hash_password
from main import app

# ============================================================================
# Pytest Configuration
# ============================================================================


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """
    Create an event loop for the test session.

    Shared across all async tests to allow session-scoped async fixtures.
    """
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ============================================================================
# Database Fixtures
# ============================================================================


@pytest_asyncio.fixture(scope="session")
async def test_engine() -> AsyncGenerator[AsyncEngine, None]:
    """
    Create a test database engine pointing at secretaria_digital_test.

    NullPool ensures no connection is reused between tests.
    Tables are created once per session and dropped at the end.
    """
    test_db_url = settings.DATABASE_URL.replace("secretaria_digital_dev", "secretaria_digital_test")

    engine = create_async_engine(
        test_db_url,
        echo=False,
        poolclass=NullPool,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        # ── RLS setup for the clients table ──────────────────────────────────
        #
        # PROBLEM: 'postgres' (the test DB user) has the BYPASSRLS privilege.
        # PostgreSQL documentation explicitly states that FORCE ROW LEVEL SECURITY
        # has NO effect on users with BYPASSRLS. Even with FORCE RLS enabled on
        # the table, postgres simply ignores all policies.
        #
        # SOLUTION: create a limited role 'test_rls_user' (NOLOGIN, no BYPASSRLS).
        # Tests that need to verify cross-tenant isolation call
        #   SET LOCAL ROLE test_rls_user
        # before their SELECT queries. Since that role lacks BYPASSRLS, RLS is
        # naturally enforced. SET LOCAL limits the role switch to the current
        # transaction — it is reverted automatically on rollback.
        #
        # WHY current_setting(..., TRUE) in the policy:
        # The TRUE flag returns NULL instead of an error when 'app.current_tenant'
        # is not set. TestClientModel tests perform only INSERTs (flush) without
        # setting a tenant; the IS NULL branch keeps those tests working.
        # The RETURNING clause of INSERT is also filtered by USING, so a strict
        # policy would silently make client.id = None after flush().
        #
        # Policy behaviour summary:
        #   - No tenant set    → all rows visible / all inserts allowed  (model tests)
        #   - Tenant set       → only rows matching professional_id = tenant visible
        #   - Role = test_rls_user + tenant set → strict isolation enforced  (RLS tests)
        await conn.execute(text("ALTER TABLE clients ENABLE ROW LEVEL SECURITY"))
        # Drop any stale policy from a previous interrupted session (create_all
        # skips existing tables, so CREATE POLICY would fail with "already exists").
        await conn.execute(text("DROP POLICY IF EXISTS tenant_isolation ON clients"))
        await conn.execute(
            text("""
            CREATE POLICY tenant_isolation ON clients
            USING (
                current_setting('app.current_tenant', TRUE) IS NULL
                OR professional_id = current_setting('app.current_tenant', TRUE)::uuid
            )
            WITH CHECK (
                current_setting('app.current_tenant', TRUE) IS NULL
                OR professional_id = current_setting('app.current_tenant', TRUE)::uuid
            )
        """)
        )

        # Create test_rls_user (non-privileged role, no BYPASSRLS).
        # Clean up any leftover role from a previous interrupted test session.
        await conn.execute(
            text("""
            DO $$ BEGIN
                IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'test_rls_user') THEN
                    DROP OWNED BY test_rls_user;
                    DROP ROLE test_rls_user;
                END IF;
            END $$
        """)
        )
        await conn.execute(text("CREATE ROLE test_rls_user NOLOGIN"))
        await conn.execute(text("GRANT USAGE ON SCHEMA public TO test_rls_user"))
        await conn.execute(text("GRANT ALL ON ALL TABLES IN SCHEMA public TO test_rls_user"))

    yield engine

    async with engine.begin() as conn:
        # Revoke all privileges before dropping tables, then remove the role.
        # DROP OWNED BY revokes all privileges granted TO the role (schema, tables).
        # Without this, DROP ROLE fails with "dependent objects still exist".
        await conn.execute(text("DROP OWNED BY test_rls_user"))
        await conn.execute(text("DROP ROLE IF EXISTS test_rls_user"))
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """
    Isolated database session for a single test.

    Each test gets a fresh transaction that is ROLLED BACK after the test.
    This guarantees test isolation without truncating tables between runs.

    Design note: the session is bound to a raw connection (not the pool),
    so SET LOCAL (RLS tenant context) works correctly within the transaction.
    """
    async with test_engine.connect() as connection:
        transaction = await connection.begin()

        session = AsyncSession(
            bind=connection,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )

        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()


@pytest_asyncio.fixture
async def db_session_with_tenant(
    db_session: AsyncSession, test_professional_id: str
) -> AsyncGenerator[AsyncSession, None]:
    """
    Database session with tenant RLS context already set.

    Use this fixture when testing queries that depend on Row-Level Security.
    """
    await db_session.execute(text(f"SET LOCAL app.current_tenant = '{test_professional_id}'"))
    yield db_session


# ============================================================================
# HTTP Client Fixtures
# ============================================================================


@pytest_asyncio.fixture
async def http_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    HTTP client that injects the test database session into FastAPI.

    By overriding get_db, all routes that use DbSession or TenantSession
    will operate on the same transaction as the test — allowing rollback
    at the end without committing anything to the real database.

    Usage: for testing routes (both public and protected).
    """
    from core.database import get_db

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://testserver") as ac:
        yield ac

    # Clean up only our override
    app.dependency_overrides.pop(get_db, None)


@pytest_asyncio.fixture
async def authenticated_http_client(
    http_client: AsyncClient,
    test_professional: "Professional",  # noqa: F821
) -> AsyncGenerator[AsyncClient, None]:
    """
    HTTP client with a valid Bearer JWT for test_professional.

    Depends on http_client (which already injects the test DB session),
    so all authenticated requests also use the isolated test transaction.
    """
    token = create_access_token(str(test_professional.id))
    http_client.headers["Authorization"] = f"Bearer {token}"
    yield http_client


# ============================================================================
# Test Data Fixtures
# ============================================================================


@pytest.fixture
def test_professional_id() -> str:
    """Random UUID string to use as a tenant identifier in unit tests."""
    return str(uuid4())


@pytest_asyncio.fixture
async def test_professional(db_session: AsyncSession):
    """
    Create and flush a real Professional record for use in tests.

    The record lives inside the test transaction and is rolled back
    after the test — no cleanup required.
    """
    from professionals.models import Professional

    prof = Professional(
        email="testpro@example.com",
        password_hash=hash_password("testpassword123"),
        full_name="Test Professional",
        specialty="Fisioterapia",
    )
    db_session.add(prof)
    await db_session.flush()
    return prof


# ============================================================================
# Authentication Fixtures
# ============================================================================


@pytest.fixture
def access_token(test_professional_id: str) -> str:
    """
    Generate a real JWT access token for test_professional_id.

    Replaces the old placeholder string.
    """
    return create_access_token(test_professional_id)


@pytest.fixture
def refresh_token() -> str:
    """
    Generate a raw refresh token for testing.

    Note: the hash of this token must be stored in the DB to be valid.
    For full flow tests, use the auth service or router fixtures instead.
    """
    from core.security import generate_refresh_token

    raw, _ = generate_refresh_token()
    return raw


# ============================================================================
# Mock Fixtures
# ============================================================================


@pytest.fixture
def mock_anthropic_response() -> dict:
    """Mock response from Anthropic API."""
    return {
        "id": "msg_test123",
        "type": "message",
        "role": "assistant",
        "content": [{"type": "text", "text": "This is a test AI response"}],
        "model": "claude-sonnet-3-5-20241022",
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 10, "output_tokens": 20},
    }


@pytest.fixture
def mock_whatsapp_webhook_payload() -> dict:
    """Mock WhatsApp webhook payload from Meta Cloud API."""
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WHATSAPP_BUSINESS_ACCOUNT_ID",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "1234567890",
                                "phone_number_id": "PHONE_NUMBER_ID",
                            },
                            "contacts": [
                                {
                                    "profile": {"name": "Test User"},
                                    "wa_id": "5511999999999",
                                }
                            ],
                            "messages": [
                                {
                                    "from": "5511999999999",
                                    "id": "wamid.test123",
                                    "timestamp": "1234567890",
                                    "text": {"body": "Ola, gostaria de agendar uma consulta"},
                                    "type": "text",
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }
