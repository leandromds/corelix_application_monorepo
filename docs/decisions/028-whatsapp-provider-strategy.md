# ADR-028: Estratégia de Provedor WhatsApp — Meta + Twilio + Terminal

**Status:** Aceita
**Data:** 2026-05-09
**Versão:** 2 (substitui rascunho anterior de 2026-05-09)
**Substitui parcialmente:** ADR-011 (Embedded Signup direto com Meta Tech Provider)

---

## Contexto

A ADR-011 estabeleceu que cada profissional conecta o próprio número via Meta Embedded Signup, exigindo que a Corelix opere como **Tech Provider** da Meta. O processo está em andamento (validação de pessoa jurídica em curso) e tem prazo indefinido — semanas ou meses, com possibilidade de negativa.

**Restrições do momento:**
- Plataforma pronta para validação com clientes pagantes em **maio/2026**
- Não pode bloquear go-to-market esperando aprovação Meta
- Onboarding do profissional deve ser inteiramente dentro da Corelix — não podemos pedir para ele criar conta Twilio, copiar Account SID, etc. Modelo "self-serve em outra plataforma" foi explicitamente rejeitado pelo dono do produto
- Budget limitado — evitar fee fixo por número durante validação
- LGPD: dados administrativos no banco, número do profissional permanece dele

**Descoberta importante:** Twilio também exige Tech Provider Program para SaaS multi-tenant. Não há atalho para entregar "número próprio por profissional via self-serve" sem aprovação Meta — independentemente do BSP.

---

## Decisão

Implementar uma **camada de abstração de provedor WhatsApp** com **três implementações intercambiáveis**, escolhidas por configuração ou por profissional:

| Provider | Uso | Estado |
|---|---|---|
| `TerminalProvider` | Dev local, testes E2E reproduzíveis, demos comerciais | Disponível desde o primeiro commit |
| `TwilioSharedAccountProvider` | Piloto com clientes reais usando número único da Corelix | Disponível em maio/2026 (Self Sign-up Twilio padrão) |
| `MetaCloudProvider` | Produção final — número próprio por profissional via Embedded Signup | Disponível após Tech Provider aprovado |

A escolha do provider para uma mensagem é resolvida pelo `WhatsAppProviderFactory`:

```
1. Se settings.WHATSAPP_FORCE_TERMINAL=true → TerminalProvider (dev/test)
2. Se profissional tem WhatsAppAccount com provider_type='meta' → MetaCloudProvider
3. Caso contrário → TwilioSharedAccountProvider (modo piloto)
```

Migração granular: profissionais novos pós-Tech Provider entram já no Meta direto, pilotos existentes continuam no Shared até migrarem.

---

## Modelo conceitual

```
┌──────────────────────────────────────────────────────────────┐
│ TerminalProvider                                             │
│   stdin/stdout ←→ service.handle_inbound_message()           │
│   Sem WhatsApp real. Iteração rápida de prompts e demos.     │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│ TwilioSharedAccountProvider (piloto)                         │
│   1 número Corelix ←→ Twilio ←→ N profissionais              │
│   Routing por tag/QR identifica de qual professional é a     │
│   mensagem antes do service ser chamado.                     │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│ MetaCloudProvider (produção final)                           │
│   N números de profissionais ←→ Meta Cloud API direto        │
│   Cada profissional tem seu número e seus templates.         │
└──────────────────────────────────────────────────────────────┘
```

---

## Interface comum

```python
# whatsapp/providers/base.py
from abc import ABC, abstractmethod
from uuid import UUID

class WhatsAppProvider(ABC):
    """Contrato unificado. Stateless e async.
    Erros do provedor externo viram ProviderError com contexto."""

    @abstractmethod
    async def send_text(
        self, *, professional_id: UUID, to: str, body: str,
    ) -> SendResult: ...

    @abstractmethod
    async def send_template(
        self, *, professional_id: UUID, to: str, template: TemplateMessage,
    ) -> SendResult: ...

    @abstractmethod
    async def parse_webhook(
        self, *, raw_payload: dict, signature_header: str | None,
    ) -> InboundMessage | None:
        """Valida assinatura, extrai mensagem, resolve professional_id.
        Retorna None se irrelevante (status update, ack).
        Levanta InvalidSignatureError se inválido."""

    @abstractmethod
    async def verify_webhook_challenge(self, *, params: dict) -> str | None:
        """Meta usa hub.challenge; Twilio retorna None; Terminal não tem webhook."""
```

`InboundMessage`, `SendResult`, `TemplateMessage` são Pydantic models compartilhados — o **dialeto interno**. O `service.py` nunca toca payload bruto.

---

## Persistência

### `whatsapp_accounts`

Vincula profissional ao provider quando há conta dedicada.

```python
class WhatsAppAccount(Base, TenantMixin, TimestampMixin):
    __tablename__ = "whatsapp_accounts"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    professional_id: Mapped[UUID] = mapped_column(
        ForeignKey("professionals.id", ondelete="CASCADE"),
        unique=True,  # 1:1
    )
    provider_type: Mapped[str] = mapped_column(
        Text,
        CheckConstraint("provider_type IN ('meta', 'twilio_shared')"),
    )
    phone_number: Mapped[str] = mapped_column(Text)         # E.164
    phone_number_id: Mapped[str] = mapped_column(Text)      # Meta phone_number_id ou Twilio messaging_service_sid
    access_token_encrypted: Mapped[bytes] = mapped_column(LargeBinary)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
```

No modo `twilio_shared` todos os profissionais compartilham o mesmo `phone_number_id`. A linha existe mesmo assim para registrar o vínculo lógico.

**Criptografia:** `access_token_encrypted` cifrado com Fernet usando `ENCRYPTION_KEY`. Service descriptografa só ao chamar o provider.

### `whatsapp_phone_bindings`

Resolve "qual profissional é dono dessa conversa" no modo shared.

```python
class WhatsAppPhoneBinding(Base, TenantMixin, TimestampMixin):
    __tablename__ = "whatsapp_phone_bindings"
    __table_args__ = (
        UniqueConstraint("phone_number", "professional_id"),
        Index("ix_phone_bindings_phone", "phone_number"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    professional_id: Mapped[UUID] = mapped_column(ForeignKey("professionals.id", ondelete="CASCADE"))
    phone_number: Mapped[str] = mapped_column(Text)        # E.164 do cliente final
    bound_via: Mapped[str] = mapped_column(Text)           # 'tag' | 'qr' | 'manual'
    bound_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, server_default=func.now())
```

Só usada pelo `TwilioSharedAccountProvider`.

### `whatsapp_messages` (já planejada na ADR-011)

Idempotência via unique `(professional_id, provider_message_id)`.

---

## Routing no modo shared

Três estratégias, todas terminam criando um `WhatsAppPhoneBinding`:

**Tag em link** — profissional divulga `wa.me/{numero_corelix}?text=DRANA-CMcm6`. Primeira mensagem com a tag → cria binding.

**QR code** — profissional gera QR único na Corelix. Cliente final escaneia, mensagem com tag pré-preenchida.

**Onboarding manual** — profissional cadastra cliente, clica "Iniciar conversa". Backend dispara template inicial e cria binding antecipado.

```python
async def parse_webhook(self, *, raw_payload, signature_header):
    self._verify_twilio_signature(raw_payload, signature_header)

    from_phone = raw_payload["From"].replace("whatsapp:", "")
    body = raw_payload["Body"]

    binding = await self.bindings_repo.find_by_phone(from_phone)
    if binding is None:
        tag = extract_professional_tag(body)
        if tag is None:
            await self._send_help_message(from_phone)
            return None
        professional = await self.professionals_repo.find_by_tag(tag)
        binding = await self.bindings_repo.create(
            professional_id=professional.id,
            phone_number=from_phone,
            bound_via='tag',
        )

    return InboundMessage(
        professional_id=binding.professional_id,
        from_phone=from_phone,
        body=body,
        provider_message_id=raw_payload["MessageSid"],
    )
```

Service nunca sabe que o número é compartilhado.

---

## Webhooks

```
POST /webhooks/whatsapp/meta      MetaCloudProvider     HMAC-SHA256
GET  /webhooks/whatsapp/meta      challenge hub.challenge
POST /webhooks/whatsapp/twilio    TwilioSharedProvider  HMAC-SHA1, X-Twilio-Signature
```

`TerminalProvider` não tem webhook — recebe via stdin no comando CLI.

---

## TerminalProvider

```bash
poetry run python -m corelix.devtools.terminal_chat \
  --professional-id <uuid> \
  --client-phone +5511999999999
```

```
[Corelix Terminal Chat — modo simulação]
Profissional: Dr. Ana Lima (psicóloga)
Cliente:      +5511999999999

> Oi, queria remarcar minha consulta de quinta
[Bot → +5511999999999] Claro! Sua consulta atual é quinta às 14h.
                       Para qual horário gostaria de remarcar?
> sexta às 16h
[Bot → +5511999999999] Confirmado: sexta-feira, 10/05, às 16h.
```

**Guard de produção obrigatório:** `TerminalProvider.__init__` levanta `RuntimeError` se `settings.is_production`.

Dashboard exibe badge "🧪 simulação" quando a mensagem veio do terminal — fica claro o que é teste e o que é real.

---

## Configuração

```env
# Comum
ENCRYPTION_KEY=...
WHATSAPP_FORCE_TERMINAL=false

# Twilio Shared (piloto)
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_MESSAGING_SERVICE_SID=...
TWILIO_SHARED_PHONE_NUMBER=+5511...
TWILIO_WEBHOOK_VALIDATION=true

# Meta (após Tech Provider aprovado)
META_APP_ID=...
META_APP_SECRET=...
META_WEBHOOK_VERIFY_TOKEN=...
```

---

## Migração entre providers

```
TerminalProvider (dev)        → não migra; cada profissional já entra em prod via Twilio
TwilioSharedAccountProvider   → MetaCloudProvider quando profissional fizer Embedded Signup
MetaCloudProvider             → estado final
```

Quando profissional migra de Shared para Meta direto:
1. Roda Embedded Signup do Meta com seu número
2. Backend cria `WhatsAppAccount` com `provider_type='meta'`
3. Próximas mensagens roteiam pelo Meta direto via factory
4. Histórico em `whatsapp_messages` permanece — chave é `professional_id`

---

## TDD — cobertura mínima

```
tests/whatsapp/providers/
  test_base.py              # contrato ABC, factory routing
  test_terminal.py          # send_text imprime, receive_loop processa, guard de produção
  test_twilio_shared.py     # send, parse_webhook, signature, routing por tag/QR
  test_meta.py              # send, parse_webhook, signature, challenge
  test_idempotency.py       # provider_message_id duplicado → 1 ação
tests/whatsapp/webhooks/
  test_meta_webhook.py      # GET challenge, POST válido/inválido
  test_twilio_webhook.py    # POST válido/inválido, primeiro contato sem binding
tests/whatsapp/devtools/
  test_terminal_chat.py     # smoke test do CLI com input/output simulados
```

Mocks via `respx` (HTTPX). `TerminalProvider` usa `io.StringIO` para capturar stdout.

---

## Consequências

### Positivas

- Validação de mercado em maio/2026 — go-to-market não depende de aprovação Meta
- Onboarding 100% dentro da Corelix durante o piloto
- Iteração de IA acelerada — terminal substitui Twilio sandbox no dia-a-dia
- Demos comerciais ao vivo antes do produto self-service estar pronto
- Migração granular para Meta — profissionais migram individualmente
- Robustez arquitetural — futuros providers entram como nova classe sem alterar service

### Negativas

- Branding compartilhado no piloto — clientes finais veem "Corelix" como remetente
- Routing por tag exige educação do profissional (mitigação: link copiável no dashboard)
- Limites Meta no início — WABA Corelix começa com 250 conversas/24h
- Templates parametrizados na WABA Corelix — todos compartilham os mesmos templates aprovados
- Complexidade extra — 3 implementações vs 1 (~800 linhas a mais)
- Cobrança em USD via Twilio — exposição cambial

### Riscos monitorados

| Risco | Probabilidade | Mitigação |
|---|---|---|
| Quality rating da WABA Corelix cair com pilotos | Média | Templates revisados, opt-in obrigatório, monitoramento semanal |
| Meta negar Tech Provider definitivamente | Alta | Plano B já é o estado atual |
| Twilio mudar política WhatsApp | Baixa | Modelo estável; abstração permite trocar BSP |
| Profissional não entender link/QR | Média | Onboarding manual + tutorial |
| Tentação de "ficar no terminal" e adiar piloto real | Média | Disciplina: terminal é dev tool, não substitui validação |

---

## Alternativas descartadas

| Alternativa | Por que descartada |
|---|---|
| Esperar Tech Provider Meta sair | Inviabiliza maio/2026 |
| Pedir profissional criar conta Twilio | UX rejeitada — onboarding deve ser inteiro na Corelix |
| Bibliotecas não-oficiais (Baileys etc.) | Viola TOS Meta, risco de banimento, conflita com LGPD |
| 360dialog em vez de Twilio | $50/mês fixo por número inviável em validação |
| Pular WhatsApp e lançar só com email | WhatsApp é parte central da proposta de valor |
| Provider único (Twilio Shared apenas) | Bloqueia migração futura para Meta direto |

---

## Referências

- ADR-001 — Multi-tenancy com RLS (aplicada a `whatsapp_accounts` e `whatsapp_phone_bindings`)
- ADR-011 — Embedded Signup com número próprio (estado final, condicional ao provider Meta)
- ADR-019 — Jobs via pgqueuer (limpeza de bindings órfãos)
- Meta Cloud API: https://developers.facebook.com/docs/whatsapp/cloud-api
- Twilio Self Sign-up: https://www.twilio.com/docs/whatsapp/self-sign-up
- Twilio Tech Provider Program: https://www.twilio.com/docs/whatsapp/tech-provider-program
