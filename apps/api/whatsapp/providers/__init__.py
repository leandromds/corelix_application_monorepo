"""
Providers WhatsApp — implementações concretas do contrato WhatsAppProvider.

Cada provider encapsula a integração com um canal de mensagens:
- TerminalProvider: dev/test/demo, imprime no stdout
- TwilioSharedAccountProvider: piloto com número compartilhado Corelix
- MetaCloudProvider: produção com número dedicado por profissional (Tech Provider)

O service layer opera exclusivamente via a interface WhatsAppProvider (base.py),
nunca importando implementações concretas diretamente.
"""
