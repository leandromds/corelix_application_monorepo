# 001 - Multi-Tenancy: Row-Level + RLS (Dupla Barreira)

**Status:** `accepted`

---

## Context

O produto é um SaaS multi-tenant onde cada profissional (tenant) deve ter isolamento
total dos seus dados. Uma falha de isolamento num sistema de saúde expõe dados sensíveis
de clientes — risco legal (LGPD) e reputacional grave.

A abordagem mais comum em SaaS é filtrar por `professional_id` na camada de aplicação.
Porém, uma única query sem o filtro (por bug, omissão ou falha de refactor) vaza dados
de todos os tenants.

## Decision

Adotar **duas barreiras independentes** de isolamento:

**Camada 1 — Aplicação (Python/SQLAlchemy):**
Todo repository filtra explicitamente por `professional_id` nas queries.

**Camada 2 — Banco (PostgreSQL RLS):**
Cada tabela tenant tem Row Level Security ativo com uma policy que impede leitura e
escrita de linhas fora do tenant corrente, mesmo que a query da aplicação omita o filtro.

```sql
ALTER TABLE clients ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON clients
    USING (professional_id = current_setting('app.current_tenant', TRUE)::uuid);
--                                                                  ^^^^ missing_ok
-- TRUE = retorna NULL em vez de lançar erro quando o contexto não está definido.
-- Sem esse flag, testes de model (que não setam tenant) quebram no INSERT ... RETURNING *.
-- Ver ADR-021 para o raciocínio completo.
```

O tenant é setado no início de cada request protegido via `SET LOCAL`:

```python
# core/database.py
async def set_tenant_context(session: AsyncSession, tenant_id: UUID) -> None:
    await session.execute(
        text(f"SET LOCAL app.current_tenant = '{tenant_id}'")
    )
```

Tabelas com RLS ativo: `clients`, `availability_slots`, `blocked_periods`,
`recurrences`, `sessions`, `whatsapp_conversations`.

Tabelas SEM RLS (acesso controlado pelo service layer): `professionals`,
`refresh_tokens`, `audit_logs`, `whatsapp_messages`.

## Rationale

- **Defense in depth:** se a camada de aplicação falhar (bug em query), o banco ainda
  bloqueia o acesso. O inverso também é verdadeiro.
- **Auditabilidade:** RLS é verificável diretamente no banco, independente do código.
- **PostgreSQL nativo:** RLS é feature de produção do PostgreSQL — sem overhead de
  bibliotecas externas, sem ponto adicional de falha.
- **Sem schema separation:** schemas separados por tenant (abordagem alternativa)
  exigiriam migrations N vezes e conexões separadas — inviável para SaaS com muitos
  tenants pequenos.
- **Sem banco separado por tenant:** custo proibitivo para o estágio atual do produto.

## Consequences

**Positivos:**
- Vazamento de dados entre tenants requer duas falhas simultâneas e independentes.
- Queries sem filtro explícito retornam conjunto vazio (não erro) — comportamento seguro.
- Testável: é possível verificar o isolamento diretamente contra o banco.

**Negativos/Limitações:**
- `SET LOCAL` é scoped à transação — nunca chamar `session.commit()` no service layer
  (ver ADR-007), pois isso encerraria a transação e perderia o contexto RLS.
- O usuário `postgres` tem `BYPASSRLS` nativo — testes de isolamento precisam de uma
  role dedicada `test_rls_user` (ver ADR-021).
- `SET LOCAL` não aceita bind params (`$1`) no PostgreSQL — UUID interpolado via
  f-string (ver ADR-008).
- Toda nova tabela tenant deve incluir manualmente a policy RLS — não é automático.
- RLS não cobre `whatsapp_messages` (acesso via `conversation_id`, controlado por join).
- A policy **deve sempre usar `current_setting('app.current_tenant', TRUE)`** (com o
  segundo argumento `TRUE` — `missing_ok`). A forma sem `TRUE` lança erro quando o
  contexto não está definido, quebrando testes de model que fazem `INSERT` sem setar
  tenant. Ver ADR-021 para a solução completa de testes de isolamento RLS.