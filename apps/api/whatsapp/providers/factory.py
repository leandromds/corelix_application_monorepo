"""
Factory de providers WhatsApp (ADR-028).

Lógica de resolução:
1. Se settings.WHATSAPP_FORCE_TERMINAL=True → TerminalProvider (dev/test)
2. Se profissional tem WhatsAppAccount com provider_type='meta' → MetaCloudProvider
3. Caso contrário → TwilioSharedAccountProvider (modo piloto)

O factory nunca levanta exceção — sempre retorna algum provider.
O chamador (service layer) decide se o provider é adequado para a operação.
"""

from typing import TYPE_CHECKING
from uuid import UUID

from core.config import settings
from whatsapp.repository import WhatsAppAccountRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from whatsapp.providers.base import WhatsAppProvider


async def get_provider_for_professional(
    *,
    professional_id: UUID,
    session: "AsyncSession",
) -> "WhatsAppProvider":
    """
    Resolve o provider WhatsApp correto para o profissional dado.

    Args:
        professional_id: UUID do profissional (tenant).
        session: Sessão de banco ativa para consultar WhatsAppAccount.

    Returns:
        Instância do provider adequado: Terminal, Twilio ou Meta.
    """
    from whatsapp.providers.meta import MetaCloudProvider
    from whatsapp.providers.terminal import TerminalProvider
    from whatsapp.providers.twilio_shared import TwilioSharedAccountProvider

    # 1. Override global de ambiente — força terminal (dev/test/CI)
    if settings.WHATSAPP_FORCE_TERMINAL:
        return TerminalProvider()

    # 2. Verificar se profissional tem conta Meta ativa
    repo = WhatsAppAccountRepository(session)
    account = await repo.find_by_professional_id(professional_id)
    if account is not None and account.provider_type == "meta":
        return MetaCloudProvider(session)

    # 3. Default: Twilio Shared (modo piloto)
    return TwilioSharedAccountProvider(session)
