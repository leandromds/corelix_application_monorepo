"""
WhatsApp service — business logic para integração com providers WhatsApp (ADR-028).

Responsabilidades:
- handle_inbound_message: processa InboundMessage normalizada (idempotente via WhatsAppProviderMessage)
- send_appointment_reminder: envia lembrete de consulta via provider correto
- Gestão de conversas: handoff, list, get_detail (mantidos do service anterior)

Design notes:
- handle_inbound_message usa ProviderMessageRepository para idempotência ANTES de processar.
  Garantia: mesmo provider_message_id nunca gera dois replies, independente de retry do provider.
- O service não sabe qual provider foi usado — recebe InboundMessage normalizada.
- process_incoming_message (legado, ainda existe para backward compat com o router existente)
  delega para a lógica da conversa, reutilizando o pattern estabelecido.
- get_provider_for_professional importado no topo (patchável em testes via
  patch("whatsapp.service.get_provider_for_professional", ...)).
- Fernet decryption permanece como método privado para o legado.
"""

import logging
from datetime import UTC, datetime
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from ai.prompts import PROMPTS
from ai.service import AIService
from core.exceptions import ExternalServiceError, NotFoundError
from professionals.models import Professional
from professionals.repository import ProfessionalsRepository
from whatsapp.models import WhatsAppConversation, WhatsAppMessage
from whatsapp.providers.factory import get_provider_for_professional
from whatsapp.repository import (
    ProviderMessageRepository,
    WhatsAppRepository,
)
from whatsapp.schemas import InboundMessage

logger = logging.getLogger(__name__)


class WhatsAppService:
    """Handles WhatsApp business logic: message routing, AI replies, provider integration."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = WhatsAppRepository(session)
        self.provider_message_repo = ProviderMessageRepository(session)
        self.ai = AIService()

    # =========================================================================
    # Provider-agnostic inbound handling (ADR-028)
    # =========================================================================

    async def handle_inbound_message(self, inbound: InboundMessage) -> None:
        """
        Processa uma mensagem entrante normalizada de qualquer provider.

        Passos:
        1. Idempotência: verifica se provider_message_id já foi processado.
           Se sim, retorna silenciosamente (Twilio e Meta têm at-least-once delivery).
        2. Registra a mensagem no log de idempotência (WhatsAppProviderMessage).
        3. Delega para process_incoming_message (conversation + AI + reply).

        O profissional é re-buscado a partir do professional_id da InboundMessage
        para garantir que os dados estejam frescos na sessão atual.

        Args:
            inbound: Mensagem normalizada retornada pelo provider.parse_webhook().
        """
        # 1. Idempotência — never process same message_id twice
        already_processed = await self.provider_message_repo.exists(
            professional_id=inbound.professional_id,
            provider_message_id=inbound.provider_message_id,
        )
        if already_processed:
            logger.info(
                "Duplicate provider message ignored (professional=%s, msg_id=%s)",
                inbound.professional_id,
                inbound.provider_message_id,
            )
            return

        # 2. Registrar no log de idempotência
        try:
            await self.provider_message_repo.create(
                professional_id=inbound.professional_id,
                provider_message_id=inbound.provider_message_id,
                direction="inbound",
                from_phone=inbound.from_phone,
                to_phone="corelix",  # número Corelix (shared ou próprio)
                body=inbound.body,
                provider_type=inbound.provider_type,
            )
        except Exception as exc:  # noqa: BLE001
            # Se INSERT falhar por race condition de idempotência (UNIQUE violation),
            # outro worker já processou — ignorar silenciosamente.
            logger.warning("Provider message insert failed (likely race/duplicate): %s", exc)
            return

        # 3. Buscar profissional e delegar para conversation flow
        prof_repo = ProfessionalsRepository(self.session)
        professional = await prof_repo.find_by_id(inbound.professional_id)
        if professional is None:
            logger.warning(
                "Professional %s not found — inbound message logged but not processed",
                inbound.professional_id,
            )
            return

        await self.process_incoming_message(
            professional=professional,
            client_phone=inbound.from_phone,
            content=inbound.body,
            whatsapp_msg_id=inbound.provider_message_id,
        )

    # =========================================================================
    # Provider-based outbound (ADR-028)
    # =========================================================================

    async def send_appointment_reminder(
        self,
        *,
        professional_id: UUID,
        to_phone: str,
        client_name: str,
        appointment_datetime: str,
    ) -> None:
        """
        Envia lembrete de consulta via provider correto do profissional.

        Resolve o provider via factory — transparente para o caller.
        Erros de provider são logados mas não relançados (best-effort).

        Args:
            professional_id: UUID do profissional (tenant).
            to_phone: Número do cliente em E.164.
            client_name: Nome do cliente para personalização.
            appointment_datetime: Data/hora formatada (ex: 'sexta, 10/05 às 14h').
        """
        body = (
            f"Olá, {client_name}! Lembrando que sua consulta está marcada para "
            f"{appointment_datetime}. Qualquer dúvida, é só responder aqui. 😊"
        )

        try:
            provider = await get_provider_for_professional(
                professional_id=professional_id,
                session=self.session,
            )
            result = await provider.send_text(
                professional_id=professional_id,
                to=to_phone,
                body=body,
            )
            logger.info(
                "Appointment reminder sent (professional=%s, to=%s, msg_id=%s)",
                professional_id,
                to_phone,
                result.provider_message_id,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Failed to send appointment reminder (professional=%s, to=%s): %s",
                professional_id,
                to_phone,
                exc,
            )

    # =========================================================================
    # Legacy: Incoming message processing (Meta Cloud API direto)
    # =========================================================================

    async def process_incoming_message(
        self,
        professional: Professional,
        client_phone: str,
        content: str,
        whatsapp_msg_id: str,
    ) -> None:
        """
        Processa mensagem inbound — mantido para compatibilidade.

        Usado pelo handle_inbound_message (novo) e pelo webhook router legado.
        Idempotência a este nível não é necessária quando chamado via
        handle_inbound_message (que já verifica em WhatsAppProviderMessage).
        Quando chamado diretamente (webhook legado), usa whatsapp_msg_id da
        WhatsAppMessage para deduplicação.
        """
        # Idempotency check (legado — via WhatsAppMessage.whatsapp_msg_id)
        existing = await self.repository.find_message_by_whatsapp_id(whatsapp_msg_id)
        if existing is not None:
            logger.info(
                "Duplicate webhook ignored (whatsapp_msg_id=%s already processed)",
                whatsapp_msg_id,
            )
            return

        conversation = await self.repository.find_active_conversation_by_phone(client_phone)
        if conversation is None:
            conversation = await self.repository.create_conversation(professional.id, client_phone)
            logger.info(
                "New conversation created (professional_id=%s, phone=%s, conversation_id=%s)",
                professional.id,
                client_phone,
                conversation.id,
            )

        await self.repository.create_message(
            conversation_id=conversation.id,
            direction="inbound",
            sender_type="client",
            content=content,
            whatsapp_msg_id=whatsapp_msg_id,
        )
        await self.repository.update_conversation(
            conversation, {"last_message_at": datetime.now(UTC)}
        )

        if conversation.mode != "ai":
            logger.debug(
                "Conversation %s is in '%s' mode — skipping AI reply",
                conversation.id,
                conversation.mode,
            )
            return

        recent_messages = await self.repository.get_messages_for_conversation(
            conversation.id, limit=20
        )
        history = [
            {
                "role": "user" if msg.direction == "inbound" else "assistant",
                "content": msg.content,
            }
            for msg in recent_messages
        ]

        try:
            system_prompt = PROMPTS["whatsapp_secretary"].format(
                professional_name=professional.full_name,
                professional_specialty=professional.specialty or "Profissional de saúde",
                session_duration=professional.session_duration,
                session_price=str(professional.session_price or "a consultar"),
            )
            ai_response = await self.ai.complete_with_history(system_prompt, history)
        except ExternalServiceError as exc:
            logger.error("AI service unavailable for conversation %s: %s", conversation.id, exc)
            return

        await self.repository.create_message(
            conversation_id=conversation.id,
            direction="outbound",
            sender_type="ai",
            content=ai_response,
        )

        access_token = self._decrypt_access_token(professional.whatsapp_access_token)
        if not access_token or not professional.whatsapp_phone_id:
            return

        try:
            meta_msg_id = await self.send_message_via_meta(
                phone=client_phone,
                message=ai_response,
                access_token=access_token,
                phone_number_id=professional.whatsapp_phone_id,
            )
            logger.info(
                "AI reply delivered via Meta (meta_msg_id=%s)",
                meta_msg_id,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Meta API delivery failed for conversation %s: %s", conversation.id, exc)

    # =========================================================================
    # Meta Cloud API (legado — mantido para o webhook legado)
    # =========================================================================

    async def send_message_via_meta(
        self,
        phone: str,
        message: str,
        access_token: str,
        phone_number_id: str,
    ) -> str | None:
        """
        Send a text message via the Meta Cloud API (legacy path).

        Used by the legacy process_incoming_message flow. New flows use
        the provider abstraction via send_appointment_reminder.
        """
        url = f"https://graph.facebook.com/v18.0/{phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": phone,
            "type": "text",
            "text": {"preview_url": False, "body": message},
        }
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    url,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                    },
                    timeout=10.0,
                )
                response.raise_for_status()
                data = response.json()
                messages = data.get("messages", [])
                return messages[0].get("id") if messages else None
            except httpx.HTTPStatusError as exc:
                raise ExternalServiceError(
                    message=f"Meta API HTTP error {exc.response.status_code}: {exc.response.text}",
                    service_name="whatsapp",
                ) from exc
            except httpx.HTTPError as exc:
                raise ExternalServiceError(
                    message=f"Meta API connection error: {exc}",
                    service_name="whatsapp",
                ) from exc

    # =========================================================================
    # Token decryption (legado)
    # =========================================================================

    def _decrypt_access_token(self, encrypted_token: str | None) -> str | None:
        """
        Decrypt the Fernet-encrypted WhatsApp access token stored in the database.

        Fails silently and returns None on any error. The caller must handle None
        by skipping Meta API delivery rather than raising.
        """
        if not encrypted_token:
            return None
        try:
            from cryptography.fernet import Fernet

            from core.config import settings

            fernet = Fernet(settings.ENCRYPTION_KEY.encode())
            return fernet.decrypt(encrypted_token.encode()).decode()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to decrypt WhatsApp access token: %s", exc)
            return None

    # =========================================================================
    # Conversation management
    # =========================================================================

    async def handoff_to_professional(self, conversation_id: UUID) -> WhatsAppConversation:
        """
        Switch a conversation from AI mode to professional (handoff) mode.

        Raises:
            NotFoundError: If no conversation with this ID is visible to the
                           current tenant (RLS-filtered lookup returns None).
        """
        conversation = await self.repository.get_conversation_by_id(conversation_id)
        if conversation is None:
            raise NotFoundError("Conversation not found")
        return await self.repository.update_conversation(
            conversation,
            {"mode": "handoff", "status": "waiting_professional"},
        )

    async def list_conversations(
        self, status_filter: str | None = None
    ) -> list[WhatsAppConversation]:
        """List conversations for the current tenant (RLS-filtered)."""
        return await self.repository.list_conversations(status=status_filter)

    async def get_conversation_detail(
        self, conversation_id: UUID
    ) -> tuple[WhatsAppConversation, list[WhatsAppMessage]]:
        """
        Fetch a conversation and its message history in one service call.

        Raises:
            NotFoundError: If the conversation doesn't exist or belongs to
                           another tenant (RLS makes them indistinguishable).
        """
        conversation = await self.repository.get_conversation_by_id(conversation_id)
        if conversation is None:
            raise NotFoundError("Conversation not found")
        messages = await self.repository.get_messages_for_conversation(conversation_id)
        return conversation, messages
