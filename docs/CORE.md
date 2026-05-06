# Corelix — Core Context

> Arquivo sempre carregado. Máximo ~150 linhas. Para detalhes, use `STATE.json`, `decisions/` e `domains/`.

---

## Produto

SaaS B2B de **secretária digital inteligente** para profissionais autônomos de saúde e bem-estar
(psicólogos, terapeutas, massagistas, personal trainers, manicures e similares).

**Problema:** esses profissionais acumulam função técnica + carga administrativa (agendamentos,
cobranças, comunicação). O produto automatiza essa carga com IA de forma transversal.

**Diferencial:** não é automação de processos — é uma secretária com inteligência que observa padrões,
gera insights e se comunica de forma humanizada. IA não é módulo isolado — permeia o produto.

**Escopo de dados:** apenas administrativos (nome, telefone, e-mail, histórico de sessões e valores).
**Sem dados clínicos ou prontuário.**

---

## Stack

| Camada      | Tecnologia                                          |
|-------------|-----------------------------------------------------|
| Frontend    | React 18 + TypeScript + Vite 5                      |
| Backend     | Python 3.11+ + FastAPI (async)                      |
| ORM         | SQLAlchemy 2.x (async) + Alembic                    |
| Banco       | PostgreSQL 16                                       |
| Auth        | JWT (15min) + Refresh Token no banco (30 dias)      |
| Jobs        | pgqueuer (sem Redis)                                |
| Testes      | pytest + pytest-asyncio + httpx + factory-boy       |
| WhatsApp    | Meta Cloud API — Embedded Signup (Tech Provider)    |
| IA          | Anthropic API (Claude Sonnet)                       |
| Hospedagem  | Hostinger VPS KVM2 + Coolify self-hosted                    |
| Deps Python | Poetry (pyproject.toml)                             |

---

## Arquitetura Backend (feature-based)

```
router.py → service.py → repository.py → banco
                ↓
           ai/service.py
                ↓
       whatsapp/service.py
```

Módulos: `auth` / `professionals` / `clients` / `agenda` / `reports` / `whatsapp` / `ai` / `core`

**Regras invioláveis de dependência:**
- Router: só HTTP — recebe request, chama service, retorna response. Nunca acessa banco.
- Service: regras de negócio, validações, orquestração. Nunca sabe que existe HTTP.
- Repository: só banco — queries ORM, nada mais. Nunca contém regra de negócio.
- Nunca pular camada.

---

## Decisões Arquiteturais Fixas

> Não sugerir alternativas salvo solicitação explícita. Ver `decisions/` para o raciocínio completo.

| # | Decisão | ADR |
|---|---------|-----|
| 1 | Multi-tenancy: Row-level isolation + RLS (dupla barreira) | ADR-001 |
| 2 | Auth: JWT (15min) + Refresh Token HttpOnly cookie (30d) | ADR-002 |
| 3 | RLS via `TenantSession` (Depends explícito), nunca middleware | ADR-003 |
| 4 | Arquitetura feature-based com 3 camadas obrigatórias | ADR-004 |
| 5 | TDD obrigatório: Red → Green → Refactor em todos os módulos | ADR-005 |
| 6 | Sem `relationship()` nos models — navegação via queries explícitas | ADR-006 |
| 7 | Nunca `session.commit()` no service layer | ADR-007 |
| 8 | `SET LOCAL` via f-string (PostgreSQL não suporta bind params em SET) | ADR-008 |
| 9 | Soft delete (`is_active`) em entidades com valor histórico | ADR-009 |
| 10 | UUID PKs, TIMESTAMPTZ em datas, NUMERIC(10,2) para moeda | ADR-010 |
| 11 | WhatsApp: cada profissional usa seu próprio número via Embedded Signup | ADR-011 |
| 12 | Anti-enumeração: mesma mensagem de erro para email/senha inválidos | ADR-012 |
| 13 | bcrypt fixado em `<4` (passlib 1.7.4 incompatível com bcrypt 4.x+) | ADR-013 |
| 14 | Token frontend em variável de módulo — nunca localStorage/state/sessionStorage | ADR-014 |
| 15 | `isLoading: true` no mount do AuthContext até restore de sessão terminar | ADR-015 |
| 16 | Fila de requests durante refresh de token (evita N refreshes simultâneos) | ADR-016 |
| 17 | `secure=settings.is_production` no cookie (False em dev, True em prod) | ADR-017 |
| 18 | CORS com `allow_credentials=True` e origens explícitas (nunca wildcard) | ADR-018 |
| 19 | Jobs via pgqueuer (sem Redis) | ADR-019 |
| 20 | Poetry para gerenciamento de dependências Python | ADR-020 |
| 21 | `test_rls_user` (NOLOGIN, sem BYPASSRLS) para testes de isolamento RLS | ADR-021 |
| 22 | Gitflow: `main` ← PR ← `develop` ← PR ← `feature/*` | ADR-022 |
| 23 | Pydantic v2 `model_validator` + `jsonable_encoder` no exception handler | ADR-023 |
| 24 | PATCH semântico: `exclude_unset=True` em vez de `exclude_none=True` | ADR-024 |
| 25 | Infra: Hostinger KVM 2 + Coolify self-hosted | ADR-025 |
| 26 | Observabilidade: Uptime Kuma + Glitchtip + PostHog Cloud | ADR-026 |
| 27 | Containerização: Docker Compose (API + worker separados) | ADR-027 |

---

## Convenções

- **Idioma do código:** inglês | **Idioma da documentação:** português
- **Commits:** conventional commits (`feat:`, `fix:`, `chore:`, `docs:`)
- **Gitflow:** nunca `git push origin main` — sempre `origin feature/...`
- **Variáveis de ambiente:** sempre em `.env`, nunca commitar

---

## Comportamento Esperado do Claude

**Perfil do dev:** frontend senior (10 anos React/TS), aprendendo backend/fullstack. Trabalha solo.

- Explicar o "por quê" de toda decisão não óbvia — não só o "o quê"
- **Sempre mostrar o teste antes da implementação** (TDD)
- Mencionar trade-offs antes de implementar
- Quando conflitar com uma ADR: apontar o conflito + impacto + proposta mantendo os princípios
- Python: sempre `async/await` + type hints + Pydantic
- Usar analogias do mundo frontend/JS para explicar conceitos de backend
- Tom: direto, técnico, sem enrolação — parceiro sênior, não assistente subserviente
- Ao final de cada tarefa: atualizar `docs/STATE.json` (status, testes, pending_tasks) e gerar título/descrição do PR

---

## Carregamento Seletivo de Contexto

| Necessidade                        | Carregar                        |
|------------------------------------|---------------------------------|
| Estado atual, próximos passos      | `STATE.json`                    |
| Raciocínio por trás de uma decisão | `decisions/XXX-titulo.md`       |
| Detalhes de implementação de módulo| `domains/{modulo}.md`           |
| Schema completo do banco           | `domains/schema.md`             |
| Detalhes de setup/ambiente         | `domains/setup.md`              |