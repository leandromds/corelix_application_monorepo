# Secretária Digital — Architecture & Project Context

> Documento vivo. Atualizar sempre que uma decisão técnica relevante for tomada.
> Usar para restaurar contexto em novas conversas com o Claude (chat ou API).

---

## 1. O que é o produto

SaaS B2B de **secretária digital inteligente** para profissionais autônomos de saúde e bem-estar (psicólogos, terapeutas, massagistas, personal trainers, manicures e similares).

**Problema que resolve:** esses profissionais acumulam a função técnica com toda a carga administrativa de uma secretaria — agendamentos, cobranças, comunicação com clientes, emissão de documentos. O produto automatiza essa carga usando IA de forma transversal, não como feature isolada.

**Diferencial central:** não é uma automação de processos — é uma secretária com inteligência, que observa padrões, gera insights e se comunica de forma humanizada.

---

## 2. Usuário principal

O próprio profissional autônomo — que é ao mesmo tempo prestador do serviço e gestor do negócio. Sem familiaridade técnica avançada.

**Escopo de dados armazenados:** apenas dados administrativos (nome, telefone, e-mail, histórico de sessões e valores). Nenhum dado clínico ou prontuário.

---

## 3. Stack tecnológica

| Camada | Tecnologia | Observação |
|---|---|---|
| Frontend | React + TypeScript + Vite | Dev tem 10 anos de experiência |
| Backend | Python + FastAPI (async) | Dev aprendendo — decisões sempre explicadas |
| ORM | SQLAlchemy (async) + Alembic | Migrations versionadas |
| Banco | PostgreSQL | Multi-tenant via Row-level + RLS |
| Auth | JWT (15min) + Refresh Token (30 dias) | Sem biblioteca de auth de terceiros |
| Fila de jobs | pgqueuer | Jobs em cima do PostgreSQL, sem Redis |
| Testes | pytest + pytest-asyncio + httpx + pytest-postgresql + factory-boy | TDD obrigatório em todos os módulos |
| WhatsApp | Meta Cloud API (Embedded Signup — Tech Provider) | Cada profissional conecta seu próprio número |
| IA | Anthropic API (Claude Sonnet) | Uso transversal e econômico |
| Hospedagem | Railway | PostgreSQL incluso, deploy via git |

**Princípio:** evitar ferramentas pagas de terceiros salvo necessidade avaliada e justificada.

---

## 4. Decisões arquiteturais tomadas

### 4.1 Multi-tenancy: Row-level + RLS (dupla barreira)

**Camada 1 — Aplicação:** toda query filtra por professional_id explicitamente.
**Camada 2 — Banco (RLS):** PostgreSQL aplica policy de isolamento automaticamente.

O backend seta o tenant no início de cada request:
```python
await db.execute(
    "SET LOCAL app.current_tenant = :tenant_id",
    {"tenant_id": str(current_user.professional_id)}
)
```

### 4.2 Autenticação: JWT + Refresh Token

- **Access Token:** JWT assinado, expira em 15 minutos, retornado no body da resposta
- **Refresh Token:** UUID armazenado no banco como SHA-256 hash, enviado e recebido via **HttpOnly cookie** (secure, samesite=strict) — nunca exposto ao JavaScript
- Logout global: revoga todos os refresh_tokens do profissional no banco
- CORS: `allow_credentials=True` com origens explícitas — nunca wildcard `*`

### 4.2.1 RLS — chamada explícita via TenantSession

`set_tenant_context()` é chamado explicitamente via FastAPI `Depends`, não via middleware automático. Rotas sem tenant (login, refresh token) não ativam RLS.

```python
# Dependency para rotas protegidas com isolamento de tenant
async def get_tenant_db(
    current_user: Professional = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AsyncGenerator[AsyncSession, None]:
    await set_tenant_context(db, current_user.id)
    yield db
```

### 4.3 TDD — ciclo obrigatório

Red (teste falha) → Green (mínimo de código) → Refactor

Ferramentas: pytest + pytest-asyncio + httpx AsyncClient + pytest-postgresql + factory-boy

Estrutura de testes espelhada por módulo:
```
api/tests/
    conftest.py
    auth/
        test_router.py
        test_service.py
        test_repository.py
    clients/
    agenda/
```

### 4.4 Arquitetura do backend: Feature-based com 3 camadas

```
router → service → repository → banco
              ↓
         ai/service
              ↓
      whatsapp/service
```

Router nunca acessa o banco. Repository nunca contém regra de negócio. Service nunca sabe que existe HTTP.

### 4.5 WhatsApp — modelo de integração

- Cada profissional conecta seu próprio número via Embedded Signup (OAuth da Meta)
- O número da plataforma é exclusivo para o bot institucional da Secretária Digital
- A plataforma precisa estar cadastrada como Tech Provider na Meta
- Cloud API opera em modo dual: profissional continua usando WhatsApp normalmente no celular
- Campo mode em whatsapp_conversations controla se IA ou profissional está respondendo
- Dashboard mostra notificações e status — não espelha o chat (o WhatsApp já faz isso)

### 4.6 Convenções de modelagem do banco

- Toda tabela de tenant tem professional_id como FK e RLS ativado
- ON DELETE CASCADE: filho sem valor sem o pai (refresh_tokens, availability_slots, blocked_periods)
- ON DELETE RESTRICT: filho com valor histórico próprio (clients, sessions, recurrences)
- ON DELETE SET NULL: vínculo pode ser removido sem perder o registro (recurrence_id em sessions, client_id em conversations)
- Constraints de integridade no banco (CHECK, UNIQUE) E no Pydantic — defense in depth
- Lógica de negócio no Python, nunca em PL/pgSQL — para manter testabilidade

---

### 4.7 Gerenciamento de dependências: Poetry

Python deps gerenciadas com Poetry (`pyproject.toml`). Motivos:
- Lock file determinístico (`poetry.lock`) — builds reproduzíveis em qualquer máquina
- Separação limpa entre deps de produção e dev (`[tool.poetry.group.dev.dependencies]`)
- Railway detecta `pyproject.toml` automaticamente e instala as deps
- Configuração centralizada: `ruff`, `mypy`, `pytest` todos no mesmo arquivo

### 4.8 RLS: `set_tenant_context()` explícito, não middleware automático

A função `set_tenant_context()` em `core/database.py` é chamada explicitamente pelo router após validar o JWT — não por um middleware automático. Razão: endpoints públicos (login, registro, webhook) não têm tenant; um middleware automático precisaria de lista de exceções propensa a bugs de segurança.

Implementação: `core/deps.py` (a criar) expõe dois tipos de sessão via FastAPI `Depends`:
- `DbSession` → `get_db()` puro, para rotas públicas
- `TenantSession` → `get_db()` + validação JWT + `set_tenant_context()`, para rotas protegidas

---

## 5. Estrutura de pastas

```
application/                          → raiz do monorepo
├── apps/
│   ├── web/                          → React 18 + TypeScript + Vite 5
│   │   ├── src/
│   │   │   ├── components/           → componentes reutilizáveis
│   │   │   ├── pages/                → páginas da aplicação
│   │   │   ├── hooks/                → hooks customizados
│   │   │   ├── services/             → chamadas à API (axios)
│   │   │   ├── types/                → tipos TypeScript
│   │   │   ├── App.tsx
│   │   │   ├── main.tsx
│   │   │   └── vite-env.d.ts
│   │   ├── index.html
│   │   ├── vite.config.ts            → proxy /api → localhost:8000
│   │   ├── tsconfig.json
│   │   └── package.json
│   │
│   └── api/                          → Python + FastAPI
│       ├── auth/                     → login, refresh token, logout
│       │   ├── router.py
│       │   ├── service.py
│       │   ├── repository.py
│       │   └── schemas.py
│       ├── professionals/            → perfil e configurações
│       ├── clients/                  → gestão de clientes (RLS)
│       ├── agenda/                   → sessões, disponibilidade, recorrências (RLS)
│       ├── reports/                  → relatórios + insights da IA
│       ├── whatsapp/                 → webhook + conversações (RLS)
│       ├── ai/
│       │   ├── service.py            → AIService: complete(), complete_with_history()
│       │   └── prompts.py            → PROMPTS registry centralizado e versionado
│       ├── core/
│       │   ├── config.py             → Settings via pydantic-settings, lê .env
│       │   ├── database.py           → engine async, pool de conexões, get_db(), set_tenant_context(), Base
│       │   ├── security.py           → hash_password, verify_password, JWT, refresh token
│       │   ├── exceptions.py         → AppException e hierarquia completa
│       │   ├── deps.py               → ⚠️ a criar: get_current_user, TenantSession, DbSession
│       │   └── middleware.py         → ⚠️ a criar: rate limiting, request ID, audit
│       ├── tests/
│       │   ├── conftest.py           → fixtures: test_engine, db_session, client (AsyncClient)
│       │   └── core/
│       │       └── test_security.py  → 17 testes TDD (fase Green — todos passando)
│       ├── alembic/
│       │   ├── env.py                → async-compatible migration environment
│       │   ├── script.py.mako        → template para arquivos de migração
│       │   └── versions/             → arquivos de migração (vazio — ⚠️ a criar)
│       ├── alembic.ini
│       ├── main.py                   → app FastAPI, CORS, lifespan, exception handlers, /health
│       ├── pyproject.toml            → dependências Poetry, ruff, mypy, pytest
│       └── README.md                 → instruções de setup e execução
│
├── docker-compose.yml                → PostgreSQL 16 Alpine + healthcheck + volume persistente
├── .env.example                      → todas as variáveis documentadas (sem valores reais)
├── .gitignore
├── ARCHITECTURE.md
├── CLAUDE_CONTEXT.md
└── PROJECT_INSTRUCTIONS.md
```

---

## 6. Schema do banco de dados

### Visão geral dos relacionamentos

```
professionals (1)
    ├── refresh_tokens (N)              [CASCADE]
    ├── clients (N)                     [RESTRICT]
    ├── availability_slots (N)          [CASCADE]
    ├── blocked_periods (N)             [CASCADE]
    ├── recurrences (N)                 [RESTRICT]
    ├── whatsapp_conversations (N)      [RESTRICT]
    │       └── whatsapp_messages (N)   [CASCADE]
    └── sessions (N)
            ├── clients (N)             [RESTRICT]
            └── recurrences (N)         [SET NULL]

audit_logs → professionals              [SET NULL] (sem RLS)
```

---

### professionals
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
    whatsapp_access_token     TEXT,
    whatsapp_connected_at     TIMESTAMPTZ,
    whatsapp_token_expires_at TIMESTAMPTZ,
    is_active                 BOOLEAN NOT NULL DEFAULT TRUE,
    created_at                TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```
Decisões: bio usada pela IA para apresentar o profissional. whatsapp_access_token armazenado criptografado. Job renova token antes de expirar. Profissional pode usar o sistema antes de conectar o WhatsApp.

---

### refresh_tokens
```sql
CREATE TABLE refresh_tokens (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    professional_id  UUID NOT NULL REFERENCES professionals(id) ON DELETE CASCADE,
    token_hash       VARCHAR(255) NOT NULL UNIQUE,
    device_info      VARCHAR(255),
    expires_at       TIMESTAMPTZ NOT NULL,
    revoked          BOOLEAN NOT NULL DEFAULT FALSE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_refresh_tokens_professional_id ON refresh_tokens(professional_id);
CREATE INDEX idx_refresh_tokens_token_hash ON refresh_tokens(token_hash);
```
Decisões: token_hash SHA-256 — nunca armazenar token puro. Sem updated_at — imutável. Job noturno limpa expirados.

---

### clients
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
    USING (professional_id = current_setting('app.current_tenant')::uuid);
```
Decisões: RESTRICT — cliente tem valor histórico. opt_in campos obrigatórios para LGPD e Meta. Validação de canal mínimo no service.py.

---

### availability_slots
```sql
CREATE TABLE availability_slots (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    professional_id  UUID NOT NULL REFERENCES professionals(id) ON DELETE CASCADE,
    day_of_week      SMALLINT NOT NULL,
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
    USING (professional_id = current_setting('app.current_tenant')::uuid);
```
Decisões: TIME em vez de TIMESTAMPTZ — padrão semanal, não momento específico. 0=domingo a 6=sábado. Múltiplos blocos por dia permitidos.

---

### blocked_periods
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
CREATE INDEX idx_blocked_periods_range ON blocked_periods(professional_id, start_datetime, end_datetime);
ALTER TABLE blocked_periods ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON blocked_periods
    USING (professional_id = current_setting('app.current_tenant')::uuid);
```
Decisões: notify_clients default TRUE — opt-out, não opt-in. Índice composto acelera verificação de conflito de agenda.

---

### sessions
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
    WHERE status = 'scheduled';
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON sessions
    USING (professional_id = current_setting('app.current_tenant')::uuid);
```
Decisões: price na sessão — congela valor no momento do agendamento. RESTRICT nos dois lados — valor histórico e legal. Índice parcial WHERE status='scheduled' — verificação de conflito só em sessões futuras.

---

### recurrences
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
    CONSTRAINT chk_recurrence_frequency CHECK (frequency IN ('weekly', 'biweekly', 'monthly')),
    CONSTRAINT chk_recurrence_interval CHECK (interval > 0),
    CONSTRAINT chk_recurrence_day_of_week CHECK (day_of_week BETWEEN 0 AND 6),
    CONSTRAINT chk_recurrence_end_date CHECK (end_date IS NULL OR end_date > start_date)
);
CREATE INDEX idx_recurrences_professional_id ON recurrences(professional_id);
CREATE INDEX idx_recurrences_client_id ON recurrences(client_id);
ALTER TABLE recurrences ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON recurrences
    USING (professional_id = current_setting('app.current_tenant')::uuid);
```
Decisões: DATE para start/end — período de validade, não momento. end_date NULL = sem fim. day_of_week opcional para recorrências mensais. Job pgqueuer gera sessões em janelas de tempo.

---

### whatsapp_conversations + whatsapp_messages
```sql
CREATE TABLE whatsapp_conversations (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    professional_id  UUID NOT NULL REFERENCES professionals(id) ON DELETE RESTRICT,
    client_id        UUID REFERENCES clients(id) ON DELETE SET NULL,
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
    CONSTRAINT chk_conversation_mode CHECK (mode IN ('ai', 'handoff'))
);

CREATE TABLE whatsapp_messages (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id  UUID NOT NULL REFERENCES whatsapp_conversations(id) ON DELETE CASCADE,
    direction        VARCHAR(10) NOT NULL,
    sender_type      VARCHAR(20) NOT NULL,
    content          TEXT NOT NULL,
    whatsapp_msg_id  VARCHAR(255),
    sent_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_message_direction CHECK (direction IN ('inbound', 'outbound')),
    CONSTRAINT chk_message_sender_type CHECK (sender_type IN ('client', 'ai', 'professional'))
);

CREATE INDEX idx_conversations_professional_id ON whatsapp_conversations(professional_id);
CREATE INDEX idx_conversations_client_phone ON whatsapp_conversations(professional_id, client_phone);
CREATE INDEX idx_conversations_status ON whatsapp_conversations(professional_id, status)
    WHERE status = 'active';
CREATE INDEX idx_messages_conversation_id ON whatsapp_messages(conversation_id);
ALTER TABLE whatsapp_conversations ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON whatsapp_conversations
    USING (professional_id = current_setting('app.current_tenant')::uuid);
```
Decisões: client_id opcional — contato pode ser de alguém não cadastrado ainda. mode controla handoff. whatsapp_msg_id evita processar webhook duplicado. Histórico para: contexto da IA, escalação e auditoria LGPD. Dashboard não espelha o chat — mostra só notificações e status.

---

### audit_logs
```sql
CREATE TABLE audit_logs (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    professional_id  UUID REFERENCES professionals(id) ON DELETE SET NULL,
    action           VARCHAR(100) NOT NULL,
    entity           VARCHAR(50) NOT NULL,
    entity_id        UUID,
    old_data         JSONB,
    new_data         JSONB,
    ip_address       VARCHAR(45),
    user_agent       TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_audit_logs_professional_id ON audit_logs(professional_id);
CREATE INDEX idx_audit_logs_entity ON audit_logs(entity, entity_id);
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at DESC);
```
Decisões: sem updated_at — imutável por definição. Sem RLS — acesso controlado pelo service layer. JSONB para snapshot antes/depois. VARCHAR(45) para IP suporta IPv6.

---

## 7. Módulos e funcionalidades

### MVP (8 semanas)

| Módulo | Funcionalidades principais |
|---|---|
| auth | Cadastro, login, logout, refresh token, logout global |
| professionals | Perfil completo com bio, conexão WhatsApp via Embedded Signup |
| clients | CRUD, histórico de sessões, gestão de opt-in |
| agenda | Sessões únicas e recorrentes, disponibilidade, bloqueios, cancelamento em massa |
| reports | Relatório de cobrança por cliente/período com observações da IA |
| whatsapp | Webhook, respostas via IA, modo handoff |
| ai | IA transversal: CRM, relatório, agenda, dashboard, WhatsApp |
| dashboard | Agenda do dia, status do bot, insights da IA, notificações |

### Pós-MVP

- Disparo automático de documentos fiscais
- Emissão de NFS-e
- Gateway de pagamento (Pix e cartão)
- App mobile

---

## 8. IA — Uso transversal

Princípio: a IA entra onde um assistente humano experiente diria "repara nesse detalhe". Pontual, intencional, nunca decorativo.

| Ponto | Como a IA atua |
|---|---|
| WhatsApp | Responde usando bio do profissional como contexto |
| Agenda | Sugere horários com base no padrão histórico |
| Relatório | Observações contextuais (faltas, cancelamentos) |
| CRM | Padrões no histórico, alertas de comportamento |
| Dashboard | Insights pontuais para o profissional |
| Lembretes | Personaliza tom e conteúdo por perfil do cliente |

Toda saída da IA é identificada como sugestão. Prompts centralizados em ai/prompts.py.

---

## 9. Compliance e segurança

- LGPD: consentimento no cadastro, política de privacidade, direito de exclusão e portabilidade
- Criptografia: TLS 1.2+ em trânsito, AES-256 em repouso (incluindo whatsapp_access_token)
- Logs de auditoria: toda alteração sensível registrada em audit_logs
- WhatsApp: opt-in/opt-out gerenciados, conformidade com políticas da Meta
- RLS: isolamento de tenant no nível do banco

---

## 10. Status do projeto

```
✅ Levantamento de requisitos
✅ Decisões arquiteturais (multi-tenancy, auth, estrutura, TDD)
✅ Schema do banco de dados
   ✅ professionals
   ✅ refresh_tokens
   ✅ clients
   ✅ availability_slots
   ✅ blocked_periods
   ✅ sessions
      ✅ recurrences
   ✅ whatsapp_conversations + whatsapp_messages
   ✅ audit_logs
✅ Setup do monorepo e ambiente
   ✅ docker-compose.yml (PostgreSQL 16 Alpine + healthcheck)
   ✅ .env.example (todas as variáveis documentadas)
   ✅ apps/api — pyproject.toml (Poetry), main.py, alembic/
   ✅ core/ — config.py, database.py, security.py, exceptions.py
   ✅ Skeletons: auth, professionals, clients, agenda, reports, whatsapp
   ✅ ai/service.py e ai/prompts.py
   ✅ tests/conftest.py + tests/core/test_security.py (17 testes TDD)
   ✅ apps/web — React 18 + Vite 5 + TypeScript scaffold
✅ Modelos SQLAlchemy + Migration inicial + RLS policies
   ✅ core/mixins.py (TimestampMixin, CreatedAtMixin)
   ✅ professionals/models.py, auth/models.py, clients/models.py
   ✅ agenda/models.py (4 models), whatsapp/models.py (2 models)
   ✅ core/models.py (AuditLog)
   ✅ alembic/versions/56f1e41b5d4c_initial_schema.py (aplicada)
   ✅ RLS ativo em 6 tabelas (policies adicionadas manualmente)
✅ core/deps.py — DbSession, TenantSession, CurrentProfessionalId
   ✅ tests/core/test_deps.py (6 testes — Green)
   ✅ tests/{professionals,auth,clients}/test_model.py (Red — aguardam DB)
⬜ Autenticação (backend + frontend)   ← próximo passo
⬜ Módulo professionals
⬜ Módulo clients
⬜ Módulo agenda
⬜ Módulo reports + IA no relatório
⬜ WhatsApp webhook + IA conversacional
⬜ Dashboard com insights
⬜ Segurança, LGPD e auditoria
⬜ Testes e deploy no Railway
```

---

## 11. Convenções do projeto

- Idioma do código: inglês
- Idioma da documentação: português
- Commits: conventional commits (feat:, fix:, chore:, docs:)
- Branches: main → develop → feature/nome-da-feature
- Variáveis de ambiente: sempre em .env, nunca commitar


---

## 12. Setup — arquivos e decisões técnicas

### O que foi implementado no setup

| Arquivo | Responsabilidade |
|---|---|
| `docker-compose.yml` | PostgreSQL 16 Alpine com healthcheck e volume persistente |
| `.env.example` | Todas as variáveis documentadas com descrição |
| `apps/api/pyproject.toml` | Deps de produção e dev com Poetry; config ruff, mypy e pytest |
| `apps/api/main.py` | App FastAPI: CORS, lifespan (startup/shutdown), 3 exception handlers, `/health` |
| `core/config.py` | `Settings` via pydantic-settings — fail-fast se variável obrigatória ausente |
| `core/database.py` | Engine async, pool de conexões, `get_db()`, `set_tenant_context()`, `Base` |
| `core/security.py` | `hash_password/verify_password` (bcrypt), JWT (HS256), `generate_refresh_token` (SHA-256) |
| `core/exceptions.py` | `AppException` + 7 subclasses com HTTP status codes corretos |
| `ai/service.py` | `AIService`: `complete()` para single-turn, `complete_with_history()` para conversas |
| `ai/prompts.py` | `PROMPTS` registry: `whatsapp_secretary`, `report_insights` |
| `tests/conftest.py` | Fixtures: `test_engine` (session-scoped), `db_session` (rollback por teste), `client` |
| `tests/core/test_security.py` | 17 testes TDD escritos na fase Red, implementados na fase Green |
| `alembic/env.py` | Ambiente async-compatible para migrations (usa `asyncio.run`) |

### Como rodar o projeto localmente

```bash
# 1. Subir PostgreSQL
docker-compose up -d

# 2. Instalar dependências Python
cd apps/api && poetry install

# 3. Configurar variáveis de ambiente
cp .env.example .env  # editar os valores

# 4. Rodar testes de setup (devem todos passar)
poetry run pytest tests/core/test_security.py -v

# 5. Iniciar a API
poetry run uvicorn main:app --reload --port 8000

# 6. Em outro terminal — frontend
cd apps/web && npm install && npm run dev
```

### Próximo passo imediato

Implementar o módulo de **autenticação** — pré-requisito para todos os demais módulos.

**Backend (TDD em cada etapa):**
1. `auth/repository.py` — CRUD na tabela `refresh_tokens`
2. `auth/service.py` — `login()`, `refresh_access_token()`, `logout()`, `logout_all()`
3. `professionals/repository.py` — `find_by_email()`, `find_by_id()`, `create()`
4. `professionals/service.py` — `register()`, validação de email único
5. `auth/router.py` — `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout`
6. `professionals/router.py` — `POST /professionals/register`, `GET /professionals/me`

**Frontend:**
7. `AuthContext` + `useAuth` hook
8. Interceptor axios — injeta Bearer, renova no 401
9. Páginas de Login e Registro
10. Proteção de rotas


---

## 13. Banco de dados — modelos, migration e decisões

### Modelos criados

| Arquivo | Model(s) | Mixin |
|---|---|---|
| `professionals/models.py` | `Professional` | `TimestampMixin` |
| `auth/models.py` | `RefreshToken` | `CreatedAtMixin` (sem `updated_at`) |
| `clients/models.py` | `Client` | `TimestampMixin` |
| `agenda/models.py` | `AvailabilitySlot`, `Recurrence`, `Session` | `TimestampMixin` |
| `agenda/models.py` | `BlockedPeriod` | `CreatedAtMixin` (sem `updated_at`) |
| `whatsapp/models.py` | `WhatsAppConversation` | `TimestampMixin` |
| `whatsapp/models.py` | `WhatsAppMessage` | Nenhum — usa `sent_at` próprio |
| `core/models.py` | `AuditLog` | `CreatedAtMixin` (sem RLS, sem `updated_at`) |

### Padrão de mixins (core/mixins.py)

- `TimestampMixin` → `created_at` + `updated_at`: tabelas editáveis
- `CreatedAtMixin` → `created_at` apenas: registros imutáveis (`refresh_tokens`, `blocked_periods`, `audit_logs`)
- `Base` define apenas `id` UUID — timestamps são opt-in via mixin

### Decisão: sem `relationship()` nos models

Apenas colunas FK. Navegação via queries explícitas nos repositories.
Motivos: elimina imports circulares, sem lazy-loading, respeita arquitetura em camadas.

### RLS adicionada manualmente na migration `56f1e41b5d4c`

Tabelas com RLS: `clients`, `availability_slots`, `blocked_periods`, `recurrences`, `sessions`, `whatsapp_conversations`

```sql
ALTER TABLE {tabela} ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON {tabela}
  USING (professional_id = current_setting('app.current_tenant')::uuid);
```

### core/deps.py

```python
DbSession             = Annotated[AsyncSession, Depends(get_db)]           # rotas públicas
CurrentProfessionalId = Annotated[str, Depends(get_current_professional_id)]
TenantSession         = Annotated[AsyncSession, Depends(get_tenant_db)]    # rotas protegidas
```

**Regra crítica:** nunca chamar `session.commit()` no service layer. O `SET LOCAL` é válido apenas na transação corrente — um commit manual antes do fim do request desativa o RLS silenciosamente.
