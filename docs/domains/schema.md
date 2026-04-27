# Schema do Banco de Dados — Referência Completa

> Fonte de verdade: `alembic/versions/56f1e41b5d4c_initial_schema.py`
> Migration aplicada. RLS ativo em 6 tabelas.

---

## Visão Geral dos Relacionamentos

```
professionals (1)
    ├── refresh_tokens (N)              [CASCADE]
    ├── clients (N)                     [RESTRICT] ← RLS
    ├── availability_slots (N)          [CASCADE]  ← RLS
    ├── blocked_periods (N)             [CASCADE]  ← RLS
    ├── recurrences (N)                 [RESTRICT] ← RLS
    ├── whatsapp_conversations (N)      [RESTRICT] ← RLS
    │       └── whatsapp_messages (N)   [CASCADE]
    └── sessions (N)                    [RESTRICT] ← RLS
            ├── clients (N)             [RESTRICT]
            └── recurrences (N)         [SET NULL]

audit_logs → professionals              [SET NULL]  (sem RLS)
```

**Tabelas com RLS:** `clients`, `availability_slots`, `blocked_periods`, `recurrences`, `sessions`, `whatsapp_conversations`

**Tabelas sem RLS:** `professionals`, `refresh_tokens`, `whatsapp_messages`, `audit_logs`

---

## Regras de ON DELETE por Semântica

| Valor | Quando usar | Exemplos |
|-------|-------------|----------|
| `CASCADE` | Filho não tem valor sem o pai | `refresh_tokens`, `availability_slots`, `blocked_periods`, `whatsapp_messages` |
| `RESTRICT` | Filho tem valor histórico próprio | `clients`, `sessions`, `recurrences`, `whatsapp_conversations` |
| `SET NULL` | Vínculo pode ser removido sem perder o registro | `recurrence_id` em `sessions`, `client_id` em `whatsapp_conversations` |

---

## professionals

```sql
CREATE TABLE professionals (
    id                        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email                     VARCHAR(255) NOT NULL UNIQUE,
    password_hash             VARCHAR(255) NOT NULL,
    full_name                 VARCHAR(255) NOT NULL,
    specialty                 VARCHAR(255),
    bio                       TEXT,
    session_duration          INTEGER NOT NULL DEFAULT 60,
    session_price             NUMERIC(10, 2),
    phone                     VARCHAR(20),
    whatsapp_phone_number     VARCHAR(20),
    whatsapp_phone_id         VARCHAR(100),
    whatsapp_access_token     TEXT,              -- armazenado criptografado (AES-256)
    whatsapp_connected_at     TIMESTAMPTZ,
    whatsapp_token_expires_at TIMESTAMPTZ,
    is_active                 BOOLEAN NOT NULL DEFAULT TRUE,
    created_at                TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

**Notas:**
- Sem RLS — acesso controlado pelo service layer
- `bio` é usada pela IA para apresentar o profissional no WhatsApp
- `whatsapp_access_token` criptografado com AES-256 em repouso
- Job `pgqueuer` renova `whatsapp_access_token` antes de `whatsapp_token_expires_at`
- Profissional pode usar o sistema sem conectar WhatsApp — campos `whatsapp_*` são nullable
- `session_price` é `NUMERIC` — serializado como `string` no JSON (cuidado no frontend)

**SQLAlchemy model:** `professionals/models.py` → `Professional` com `TimestampMixin`

---

## refresh_tokens

```sql
CREATE TABLE refresh_tokens (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    professional_id  UUID NOT NULL REFERENCES professionals(id) ON DELETE CASCADE,
    token_hash       VARCHAR(255) NOT NULL UNIQUE,  -- SHA-256 do token raw
    device_info      VARCHAR(255),
    expires_at       TIMESTAMPTZ NOT NULL,
    revoked          BOOLEAN NOT NULL DEFAULT FALSE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_refresh_tokens_professional_id ON refresh_tokens(professional_id);
CREATE INDEX idx_refresh_tokens_token_hash ON refresh_tokens(token_hash);
```

**Notas:**
- `token_hash` = `hashlib.sha256(raw_token.encode()).hexdigest()` — nunca armazenar token puro
- Sem `updated_at` — registro imutável após criação (`CreatedAtMixin`)
- `CASCADE` — refresh tokens sem sentido sem o profissional
- Job noturno chama `delete_expired()` para limpar tokens com `expires_at < NOW()`
- `device_info` preparado para feature futura de "gerenciar sessões ativas"

**SQLAlchemy model:** `auth/models.py` → `RefreshToken` com `CreatedAtMixin`

---

## clients

```sql
CREATE TABLE clients (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    professional_id  UUID NOT NULL REFERENCES professionals(id) ON DELETE RESTRICT,
    full_name        VARCHAR(255) NOT NULL,
    phone            VARCHAR(20),
    email            VARCHAR(255),
    notes            TEXT,
    whatsapp_opt_in  BOOLEAN NOT NULL DEFAULT FALSE,
    email_opt_in     BOOLEAN NOT NULL DEFAULT FALSE,
    is_active        BOOLEAN NOT NULL DEFAULT TRUE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_clients_professional_id ON clients(professional_id);
CREATE INDEX idx_clients_phone ON clients(professional_id, phone);

ALTER TABLE clients ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON clients
    USING (
        professional_id = current_setting('app.current_tenant', TRUE)::uuid
    );
```

**Notas:**
- `RESTRICT` — cliente tem valor histórico (sessões, financeiro, IA)
- Pelo menos um de `phone` ou `email` deve ser fornecido — validação via `model_validator` no Pydantic (`ClientCreate`)
- `whatsapp_opt_in` e `email_opt_in` obrigatórios para LGPD e conformidade com Meta
- Soft delete via `is_active` (ver ADR-009) — `find_all(active_only=True)` por padrão
- `find_by_phone()` só retorna clientes ativos — cliente inativo com mesmo telefone não gera `ConflictError`
- Índice composto `(professional_id, phone)` para busca rápida por telefone dentro do tenant

**SQLAlchemy model:** `clients/models.py` → `Client` com `TimestampMixin`

---

## availability_slots

```sql
CREATE TABLE availability_slots (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    professional_id  UUID NOT NULL REFERENCES professionals(id) ON DELETE CASCADE,
    day_of_week      SMALLINT NOT NULL,    -- 0=domingo, 6=sábado
    start_time       TIME NOT NULL,
    end_time         TIME NOT NULL,
    is_active        BOOLEAN NOT NULL DEFAULT TRUE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_availability_slot UNIQUE (professional_id, day_of_week, start_time),
    CONSTRAINT chk_time_range CHECK (end_time > start_time),
    CONSTRAINT chk_day_of_week CHECK (day_of_week BETWEEN 0 AND 6)
);

CREATE INDEX idx_availability_slots_professional_id ON availability_slots(professional_id);

ALTER TABLE availability_slots ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON availability_slots
    USING (
        professional_id = current_setting('app.current_tenant', TRUE)::uuid
    );
```

**Notas:**
- `TIME` (sem data) — representa padrão semanal recorrente, não momento específico
- `TIMESTAMPTZ` não faria sentido aqui — um slot de "segunda 9h-10h" não é um instante
- `CASCADE` — configuração de agenda sem sentido sem o profissional
- Múltiplos blocos por dia permitidos (ex: 9h-12h e 14h-18h)
- `day_of_week`: 0=domingo, 1=segunda, ..., 6=sábado
- Soft delete via `is_active` — histórico de configurações de agenda preservado

**SQLAlchemy model:** `agenda/models.py` → `AvailabilitySlot` com `TimestampMixin`

---

## blocked_periods

```sql
CREATE TABLE blocked_periods (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    professional_id  UUID NOT NULL REFERENCES professionals(id) ON DELETE CASCADE,
    start_datetime   TIMESTAMPTZ NOT NULL,
    end_datetime     TIMESTAMPTZ NOT NULL,
    reason           VARCHAR(255),
    notify_clients   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_blocked_period_range CHECK (end_datetime > start_datetime)
);

CREATE INDEX idx_blocked_periods_professional_id ON blocked_periods(professional_id);
CREATE INDEX idx_blocked_periods_range
    ON blocked_periods(professional_id, start_datetime, end_datetime);

ALTER TABLE blocked_periods ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON blocked_periods
    USING (
        professional_id = current_setting('app.current_tenant', TRUE)::uuid
    );
```

**Notas:**
- `TIMESTAMPTZ` aqui (diferente de `availability_slots`) — bloqueio é um período específico no tempo
- `CASCADE` — sem sentido sem o profissional
- `notify_clients DEFAULT TRUE` — opt-out, não opt-in. Profissional precisa desmarcar para não notificar
- Sem `updated_at` — `CreatedAtMixin` (periodos bloqueados são criados e deletados, não editados)
- Índice composto `(professional_id, start_datetime, end_datetime)` — verificação de conflito de agenda

**SQLAlchemy model:** `agenda/models.py` → `BlockedPeriod` com `CreatedAtMixin`

---

## sessions

```sql
CREATE TABLE sessions (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    professional_id  UUID NOT NULL REFERENCES professionals(id) ON DELETE RESTRICT,
    client_id        UUID NOT NULL REFERENCES clients(id) ON DELETE RESTRICT,
    recurrence_id    UUID REFERENCES recurrences(id) ON DELETE SET NULL,
    scheduled_at     TIMESTAMPTZ NOT NULL,
    duration_minutes INTEGER NOT NULL,
    price            NUMERIC(10, 2) NOT NULL,
    status           VARCHAR(20) NOT NULL DEFAULT 'scheduled',
    notes            TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_session_status
        CHECK (status IN ('scheduled', 'completed', 'cancelled', 'no_show')),
    CONSTRAINT chk_duration CHECK (duration_minutes > 0)
);

CREATE INDEX idx_sessions_professional_id ON sessions(professional_id);
CREATE INDEX idx_sessions_client_id ON sessions(client_id);
CREATE INDEX idx_sessions_scheduled_at ON sessions(professional_id, scheduled_at);
CREATE INDEX idx_sessions_conflict_check
    ON sessions(professional_id, scheduled_at, status)
    WHERE status = 'scheduled';    -- índice parcial — só sessões futuras

ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON sessions
    USING (
        professional_id = current_setting('app.current_tenant', TRUE)::uuid
    );
```

**Notas:**
- `price` congelado no momento do agendamento — mudança de preço não afeta sessões passadas
- `RESTRICT` em ambos `professional_id` e `client_id` — valor histórico e legal
- `recurrence_id SET NULL` — sessão persiste se a recorrência for encerrada
- Status: `scheduled` → `completed` | `cancelled` | `no_show`
- Sessões nunca são deletadas fisicamente — status cumpre a função de "remoção"
- Índice parcial `WHERE status = 'scheduled'` — verificação de conflito de horário só em sessões futuras (performance)

**SQLAlchemy model:** `agenda/models.py` → `Session` com `TimestampMixin`

---

## recurrences

```sql
CREATE TABLE recurrences (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    professional_id  UUID NOT NULL REFERENCES professionals(id) ON DELETE RESTRICT,
    client_id        UUID NOT NULL REFERENCES clients(id) ON DELETE RESTRICT,
    frequency        VARCHAR(20) NOT NULL,
    interval         INTEGER NOT NULL DEFAULT 1,
    day_of_week      SMALLINT,
    start_date       DATE NOT NULL,
    end_date         DATE,
    session_duration INTEGER NOT NULL,
    session_price    NUMERIC(10, 2) NOT NULL,
    is_active        BOOLEAN NOT NULL DEFAULT TRUE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_recurrence_frequency
        CHECK (frequency IN ('weekly', 'biweekly', 'monthly')),
    CONSTRAINT chk_recurrence_interval CHECK (interval > 0),
    CONSTRAINT chk_recurrence_day_of_week
        CHECK (day_of_week BETWEEN 0 AND 6),
    CONSTRAINT chk_recurrence_end_date
        CHECK (end_date IS NULL OR end_date > start_date)
);

CREATE INDEX idx_recurrences_professional_id ON recurrences(professional_id);
CREATE INDEX idx_recurrences_client_id ON recurrences(client_id);

ALTER TABLE recurrences ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON recurrences
    USING (
        professional_id = current_setting('app.current_tenant', TRUE)::uuid
    );
```

**Notas:**
- `DATE` para `start_date`/`end_date` — período de validade, não instante no tempo
- `end_date NULL` = recorrência sem fim definido
- `day_of_week` é nullable — obrigatório para `weekly`/`biweekly`, opcional para `monthly`
- Job `pgqueuer` lê recorrências ativas e gera sessões em janela de tempo futura
- `session_price` na recorrência define o preço padrão para sessões geradas automaticamente
- Soft delete via `is_active` — histórico de séries de sessões preservado

**SQLAlchemy model:** `agenda/models.py` → `Recurrence` com `TimestampMixin`

---

## whatsapp_conversations

```sql
CREATE TABLE whatsapp_conversations (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    professional_id  UUID NOT NULL REFERENCES professionals(id) ON DELETE RESTRICT,
    client_id        UUID REFERENCES clients(id) ON DELETE SET NULL,  -- nullable
    client_phone     VARCHAR(20) NOT NULL,
    status           VARCHAR(20) NOT NULL DEFAULT 'active',
    mode             VARCHAR(20) NOT NULL DEFAULT 'ai',
    started_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_message_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at         TIMESTAMPTZ,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_conversation_status
        CHECK (status IN ('active', 'resolved', 'waiting_professional')),
    CONSTRAINT chk_conversation_mode
        CHECK (mode IN ('ai', 'handoff'))
);

CREATE INDEX idx_conversations_professional_id
    ON whatsapp_conversations(professional_id);
CREATE INDEX idx_conversations_client_phone
    ON whatsapp_conversations(professional_id, client_phone);
CREATE INDEX idx_conversations_status
    ON whatsapp_conversations(professional_id, status)
    WHERE status = 'active';    -- índice parcial — só conversas abertas

ALTER TABLE whatsapp_conversations ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON whatsapp_conversations
    USING (
        professional_id = current_setting('app.current_tenant', TRUE)::uuid
    );
```

**Notas:**
- `client_id` nullable — contato pode ser de alguém não cadastrado no sistema ainda
- `client_phone` sempre presente — identifica o contato mesmo sem cadastro
- `mode`: `ai` = secretária responde automaticamente | `handoff` = profissional assumiu
- Dashboard mostra notificações e status — não espelha o chat (o WhatsApp faz isso)
- Histórico serve para: contexto da IA, escalação e auditoria LGPD
- `RESTRICT` em `professional_id` — conversas têm valor histórico e legal

**SQLAlchemy model:** `whatsapp/models.py` → `WhatsAppConversation` com `TimestampMixin`

---

## whatsapp_messages

```sql
CREATE TABLE whatsapp_messages (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id  UUID NOT NULL
                     REFERENCES whatsapp_conversations(id) ON DELETE CASCADE,
    direction        VARCHAR(10) NOT NULL,
    sender_type      VARCHAR(20) NOT NULL,
    content          TEXT NOT NULL,
    whatsapp_msg_id  VARCHAR(255) UNIQUE,   -- ID da Meta API — evita duplicatas de webhook
    sent_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_message_direction
        CHECK (direction IN ('inbound', 'outbound')),
    CONSTRAINT chk_message_sender_type
        CHECK (sender_type IN ('client', 'ai', 'professional'))
);

CREATE INDEX idx_messages_conversation_id ON whatsapp_messages(conversation_id);
```

**Notas:**
- Sem RLS — acesso sempre via `conversation_id`, controlado por join com a conversa (que tem RLS)
- Sem `updated_at` — mensagens são imutáveis após criação (sem mixin — usa `sent_at` próprio)
- `whatsapp_msg_id UNIQUE` — evita processar o mesmo webhook da Meta duas vezes (idempotência)
- `direction`: `inbound` = chegou do cliente | `outbound` = enviado pelo sistema
- `sender_type`: `client` | `ai` | `professional` — rastreabilidade de quem enviou cada mensagem
- `CASCADE` — mensagens sem conversa não têm sentido

**SQLAlchemy model:** `whatsapp/models.py` → `WhatsAppMessage` (sem mixin — usa `sent_at`)

---

## audit_logs

```sql
CREATE TABLE audit_logs (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    professional_id  UUID REFERENCES professionals(id) ON DELETE SET NULL,
    action           VARCHAR(100) NOT NULL,
    entity           VARCHAR(50) NOT NULL,
    entity_id        UUID,
    old_data         JSONB,
    new_data         JSONB,
    ip_address       VARCHAR(45),   -- VARCHAR(45) suporta IPv6
    user_agent       TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_logs_professional_id ON audit_logs(professional_id);
CREATE INDEX idx_audit_logs_entity ON audit_logs(entity, entity_id);
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at DESC);
```

**Notas:**
- Sem RLS — acesso controlado pelo service layer (registro de auditoria não deve ser filtrado por tenant)
- `SET NULL` em `professional_id` — log persiste mesmo se o profissional for deletado
- Sem `updated_at` — imutável por definição (`CreatedAtMixin`)
- `JSONB` para `old_data`/`new_data` — snapshot de antes/depois para compliance LGPD
- `VARCHAR(45)` para `ip_address` suporta endereços IPv6 (`2001:db8::1` tem 39 chars, com mapeamento IPv4 chega a 45)
- Índice `created_at DESC` — queries de auditoria são geralmente ordenadas pelo mais recente

**SQLAlchemy model:** `core/models.py` → `AuditLog` com `CreatedAtMixin`

---

## Convenções Globais

| Convenção | Valor | ADR |
|-----------|-------|-----|
| Primary Keys | `UUID DEFAULT gen_random_uuid()` | ADR-010 |
| Timestamps | `TIMESTAMPTZ NOT NULL DEFAULT NOW()` | ADR-010 |
| Valores monetários | `NUMERIC(10, 2)` | ADR-010 |
| Strings sem limite | `TEXT` | ADR-010 |
| Booleans | `BOOLEAN NOT NULL DEFAULT <valor>` | ADR-010 |
| Soft delete | `is_active BOOLEAN NOT NULL DEFAULT TRUE` | ADR-009 |
| Lógica de negócio | Python, nunca PL/pgSQL | ADR-004 |
| Constraints de integridade | Banco (`CHECK`, `UNIQUE`) + Pydantic | — |