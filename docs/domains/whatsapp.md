# Domain: whatsapp/

> Status: modelos implementados, migration aplicada. Implementação do módulo pendente.

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