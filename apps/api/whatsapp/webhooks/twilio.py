"""
Webhook endpoint para Twilio WhatsApp (ADR-028).

POST /webhooks/whatsapp/twilio — recebe mensagens entrantes com HMAC-SHA1

Usa TwilioSharedAccountProvider.parse_webhook() para validação e roteamento.
Background task cria sessão própria (ADR: BackgroundTasks + sessão própria).
"""

import logging

from fastapi import APIRouter, BackgroundTasks, Request, Response, status

from core.database import async_session_maker, set_tenant_context
from whatsapp.providers.base import InvalidSignatureError

logger = logging.getLogger(__name__)

router = APIRouter()


async def _process_twilio_inbound(
    raw_payload: dict,
    signature_header: str,
) -> None:
    """Processa mensagem Twilio em background — sessão própria."""
    async with async_session_maker() as session:
        try:
            from whatsapp.providers.twilio_shared import TwilioSharedAccountProvider
            from whatsapp.service import WhatsAppService

            provider = TwilioSharedAccountProvider(session)
            inbound = await provider.parse_webhook(
                raw_payload=raw_payload,
                signature_header=signature_header,
            )
            if inbound is None:
                return

            await set_tenant_context(session, inbound.professional_id)
            service = WhatsAppService(session)
            await service.handle_inbound_message(inbound)
            await session.commit()
        except InvalidSignatureError:
            logger.warning("Twilio webhook background: invalid signature")
        except Exception as exc:  # noqa: BLE001
            await session.rollback()
            logger.error("Twilio webhook background processing failed: %s", exc, exc_info=True)


@router.post("", status_code=status.HTTP_200_OK)
async def twilio_webhook_receive(
    request: Request,
    background_tasks: BackgroundTasks,
) -> Response:
    """
    Recebe mensagens Twilio WhatsApp (POST).

    Twilio envia form-encoded (application/x-www-form-urlencoded).
    Responde 200 imediatamente — Twilio tem timeout de ~15s e reenvia se não receber 200.
    Processamento real ocorre em background task.
    """
    form = await request.form()
    payload = dict(form)
    signature = request.headers.get("X-Twilio-Signature", "")

    background_tasks.add_task(
        _process_twilio_inbound,
        raw_payload=payload,
        signature_header=signature,
    )
    return Response(status_code=status.HTTP_200_OK)
