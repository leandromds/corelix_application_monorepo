# Corelix — Secretaria Digital

Plataforma SaaS para profissionais de saúde autônomos (psicólogos, personal trainers, etc.) gerenciarem agenda, clientes, finanças e atendimento via WhatsApp com IA.

## Stack

| Camada | Tecnologia |
|---|---|
| Backend | FastAPI + asyncpg + PostgreSQL 16 (RLS multi-tenant) |
| Frontend | React 18 + Vite + TanStack Query + React Hook Form + Zod |
| Background jobs | pgqueuer |
| Observabilidade | Glitchtip (Sentry-compatible) + PostHog |
| Infra | Docker Compose + Coolify (produção) |

---

## Rodando localmente

### Pré-requisitos

- Docker + Docker Compose
- Python 3.12+
- Node.js 20+
- Poetry (`pip install poetry`)

---

### 1. Banco de dados

```bash
docker compose -f docker-compose.dev.yml up -d
```

Sobe o PostgreSQL 16 na porta `5432`. Aguarde o healthcheck ficar verde antes de continuar.

---

### 2. Backend

```bash
cd apps/api
```

**Configurar variáveis de ambiente:**

```bash
cp .env.example .env
```

Edite `.env` e preencha obrigatoriamente:

```env
SECRET_KEY=<string aleatória longa>
ENCRYPTION_KEY=<chave Fernet>
```

Gere os valores:

```bash
# SECRET_KEY
openssl rand -hex 32

# ENCRYPTION_KEY
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

**Instalar dependências, aplicar migrations e rodar:**

```bash
poetry install
poetry run alembic upgrade head
poetry run uvicorn main:app --reload --port 8000
```

API disponível em `http://localhost:8000` — docs em `http://localhost:8000/docs`.

---

### 3. Frontend

```bash
cd apps/web
```

**Configurar variáveis de ambiente:**

```bash
cp .env.example .env
```

O arquivo padrão já funciona para desenvolvimento sem nenhuma alteração.

**Instalar dependências e rodar:**

```bash
npm install
npm run dev
```

Acesse **http://localhost:5173** — o Vite proxeia `/api` automaticamente para `localhost:8000`.

---

### 4. Terminal Chat (testar o fluxo de IA sem WhatsApp real)

O `TerminalProvider` permite simular uma conversa de cliente via WhatsApp diretamente
no terminal — sem credenciais Meta/Twilio, sem rede externa.

**Pré-requisitos:**
- Postgres no ar e migrações aplicadas (`alembic upgrade head`)
- `.env` configurado com `AI_API_KEY` real e `AI_BASE_URL` apontando para um provider compatível
- `WHATSAPP_FORCE_TERMINAL=true` no `.env`

**Gerar `ENCRYPTION_KEY` (obrigatória mesmo sem WhatsApp real):**

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

**Criar um profissional e obter o UUID:**

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "dev@example.com",
    "password": "senha1234",
    "full_name": "Dev Local"
  }' | python3 -m json.tool
```

Copie o campo `id` da resposta — esse é o `<uuid>` do profissional.

**Iniciar o chat:**

```bash
cd apps/api
poetry run python -m whatsapp.devtools.terminal_chat \
  --professional-id <uuid> \
  --client-phone +5511999999999
```

Comandos internos disponíveis durante o chat:
- `/reset` — apaga o histórico da conversa atual
- `/exit` — encerra o chat

> **Nota:** `AI_BASE_URL` aceita qualquer provider OpenAI-compatible: OpenAI, OpenRouter,
> DeepSeek, Groq ou LiteLLM proxy — sem alteração de código.

---

### Ordem de inicialização

```
1. docker compose  →  2. uvicorn  →  3. npm run dev
```

---

## Testes

**Backend:**

```bash
cd apps/api
poetry run pytest
```

**Frontend:**

```bash
cd apps/web
npm test
```

---

## Estrutura do projeto

```
corelix_application_monorepo/
├── apps/
│   ├── api/                  # FastAPI
│   │   ├── auth/
│   │   ├── agenda/
│   │   ├── clients/
│   │   ├── reports/
│   │   ├── whatsapp/
│   │   ├── ai/
│   │   ├── jobs/
│   │   └── core/
│   └── web/                  # React + Vite
│       └── src/
│           ├── features/     # agenda, clients, reports, settings, whatsapp
│           ├── components/   # layout, shared, ui (design system)
│           ├── pages/        # Dashboard, Login, Register
│           └── hooks/
├── docs/                     # ADRs, domínios, STATE.json
├── docker-compose.yml        # produção (Coolify)
└── docker-compose.dev.yml    # desenvolvimento (postgres local)
```

---

## Gitflow

| Branch | Propósito |
|---|---|
| `main` | Produção — apenas releases estáveis |
| `develop` | Integração contínua — PRs de feature entram aqui |
| `feature/*` | Novas funcionalidades |
| `fix/*` | Correções |
| `chore/*` | Infraestrutura, CI, docs |

---

## Variáveis de ambiente

### Backend (`apps/api/.env`)

| Variável | Obrigatória | Descrição |
|---|---|---|
| `DATABASE_URL` | ✅ | URL de conexão asyncpg |
| `SECRET_KEY` | ✅ | Chave JWT (openssl rand -hex 32) |
| `ENCRYPTION_KEY` | ✅ | Chave Fernet para tokens WhatsApp |
| `ALGORITHM` | — | Padrão: `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | — | Padrão: `15` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | — | Padrão: `30` |
| `AI_API_KEY` | — | Chave OpenAI-compatible (IA secretária) |
| `AI_BASE_URL` | — | Padrão: `https://api.openai.com/v1` |
| `WHATSAPP_VERIFY_TOKEN` | — | Token de verificação do webhook Meta |
| `WHATSAPP_APP_SECRET` | — | App secret da Meta |
| `WHATSAPP_FORCE_TERMINAL` | — | `true` para usar TerminalProvider (dev/demo) — nunca `true` em produção |
| `GLITCHTIP_DSN` | — | DSN Glitchtip (deixe vazio em dev) |

### Frontend (`apps/web/.env`)

| Variável | Obrigatória | Descrição |
|---|---|---|
| `VITE_API_URL` | — | Padrão: `/api/v1` (proxy Vite em dev) |
| `VITE_GLITCHTIP_DSN` | — | DSN Glitchtip (deixe vazio em dev) |
| `VITE_POSTHOG_KEY` | — | Chave PostHog (deixe vazio em dev) |
