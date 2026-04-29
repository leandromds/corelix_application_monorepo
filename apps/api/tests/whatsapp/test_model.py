"""
Tests for WhatsApp models — structural validation and constraint checks.

Coverage:
- WhatsAppConversation: default status='active' and mode='ai', professional_id FK
- WhatsAppMessage: required fields, whatsapp_msg_id UNIQUE constraint

Design: uses db_session (no RLS needed for model tests — the null-permissive
policy allows INSERT without a tenant context, same pattern as agenda/clients).

Helpers:
  _make_prof(session, email)              — minimal Professional
  _make_conversation(session, prof_id)   — minimal WhatsAppConversation
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from professionals.models import Professional
from whatsapp.models import WhatsAppConversation, WhatsAppMessage

# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


async def _make_prof(session: AsyncSession, email: str) -> Professional:
    """Create and flush a minimal Professional record."""
    p = Professional(email=email, password_hash="h", full_name="WA Test Pro")
    session.add(p)
    await session.flush()
    await session.refresh(p)
    return p


async def _make_conversation(
    session: AsyncSession,
    professional_id,
    *,
    client_phone: str = "5511999999999",
    status: str = "active",
    mode: str = "ai",
) -> WhatsAppConversation:
    """Create and flush a minimal WhatsAppConversation."""
    now = datetime.now(UTC)
    conv = WhatsAppConversation(
        professional_id=professional_id,
        client_phone=client_phone,
        status=status,
        mode=mode,
        started_at=now,
        last_message_at=now,
    )
    session.add(conv)
    await session.flush()
    await session.refresh(conv)
    return conv


# ===========================================================================
# TestWhatsAppConversationModel
# ===========================================================================


class TestWhatsAppConversationModel:
    async def test_create_conversation_defaults_status_active_and_mode_ai(
        self, db_session: AsyncSession
    ) -> None:
        """
        WhatsAppConversation created without explicit status/mode should
        default to status='active' and mode='ai'.

        These server_default values are critical for the incoming webhook flow:
        process_incoming_message() relies on a new conversation starting in
        AI mode so the bot can greet the client automatically.
        """
        prof = await _make_prof(db_session, "conv_defaults@example.com")
        now = datetime.now(UTC)
        conv = WhatsAppConversation(
            professional_id=prof.id,
            client_phone="5511888888888",
            started_at=now,
            last_message_at=now,
            # status and mode intentionally omitted — testing Python defaults
        )
        db_session.add(conv)
        await db_session.flush()
        await db_session.refresh(conv)

        assert conv.id is not None
        assert conv.status == "active"
        assert conv.mode == "ai"
        assert conv.client_phone == "5511888888888"
        assert conv.professional_id == prof.id
        assert conv.ended_at is None  # nullable, not set on creation

    async def test_conversation_requires_valid_professional_id_fk(
        self, db_session: AsyncSession
    ) -> None:
        """
        WhatsAppConversation with a non-existent professional_id should raise
        IntegrityError because of the RESTRICT foreign key constraint.

        This test verifies the database enforces tenant integrity at the
        storage layer, not just at the application layer.
        """
        invalid_id = uuid4()  # random UUID — guaranteed not in DB
        now = datetime.now(UTC)
        conv = WhatsAppConversation(
            professional_id=invalid_id,
            client_phone="5511777777777",
            status="active",
            mode="ai",
            started_at=now,
            last_message_at=now,
        )
        db_session.add(conv)

        with pytest.raises(IntegrityError):
            await db_session.flush()


# ===========================================================================
# TestWhatsAppMessageModel
# ===========================================================================


class TestWhatsAppMessageModel:
    async def test_create_message_with_required_fields(self, db_session: AsyncSession) -> None:
        """
        WhatsAppMessage should persist successfully with all required fields
        and receive a server-generated UUID id.

        sent_at is required (no Python-level default; relies on server_default
        in production, but must be supplied explicitly in tests that do not
        go through the repository).
        """
        prof = await _make_prof(db_session, "msg_required@example.com")
        conv = await _make_conversation(db_session, prof.id)

        now = datetime.now(UTC)
        msg = WhatsAppMessage(
            conversation_id=conv.id,
            direction="inbound",
            sender_type="client",
            content="Ola, gostaria de agendar uma consulta",
            sent_at=now,
        )
        db_session.add(msg)
        await db_session.flush()
        await db_session.refresh(msg)

        assert msg.id is not None
        assert msg.conversation_id == conv.id
        assert msg.direction == "inbound"
        assert msg.sender_type == "client"
        assert msg.content == "Ola, gostaria de agendar uma consulta"
        assert msg.whatsapp_msg_id is None  # nullable — OK for outbound messages

    async def test_message_whatsapp_msg_id_unique_constraint_raises_on_duplicate(
        self, db_session: AsyncSession
    ) -> None:
        """
        Inserting two WhatsAppMessage rows with the same whatsapp_msg_id
        should raise IntegrityError because of the UNIQUE constraint.

        This constraint is the foundation of webhook idempotency: Meta may
        re-deliver the same message, and we must not process it twice.
        If the DB allows duplicates, the service-layer check
        (find_message_by_whatsapp_id) becomes a TOCTOU race condition.
        """
        prof = await _make_prof(db_session, "msg_unique@example.com")
        conv = await _make_conversation(db_session, prof.id)

        now = datetime.now(UTC)
        duplicate_id = "wamid.duplicate_test_001"

        msg1 = WhatsAppMessage(
            conversation_id=conv.id,
            direction="inbound",
            sender_type="client",
            content="First delivery",
            whatsapp_msg_id=duplicate_id,
            sent_at=now,
        )
        db_session.add(msg1)
        await db_session.flush()  # persists the first message

        msg2 = WhatsAppMessage(
            conversation_id=conv.id,
            direction="inbound",
            sender_type="client",
            content="Re-delivery (duplicate)",
            whatsapp_msg_id=duplicate_id,  # same Meta message ID
            sent_at=now,
        )
        db_session.add(msg2)

        with pytest.raises(IntegrityError):
            await db_session.flush()
