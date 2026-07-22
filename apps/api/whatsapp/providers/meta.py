"""
MetaCloudProvider — provider WhatsApp Cloud API para número próprio (ADR-028).

Estado: disponível após aprovação como Tech Provider Meta.
Cada profissional tem seu próprio número WhatsApp Business.
Credenciais armazenadas em whatsapp_accounts.access_token_encrypted.

Webhook HMAC usa META_APP_SECRET (ou fallback para WHATSAPP_APP_SECRET legado).
Webhook challenge usa META_WEBHOOK_VERIFY_TOKEN (ou WHATSAPP_VERIFY_TOKEN legado).
"""

import hashlib
import hmac as _hmac
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

import httpx

from core.config import settings
from whatsapp.providers.base import InvalidSignatureError, ProviderError, WhatsAppProvider
from whatsapp.schemas import InboundMessage, SendResult, TemplateMessage

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

_META_API_BASE = "https://graph.facebook.com/v18.0"


def _get_app_secret() -> str:
    """Retorna META_APP_SECRET se configurado, senão WHATSAPP_APP_SECRET legado."""
    return settings.META_APP_SECRET or settings.WHATSAPP_APP_SECRET


def _get_verify_token() -> str:
    """Retorna META_WEBHOOK_VERIFY_TOKEN se configurado, senão WHATSAPP_VERIFY_TOKEN legado."""
    return settings.META_WEBHOOK_VERIFY_TOKEN or settings.WHATSAPP_VERIFY_TOKEN


class MetaCloudProvider(WhatsAppProvider):
    """
    Provider Meta Cloud API — número próprio por profissional.

    Requer que o profissional tenha um WhatsAppAccount ativo com
    provider_type='meta' e access_token_encrypted válido.

    session é injetado para buscar credenciais por professional_id.
    """

    def __init__(self, session: "AsyncSession") -> None:
        self._session = session

    async def _get_access_token(self, professional_id: UUID) -> str:
        """
        Busca e descriptografa o access token Meta do profissional.

        Raises:
            ProviderError: Se não há conta Meta ativa ou token inválido.
        """
        from whatsapp.providers.crypto import decrypt_credentials
        from whatsapp.repository import WhatsAppAccountRepository

        repo = WhatsAppAccountRepository(self._session)
        account = await repo.find_by_professional_id(professional_id)
        if account is None or account.provider_type != "meta":
            raise ProviderError(
                provider="meta",
                message="Profissional não tem conta Meta WhatsApp ativa",
            )
        return decrypt_credentials(account.access_token_encrypted)

    async def _get_phone_number_id(self, professional_id: UUID) -> str:
        """Busca o phone_number_id Meta do profissional."""
        from whatsapp.repository import WhatsAppAccountRepository

        repo = WhatsAppAccountRepository(self._session)
        account = await repo.find_by_professional_id(professional_id)
        if account is None:
            raise ProviderError(
                provider="meta",
                message="Profissional não tem conta Meta WhatsApp ativa",
            )
        return str(account.phone_number_id)

    async def send_text(
        self,
        *,
        professional_id: UUID,
        to: str,
        body: str,
    ) -> SendResult:
        """Envia texto via Meta Cloud API usando credenciais do profissional."""
        access_token = await self._get_access_token(professional_id)
        phone_number_id = await self._get_phone_number_id(professional_id)

        url = f"{_META_API_BASE}/{phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"preview_url": False, "body": body},
        }

        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(
                    url,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                    },
                    timeout=10.0,
                )
                resp.raise_for_status()
                data = resp.json()
                messages = data.get("messages", [])
                msg_id = messages[0].get("id") if messages else f"meta-{uuid.uuid4()}"
                return SendResult(provider_message_id=msg_id, status="sent")
            except httpx.HTTPStatusError as exc:
                raise ProviderError(
                    provider="meta",
                    message=f"Erro HTTP {exc.response.status_code}: {exc.response.text}",
                    status_code=exc.response.status_code,
                ) from exc
            except httpx.HTTPError as exc:
                raise ProviderError(
                    provider="meta",
                    message=f"Erro de conexão: {exc}",
                ) from exc

    async def send_template(
        self,
        *,
        professional_id: UUID,
        to: str,
        template: TemplateMessage,
    ) -> SendResult:
        """Envia template aprovado via Meta Cloud API."""
        access_token = await self._get_access_token(professional_id)
        phone_number_id = await self._get_phone_number_id(professional_id)

        components = []
        if template.params:
            components = [
                {
                    "type": "body",
                    "parameters": [{"type": "text", "text": v} for v in template.params.values()],
                }
            ]

        url = f"{_META_API_BASE}/{phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "template",
            "template": {
                "name": template.name,
                "language": {"code": template.language_code},
                "components": components,
            },
        }

        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(
                    url,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                    },
                    timeout=10.0,
                )
                resp.raise_for_status()
                data = resp.json()
                messages = data.get("messages", [])
                msg_id = messages[0].get("id") if messages else f"meta-tpl-{uuid.uuid4()}"
                return SendResult(provider_message_id=msg_id, status="sent")
            except httpx.HTTPStatusError as exc:
                raise ProviderError(
                    provider="meta",
                    message=f"Erro de template HTTP {exc.response.status_code}: {exc.response.text}",
                    status_code=exc.response.status_code,
                ) from exc
            except httpx.HTTPError as exc:
                raise ProviderError(
                    provider="meta",
                    message=f"Erro de conexão ao enviar template: {exc}",
                ) from exc

    async def parse_webhook(
        self,
        *,
        raw_payload: dict,
        signature_header: str | None,
    ) -> InboundMessage | None:
        """
        Processa webhook Meta, valida HMAC-SHA256 e extrai mensagem.

        Retorna None para payloads não-texto ou status updates.
        Levanta InvalidSignatureError se assinatura inválida.
        """
        import json

        body_bytes = json.dumps(raw_payload, separators=(",", ":")).encode()
        self._verify_hmac(body_bytes=body_bytes, signature_header=signature_header or "")

        # Extrair mensagens de texto do payload Meta
        for entry in raw_payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                messages = value.get("messages", [])
                metadata = value.get("metadata", {})
                phone_number_id = metadata.get("phone_number_id", "")

                for msg in messages:
                    if msg.get("type") != "text":
                        continue
                    from_phone = msg.get("from", "")
                    if not from_phone.startswith("+"):
                        from_phone = f"+{from_phone}"
                    text_body = (msg.get("text") or {}).get("body", "")
                    if not text_body:
                        continue

                    # Resolver professional_id pelo phone_number_id
                    professional_id = await self._resolve_professional(phone_number_id)
                    if professional_id is None:
                        continue

                    return InboundMessage(
                        professional_id=professional_id,
                        from_phone=from_phone,
                        body=text_body,
                        provider_message_id=msg.get("id", f"meta-{uuid.uuid4()}"),
                        received_at=datetime.now(UTC),
                        provider_type="meta",
                    )
        return None

    async def verify_webhook_challenge(
        self,
        *,
        params: dict,
    ) -> str | None:
        """
        Responde ao desafio de verificação de webhook Meta.

        Retorna hub.challenge se hub.verify_token coincidir com o configurado.
        Retorna None se o token não coincidir (chamador deve responder 403).
        """
        mode = params.get("hub.mode")
        verify_token = params.get("hub.verify_token")
        challenge = params.get("hub.challenge")

        if mode == "subscribe" and verify_token == _get_verify_token():
            return challenge
        return None

    def _verify_hmac(self, *, body_bytes: bytes, signature_header: str) -> None:
        """
        Valida assinatura HMAC-SHA256 do Meta webhook.

        Format: X-Hub-Signature-256: sha256=<hexdigest>
        """
        if not signature_header.startswith("sha256="):
            raise InvalidSignatureError(provider="meta")
        expected = signature_header.removeprefix("sha256=")
        computed = _hmac.new(
            _get_app_secret().encode(),
            body_bytes,
            hashlib.sha256,
        ).hexdigest()
        if not _hmac.compare_digest(computed, expected):
            raise InvalidSignatureError(provider="meta")

    async def _resolve_professional(self, phone_number_id: str) -> UUID | None:
        """Resolve professional_id a partir do phone_number_id Meta."""
        from sqlalchemy import select

        from whatsapp.models import WhatsAppAccount

        result = await self._session.execute(
            select(WhatsAppAccount).where(
                WhatsAppAccount.phone_number_id == phone_number_id,
                WhatsAppAccount.is_active.is_(True),
                WhatsAppAccount.provider_type == "meta",
            )
        )
        account = result.scalar_one_or_none()
        return account.professional_id if account else None
