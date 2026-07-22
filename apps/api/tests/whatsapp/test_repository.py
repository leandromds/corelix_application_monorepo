"""
Tests for WhatsAppRepository — data access layer for whatsapp_conversations and
whatsapp_messages tables.

Coverage:
- create_conversation        : returns conversation with id, sets correct professional_id
- find_active_conversation_by_phone : finds active, ignores resolved, respects RLS
- get_conversation_by_id     : found / not found
- list_conversations         : all for tenant, filtered by status
- create_message             : returns message with id, direction, sender_type
- find_message_by_whatsapp_id: found / not found
- get_messages_for_conversation: ordered by sent_at ASC

RLS isolation pattern (same as tests/agenda/test_repository.py):
  1. Create "other tenant" professional + conversation using db_session
     (postgres superuser has BYPASSRLS — inserts succeed without a tenant context).
  2. SET LOCAL ROLE test_rls_user  → activates RLS enforcement.
  3. SET LOCAL app.current_tenant = test_professional.id  → sets the tenant UUID.
  4. Query → RLS filters out the other tenant's rows (returns None / []).
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from professionals.models import Professional
from whatsapp.models import WhatsAppConversation, WhatsAppMessage
from whatsapp.providers.crypto import encrypt_credentials
from whatsapp.repository import (
    PhoneBindingRepository,
    ProviderMessageRepository,
    WhatsAppAccountRepository,
    WhatsAppRepository,
)

# ---------------------------------------------------------------------------
# Module-level helpers (avoid repetition across test classes)
# ---------------------------------------------------------------------------


async def _make_prof(session: AsyncSession, email: str) -> Professional:
    """Create and flush a minimal Professional (no RLS context needed)."""
    p = Professional(email=email, password_hash="h", full_name="Repo WA Test Pro")
    session.add(p)
    await session.flush()
    await session.refresh(p)
    return p


def _new_conversation(
    professional_id, *, client_phone: str = "5511999999999"
) -> WhatsAppConversation:
    """Build a WhatsAppConversation instance (not yet flushed)."""
    now = datetime.now(UTC)
    return WhatsAppConversation(
        professional_id=professional_id,
        client_phone=client_phone,
        status="active",
        mode="ai",
        started_at=now,
        last_message_at=now,
    )


# ===========================================================================
# create_conversation
# ===========================================================================


class TestCreateConversation:
    async def test_create_conversation_returns_conversation_with_id(
        self,
        tenant_session: AsyncSession,
        test_professional,
    ) -> None:
        """
        create_conversation() deve retornar WhatsAppConversation com id gerado
        pelo banco, status='active' e mode='ai' (defaults do domínio).
        """
        repo = WhatsAppRepository(tenant_session)

        conv = await repo.create_conversation(
            professional_id=test_professional.id,
            client_phone="5511111111111",
        )

        assert conv.id is not None
        assert conv.status == "active"
        assert conv.mode == "ai"
        assert conv.client_phone == "5511111111111"
        assert conv.professional_id == test_professional.id

    async def test_create_conversation_sets_correct_professional_id(
        self,
        tenant_session: AsyncSession,
        test_professional,
    ) -> None:
        """professional_id no objeto retornado deve corresponder ao argumento passado."""
        repo = WhatsAppRepository(tenant_session)

        conv = await repo.create_conversation(
            professional_id=test_professional.id,
            client_phone="5511222222222",
        )

        assert conv.professional_id == test_professional.id


# ===========================================================================
# find_active_conversation_by_phone
# ===========================================================================


class TestFindActiveConversationByPhone:
    async def test_find_active_conversation_by_phone_returns_active(
        self,
        tenant_session: AsyncSession,
        test_conversation: WhatsAppConversation,
    ) -> None:
        """
        Uma conversa com status='active' deve ser encontrada pelo número de telefone.
        """
        repo = WhatsAppRepository(tenant_session)

        found = await repo.find_active_conversation_by_phone(test_conversation.client_phone)

        assert found is not None
        assert found.id == test_conversation.id

    async def test_find_active_conversation_by_phone_returns_none_when_resolved(
        self,
        tenant_session: AsyncSession,
        test_professional,
    ) -> None:
        """
        Uma conversa com status='resolved' NÃO deve ser retornada.

        A lógica do serviço cria uma nova conversa quando find_active retorna None,
        portanto uma conversa resolvida deve ser invisível para o fluxo de entrada.
        """
        now = datetime.now(UTC)
        resolved_conv = WhatsAppConversation(
            professional_id=test_professional.id,
            client_phone="5511333333333",
            status="resolved",
            mode="ai",
            started_at=now,
            last_message_at=now,
        )
        tenant_session.add(resolved_conv)
        await tenant_session.flush()

        repo = WhatsAppRepository(tenant_session)
        found = await repo.find_active_conversation_by_phone("5511333333333")

        assert found is None

    async def test_find_active_conversation_by_phone_rls_other_tenant_not_visible(
        self,
        db_session: AsyncSession,
        test_professional,
    ) -> None:
        """
        Uma conversa de outro tenant com o mesmo número de telefone NÃO deve
        ser visível após ativar o RLS para test_professional.

        Padrão de isolamento RLS:
          1. Criar dado do outro tenant SEM contexto (postgres = BYPASSRLS).
          2. Ativar RLS com SET LOCAL ROLE + SET LOCAL app.current_tenant.
          3. Consultar — RLS filtra o dado do outro tenant → retorna None.
        """
        # Step 1: create another professional's conversation WITHOUT RLS
        other_prof = await _make_prof(db_session, "wa_rls_other@example.com")
        conv = _new_conversation(other_prof.id, client_phone="5511999999999")
        db_session.add(conv)
        await db_session.flush()

        # Step 2: activate RLS for test_professional
        await db_session.execute(text("SET LOCAL ROLE test_rls_user"))
        await db_session.execute(text(f"SET LOCAL app.current_tenant = '{test_professional.id}'"))

        # Step 3: query — should not see other tenant's conversation
        repo = WhatsAppRepository(db_session)
        found = await repo.find_active_conversation_by_phone("5511999999999")

        assert found is None


# ===========================================================================
# get_conversation_by_id
# ===========================================================================


class TestGetConversationById:
    async def test_get_conversation_by_id_returns_conversation(
        self,
        tenant_session: AsyncSession,
        test_conversation: WhatsAppConversation,
    ) -> None:
        """get_conversation_by_id() deve retornar a conversa quando o ID existe."""
        repo = WhatsAppRepository(tenant_session)

        found = await repo.get_conversation_by_id(test_conversation.id)

        assert found is not None
        assert found.id == test_conversation.id

    async def test_get_conversation_by_id_returns_none_for_unknown(
        self,
        tenant_session: AsyncSession,
    ) -> None:
        """get_conversation_by_id() deve retornar None para um UUID inexistente."""
        repo = WhatsAppRepository(tenant_session)

        found = await repo.get_conversation_by_id(uuid4())

        assert found is None


# ===========================================================================
# list_conversations
# ===========================================================================


class TestListConversations:
    async def test_list_conversations_returns_all_for_tenant(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_conversation: WhatsAppConversation,
    ) -> None:
        """
        list_conversations() deve retornar todas as conversas do tenant.

        test_conversation já existe (criado pelo fixture).
        Criamos uma segunda para garantir que o count é 2.
        """
        now = datetime.now(UTC)
        second_conv = WhatsAppConversation(
            professional_id=test_professional.id,
            client_phone="5511444444444",
            status="active",
            mode="ai",
            started_at=now,
            last_message_at=now,
        )
        tenant_session.add(second_conv)
        await tenant_session.flush()

        repo = WhatsAppRepository(tenant_session)
        conversations = await repo.list_conversations()

        assert len(conversations) == 2
        ids = {c.id for c in conversations}
        assert test_conversation.id in ids
        assert second_conv.id in ids

    async def test_list_conversations_filters_by_status(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_conversation: WhatsAppConversation,
    ) -> None:
        """
        list_conversations(status='active') deve retornar somente conversas ativas.

        test_conversation tem status='active'. Criamos uma resolved — ela NÃO
        deve aparecer no resultado filtrado.
        """
        now = datetime.now(UTC)
        resolved_conv = WhatsAppConversation(
            professional_id=test_professional.id,
            client_phone="5511555555555",
            status="resolved",
            mode="ai",
            started_at=now,
            last_message_at=now,
        )
        tenant_session.add(resolved_conv)
        await tenant_session.flush()

        repo = WhatsAppRepository(tenant_session)
        active_only = await repo.list_conversations(status="active")

        assert len(active_only) == 1
        assert active_only[0].id == test_conversation.id
        assert active_only[0].status == "active"


# ===========================================================================
# create_message
# ===========================================================================


class TestCreateMessage:
    async def test_create_message_returns_message_with_id(
        self,
        tenant_session: AsyncSession,
        test_conversation: WhatsAppConversation,
    ) -> None:
        """
        create_message() deve retornar WhatsAppMessage com id gerado pelo banco,
        direction e sender_type corretos.
        """
        repo = WhatsAppRepository(tenant_session)

        msg = await repo.create_message(
            conversation_id=test_conversation.id,
            direction="inbound",
            sender_type="client",
            content="Quero agendar uma consulta",
            whatsapp_msg_id="wamid.repo_test_001",
        )

        assert msg.id is not None
        assert msg.conversation_id == test_conversation.id
        assert msg.direction == "inbound"
        assert msg.sender_type == "client"
        assert msg.content == "Quero agendar uma consulta"
        assert msg.whatsapp_msg_id == "wamid.repo_test_001"


# ===========================================================================
# find_message_by_whatsapp_id
# ===========================================================================


class TestFindMessageByWhatsappId:
    async def test_find_message_by_whatsapp_id_returns_message(
        self,
        tenant_session: AsyncSession,
        test_message: WhatsAppMessage,
    ) -> None:
        """
        find_message_by_whatsapp_id() deve encontrar a mensagem pelo ID do Meta.

        test_message tem whatsapp_msg_id='wamid.fixture001' (definido no conftest).
        """
        repo = WhatsAppRepository(tenant_session)

        found = await repo.find_message_by_whatsapp_id("wamid.fixture001")

        assert found is not None
        assert found.id == test_message.id
        assert found.whatsapp_msg_id == "wamid.fixture001"

    async def test_find_message_by_whatsapp_id_returns_none_for_unknown(
        self,
        tenant_session: AsyncSession,
    ) -> None:
        """find_message_by_whatsapp_id() deve retornar None para ID inexistente."""
        repo = WhatsAppRepository(tenant_session)

        found = await repo.find_message_by_whatsapp_id("wamid.nonexistent_xyz")

        assert found is None


# ===========================================================================
# get_messages_for_conversation
# ===========================================================================


class TestGetMessagesForConversation:
    async def test_get_messages_ordered_by_sent_at_asc(
        self,
        tenant_session: AsyncSession,
        test_conversation: WhatsAppConversation,
    ) -> None:
        """
        get_messages_for_conversation() deve retornar mensagens ordenadas por
        sent_at ASC (ordem cronológica).

        Inserimos as mensagens em ordem inversa (msg_later primeiro) para
        garantir que o ORDER BY é o que produz a ordenação correta, não a
        ordem de inserção.
        """
        earlier_time = datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC)
        later_time = datetime(2024, 6, 1, 12, 0, 0, tzinfo=UTC)

        # Add in reverse order to prove ORDER BY is the source of ordering
        msg_later = WhatsAppMessage(
            conversation_id=test_conversation.id,
            direction="outbound",
            sender_type="ai",
            content="Segunda mensagem",
            sent_at=later_time,
        )
        msg_earlier = WhatsAppMessage(
            conversation_id=test_conversation.id,
            direction="inbound",
            sender_type="client",
            content="Primeira mensagem",
            sent_at=earlier_time,
        )
        tenant_session.add(msg_later)
        tenant_session.add(msg_earlier)
        await tenant_session.flush()

        repo = WhatsAppRepository(tenant_session)
        messages = await repo.get_messages_for_conversation(test_conversation.id)

        assert len(messages) == 2
        assert messages[0].content == "Primeira mensagem"
        assert messages[1].content == "Segunda mensagem"
        assert messages[0].sent_at < messages[1].sent_at


# ===========================================================================
# TestWhatsAppAccountRepository
# ===========================================================================


class TestWhatsAppAccountRepository:
    async def test_create_and_find_by_professional_id(
        self,
        tenant_session: AsyncSession,
        test_professional,
    ) -> None:
        """
        create() deve retornar WhatsAppAccount com id gerado e is_active=True.
        find_by_professional_id() deve retornar a conta recém-criada.
        """
        repo = WhatsAppAccountRepository(tenant_session)
        account = await repo.create(
            professional_id=test_professional.id,
            provider_type="twilio_shared",
            phone_number="+5511000001111",
            phone_number_id="MSGSVC_001",
            access_token_encrypted=encrypt_credentials("access_token_1"),
            routing_tag="tag001",
        )

        assert account.id is not None
        assert account.is_active is True
        assert account.routing_tag == "tag001"

        found = await repo.find_by_professional_id(test_professional.id)
        assert found is not None
        assert found.id == account.id
        assert found.routing_tag == "tag001"

    async def test_find_returns_none_for_unknown_professional(
        self,
        tenant_session: AsyncSession,
        test_professional,
    ) -> None:
        """
        find_by_professional_id() deve retornar None quando não há conta
        para o UUID fornecido.
        """
        repo = WhatsAppAccountRepository(tenant_session)
        found = await repo.find_by_professional_id(uuid4())
        assert found is None

    async def test_find_by_routing_tag(
        self,
        tenant_session: AsyncSession,
        test_professional,
    ) -> None:
        """
        find_by_routing_tag() deve retornar a conta com o tag fornecido
        e None para um tag inexistente.
        """
        repo = WhatsAppAccountRepository(tenant_session)
        account = await repo.create(
            professional_id=test_professional.id,
            provider_type="twilio_shared",
            phone_number="+5511000002222",
            phone_number_id="MSGSVC_002",
            access_token_encrypted=encrypt_credentials("access_token_2"),
            routing_tag="unique_slug",
        )

        found = await repo.find_by_routing_tag("unique_slug")
        assert found is not None
        assert found.id == account.id

        not_found = await repo.find_by_routing_tag("nonexistent_slug")
        assert not_found is None


# ===========================================================================
# TestPhoneBindingRepository
# ===========================================================================


class TestPhoneBindingRepository:
    async def test_create_and_find_by_phone(
        self,
        db_session: AsyncSession,
        test_professional,
    ) -> None:
        """
        create() deve retornar WhatsAppPhoneBinding com id e phone_number corretos.
        find_by_phone() deve encontrar o vínculo pelo número (cross-tenant).
        """
        repo = PhoneBindingRepository(db_session)
        binding = await repo.create(
            professional_id=test_professional.id,
            phone_number="+5511888000001",
            bound_via="tag",
        )

        assert binding.id is not None
        assert binding.phone_number == "+5511888000001"
        assert binding.bound_via == "tag"

        found = await repo.find_by_phone("+5511888000001")
        assert found is not None
        assert found.id == binding.id

    async def test_find_by_phone_returns_none_if_not_exists(
        self,
        db_session: AsyncSession,
        test_professional,
    ) -> None:
        """
        find_by_phone() deve retornar None quando não há vínculo para o número.
        """
        repo = PhoneBindingRepository(db_session)
        found = await repo.find_by_phone("+5500000000000")
        assert found is None

    async def test_list_by_professional(
        self,
        db_session: AsyncSession,
        test_professional,
    ) -> None:
        """
        list_by_professional() deve retornar todos os vínculos do profissional,
        ordenados por bound_at DESC.
        """
        repo = PhoneBindingRepository(db_session)
        b1 = await repo.create(
            professional_id=test_professional.id,
            phone_number="+5511777000001",
            bound_via="tag",
        )
        b2 = await repo.create(
            professional_id=test_professional.id,
            phone_number="+5511777000002",
            bound_via="qr",
        )

        bindings = await repo.list_by_professional(test_professional.id)
        assert len(bindings) == 2
        ids = {b.id for b in bindings}
        assert b1.id in ids
        assert b2.id in ids


# ===========================================================================
# TestProviderMessageRepository
# ===========================================================================


class TestProviderMessageRepository:
    async def test_create_and_exists_returns_true(
        self,
        tenant_session: AsyncSession,
        test_professional,
    ) -> None:
        """
        create() deve persistir a mensagem.
        exists() deve retornar True após a inserção.

        Este é o fluxo normal: criar o registro e depois consultar
        se já existe antes de processar um novo webhook.
        """
        repo = ProviderMessageRepository(tenant_session)
        msg = await repo.create(
            professional_id=test_professional.id,
            provider_message_id="SM_test_001",
            direction="inbound",
            from_phone="+5511999888001",
            to_phone="+5511000000000",
            body="Ola, quero agendar",
            provider_type="twilio_shared",
        )

        assert msg.id is not None

        already_processed = await repo.exists(
            professional_id=test_professional.id,
            provider_message_id="SM_test_001",
        )
        assert already_processed is True

    async def test_exists_returns_false_for_unknown_id(
        self,
        tenant_session: AsyncSession,
        test_professional,
    ) -> None:
        """
        exists() deve retornar False quando o provider_message_id não existe
        para o profissional.
        """
        repo = ProviderMessageRepository(tenant_session)
        result = await repo.exists(
            professional_id=test_professional.id,
            provider_message_id="SM_nonexistent_999",
        )
        assert result is False

    async def test_duplicate_raises_integrity_error(
        self,
        tenant_session: AsyncSession,
        test_professional,
    ) -> None:
        """
        Tentar criar dois registros com o mesmo professional_id +
        provider_message_id deve levantar IntegrityError.

        Garante que a constraint uq_provider_msg funciona como guard de
        idempotência no banco, além da verificação do método exists().
        """
        repo = ProviderMessageRepository(tenant_session)
        await repo.create(
            professional_id=test_professional.id,
            provider_message_id="SM_dup_001",
            direction="inbound",
            from_phone="+5511999888002",
            to_phone="+5511000000000",
            body="First delivery",
            provider_type="twilio_shared",
        )

        with pytest.raises(IntegrityError):
            await repo.create(
                professional_id=test_professional.id,
                provider_message_id="SM_dup_001",  # mesmo ID
                direction="inbound",
                from_phone="+5511999888002",
                to_phone="+5511000000000",
                body="Re-delivery (duplicate)",
                provider_type="twilio_shared",
            )
