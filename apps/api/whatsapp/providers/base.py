"""
Contrato unificado para providers WhatsApp (ADR-028).

Todos os providers implementam WhatsAppProvider. O service layer
chama apenas a interface — nunca a implementação concreta.
"""

from abc import ABC, abstractmethod
from uuid import UUID

from whatsapp.schemas import InboundMessage, SendResult, TemplateMessage


class ProviderError(Exception):
    """
    Erro originado no provider externo (Twilio, Meta).

    Carrega o nome do provider e contexto adicional para logging.
    Não deve vazar detalhes de implementação para o cliente HTTP.
    """

    def __init__(self, *, provider: str, message: str, status_code: int | None = None) -> None:
        self.provider = provider
        self.status_code = status_code
        super().__init__(f"[{provider}] {message}")


class InvalidSignatureError(Exception):
    """
    Assinatura HMAC inválida no webhook recebido.

    Indica possível request forjado — rejeitar com 400 sem detalhar o motivo.
    """

    def __init__(self, *, provider: str) -> None:
        self.provider = provider
        super().__init__(f"Assinatura inválida do provider {provider}")


class WhatsAppProvider(ABC):
    """
    Interface unificada para envio e recebimento de mensagens WhatsApp.

    Stateless e async. Implementações:
    - TerminalProvider: dev/test/demo, imprime no stdout
    - TwilioSharedAccountProvider: piloto com número compartilhado
    - MetaCloudProvider: produção com número por profissional

    Todas as assinaturas usam kwargs explícitos (*) para legibilidade
    obrigatória nos call-sites.
    """

    @abstractmethod
    async def send_text(
        self,
        *,
        professional_id: UUID,
        to: str,
        body: str,
    ) -> SendResult:
        """
        Envia uma mensagem de texto simples.

        Args:
            professional_id: UUID do profissional remetente (tenant).
            to: Número do destinatário em formato E.164 (ex: +5511999999999).
            body: Corpo da mensagem (máx 4096 chars).

        Returns:
            SendResult com provider_message_id e status.

        Raises:
            ProviderError: Se o provider externo retornar erro.
        """
        ...

    @abstractmethod
    async def send_template(
        self,
        *,
        professional_id: UUID,
        to: str,
        template: TemplateMessage,
    ) -> SendResult:
        """
        Envia uma mensagem de template aprovado.

        Args:
            professional_id: UUID do profissional remetente.
            to: Número do destinatário em formato E.164.
            template: Template aprovado com nome, idioma e parâmetros.

        Returns:
            SendResult com provider_message_id e status.

        Raises:
            ProviderError: Se o template não existir ou o provider rejeitar.
        """
        ...

    @abstractmethod
    async def parse_webhook(
        self,
        *,
        raw_payload: dict,
        signature_header: str | None,
    ) -> InboundMessage | None:
        """
        Valida assinatura, extrai e normaliza mensagem do webhook.

        Args:
            raw_payload: Payload bruto do webhook (já parseado como dict).
            signature_header: Valor do header de assinatura (X-Twilio-Signature
                              ou X-Hub-Signature-256). None se ausente.

        Returns:
            InboundMessage normalizada, ou None se o payload for irrelevante
            (status update, ack, mensagem de tipo não suportado).

        Raises:
            InvalidSignatureError: Se a assinatura HMAC for inválida.
        """
        ...

    @abstractmethod
    async def verify_webhook_challenge(
        self,
        *,
        params: dict,
    ) -> str | None:
        """
        Responde ao desafio de verificação de webhook.

        Args:
            params: Query parameters do GET request de verificação.

        Returns:
            String com o hub.challenge (Meta) ou None se não aplicável
            (Twilio e Terminal não usam challenge).
        """
        ...
