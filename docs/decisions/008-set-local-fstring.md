# 008 - SET LOCAL via f-string (PostgreSQL não suporta bind params em SET)

**Status:** `accepted`

---

## Context

O sistema usa `SET LOCAL app.current_tenant = <uuid>` para ativar o contexto de tenant
antes de cada query com RLS. A forma idiomática de passar valores em queries SQLAlchemy
é via bind parameters (`$1` / `:param`) — que previne SQL injection.

A primeira implementação natural foi:

```python
# Tentativa com bind params — ERRADO
await session.execute(
    text("SET LOCAL app.current_tenant = :tenant_id"),
    {"tenant_id": str(professional_id)}
)
```

Isso gera `ProgrammingError: syntax error at or near "$1"` — o PostgreSQL não aceita
parâmetros de bind em comandos `SET`. Apenas literais são válidos na posição do valor.

## Decision

Usar f-string com o UUID interpolado diretamente:

```python
# core/database.py
async def set_tenant_context(session: AsyncSession, tenant_id: UUID) -> None:
    await session.execute(
        text(f"SET LOCAL app.current_tenant = '{tenant_id}'")
    )
```

## Rationale

**Por que f-string é seguro aqui (e não SQL injection)?**

SQL injection ocorre quando input arbitrário do usuário é interpolado diretamente em
uma query. Aqui, `tenant_id` é um `UUID` validado pelo Python antes de chegar a esta
função — o tipo `UUID` só aceita valores no formato `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`.
Qualquer string que não respeite esse formato lança `ValueError` antes da interpolação.

O fluxo de origem do valor:
```
JWT → decode_access_token() → UUID(payload["sub"]) → set_tenant_context()
```

O `UUID()` do Python é o validador. Não existe caminho para um valor arbitrário chegar aqui.

**Por que não usar `EXECUTE format(...)` no PostgreSQL?**
Exigiria trocar `SET LOCAL` por uma stored procedure — adicionaria complexidade, lógica
no banco (violando ADR-004) e tornaria os testes mais difíceis.

**Por que não usar `set_config()`?**
`set_config('app.current_tenant', $1, true)` aceita bind params e é uma alternativa válida.
`SET LOCAL` foi escolhido por ser mais legível e idiomático para configuração de sessão.
`set_config` com `is_local=true` é equivalente e pode ser adotado no futuro se necessário.

## Consequences

**Positivos:**
- Funciona — não há outra forma de passar valores para `SET` no PostgreSQL
- Seguro pelo tipo: `UUID` é um validador explícito antes da interpolação
- Simples e legível

**Negativos / Limitações:**
- Foge do padrão de bind params do SQLAlchemy — pode confundir devs acostumados com a
  convenção `:param`
- Exige atenção em code reviews: qualquer alteração que substitua `UUID` por `str` sem
  validação prévia criaria um vetor de injeção

**Regra de manutenção:** o argumento `tenant_id` de `set_tenant_context()` deve sempre
ser do tipo `UUID` (Python), nunca `str`. O type hint deve ser mantido e o mypy deve
estar ativo para garantir isso.

## Referências

- `core/database.py` — implementação de `set_tenant_context()`
- `core/deps.py` — ponto de chamada via `TenantSession` (ADR-003)
- `ADR-001` — contexto do uso de RLS
- `ADR-021` — testes de isolamento RLS