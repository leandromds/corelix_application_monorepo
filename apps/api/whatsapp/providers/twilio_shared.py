"""
TwilioSharedAccountProvider — provider para piloto WhatsApp (ADR-028).

Corelix opera com UM número WhatsApp (TWILIO_SHARED_PHONE_NUMBER) que é
compartilhado por N profissionais. O routing resolve de qual profissional
é cada conversa antes de passar para o service layer.

Roteamento (em ordem de prioridade):
1. Binding existente: phone_number → professional_id (conversa já estabelecida)
2. Tag no início da mensagem: DRANA-{tag} → cria binding com bound_via='tag'
3. Sem binding e sem tag: envia mensagem de ajuda e retorna None

Validação de assinatura: HMAC-SHA1 via twilio.request_validator.RequestValidator.
Desabilitar apenas para testes (settings.TWILIO_WEBHOOK_VALIDATION=False).
"""

import re
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

import httpx
from twilio.request_validator import RequestValidator

from core.config import settings
from whatsapp.providers.base import InvalidSignatureError, ProviderError, WhatsAppProvider
from whatsapp.repository import PhoneBindingRepository, WhatsAppAccountRepository
from whatsapp.schemas import InboundMessage, SendResult, TemplateMessage

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

# Pattern para extração de tag da primeira mensagem
# Aceita DRANA-XXXXXX no início do corpo (case-insensitive)
_TAG_PATTERN = re.compile(r"^DRANA-([A-Za-z0-9]+)", re.IGNORECASE)

# URL base para Twilio Messaging REST API
_TWILIO_API_BASE = "https://api.twilio.com/2010-04-01"


def _extract_tag(body: str) -> str | None:
    """Extrai o routing tag do início do corpo da mensagem, se presente."""
    match = _TAG_PATTERN.match(body.strip())
    return match.group(1) if match else None


class TwilioSharedAccountProvider(WhatsAppProvider):
    """
    Provider WhatsApp usando número compartilhado Corelix via Twilio (piloto).

    session é necessário para resolver bindings e contas pelo banco.
    Injetar a sessão no __init__ permite usar o provider como stateless
    dentro do ciclo de vida de uma request/background task.
    """

    def __init__(self, session: "AsyncSession") -> None:
        self._session = session
        self._validator = RequestValidator(settings.TWILIO_AUTH_TOKEN or "")

    def _verify_signature(self, *, url: str, params: dict, signature: str) -> None:
        """
        Valida assinatura HMAC-SHA1 do Twilio.

        Levanta InvalidSignatureError se inválida ou se validação estiver ativa
        e a assinatura estiver faltando.
        """
        if not settings.TWILIO_WEBHOOK_VALIDATION:
            return
        if not signature:
            raise InvalidSignatureError(provider="twilio")
        if not self._validator.validate(url, params, signature):
            raise InvalidSignatureError(provider="twilio")

    async def send_text(
        self,
        *,
        professional_id: UUID,
        to: str,
        body: str,
    ) -> SendResult:
        """
        Envia texto via Twilio Messaging Service REST API.

        Usa TWILIO_MESSAGING_SERVICE_SID como remetente para aproveitar
        o pool de números e Sender ID da Corelix.
        """
        if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
            raise ProviderError(
                provider="twilio",
                message="Credenciais Twilio não configuradas (TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN)",
            )
        url = f"{_TWILIO_API_BASE}/Accounts/{settings.TWILIO_ACCOUNT_SID}/Messages.json"
        payload = {
            "To": f"whatsapp:{to}",
            "From": f"whatsapp:{settings.TWILIO_SHARED_PHONE_NUMBER}",
            "Body": body,
        }
        if settings.TWILIO_MESSAGING_SERVICE_SID:
            payload["MessagingServiceSid"] = settings.TWILIO_MESSAGING_SERVICE_SID

        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(
                    url,
                    data=payload,
                    auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
                    timeout=10.0,
                )
                resp.raise_for_status()
                data = resp.json()
                return SendResult(
                    provider_message_id=data.get("sid", f"twilio-{uuid.uuid4()}"),
                    status="queued",
                )
            except httpx.HTTPStatusError as exc:
                raise ProviderError(
                    provider="twilio",
                    message=f"Erro HTTP {exc.response.status_code}: {exc.response.text}",
                    status_code=exc.response.status_code,
                ) from exc
            except httpx.HTTPError as exc:
                raise ProviderError(
                    provider="twilio",
                    message=f"Erro de conexão: {exc}",
                ) from exc

    async def send_template(
        self,
        *,
        professional_id: UUID,
        to: str,
        template: TemplateMessage,
    ) -> SendResult:
        """
        Envia template Twilio Content Template (Content SID como nome).

        No modo Twilio Shared, o template.name é tratado como o Content SID
        registrado na WABA Corelix.
        """
        body_parts = [f"Template: {template.name}"]
        if template.params:
            for k, v in template.params.items():
                body_parts.append(f"{k}={v}")
        return await self.send_text(
            professional_id=professional_id,
            to=to,
            body=" | ".join(body_parts),
        )

    async def parse_webhook(
        self,
        *,
        raw_payload: dict,
        signature_header: str | None,
    ) -> InboundMessage | None:
        """
        Processa webhook Twilio, valida assinatura e resolve professional_id.

        Fluxo:
        1. Valida assinatura HMAC-SHA1
        2. Extrai from_phone e body do payload Twilio
        3. Tenta encontrar binding existente para from_phone
        4. Se não há binding, tenta extrair tag da mensagem
        5. Se há tag válida, cria binding e retorna InboundMessage
        6. Se não há tag, envia mensagem de ajuda e retorna None
        """
        # 1. Validar assinatura
        webhook_url = settings.TWILIO_SHARED_PHONE_NUMBER or ""
        self._verify_signature(
            url=webhook_url,
            params=raw_payload,
            signature=signature_header or "",
        )

        # 2. Extrair campos do payload Twilio
        from_raw = raw_payload.get("From", "")
        from_phone = from_raw.replace("whatsapp:", "").strip()
        body = raw_payload.get("Body", "").strip()
        message_sid = raw_payload.get("MessageSid", f"twilio-{uuid.uuid4()}")

        if not from_phone or not body:
            return None

        # 3. Tentar binding existente
        binding_repo = PhoneBindingRepository(self._session)
        account_repo = WhatsAppAccountRepository(self._session)

        binding = await binding_repo.find_by_phone(from_phone)

        if binding is not None:
            professional_id = binding.professional_id
        else:
            # 4. Sem binding — tentar resolver pela tag na mensagem
            tag = _extract_tag(body)
            if tag is None:
                # Sem tag e sem binding — enviar ajuda (best-effort, não bloqueia)
                await self._send_help_message(from_phone)
                return None

            # Resolver profissional pelo routing tag
            account = await account_repo.find_by_routing_tag(tag)
            if account is None:
                await self._send_help_message(from_phone)
                return None

            # 5. Criar binding para futuras mensagens deste número
            binding = await binding_repo.create(
                professional_id=account.professional_id,
                phone_number=from_phone,
                bound_via="tag",
            )
            professional_id = binding.professional_id

        return InboundMessage(
            professional_id=professional_id,
            from_phone=from_phone,
            body=body,
            provider_message_id=message_sid,
            received_at=datetime.now(UTC),
            provider_type="twilio_shared",
        )

    async def verify_webhook_challenge(
        self,
        *,
        params: dict,
    ) -> str | None:
        """Twilio não usa webhook challenge — retorna None."""
        return None

    async def _send_help_message(self, to_phone: str) -> None:
        """
        Envia mensagem de ajuda para números sem binding.

        Best-effort: erros são silenciados para não bloquear o webhook.
        """
        if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
            return
        try:
            await self.send_text(
                professional_id=uuid.UUID(int=0),  # sentinel — não é um tenant real
                to=to_phone,
                body=(
                    "Olá! Para falar com seu profissional Corelix, "
                    "inicie a conversa com o link enviado por ele."
                ),
            )
        except Exception:  # noqa: BLE001
            pass
