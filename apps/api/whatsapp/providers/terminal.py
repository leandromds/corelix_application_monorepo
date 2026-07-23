"""
TerminalProvider — provider de desenvolvimento para WhatsApp (ADR-028).

Imprime mensagens no stdout/stderr em vez de enviar via API real.
Permite:
  - Desenvolvimento sem credenciais WhatsApp
  - Testes E2E reproduzíveis (sem mocks de HTTP)
  - Demos comerciais ao vivo

GUARD DE PRODUÇÃO: __init__ levanta RuntimeError se settings.is_production=True.
Nunca deve ser usado em produção — risco de dados de clientes reais em stdout.
"""

import uuid
from datetime import UTC, datetime
from uuid import UUID

from core.config import settings
from whatsapp.providers.base import WhatsAppProvider
from whatsapp.schemas import InboundMessage, SendResult, TemplateMessage


class TerminalProvider(WhatsAppProvider):
    """
    Provider de desenvolvimento que escreve mensagens no terminal.

    Levanta RuntimeError se instanciado em ambiente de produção.
    Não faz nenhuma chamada de rede — seguro para dev/test/CI.
    """

    def __init__(self) -> None:
        if settings.is_production:
            raise RuntimeError(
                "TerminalProvider não pode ser usado em produção. "
                "Configure um provider real (Meta ou Twilio Shared)."
            )

    async def send_text(
        self,
        *,
        professional_id: UUID,
        to: str,
        body: str,
    ) -> SendResult:
        """Imprime mensagem de texto no stdout e retorna SendResult."""
        msg_id = f"terminal-{uuid.uuid4()}"
        print(f"[TerminalProvider → {to}] {body}")
        return SendResult(provider_message_id=msg_id, status="sent")

    async def send_template(
        self,
        *,
        professional_id: UUID,
        to: str,
        template: TemplateMessage,
    ) -> SendResult:
        """Imprime template no stdout com nome, idioma e parâmetros."""
        msg_id = f"terminal-tpl-{uuid.uuid4()}"
        params_str = ", ".join(f"{k}={v}" for k, v in template.params.items())
        print(
            f"[TerminalProvider TEMPLATE → {to}] "
            f"name={template.name} lang={template.language_code} params={{{params_str}}}"
        )
        return SendResult(provider_message_id=msg_id, status="sent")

    async def parse_webhook(
        self,
        *,
        raw_payload: dict,
        signature_header: str | None,
    ) -> InboundMessage | None:
        """
        Terminal não recebe webhooks reais.

        Aceita payloads no formato interno do terminal_chat CLI:
        {"from_phone": "+55...", "body": "...", "professional_id": "uuid", "message_id": "..."}
        Retorna None para payloads não reconhecidos (ignora silenciosamente).
        """
        if not raw_payload.get("from_phone"):
            return None
        try:
            return InboundMessage(
                professional_id=UUID(raw_payload["professional_id"]),
                from_phone=raw_payload["from_phone"],
                body=raw_payload["body"],
                provider_message_id=raw_payload.get("message_id", f"terminal-{uuid.uuid4()}"),
                received_at=datetime.now(UTC),
                provider_type="terminal",
            )
        except (KeyError, ValueError):
            return None

    async def verify_webhook_challenge(
        self,
        *,
        params: dict,
    ) -> str | None:
        """Terminal não usa webhook challenge — retorna sempre None."""
        return None
