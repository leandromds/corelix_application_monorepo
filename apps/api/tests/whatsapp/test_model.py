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
from whatsapp.models import (
    WhatsAppAccount,
    WhatsAppConversation,
    WhatsAppMessage,
    WhatsAppPhoneBinding,
    WhatsAppProviderMessage,
)
from whatsapp.providers.crypto import encrypt_credentials

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


# ===========================================================================
# Helpers — provider models
# ===========================================================================


async def _make_account(
    session: AsyncSession,
    professional_id,
    routing_tag: str | None = None,
) -> WhatsAppAccount:
    """Create and flush a minimal WhatsAppAccount."""
    account = WhatsAppAccount(
        professional_id=professional_id,
        provider_type="twilio_shared",
        phone_number="+5511000000000",
        phone_number_id="MSGSVC_SID",
        access_token_encrypted=encrypt_credentials("fake_token"),
        routing_tag=routing_tag,
    )
    session.add(account)
    await session.flush()
    await session.refresh(account)
    return account


async def _make_binding(
    session: AsyncSession,
    professional_id,
    phone_number: str = "+5511999111111",
    bound_via: str = "tag",
) -> WhatsAppPhoneBinding:
    """Create and flush a minimal WhatsAppPhoneBinding."""
    from datetime import UTC, datetime

    binding = WhatsAppPhoneBinding(
        professional_id=professional_id,
        phone_number=phone_number,
        bound_via=bound_via,
        bound_at=datetime.now(UTC),
    )
    session.add(binding)
    await session.flush()
    await session.refresh(binding)
    return binding


async def _make_provider_message(
    session: AsyncSession,
    professional_id,
    provider_message_id: str = "msg_id_001",
) -> WhatsAppProviderMessage:
    """Create and flush a minimal WhatsAppProviderMessage."""
    msg = WhatsAppProviderMessage(
        professional_id=professional_id,
        provider_message_id=provider_message_id,
        direction="inbound",
        from_phone="+5511999000000",
        to_phone="+5511000000000",
        body="Hello",
        provider_type="twilio_shared",
    )
    session.add(msg)
    await session.flush()
    await session.refresh(msg)
    return msg


# ===========================================================================
# TestWhatsAppAccountModel
# ===========================================================================


class TestWhatsAppAccountModel:
    async def test_create_account_defaults_is_active_true(self, db_session: AsyncSession) -> None:
        """
        WhatsAppAccount criada sem especificar is_active deve ter is_active=True.

        O default garante que toda conta nova está ativa imediatamente,
        sem precisar de uma etapa de ativação separada.
        """
        prof = await _make_prof(db_session, "acct_defaults@example.com")
        account = await _make_account(db_session, prof.id)

        assert account.id is not None
        assert account.is_active is True
        assert account.professional_id == prof.id
        assert account.provider_type == "twilio_shared"
        assert account.phone_number == "+5511000000000"
        assert account.routing_tag is None

    async def test_account_professional_id_is_unique(self, db_session: AsyncSession) -> None:
        """
        Não deve ser possível criar dois WhatsAppAccount para o mesmo profissional.

        Um profissional tem exatamente um provider ativo por vez.
        A constraint UNIQUE em professional_id enforce isso no banco.
        """
        prof = await _make_prof(db_session, "acct_unique_prof@example.com")
        await _make_account(db_session, prof.id, routing_tag="tag_first")

        second = WhatsAppAccount(
            professional_id=prof.id,  # mesmo professional_id
            provider_type="meta",
            phone_number="+5511000000001",
            phone_number_id="PHONE_ID_2",
            access_token_encrypted=encrypt_credentials("another_token"),
            routing_tag="tag_second",
        )
        db_session.add(second)

        with pytest.raises(IntegrityError):
            await db_session.flush()

    async def test_routing_tag_is_unique(self, db_session: AsyncSession) -> None:
        """
        Não deve ser possível criar dois WhatsAppAccount com o mesmo routing_tag.

        routing_tag é o slug usado para identificar o profissional em mensagens
        Twilio Shared. Duplicidade causaria ambiguidade no roteamento.
        """
        prof1 = await _make_prof(db_session, "acct_tag1@example.com")
        prof2 = await _make_prof(db_session, "acct_tag2@example.com")
        await _make_account(db_session, prof1.id, routing_tag="shared_slug")

        second = WhatsAppAccount(
            professional_id=prof2.id,
            provider_type="twilio_shared",
            phone_number="+5511000000002",
            phone_number_id="MSGSVC_SID_2",
            access_token_encrypted=encrypt_credentials("token2"),
            routing_tag="shared_slug",  # mesmo tag
        )
        db_session.add(second)

        with pytest.raises(IntegrityError):
            await db_session.flush()


# ===========================================================================
# TestWhatsAppPhoneBindingModel
# ===========================================================================


class TestWhatsAppPhoneBindingModel:
    async def test_create_binding_with_required_fields(self, db_session: AsyncSession) -> None:
        """
        WhatsAppPhoneBinding deve persistir com os campos obrigatórios
        e receber um UUID gerado pelo banco.
        """
        prof = await _make_prof(db_session, "binding_create@example.com")
        binding = await _make_binding(db_session, prof.id)

        assert binding.id is not None
        assert binding.phone_number == "+5511999111111"
        assert binding.bound_via == "tag"
        assert binding.professional_id == prof.id
        assert binding.bound_at is not None

    async def test_binding_unique_per_phone_and_professional(
        self, db_session: AsyncSession
    ) -> None:
        """
        Não deve ser possível criar dois vínculos com o mesmo phone_number
        e professional_id.

        A constraint (phone_number, professional_id) evita duplicatas:
        um cliente só precisa ser vinculado uma vez por profissional.
        """
        from datetime import UTC, datetime

        prof = await _make_prof(db_session, "binding_unique@example.com")
        await _make_binding(db_session, prof.id, phone_number="+5511000000003")

        dup = WhatsAppPhoneBinding(
            professional_id=prof.id,
            phone_number="+5511000000003",  # mesmo phone + mesmo profissional
            bound_via="qr",
            bound_at=datetime.now(UTC),
        )
        db_session.add(dup)

        with pytest.raises(IntegrityError):
            await db_session.flush()


# ===========================================================================
# TestWhatsAppProviderMessageModel
# ===========================================================================


class TestWhatsAppProviderMessageModel:
    async def test_create_provider_message_with_required_fields(
        self, db_session: AsyncSession
    ) -> None:
        """
        WhatsAppProviderMessage deve persistir com todos os campos obrigatórios
        e receber um UUID gerado pelo banco.
        """
        prof = await _make_prof(db_session, "prov_msg_create@example.com")
        msg = await _make_provider_message(db_session, prof.id)

        assert msg.id is not None
        assert msg.direction == "inbound"
        assert msg.from_phone == "+5511999000000"
        assert msg.to_phone == "+5511000000000"
        assert msg.body == "Hello"
        assert msg.provider_type == "twilio_shared"
        assert msg.professional_id == prof.id
        assert msg.created_at is not None

    async def test_provider_message_idempotency_constraint(self, db_session: AsyncSession) -> None:
        """
        Não deve ser possível inserir duas linhas com o mesmo professional_id
        e provider_message_id.

        Esta constraint é a garantia de idempotência de mensagens: se o provider
        reenviar o mesmo webhook, o banco rejeitá a segunda inserção,
        evitando processamento duplicado.
        """
        prof = await _make_prof(db_session, "prov_msg_idem@example.com")
        await _make_provider_message(db_session, prof.id, provider_message_id="idem_msg_001")

        dup = WhatsAppProviderMessage(
            professional_id=prof.id,
            provider_message_id="idem_msg_001",  # mesmo ID
            direction="inbound",
            from_phone="+5511999000000",
            to_phone="+5511000000000",
            body="Re-delivery",
            provider_type="twilio_shared",
        )
        db_session.add(dup)

        with pytest.raises(IntegrityError):
            await db_session.flush()
