"""Shared fixtures for whatsapp tests."""

from datetime import UTC, datetime

import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from whatsapp.models import WhatsAppConversation, WhatsAppMessage


@pytest_asyncio.fixture
async def tenant_session(db_session: AsyncSession, test_professional) -> AsyncSession:
    """
    DB session with RLS enforced for test_professional.

    Same pattern as agenda/clients conftest:
      1. SET LOCAL ROLE test_rls_user  — activates RLS enforcement (postgres
         superuser has BYPASSRLS and would skip all policies otherwise).
      2. SET LOCAL app.current_tenant  — sets the UUID read by the policy.

    Both settings are transaction-scoped and reverted automatically on rollback.
    """
    await db_session.execute(text("SET LOCAL ROLE test_rls_user"))
    await db_session.execute(text(f"SET LOCAL app.current_tenant = '{test_professional.id}'"))
    return db_session


@pytest_asyncio.fixture
async def test_conversation(
    tenant_session: AsyncSession, test_professional
) -> WhatsAppConversation:
    """
    A real WhatsAppConversation for test_professional, inside the test transaction.

    status='active', mode='ai' — the standard initial state for a new conversation.
    Lives inside the test transaction and is rolled back automatically after the test.
    """
    now = datetime.now(UTC)
    conv = WhatsAppConversation(
        professional_id=test_professional.id,
        client_phone="5511999999999",
        status="active",
        mode="ai",
        started_at=now,
        last_message_at=now,
    )
    tenant_session.add(conv)
    await tenant_session.flush()
    await tenant_session.refresh(conv)
    return conv


@pytest_asyncio.fixture
async def test_message(
    tenant_session: AsyncSession, test_conversation: WhatsAppConversation
) -> WhatsAppMessage:
    """
    A real WhatsAppMessage inside test_conversation.

    whatsapp_msg_id='wamid.fixture001' — used in find_by_whatsapp_id tests.
    Lives inside the test transaction and is rolled back automatically.
    """
    msg = WhatsAppMessage(
        conversation_id=test_conversation.id,
        direction="inbound",
        sender_type="client",
        content="Ola, gostaria de agendar",
        whatsapp_msg_id="wamid.fixture001",
        sent_at=datetime.now(UTC),
    )
    tenant_session.add(msg)
    await tenant_session.flush()
    await tenant_session.refresh(msg)
    return msg
