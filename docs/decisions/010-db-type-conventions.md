# 010 - Convenções de Tipo no Banco de Dados

**Status:** `accepted`

---

## Context

Decisões de tipo de coluna parecem detalhes de implementação, mas têm impacto direto em
segurança, precisão de dados, comportamento em produção e manutenibilidade. Sem convenções
explícitas, cada tabela nova pode tomar decisões inconsistentes — `SERIAL` vs `UUID`,
`TIMESTAMP` vs `TIMESTAMPTZ`, `FLOAT` vs `NUMERIC` — criando comportamentos imprevisíveis
em produção e dívida técnica acumulada.

## Decision

### PKs: UUID via `gen_random_uuid()`

```sql
id UUID PRIMARY KEY DEFAULT gen_random_uuid()
```

Nunca usar `SERIAL` ou `BIGSERIAL`.

### Datas: `TIMESTAMPTZ`

```sql
created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
```

Nunca usar `TIMESTAMP` (sem timezone).

Exceção intencional: `availability_slots.start_time` e `end_time` usam `TIME` (sem data)
porque representam um padrão semanal recorrente, não um momento específico no tempo.
`recurrences.start_date` e `end_date` usam `DATE` porque representam períodos de validade,
não instantes.

### Valores monetários: `NUMERIC(10, 2)`

```sql
session_price NUMERIC(10, 2)
price         NUMERIC(10, 2) NOT NULL
```

Nunca usar `FLOAT` ou `DOUBLE PRECISION` para dinheiro.

### Strings com tamanho definido: `VARCHAR(N)`

Usar `VARCHAR(N)` quando o tamanho máximo é conhecido e relevante para o domínio.
Usar `TEXT` para conteúdo sem limite prático (bio, notes, content de mensagens).

### Booleans: `BOOLEAN NOT NULL DEFAULT <valor>`

Sempre `NOT NULL` com default explícito — nunca boolean nullable.

### Mixins de timestamp (`core/mixins.py`)

```python
class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False
    )

class CreatedAtMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
```

`TimestampMixin` → entidades editáveis (`clients`, `sessions`, `professionals`, etc.)
`CreatedAtMixin` → registros imutáveis (`refresh_tokens`, `blocked_periods`, `audit_logs`)

## Rationale

### UUID vs SERIAL

| Critério | UUID | SERIAL |
|----------|------|--------|
| Enumeração de IDs por atacante | Impossível | Trivial (`/clients/1`, `/clients/2`) |
| Merge de dados entre ambientes | Sem colisão | Colisão garantida |
| Geração no cliente (antes de insert) | Possível | Impossível |
| Legibilidade em logs | Menor | Maior |
| Performance de index B-tree | Levemente menor | Maior |

Para um SaaS com dados sensíveis, a impossibilidade de enumeração e a segurança de merge
superam a pequena desvantagem de performance.

### TIMESTAMPTZ vs TIMESTAMP

`TIMESTAMP` armazena data/hora sem informação de fuso horário. Se o servidor muda de
timezone (deploy em região diferente, DST, migração de infraestrutura), os valores
armazenados se tornam ambíguos. `TIMESTAMPTZ` armazena em UTC internamente e converte
para o timezone da sessão na leitura — comportamento sempre previsível e portável.

### NUMERIC vs FLOAT

`FLOAT` usa representação binária de ponto flutuante — `0.1 + 0.2 = 0.30000000000004`.
Para valores monetários, isso gera erros de arredondamento acumulados em relatórios
financeiros. `NUMERIC(10, 2)` é aritmética decimal exata — sem surpresas em cobranças.

**Nota de serialização:** `NUMERIC` do PostgreSQL é retornado como `string` no JSON pelo
FastAPI (via Pydantic). Campos como `session_price` e `price` devem ser `str` nos tipos
TypeScript do frontend (`src/types/auth.ts`), não `number`.

## Consequences

**Positivos:**
- IDs não enumeráveis — sem IDOR trivial
- Datas sempre em UTC no banco — sem ambiguidade de timezone em produção
- Valores monetários exatos — relatórios financeiros corretos
- Convenções explícitas reduzem decisões por tabela nova

**Negativos / Trade-offs:**
- UUID aumenta tamanho de PKs e FKs (16 bytes vs 4 bytes do SERIAL) — impacto mínimo para o volume do MVP
- `NUMERIC` serializado como `string` no JSON — frontend deve usar `parseFloat()` ou biblioteca de decimal para cálculos
- `TIMESTAMPTZ` usa `DateTime(timezone=True)` no SQLAlchemy — deve ser consistente em todos os `mapped_column`

## Referências

- `core/mixins.py` — `TimestampMixin`, `CreatedAtMixin`
- `domains/schema.md` — schema completo com todos os tipos
- `src/types/auth.ts` — `session_price: string` (NUMERIC → string no JSON)