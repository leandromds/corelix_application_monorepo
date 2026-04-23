"""
Shared pytest fixtures for testing.

This module provides:
- Database fixtures (isolated test database)
- HTTP client fixtures (AsyncClient)
- Authentication fixtures (test users, tokens)
- Factory fixtures (test data generation)
"""

import asyncio
from typing import AsyncGenerator, Generator
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from core.config import settings
from core.database import Base, async_session_maker
from main import app

# ============================================================================
# Pytest Configuration
# ============================================================================


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """
    Create an event loop for the test session.

    This ensures all async tests share the same event loop,
    which is required for session-scoped async fixtures.
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
    Create a test database engine.

    Uses a separate database URL for tests to avoid interfering with
    development data. NullPool ensures connections are not reused
    between tests.
    """
    # Use test database (modify DATABASE_URL to append _test)
    test_db_url = settings.DATABASE_URL.replace("secretaria_digital_dev", "secretaria_digital_test")

    engine = create_async_engine(
        test_db_url,
        echo=False,  # Disable SQL logging in tests
        poolclass=NullPool,  # Create new connection for each test
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Drop all tables after tests
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """
    Create a database session for a single test.

    Each test gets a fresh transaction that is rolled back after
    the test completes. This ensures test isolation.

    Usage:
    ```python
    async def test_create_client(db_session: AsyncSession):
        client = Client(name="Test")
        db_session.add(client)
        await db_session.commit()
        assert client.id is not None
    ```
    """
    async with test_engine.connect() as connection:
        # Start a transaction
        transaction = await connection.begin()

        # Create session bound to this connection
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
            # Rollback transaction to clean up test data
            await transaction.rollback()


@pytest_asyncio.fixture
async def db_session_with_tenant(
    db_session: AsyncSession, test_professional_id: str
) -> AsyncGenerator[AsyncSession, None]:
    """
    Create a database session with tenant context already set.

    Use this fixture when testing tenant-isolated operations.

    Usage:
    ```python
    async def test_list_clients(db_session_with_tenant: AsyncSession):
        # Tenant context is already set
        clients = await client_repository.find_all(db_session_with_tenant)
        assert len(clients) == 0
    ```
    """
    # Set tenant context
    await db_session.execute(
        text("SET LOCAL app.current_tenant = :tenant_id"),
        {"tenant_id": test_professional_id},
    )
    yield db_session


# ============================================================================
# HTTP Client Fixtures
# ============================================================================


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """
    Create an HTTP client for testing FastAPI endpoints.

    This client makes requests to the FastAPI app without
    starting an actual HTTP server.

    Usage:
    ```python
    async def test_health_endpoint(client: AsyncClient):
        response = await client.get("/health")
        assert response.status_code == 200
    ```
    """
    async with AsyncClient(app=app, base_url="http://testserver") as ac:
        yield ac


@pytest_asyncio.fixture
async def authenticated_client(
    client: AsyncClient, access_token: str
) -> AsyncGenerator[AsyncClient, None]:
    """
    Create an HTTP client with authentication headers.

    Use this for testing protected endpoints.

    Usage:
    ```python
    async def test_get_profile(authenticated_client: AsyncClient):
        response = await authenticated_client.get("/api/v1/professionals/me")
        assert response.status_code == 200
    ```
    """
    client.headers.update({"Authorization": f"Bearer {access_token}"})
    yield client


# ============================================================================
# Test Data Fixtures
# ============================================================================


@pytest.fixture
def test_professional_id() -> str:
    """
    Generate a test professional ID (tenant identifier).

    Returns a consistent UUID string for use in tests.
    """
    return str(uuid4())


@pytest.fixture
def test_client_id() -> str:
    """
    Generate a test client ID.

    Returns a consistent UUID string for use in tests.
    """
    return str(uuid4())


@pytest.fixture
def test_session_id() -> str:
    """
    Generate a test session ID.

    Returns a consistent UUID string for use in tests.
    """
    return str(uuid4())


# ============================================================================
# Authentication Fixtures
# ============================================================================


@pytest.fixture
def access_token(test_professional_id: str) -> str:
    """
    Generate a valid access token for testing.

    This token can be used to authenticate requests in tests.

    Note: This will be implemented after auth module is created.
    For now, returns a placeholder.

    Usage:
    ```python
    def test_protected_endpoint(client: AsyncClient, access_token: str):
        headers = {"Authorization": f"Bearer {access_token}"}
        response = client.get("/api/v1/protected", headers=headers)
        assert response.status_code == 200
    ```
    """
    # TODO: Implement after auth.service is created
    # from auth.service import create_access_token
    # return create_access_token({"sub": test_professional_id})
    return "test_access_token_placeholder"


@pytest.fixture
def refresh_token(test_professional_id: str) -> str:
    """
    Generate a valid refresh token for testing.

    Note: This will be implemented after auth module is created.
    For now, returns a placeholder.
    """
    # TODO: Implement after auth.service is created
    return "test_refresh_token_placeholder"


# ============================================================================
# Utility Fixtures
# ============================================================================


@pytest_asyncio.fixture
async def clean_database(db_session: AsyncSession) -> AsyncGenerator[None, None]:
    """
    Ensure database is clean before and after test.

    Use this when you need a completely clean slate.

    Usage:
    ```python
    async def test_with_clean_db(db_session: AsyncSession, clean_database):
        # Database is guaranteed to be empty
        pass
    ```
    """
    # Clean before test
    async with db_session.begin():
        # Delete all data from all tables
        await db_session.execute(text("TRUNCATE TABLE professionals CASCADE"))
        await db_session.execute(text("TRUNCATE TABLE clients CASCADE"))
        await db_session.execute(text("TRUNCATE TABLE sessions CASCADE"))
        # Add other tables as needed

    yield

    # Clean after test (transaction rollback handles this)


@pytest.fixture
def mock_anthropic_response() -> dict:
    """
    Mock response from Anthropic API for testing AI functionality.

    Returns a sample Claude API response structure.
    """
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
    """
    Mock WhatsApp webhook payload for testing message reception.

    Returns a sample webhook structure from Meta Cloud API.
    """
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
                                {"profile": {"name": "Test User"}, "wa_id": "5511999999999"}
                            ],
                            "messages": [
                                {
                                    "from": "5511999999999",
                                    "id": "wamid.test123",
                                    "timestamp": "1234567890",
                                    "text": {"body": "Olá, gostaria de agendar uma consulta"},
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
