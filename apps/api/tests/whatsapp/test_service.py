"""
Tests for WhatsAppService — business logic layer for WhatsApp integration.

All repository and AI calls are mocked via AsyncMock so no database or
external API is needed. This follows the same pattern as tests/reports/test_service.py.

Coverage (17 tests):
1.  process_incoming_message is idempotent (duplicate whatsapp_msg_id skipped)
2.  process_incoming_message creates conversation on first contact
3.  process_incoming_message reuses an existing active conversation
4.  process_incoming_message saves the inbound message (direction='inbound', sender_type='client')
5.  process_incoming_message in AI mode calls AI and saves outbound reply
6.  process_incoming_message in handoff mode does NOT call AI
7.  process_incoming_message gracefully degrades when AI raises ExternalServiceError
8.  handoff_to_professional calls update_conversation with mode='handoff'
9.  handoff_to_professional raises NotFoundError when conversation not found
10. list_conversations delegates entirely to repository.list_conversations
11. get_conversation_detail returns (conversation, messages) tuple
12. get_conversation_detail raises NotFoundError for unknown conversation_id
"""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from core.exceptions import ExternalServiceError, NotFoundError
from whatsapp.schemas import InboundMessage
from whatsapp.service import WhatsAppService

# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture
def service() -> WhatsAppService:
    """
    WhatsAppService with repository and AI fully mocked.

    We instantiate the real service class (to exercise __init__ wiring) and
    then replace self.repository and self.ai with AsyncMock objects so no
    database or external API is invoked.
    """
    mock_db = AsyncMock()
    svc = WhatsAppService(mock_db)
    svc.repository = AsyncMock()
    svc.ai = AsyncMock()
    return svc


@pytest.fixture
def mock_professional() -> MagicMock:
    """
    Minimal Professional mock used as the first argument to process_incoming_message.

    whatsapp_access_token=None means send_message_via_meta is never called,
    keeping these unit tests focused on the service logic rather than the
    Meta HTTP integration.
    """
    prof = MagicMock()
    prof.id = uuid4()
    prof.full_name = "Dr. Test"
    prof.specialty = "Fisioterapia"
    prof.session_duration = 60
    prof.session_price = Decimal("150.00")
    prof.whatsapp_phone_id = "PHONE_NUMBER_ID"
    prof.whatsapp_access_token = None  # No token → Meta delivery skipped
    return prof


@pytest.fixture
def mock_conversation() -> MagicMock:
    """
    Minimal WhatsAppConversation mock.

    mode='ai' matches the default for new conversations.
    Tests that need handoff behaviour override mock_conversation.mode directly.
    """
    conv = MagicMock()
    conv.id = uuid4()
    conv.mode = "ai"
    conv.status = "active"
    return conv


# ===========================================================================
# TestProcessIncomingMessage
# ===========================================================================


class TestProcessIncomingMessage:
    # -----------------------------------------------------------------------
    # 1. Idempotency
    # -----------------------------------------------------------------------

    async def test_process_incoming_message_is_idempotent(
        self,
        service: WhatsAppService,
        mock_professional: MagicMock,
    ) -> None:
        """
        If find_message_by_whatsapp_id returns an existing message, the service
        must return early and NOT call create_message again.

        Meta's webhook has at-least-once delivery semantics. Without this guard,
        the same inbound message could generate multiple AI replies and duplicate
        conversation entries.
        """
        service.repository.find_message_by_whatsapp_id.return_value = MagicMock()

        await service.process_incoming_message(
            professional=mock_professional,
            client_phone="5511999999999",
            content="Ola",
            whatsapp_msg_id="wamid.already_processed",
        )

        service.repository.create_message.assert_not_called()

    # -----------------------------------------------------------------------
    # 2. First contact — create conversation
    # -----------------------------------------------------------------------

    async def test_process_incoming_message_creates_conversation_on_first_contact(
        self,
        service: WhatsAppService,
        mock_professional: MagicMock,
        mock_conversation: MagicMock,
    ) -> None:
        """
        When find_active_conversation_by_phone returns None (first message from
        this phone number), create_conversation MUST be called.

        The new conversation becomes the parent for the inbound message and
        the subsequent AI reply.
        """
        service.repository.find_message_by_whatsapp_id.return_value = None
        service.repository.find_active_conversation_by_phone.return_value = None
        service.repository.create_conversation.return_value = mock_conversation
        service.ai.complete_with_history.return_value = "Olá! Como posso ajudar?"
        service.repository.get_messages_for_conversation.return_value = []

        await service.process_incoming_message(
            professional=mock_professional,
            client_phone="5511999999999",
            content="Primeira mensagem",
            whatsapp_msg_id="wamid.first_contact",
        )

        service.repository.create_conversation.assert_called_once_with(
            mock_professional.id, "5511999999999"
        )

    # -----------------------------------------------------------------------
    # 3. Existing conversation — do NOT create a new one
    # -----------------------------------------------------------------------

    async def test_process_incoming_message_reuses_existing_conversation(
        self,
        service: WhatsAppService,
        mock_professional: MagicMock,
        mock_conversation: MagicMock,
    ) -> None:
        """
        When an active conversation already exists for this phone number,
        create_conversation must NOT be called — the existing conversation
        is reused to maintain conversation continuity.
        """
        service.repository.find_message_by_whatsapp_id.return_value = None
        service.repository.find_active_conversation_by_phone.return_value = mock_conversation
        service.ai.complete_with_history.return_value = "Resposta da IA"
        service.repository.get_messages_for_conversation.return_value = []

        await service.process_incoming_message(
            professional=mock_professional,
            client_phone="5511999999999",
            content="Mensagem seguinte",
            whatsapp_msg_id="wamid.followup",
        )

        service.repository.create_conversation.assert_not_called()

    # -----------------------------------------------------------------------
    # 4. Inbound message persisted
    # -----------------------------------------------------------------------

    async def test_process_incoming_message_saves_inbound_message(
        self,
        service: WhatsAppService,
        mock_professional: MagicMock,
        mock_conversation: MagicMock,
    ) -> None:
        """
        create_message must be called with direction='inbound' and
        sender_type='client' to record the client's message, regardless of
        what happens in the AI reply step.
        """
        service.repository.find_message_by_whatsapp_id.return_value = None
        service.repository.find_active_conversation_by_phone.return_value = mock_conversation
        service.ai.complete_with_history.return_value = "Resposta"
        service.repository.get_messages_for_conversation.return_value = []

        await service.process_incoming_message(
            professional=mock_professional,
            client_phone="5511999999999",
            content="Quero agendar",
            whatsapp_msg_id="wamid.inbound_save",
        )

        service.repository.create_message.assert_any_call(
            conversation_id=mock_conversation.id,
            direction="inbound",
            sender_type="client",
            content="Quero agendar",
            whatsapp_msg_id="wamid.inbound_save",
        )

    # -----------------------------------------------------------------------
    # 5. AI mode — calls AI and saves outbound reply
    # -----------------------------------------------------------------------

    async def test_process_incoming_message_ai_mode_calls_ai_and_saves_reply(
        self,
        service: WhatsAppService,
        mock_professional: MagicMock,
        mock_conversation: MagicMock,
    ) -> None:
        """
        In AI mode (conversation.mode == 'ai'):
        - ai.complete_with_history must be called with the conversation history.
        - The AI response must be persisted as an outbound message
          with direction='outbound' and sender_type='ai'.
        """
        mock_conversation.mode = "ai"
        service.repository.find_message_by_whatsapp_id.return_value = None
        service.repository.find_active_conversation_by_phone.return_value = mock_conversation
        service.repository.get_messages_for_conversation.return_value = []
        service.ai.complete_with_history.return_value = "Tenho horários na terça!"

        await service.process_incoming_message(
            professional=mock_professional,
            client_phone="5511999999999",
            content="Tem horário disponível?",
            whatsapp_msg_id="wamid.ai_mode",
        )

        service.ai.complete_with_history.assert_called_once()

        service.repository.create_message.assert_any_call(
            conversation_id=mock_conversation.id,
            direction="outbound",
            sender_type="ai",
            content="Tenho horários na terça!",
        )

    # -----------------------------------------------------------------------
    # 6. Handoff mode — AI must NOT be called
    # -----------------------------------------------------------------------

    async def test_process_incoming_message_handoff_mode_does_not_call_ai(
        self,
        service: WhatsAppService,
        mock_professional: MagicMock,
        mock_conversation: MagicMock,
    ) -> None:
        """
        When conversation.mode == 'handoff', the professional is handling the
        conversation manually. The AI must NOT be called — an automated reply
        would contradict the professional's active engagement.
        """
        mock_conversation.mode = "handoff"
        service.repository.find_message_by_whatsapp_id.return_value = None
        service.repository.find_active_conversation_by_phone.return_value = mock_conversation

        await service.process_incoming_message(
            professional=mock_professional,
            client_phone="5511999999999",
            content="Olá, voltei",
            whatsapp_msg_id="wamid.handoff_mode",
        )

        service.ai.complete_with_history.assert_not_called()

    # -----------------------------------------------------------------------
    # 7. AI failure — graceful degradation
    # -----------------------------------------------------------------------

    async def test_process_incoming_message_graceful_degradation_on_ai_failure(
        self,
        service: WhatsAppService,
        mock_professional: MagicMock,
        mock_conversation: MagicMock,
    ) -> None:
        """
        If ai.complete_with_history raises ExternalServiceError, the service
        must NOT propagate the exception to the caller.

        The inbound message is already saved at this point; failing the entire
        request would mean the inbound message is lost (rollback). Instead:
        - Catch the error silently (log it in the real implementation).
        - Return normally without an AI reply.

        This is the same graceful degradation pattern used in ReportsService.
        """
        mock_conversation.mode = "ai"
        service.repository.find_message_by_whatsapp_id.return_value = None
        service.repository.find_active_conversation_by_phone.return_value = mock_conversation
        service.repository.get_messages_for_conversation.return_value = []
        service.ai.complete_with_history.side_effect = ExternalServiceError(
            message="Anthropic API unavailable",
            service_name="ai",
        )

        # Must not raise — graceful degradation
        await service.process_incoming_message(
            professional=mock_professional,
            client_phone="5511999999999",
            content="Mensagem com IA falhando",
            whatsapp_msg_id="wamid.ai_failure",
        )


# ===========================================================================
# TestHandoffToProfessional
# ===========================================================================


class TestHandoffToProfessional:
    # -----------------------------------------------------------------------
    # 8. Successful handoff — update_conversation called with correct data
    # -----------------------------------------------------------------------

    async def test_handoff_to_professional_updates_mode(
        self,
        service: WhatsAppService,
        mock_conversation: MagicMock,
    ) -> None:
        """
        handoff_to_professional() must call update_conversation with
        mode='handoff' and status='waiting_professional'.

        The returned value is whatever update_conversation returns (mocked here)
        — the test is focused on the mutation call, not the return value.
        """
        service.repository.get_conversation_by_id.return_value = mock_conversation
        service.repository.update_conversation.return_value = mock_conversation

        await service.handoff_to_professional(mock_conversation.id)

        service.repository.update_conversation.assert_called_once_with(
            mock_conversation,
            {"mode": "handoff", "status": "waiting_professional"},
        )

    # -----------------------------------------------------------------------
    # 9. Conversation not found → NotFoundError
    # -----------------------------------------------------------------------

    async def test_handoff_to_professional_raises_not_found(
        self,
        service: WhatsAppService,
    ) -> None:
        """
        When get_conversation_by_id returns None (UUID unknown or belongs to
        another tenant), handoff_to_professional must raise NotFoundError.

        RLS makes cross-tenant UUIDs indistinguishable from missing UUIDs —
        both return None — so the error message does not leak tenant information.
        """
        service.repository.get_conversation_by_id.return_value = None

        with pytest.raises(NotFoundError):
            await service.handoff_to_professional(uuid4())


# ===========================================================================
# TestListConversations
# ===========================================================================


class TestListConversations:
    # -----------------------------------------------------------------------
    # 10. Delegates to repository
    # -----------------------------------------------------------------------

    async def test_list_conversations_delegates_to_repository(
        self,
        service: WhatsAppService,
    ) -> None:
        """
        list_conversations() is a thin wrapper — it must call
        repository.list_conversations(status=status_filter) and return
        the result unchanged.
        """
        service.repository.list_conversations.return_value = []

        result = await service.list_conversations()

        service.repository.list_conversations.assert_called_once_with(status=None)
        assert result == []

    async def test_list_conversations_passes_status_filter_to_repository(
        self,
        service: WhatsAppService,
    ) -> None:
        """Status filter is forwarded as-is to the repository."""
        service.repository.list_conversations.return_value = []

        await service.list_conversations(status_filter="active")

        service.repository.list_conversations.assert_called_once_with(status="active")


# ===========================================================================
# TestGetConversationDetail
# ===========================================================================


class TestGetConversationDetail:
    # -----------------------------------------------------------------------
    # 11. Returns (conversation, messages) tuple
    # -----------------------------------------------------------------------

    async def test_get_conversation_detail_returns_tuple(
        self,
        service: WhatsAppService,
        mock_conversation: MagicMock,
    ) -> None:
        """
        get_conversation_detail() must return a tuple of
        (WhatsAppConversation, list[WhatsAppMessage]).

        The caller (router) uses this to build ConversationWithMessagesResponse
        in a single service call — keeping the controller thin.
        """
        mock_messages = [MagicMock(), MagicMock()]
        service.repository.get_conversation_by_id.return_value = mock_conversation
        service.repository.get_messages_for_conversation.return_value = mock_messages

        result = await service.get_conversation_detail(mock_conversation.id)

        assert result == (mock_conversation, mock_messages)

    # -----------------------------------------------------------------------
    # 12. Unknown conversation → NotFoundError
    # -----------------------------------------------------------------------

    async def test_get_conversation_detail_raises_not_found_for_unknown(
        self,
        service: WhatsAppService,
    ) -> None:
        """
        get_conversation_detail() must raise NotFoundError when the conversation
        does not exist (or is from another tenant — RLS makes them equivalent).
        """
        service.repository.get_conversation_by_id.return_value = None

        with pytest.raises(NotFoundError):
            await service.get_conversation_detail(uuid4())


# ===========================================================================
# Tests for handle_inbound_message (ADR-028)
# ===========================================================================


class TestHandleInboundMessage:
    @pytest.fixture
    def service_with_mocks(self) -> WhatsAppService:
        mock_db = AsyncMock()
        svc = WhatsAppService(mock_db)
        svc.repository = AsyncMock()
        svc.provider_message_repo = AsyncMock()
        svc.ai = AsyncMock()
        return svc

    async def test_skips_processing_when_already_processed(
        self, service_with_mocks: WhatsAppService
    ) -> None:
        """Se provider_message_id já existe, retorna sem processar."""
        service_with_mocks.provider_message_repo.exists = AsyncMock(return_value=True)

        inbound = InboundMessage(
            professional_id=uuid4(),
            from_phone="+5511999999999",
            body="oi",
            provider_message_id="SM_DUP",
            received_at=datetime.now(UTC),
        )
        await service_with_mocks.handle_inbound_message(inbound)

        # Não deve chamar create no provider_message_repo
        service_with_mocks.provider_message_repo.create.assert_not_awaited()

    async def test_registers_message_in_idempotency_log(
        self, service_with_mocks: WhatsAppService
    ) -> None:
        """Mensagem nova deve ser registrada em WhatsAppProviderMessage."""
        from professionals.models import Professional

        service_with_mocks.provider_message_repo.exists = AsyncMock(return_value=False)
        service_with_mocks.provider_message_repo.create = AsyncMock()

        mock_prof = MagicMock(spec=Professional)
        mock_prof.id = uuid4()
        mock_prof.full_name = "Dr. Ana"
        mock_prof.specialty = "Psicologia"
        mock_prof.session_duration = 50
        mock_prof.session_price = None
        mock_prof.whatsapp_access_token = None
        mock_prof.whatsapp_phone_id = None

        with patch("whatsapp.service.ProfessionalsRepository") as MockRepo:
            mock_repo_instance = AsyncMock()
            mock_repo_instance.find_by_id = AsyncMock(return_value=mock_prof)
            MockRepo.return_value = mock_repo_instance

            # Mock conversation flow
            service_with_mocks.repository.find_message_by_whatsapp_id = AsyncMock(
                return_value=None
            )
            service_with_mocks.repository.find_active_conversation_by_phone = AsyncMock(
                return_value=None
            )
            mock_conv = MagicMock()
            mock_conv.id = uuid4()
            mock_conv.mode = "handoff"  # handoff → não chama AI
            service_with_mocks.repository.create_conversation = AsyncMock(
                return_value=mock_conv
            )
            service_with_mocks.repository.create_message = AsyncMock()
            service_with_mocks.repository.update_conversation = AsyncMock(
                return_value=mock_conv
            )

            inbound = InboundMessage(
                professional_id=mock_prof.id,
                from_phone="+5511999999999",
                body="oi",
                provider_message_id="SM_NEW",
                received_at=datetime.now(UTC),
            )
            await service_with_mocks.handle_inbound_message(inbound)

        service_with_mocks.provider_message_repo.create.assert_awaited_once()


# ===========================================================================
# Tests for send_appointment_reminder (ADR-028)
# ===========================================================================


class TestSendAppointmentReminder:
    async def test_sends_via_provider(self) -> None:
        """Lembrete deve ser enviado via provider correto (factory resolvido)."""
        mock_db = AsyncMock()
        svc = WhatsAppService(mock_db)
        svc.provider_message_repo = AsyncMock()

        mock_provider = AsyncMock()
        mock_result = MagicMock()
        mock_result.provider_message_id = "SM_REMINDER_01"
        mock_provider.send_text = AsyncMock(return_value=mock_result)

        with patch(
            "whatsapp.service.get_provider_for_professional",
            return_value=mock_provider,
        ) as mock_factory:
            await svc.send_appointment_reminder(
                professional_id=uuid4(),
                to_phone="+5511999999999",
                client_name="João",
                appointment_datetime="sexta, 10/05 às 14h",
            )
            mock_factory.assert_awaited_once()
            mock_provider.send_text.assert_awaited_once()

    async def test_graceful_degradation_on_provider_error(self) -> None:
        """Falha no provider não deve propagar exceção (best-effort)."""
        from whatsapp.providers.base import ProviderError

        mock_db = AsyncMock()
        svc = WhatsAppService(mock_db)

        mock_provider = AsyncMock()
        mock_provider.send_text = AsyncMock(
            side_effect=ProviderError(provider="twilio", message="timeout")
        )

        with patch(
            "whatsapp.service.get_provider_for_professional",
            return_value=mock_provider,
        ):
            # Não deve levantar exceção
            await svc.send_appointment_reminder(
                professional_id=uuid4(),
                to_phone="+5511999999999",
                client_name="Ana",
                appointment_datetime="segunda, 12/05 às 10h",
            )
