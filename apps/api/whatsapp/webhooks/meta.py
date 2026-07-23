"""
Webhook endpoints para Meta Cloud API WhatsApp (ADR-028).

GET  /webhooks/whatsapp/meta — verificação de webhook (hub.challenge)
POST /webhooks/whatsapp/meta — recebe mensagens entrantes com HMAC-SHA256

Usa MetaCloudProvider.parse_webhook() para validação e normalização.
Delega para WhatsAppService.handle_inbound_message() em background task.
Background task cria sessão própria (ADR: BackgroundTasks + sessão própria).
"""

import json
import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request, Response, status
from fastapi.responses import PlainTextResponse

from core.database import async_session_maker, set_tenant_context
from whatsapp.providers.base import InvalidSignatureError

logger = logging.getLogger(__name__)

router = APIRouter()


async def _process_meta_inbound(
    raw_payload: dict,
    signature_header: str,
) -> None:
    """
    Processa mensagem Meta em background — sessão própria, isolada do request.

    Valida assinatura novamente (re-parsed) e chama handle_inbound_message.
    Sessão própria garante que SET LOCAL tenant persista durante o processamento.
    """
    async with async_session_maker() as session:
        try:
            from whatsapp.providers.meta import MetaCloudProvider
            from whatsapp.service import WhatsAppService

            provider = MetaCloudProvider(session)
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
            logger.warning("Meta webhook background: invalid signature (re-check)")
        except Exception as exc:  # noqa: BLE001
            await session.rollback()
            logger.error("Meta webhook background processing failed: %s", exc, exc_info=True)


@router.get("", response_class=PlainTextResponse)
async def meta_webhook_challenge(
    hub_mode: str = Query(alias="hub.mode", default=""),
    hub_challenge: str = Query(alias="hub.challenge", default=""),
    hub_verify_token: str = Query(alias="hub.verify_token", default=""),
) -> str:
    """
    Verificação de webhook Meta (GET).

    Meta envia GET com hub.mode='subscribe' quando o URL é registrado.
    Responder com hub.challenge confirma ownership do endpoint.
    """
    from whatsapp.providers.meta import MetaCloudProvider

    provider = MetaCloudProvider(None)  # type: ignore[arg-type]
    challenge = await provider.verify_webhook_challenge(
        params={
            "hub.mode": hub_mode,
            "hub.verify_token": hub_verify_token,
            "hub.challenge": hub_challenge,
        }
    )
    if challenge is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token de verificação inválido",
        )
    return challenge


@router.post("", status_code=status.HTTP_200_OK)
async def meta_webhook_receive(
    request: Request,
    background_tasks: BackgroundTasks,
) -> Response:
    """
    Recebe mensagens Meta WhatsApp (POST).

    Responde 200 imediatamente — processamento real ocorre em background task.
    Sem background task ativo a assinatura é validada pelo provider no background.
    """
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")

    try:
        payload = json.loads(body)
    except (ValueError, TypeError):
        return Response(status_code=status.HTTP_200_OK)

    background_tasks.add_task(
        _process_meta_inbound,
        raw_payload=payload,
        signature_header=signature,
    )
    return Response(status_code=status.HTTP_200_OK)
