"""
Terminal Chat — CLI interativo para desenvolvimento WhatsApp (ADR-028).

Simula uma conversa WhatsApp usando o TerminalProvider, sem necessidade de
credenciais reais ou conta WhatsApp. Ideal para:
  - Iterar prompts de IA rapidamente
  - Demos comerciais ao vivo
  - Testes E2E sem dependência de rede

Uso:
    poetry run python -m whatsapp.devtools.terminal_chat \\
        --professional-id <uuid> \\
        --client-phone +5511999999999

Controles:
    Ctrl+C ou Ctrl+D — encerra o chat
    /exit             — encerra o chat
    /reset            — reinicia a sessão (nova conversa)
"""

import argparse
import asyncio
import sys
import uuid


def _build_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="terminal_chat",
        description="Corelix Terminal Chat — simulação de conversa WhatsApp",
    )
    parser.add_argument(
        "--professional-id",
        required=True,
        help="UUID do profissional (tenant) para a simulação",
    )
    parser.add_argument(
        "--client-phone",
        required=True,
        help="Número do cliente simulado em formato E.164 (ex: +5511999999999)",
    )
    return parser.parse_args()


async def run_chat(*, professional_id: uuid.UUID, client_phone: str) -> None:
    """
    Loop principal do chat interativo.

    Usa TerminalProvider para envio e recebimento — não faz chamadas de rede.
    Cria sessão de banco real para persistir conversa e histórico de IA.
    """
    from core.database import async_session_maker, set_tenant_context
    from whatsapp.providers.terminal import TerminalProvider
    from whatsapp.service import WhatsAppService

    print("\n[Corelix Terminal Chat — modo simulação]")
    print(f"Profissional: {professional_id}")
    print(f"Cliente:      {client_phone}")
    print("─" * 50)
    print("Digite sua mensagem e pressione Enter.")
    print("Comandos: /exit para sair | /reset para nova conversa")
    print("─" * 50)

    provider = TerminalProvider()

    async with async_session_maker() as session:
        await set_tenant_context(session, professional_id)

        while True:
            try:
                line = await asyncio.get_event_loop().run_in_executor(None, lambda: input("\n> "))
            except (EOFError, KeyboardInterrupt):
                print("\n[Chat encerrado]")
                break

            line = line.strip()
            if not line:
                continue
            if line == "/exit":
                print("[Chat encerrado]")
                break
            if line == "/reset":
                print("[Nova conversa iniciada]")
                continue

            # Simular mensagem entrante via TerminalProvider
            payload = {
                "professional_id": str(professional_id),
                "from_phone": client_phone,
                "body": line,
                "message_id": f"terminal-{uuid.uuid4()}",
            }
            inbound = await provider.parse_webhook(raw_payload=payload, signature_header=None)
            if inbound is None:
                print("[Erro: não foi possível processar a mensagem]")
                continue

            service = WhatsAppService(session)
            try:
                await service.handle_inbound_message(inbound)
                await session.commit()
            except Exception as exc:  # noqa: BLE001
                print(f"[Erro ao processar: {exc}]")
                await session.rollback()


def main() -> None:
    """Entrypoint do CLI — parse args e inicia o event loop."""
    args = _build_args()

    try:
        professional_id = uuid.UUID(args.professional_id)
    except ValueError:
        print(f"Erro: '{args.professional_id}' não é um UUID válido", file=sys.stderr)
        sys.exit(1)

    asyncio.run(
        run_chat(
            professional_id=professional_id,
            client_phone=args.client_phone,
        )
    )


if __name__ == "__main__":
    main()
