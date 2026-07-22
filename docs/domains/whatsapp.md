# Domain: whatsapp/

> Status: conversation layer implementado (models, repository, service, router). Provider architecture (ADR-028) em andamento — models + repositories implementados.

---

## Responsabilidade

Receber mensagens de clientes via WhatsApp (webhook da Meta Cloud API ou Twilio Shared),
processar com IA (`ai/service.py`), enviar respostas e gerenciar o ciclo de vida das
conversas. Suporta modo `handoff` para o profissional assumir a conversa manualmente via
dashboard.

---

## Modelos (`whatsapp/models.py`)

### `WhatsAppConversation` (conversation layer)

```python
class WhatsAppConversation(Base, TimestampMixin):
    __tablename__ = "whatsapp_conversations"

    professional_id: Mapped[UUID]        # RESTRICT — valor histórico
    client_id: Mapped[UUID | None]       # SET NULL — contato pode não estar cadastrado
    client_phone: Mapped[str]            # VARCHAR(20) — sempre presente
    status: Mapped[str]                  # 'active' | 'resolved' | 'waiting_professional'
    mode: Mapped[str]                    # 'ai' | 'handoff'
    started_at: Mapped[datetime]
    last_message_at: Mapped[datetime]
    ended_at: Mapped[datetime | None]
```

**RLS ativo:** policy `tenant_isolation` via `professional_id`.

---

### `WhatsAppMessage` (conversation layer)

```python
class WhatsAppMessage(Base):
    __tablename__ = "whatsapp_messages"

    # Sem mixin — usa sent_at próprio (não created_at)
    conversation_id: Mapped[UUID]        # CASCADE — mensagem sem conversa não existe
    direction: Mapped[str]               # 'inbound' | 'outbound'
    sender_type: Mapped[str]             # 'client' | 'ai' | 'professional'
    content: Mapped[str]                 # TEXT
    whatsapp_msg_id: Mapped[str | None]  # UNIQUE — evita duplicatas de webhook
    sent_at: Mapped[datetime]            # DEFAULT NOW()
```

**Sem RLS:** acesso sempre via `conversation_id`.

---

## Provider Architecture (ADR-028)

```
whatsapp/providers/
└── crypto.py   → encrypt_credentials(str) → bytes, decrypt_credentials(bytes) → str
                  Fernet symmetric encryption com ENCRYPTION_KEY (settings)
```

### `WhatsAppAccount` (provider layer)

```python
class WhatsAppAccount(TimestampMixin, Base):
    __tablename__ = "whatsapp_accounts"

    professional_id: Mapped[UUID]              # UNIQUE — um provider por profissional
    provider_type: Mapped[str]                 # 'meta' | 'twilio_shared'
    phone_number: Mapped[str]                  # E.164
    phone_number_id: Mapped[str]               # Meta phone_number_id ou Twilio MSGSVC SID
    access_token_encrypted: Mapped[bytes]      # Fernet-encrypted (LargeBinary)
    routing_tag: Mapped[str | None]            # UNIQUE — slug curto para Twilio Shared
    is_active: Mapped[bool]                    # DEFAULT true
```

**Invariante:** `unique(professional_id)` — um profissional tem exatamente um
provider ativo. Para trocar de provider: soft-deactivate o atual, criar novo.

**RLS ativo** (policy null-permissive no banco de testes).

---

### `WhatsAppPhoneBinding` (provider layer)

```python
class WhatsAppPhoneBinding(CreatedAtMixin, Base):
    __tablename__ = "whatsapp_phone_bindings"

    professional_id: Mapped[UUID]    # CASCADE
    phone_number: Mapped[str]        # E.164 — único por (phone_number, professional_id)
    bound_via: Mapped[str]           # 'tag' | 'qr' | 'manual'
    bound_at: Mapped[datetime]       # DEFAULT NOW()
```

**Uso:** `PhoneBindingRepository.find_by_phone(phone)` é chamado no webhook Twilio
Shared (cross-tenant) para resolver qual profissional recebe a mensagem. A query usa
`db_session` sem tenant context — a policy null-permissive permite a leitura.

**Índice:** `ix_phone_bindings_phone` em `phone_number` para lookup O(log n) por webhook.

**RLS ativo** (null-permissive — lookup cross-tenant funciona sem current_tenant).

---

### `WhatsAppProviderMessage` (provider layer — idempotência)

```python
class WhatsAppProviderMessage(CreatedAtMixin, Base):
    __tablename__ = "whatsapp_provider_messages"

    professional_id: Mapped[UUID]        # RESTRICT
    provider_message_id: Mapped[str]     # ID do provider (WAMID Meta ou SM* Twilio)
    direction: Mapped[str]               # 'inbound' | 'outbound'
    from_phone: Mapped[str]              # E.164
    to_phone: Mapped[str]                # E.164
    body: Mapped[str]                    # TEXT
    provider_type: Mapped[str]           # 'meta' | 'twilio_shared' | 'terminal'
```

**Invariante:** `unique(professional_id, provider_message_id)` — log de idempotência.
Antes de processar cada webhook, chamar `ProviderMessageRepository.exists()`. Se True,
ignorar silenciosamente (at-least-once delivery dos providers).

**Por que separado de `WhatsAppMessage`?** `WhatsAppMessage` é conversation-based
(ligado a `conversation_id`). `WhatsAppProviderMessage` é uma preocupação do
provider layer — existe mesmo para mensagens que ainda não criaram uma conversa.

**RLS ativo.**

---

## Repositories

### `WhatsAppRepository` (conversation layer)
CRUD de `whatsapp_conversations` e `whatsapp_messages`. Ver `repository.py` para
documentação completa de cada método.

### `WhatsAppAccountRepository` (provider layer)
- `create(professional_id, provider_type, phone_number, phone_number_id, access_token_encrypted, routing_tag)` → WhatsAppAccount
- `find_by_professional_id(professional_id)` → WhatsAppAccount | None (filtra is_active=True)
- `find_by_routing_tag(routing_tag)` → WhatsAppAccount | None (filtra is_active=True)

### `PhoneBindingRepository` (provider layer)
- `create(professional_id, phone_number, bound_via)` → WhatsAppPhoneBinding
- `find_by_phone(phone_number)` → WhatsAppPhoneBinding | None (**cross-tenant**, usar db_session)
- `list_by_professional(professional_id)` → list[WhatsAppPhoneBinding] (order by bound_at DESC)

### `ProviderMessageRepository` (provider layer)
- `create(professional_id, provider_message_id, direction, from_phone, to_phone, body, provider_type)` → WhatsAppProviderMessage
- `exists(professional_id, provider_message_id)` → bool (guard de idempotência)

---

## Providers (`whatsapp/providers/`)

### Interface base (`base.py`)

```python
class WhatsAppProvider(ABC):
    async def send_text(*, professional_id, to, body) -> SendResult
    async def send_template(*, professional_id, to, template) -> SendResult
    async def parse_webhook(*, raw_payload, signature_header) -> InboundMessage | None
    async def verify_webhook_challenge(*, params) -> str | None

class ProviderError(Exception):  # provider, message, status_code
class InvalidSignatureError(Exception):  # provider
```

### `TerminalProvider` (`terminal.py`)

- **Dev/test/CI only** — guarda de produção levanta `RuntimeError` se `settings.is_production=True`
- `send_text`: `print("[TerminalProvider → {to}] {body}")` → `SendResult(status='sent')`
- `send_template`: imprime `name`, `language_code`, `params` no stdout
- `parse_webhook`: aceita payload interno `{from_phone, body, professional_id, message_id}` → `InboundMessage`
- `verify_webhook_challenge`: sempre retorna `None`

### `TwilioSharedAccountProvider` (`twilio_shared.py`)

- Um número Corelix compartilhado entre N profissionais
- **Roteamento de entrada** (em ordem):
  1. `PhoneBindingRepository.find_by_phone(from_phone)` → binding existente
  2. Tag `DRANA-{slug}` no início da mensagem → `WhatsAppAccountRepository.find_by_routing_tag()` → cria binding
  3. Sem binding e sem tag → `_send_help_message()` (best-effort) → retorna `None`
- **Validação**: `twilio.request_validator.RequestValidator` (HMAC-SHA1). Desabilitar em testes via `settings.TWILIO_WEBHOOK_VALIDATION=False`
- `send_text`: REST API `POST /Accounts/{SID}/Messages.json` com `data=` e `auth=(SID, token)`
- `send_template`: delega para `send_text` com body composto
- `verify_webhook_challenge`: retorna `None` (Twilio não usa challenge)
- `_send_help_message(to)`: best-effort, captura exceções silenciosamente
- **Importações no topo do módulo**: `PhoneBindingRepository` e `WhatsAppAccountRepository` (necessário para que `unittest.mock.patch` consiga interceptar)

### `MetaCloudProvider` (`meta.py`)

- Número próprio por profissional (Tech Provider aprovado)
- `_get_access_token(professional_id)`: busca `WhatsAppAccount` por `professional_id`, descriptografa `access_token_encrypted` via `decrypt_credentials()`
- `_get_phone_number_id(professional_id)`: retorna `account.phone_number_id`
- `send_text`: `POST /{phone_number_id}/messages` com `json=` e `Authorization: Bearer {token}`
- `send_template`: monta `components` com `params.values()` como parâmetros do body
- `parse_webhook`: verifica HMAC-SHA256 (`_verify_hmac`), extrai mensagens de texto, resolve `professional_id` via `_resolve_professional(phone_number_id)`
- `verify_webhook_challenge`: verifica `hub.verify_token` contra `_get_verify_token()` (META_WEBHOOK_VERIFY_TOKEN ou fallback WHATSAPP_VERIFY_TOKEN)
- `_verify_hmac`: format `sha256={hexdigest}`, `hmac.compare_digest` (timing-safe)
- `_resolve_professional(phone_number_id)`: query direta `select(WhatsAppAccount).where(phone_number_id=..., is_active=True, provider_type='meta')`
- **Fallbacks legados**: `_get_app_secret()` → `META_APP_SECRET or WHATSAPP_APP_SECRET`, `_get_verify_token()` → `META_WEBHOOK_VERIFY_TOKEN or WHATSAPP_VERIFY_TOKEN`

### Factory (`factory.py`)

```python
async def get_provider_for_professional(
    *, professional_id: UUID, session: AsyncSession
) -> WhatsAppProvider:
    # 1. WHATSAPP_FORCE_TERMINAL=True → TerminalProvider()
    # 2. WhatsAppAccount.provider_type == 'meta' → MetaCloudProvider(session)
    # 3. default → TwilioSharedAccountProvider(session)
```

- Nunca levanta exceção — sempre retorna algum provider
- `WhatsAppAccountRepository` importado no topo do módulo (permite `patch('whatsapp.providers.factory.WhatsAppAccountRepository')`)
- Providers concretos importados localmente (evita circular, não precisam de patch no factory)

---

## Crypto (`whatsapp/providers/crypto.py`)

```python
encrypt_credentials(plaintext: str) -> bytes   # Fernet.encrypt()
decrypt_credentials(ciphertext: bytes) -> str  # Fernet.decrypt()
```

Usa `settings.ENCRYPTION_KEY` (str Fernet base64 de 32 bytes). Descriptografar
apenas no momento do uso da API — nunca manter plaintext em memória além do necessário.

**Gotcha:** `Fernet(key)` requer bytes. `settings.ENCRYPTION_KEY` é str → `.encode('utf-8')`
before passing to Fernet.

---

## Fluxo do Webhook (implementado)

```
1. Meta/Twilio envia POST /whatsapp/webhook
2. router.py verifica assinatura HMAC
3. service.py extrai professional_id, client_phone, content
4. ProviderMessageRepository.exists() — idempotência
5. service.py resolve conversa via WhatsAppRepository
6. ai/service.complete_with_history() → resposta
7. Envia via provider (Meta Graph API ou Twilio SDK)
8. Persiste WhatsAppMessage + WhatsAppProviderMessage
9. Retorna 200 OK
```

---

## Testes

| Arquivo | Testes | Status |
|---|---|---|
| tests/whatsapp/test_model.py | 11 | ✅ Green |
| tests/whatsapp/test_repository.py | 22 | ✅ Green |
| tests/whatsapp/test_service.py | 13 | ✅ Green |
| tests/whatsapp/test_router.py | 14 | ✅ Green |
| tests/whatsapp/providers/test_base.py | 5 | ✅ Green |
| tests/whatsapp/providers/test_crypto.py | 6 | ✅ Green |
| tests/whatsapp/providers/test_terminal.py | 8 | ✅ Green |
| tests/whatsapp/providers/test_twilio_shared.py | 13 | ✅ Green |
| tests/whatsapp/providers/test_meta.py | 9 | ✅ Green |
| tests/whatsapp/providers/test_factory.py | 5 | ✅ Green |
| tests/whatsapp/providers/test_idempotency.py | 4 | ✅ Green |

---

## Referências

- `whatsapp/models.py` — todos os 5 models
- `whatsapp/repository.py` — WhatsAppRepository + 3 provider repos
- `whatsapp/providers/crypto.py` — Fernet encrypt/decrypt
- `ai/service.py` — `AIService.complete_with_history()`
- `domains/schema.md` — schema SQL completo
- ADR-011 — Embedded Signup por profissional
- ADR-028 — Provider architecture (Meta + Twilio Shared + Terminal)

---

## Responsabilidade

Receber mensagens de clientes via WhatsApp (webhook da Meta Cloud API), processar com IA
(`ai/service.py`), enviar respostas e gerenciar o ciclo de vida das conversas. Suporta
modo `handoff` para o profissional assumir a conversa manualmente via dashboard.

---

## Modelos (`whatsapp/models.py`)

### `WhatsAppConversation`

```python
class WhatsAppConversation(Base, TimestampMixin):
    __tablename__ = "whatsapp_conversations"

    professional_id: Mapped[UUID]        # RESTRICT — valor histórico
    client_id: Mapped[UUID | None]       # SET NULL — contato pode não estar cadastrado
    client_phone: Mapped[str]            # VARCHAR(20) — sempre presente
    status: Mapped[str]                  # 'active' | 'resolved' | 'waiting_professional'
    mode: Mapped[str]                    # 'ai' | 'handoff'
    started_at: Mapped[datetime]
    last_message_at: Mapped[datetime]
    ended_at: Mapped[datetime | None]
```

**Campo `mode`:**
- `ai` → secretária digital responde automaticamente via `ai/service.py`
- `handoff` → profissional assumiu a conversa; IA silenciada até retornar para `ai`

**Campo `status`:**
- `active` → conversa em andamento (IA ou profissional respondendo)
- `waiting_professional` → IA não conseguiu resolver, aguarda ação humana
- `resolved` → conversa encerrada

**RLS ativo:** policy `tenant_isolation` via `professional_id`.

---

### `WhatsAppMessage`

```python
class WhatsAppMessage(Base):
    __tablename__ = "whatsapp_messages"

    # Sem mixin — usa sent_at próprio (não created_at)
    conversation_id: Mapped[UUID]        # CASCADE — mensagem sem conversa não existe
    direction: Mapped[str]               # 'inbound' | 'outbound'
    sender_type: Mapped[str]             # 'client' | 'ai' | 'professional'
    content: Mapped[str]                 # TEXT
    whatsapp_msg_id: Mapped[str | None]  # UNIQUE — evita duplicatas de webhook
    sent_at: Mapped[datetime]            # DEFAULT NOW()
```

**Sem RLS:** acesso sempre via `conversation_id`, controlado por join com
`whatsapp_conversations` (que tem RLS). Ver `domains/schema.md`.

**`whatsapp_msg_id` UNIQUE:** o webhook da Meta pode entregar a mesma mensagem mais de
uma vez (retry em falha de rede). O `UNIQUE` no banco + verificação no service garantem
idempotência.

---

## Arquitetura do Módulo (a implementar)

```
whatsapp/
├── router.py       → webhook POST /whatsapp/webhook (público — sem auth)
│                     dashboard endpoints (TenantSession)
├── service.py      → processa mensagem, chama ai/service, envia resposta
├── repository.py   → CRUD de conversations e messages
└── schemas.py      → WebhookPayload, ConversationResponse, MessageResponse
```

**Dependências do service layer:**
```
whatsapp/service.py
    → whatsapp/repository.py     (persistência)
    → ai/service.py              (gerar resposta)
    → Meta Cloud API             (enviar mensagem via HTTP)
    → clients/repository.py      (resolver client_id por telefone)
```

---

## Fluxo do Webhook (a implementar)

```
1. Meta envia POST /whatsapp/webhook com payload de mensagem recebida
2. router.py verifica assinatura HMAC-SHA256 (X-Hub-Signature-256)
3. router.py verifica token de verificação no GET inicial da Meta
4. service.py extrai: professional_id (via whatsapp_phone_id), client_phone, content

5. service.py resolve a conversa:
   a. Busca conversa ativa para (professional_id, client_phone)
   b. Se não existe → cria WhatsAppConversation(mode='ai', status='active')
   c. Tenta resolver client_id via clients_repo.find_by_phone(client_phone)

6. service.py persiste mensagem recebida:
   WhatsAppMessage(direction='inbound', sender_type='client', ...)

7. service.py decide o que fazer baseado no mode:
   - mode='ai'      → chama ai/service.complete_with_history(system_prompt, history)
   - mode='handoff' → notifica profissional via dashboard (sem resposta automática)

8. Se mode='ai':
   a. Carrega histórico das últimas N mensagens da conversa
   b. ai/service retorna resposta gerada
   c. Envia via Meta Cloud API (POST para graph.facebook.com)
   d. Persiste resposta: WhatsAppMessage(direction='outbound', sender_type='ai', ...)
   e. Atualiza conversation.last_message_at

9. Retorna 200 OK para a Meta (obrigatório — qualquer outro status causa retry)
```

---

## Prompt do Sistema (`ai/prompts.py`)

```python
PROMPTS["whatsapp_secretary"] = """
Você é a secretária digital de {professional_name}, {specialty}.

Sobre {professional_name}:
{bio}

Suas responsabilidades:
- Confirmar e reagendar sessões
- Responder dúvidas sobre disponibilidade e valores
- Comunicar de forma amigável e profissional

Regras:
- Nunca inventar informações sobre disponibilidade — consulte a agenda
- Se não souber responder, diga que vai verificar com {professional_name}
- Tom: {communication_style}
"""
```

O `system_prompt` é montado dinamicamente com dados do `Professional` antes de cada
chamada à IA.

---

## Verificação do Webhook Meta

```python
# router.py — verificação inicial (GET)
@router.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
):
    if hub_mode == "subscribe" and hub_verify_token == settings.WHATSAPP_VERIFY_TOKEN:
        return PlainTextResponse(hub_challenge)
    raise HTTPException(status_code=403)

# router.py — recebimento de mensagens (POST)
@router.post("/webhook", status_code=200)
async def receive_message(
    request: Request,
    background_tasks: BackgroundTasks,
    db: DbSession,
):
    # 1. Verificar assinatura HMAC-SHA256
    # 2. Parsear payload
    # 3. Processar em background_task (resposta 200 imediata para a Meta)
    background_tasks.add_task(process_webhook, payload, db)
    return {"status": "ok"}
```

**Por que `BackgroundTasks`?** A Meta espera resposta em < 20 segundos. Processar IA e
enviar mensagem pode levar mais tempo. Responder imediatamente e processar em background
garante que a Meta não faça retry desnecessário.

---

## Integração com Meta Cloud API (a implementar)

```python
# whatsapp/service.py
async def send_message(phone: str, content: str, phone_id: str, access_token: str) -> str:
    """Envia mensagem via Meta Cloud API. Retorna whatsapp_msg_id."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"https://graph.facebook.com/v19.0/{phone_id}/messages",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "messaging_product": "whatsapp",
                "to": phone,
                "type": "text",
                "text": {"body": content},
            },
        )
        response.raise_for_status()
        return response.json()["messages"][0]["id"]
```

**Tratamento de erros:**
- `httpx.HTTPStatusError` → capturar e lançar `ExternalServiceError`
- Token expirado (401 da Meta) → sinalizar para renovação via job `pgqueuer`
- Rate limit da Meta → `RateLimitError` com retry exponencial

---

## Dashboard (a implementar)

Endpoints para o profissional gerenciar conversas:

| Método | Path | Descrição |
|---|---|---|
| GET | `/whatsapp/conversations` | Lista conversas ativas (paginado) |
| GET | `/whatsapp/conversations/{id}` | Conversa + histórico de mensagens |
| PATCH | `/whatsapp/conversations/{id}/mode` | Alterna `ai` ↔ `handoff` |
| POST | `/whatsapp/conversations/{id}/messages` | Profissional envia mensagem manual |
| PATCH | `/whatsapp/conversations/{id}/resolve` | Encerra conversa |

**Todos os endpoints de dashboard usam `TenantSession` (JWT + RLS).**
O webhook usa `DbSession` (público — sem JWT).

---

## Campos em `professionals` para WhatsApp

```python
# Preenchidos via fluxo de Embedded Signup (ADR-011)
whatsapp_phone_number: str | None      # ex: "+5511999999999"
whatsapp_phone_id: str | None          # ID do número na Meta API
whatsapp_access_token: str | None      # Token OAuth — criptografado AES-256
whatsapp_connected_at: datetime | None
whatsapp_token_expires_at: datetime | None
```

O `whatsapp_phone_id` é usado para identificar qual profissional recebeu a mensagem
no payload do webhook (a Meta envia o ID do número que recebeu, não o JWT).

---

## Segurança

- **Verificação de assinatura:** todo POST do webhook verifica `X-Hub-Signature-256`
  com `HMAC-SHA256(APP_SECRET, payload)` — sem verificação, qualquer fonte pode enviar
  mensagens falsas
- **`whatsapp_access_token` criptografado:** AES-256 em repouso — nunca em plaintext no banco
- **Idempotência via `whatsapp_msg_id`:** duplicatas do webhook são silenciosamente ignoradas
- **RLS em conversas:** `whatsapp_conversations` tem RLS ativo — profissional só acessa
  suas próprias conversas

---

## Testes (a criar — TDD)

Ordem sugerida:
1. `tests/whatsapp/test_model.py` — constraints, defaults, modes e statuses válidos
2. `tests/whatsapp/test_repository.py` — CRUD, find_by_phone, find_active_conversation
3. `tests/whatsapp/test_service.py` — mock da Meta API, fluxo completo, idempotência
4. `tests/whatsapp/test_router.py` — webhook verification, HMAC check, dashboard endpoints

**Mock da Meta API nos testes:** usar `respx` (mock para `httpx`) — não fazer chamadas
reais à Meta em testes automatizados.

---

## Referências

- `whatsapp/models.py` — `WhatsAppConversation`, `WhatsAppMessage`
- `ai/service.py` — `AIService.complete_with_history()` (chamado pelo whatsapp/service)
- `ai/prompts.py` — `PROMPTS["whatsapp_secretary"]`
- `domains/schema.md` — schema SQL completo das tabelas whatsapp
- `domains/ai.md` — detalhes do AIService
- ADR-011 — Embedded Signup por profissional
- ADR-019 — pgqueuer para renovação de token WhatsApp