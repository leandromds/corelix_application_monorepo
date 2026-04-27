# 009 - Soft Delete com `is_active` em Entidades Históricas

**Status:** `accepted`

---

## Context

O sistema gerencia entidades que possuem valor histórico mesmo após serem "removidas" pelo
profissional — clientes, sessões, recorrências. Um cliente inativo ainda aparece no histórico
financeiro. Uma sessão cancelada ainda conta nas estatísticas de faltas.

Se essas entidades fossem deletadas fisicamente (`DELETE FROM ...`), relatórios históricos
quebrariam, constraints de FK seriam violadas em cascata, e a IA perderia contexto para
gerar insights longitudinais.

## Decision

Entidades com valor histórico usam **soft delete** via campo `is_active BOOLEAN NOT NULL DEFAULT TRUE`.

Deletar = setar `is_active = false`. O registro permanece no banco.

**Entidades com soft delete:**
- `clients` — histórico de sessões e financeiro
- `availability_slots` — histórico de configuração de agenda
- `recurrences` — rastreabilidade de séries de sessões

**Entidades sem soft delete (delete físico ou imutáveis):**
- `refresh_tokens` — sem valor histórico, limpeza via job noturno
- `blocked_periods` — sem valor após a data de fim
- `sessions` — nunca deletadas diretamente; status `cancelled` / `no_show` cumpre a função
- `audit_logs` — imutáveis por definição

## Rationale

**Integridade referencial:** `sessions` referencia `clients` com `ON DELETE RESTRICT`.
Deletar fisicamente um cliente com sessões históricas geraria erro de FK — seria necessário
deletar as sessões em cascata, destruindo dados financeiros e histórico da IA.

**Relatórios e IA:** a IA usa o histórico completo de sessões para gerar insights. Um cliente
"deletado" não deve apagar o contexto acumulado — apenas parar de aparecer nas listas ativas.

**LGPD — direito ao esquecimento:** quando o profissional quiser exercer o direito de
apagamento de um cliente por solicitação, isso é tratado como uma operação administrativa
específica e auditada — não como o fluxo normal de "remoção". `is_active = false` é a
operação cotidiana; anonimização ou hard delete é o caso LGPD tratado separadamente.

**Consistência de queries:** o repository usa `active_only=True` por padrão em `find_all()`.
Queries que precisam de histórico completo passam `active_only=False` explicitamente.

## Consequences

**Positivos:**
- Histórico financeiro, de sessões e de relacionamento sempre preservado
- IA tem contexto completo para análise longitudinal
- Sem erros de FK em cascata por operações de remoção cotidianas
- Operações de "undeletar" são triviais (`is_active = true`)

**Negativos / Trade-offs:**
- Tabelas crescem indefinidamente sem hard delete — precisa de política de retenção futura
- Queries de listagem devem sempre filtrar `is_active = true` — risco de mostrar dados
  "deletados" se o dev esquecer o filtro (mitigado pelo `active_only=True` como default no repository)
- `find_by_phone()` no `ClientsRepository` só busca clientes ativos — cliente inativo com
  mesmo telefone não gera `ConflictError` ao criar um novo (comportamento intencional)

## Referências

- `clients/repository.py` — `find_all(active_only=True)`, `soft_delete()`, `find_by_phone()`
- `clients/service.py` — `delete_client()` chama `soft_delete()`
- `ADR-001` — RLS garante que soft delete de um tenant não afeta queries de outro