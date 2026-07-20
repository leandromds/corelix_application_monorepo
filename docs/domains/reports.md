# Domain: reports/

> Status: **pendente** — módulo não iniciado. Depende de `agenda` (sessions) estar implementado.

---

## Responsabilidade

Geração de relatórios de cobrança por cliente e por período, com observações contextuais
geradas pela IA. O relatório é o principal instrumento financeiro do profissional autônomo —
substitui planilhas manuais de controle de sessões realizadas e valores a receber.

---

## Valor de Negócio

O profissional precisa saber, por período (semana, mês):
- Quais sessões foram realizadas com qual cliente
- Quanto foi cobrado e o total do período
- Clientes com padrão anômalo (faltas frequentes, cancelamentos de última hora)
- Recorrências próximas do fim

A IA não gera o relatório — ela **adiciona observações contextuais** sobre o que os dados
indicam. O profissional vê os números e as observações lado a lado.

---

## Arquitetura do Módulo (a implementar)

```
reports/
├── router.py     → GET /reports/billing (TenantSession)
├── service.py    → agrega dados de sessions + chama ai/service
├── repository.py → queries de sessions por período, agrupadas por cliente
└── schemas.py    → BillingReportRequest, BillingReportResponse, ClientBillingEntry
```

Dependências do service layer:

```
reports/service.py
    → reports/repository.py    (queries de sessões do período)
    → ai/service.py            (gerar observações sobre o período)
```

Sem dependência de WhatsApp. Sem modelos próprios — lê de `sessions` e `clients`.

---

## Schemas a Implementar (`reports/schemas.py`)

### Request

```python
class BillingReportRequest(BaseModel):
    start_date: date
    end_date: date
    client_id: UUID | None = None    # None = todos os clientes do período
    status_filter: list[Literal[
        "completed", "cancelled", "no_show", "scheduled"
    ]] = ["completed"]               # padrão: apenas sessões realizadas

    @model_validator(mode="after")
    def validate_date_range(self) -> "BillingReportRequest":
        if self.end_date < self.start_date:
            raise ValueError("end_date must be >= start_date")
        if (self.end_date - self.start_date).days > 366:
            raise ValueError("Report range cannot exceed 366 days")
        return self
```

### Response

```python
class SessionEntry(BaseModel):
    session_id: UUID
    client_id: UUID
    client_name: str
    scheduled_at: datetime
    duration_minutes: int
    price: str              # NUMERIC → string no JSON (ADR-010)
    status: str
    notes: str | None

    model_config = ConfigDict(from_attributes=True)


class ClientBillingEntry(BaseModel):
    client_id: UUID
    client_name: str
    session_count: int
    total_amount: str       # NUMERIC → string — soma dos prices (ADR-010)
    sessions: list[SessionEntry]


class BillingReportResponse(BaseModel):
    period_start: date
    period_end: date
    total_sessions: int
    total_amount: str       # NUMERIC → string — total geral do período
    clients: list[ClientBillingEntry]
    ai_insights: str | None # None se IA indisponível (degradação graceful)
    generated_at: datetime
```

---

## Repository a Implementar (`reports/repository.py`)

```python
class ReportsRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def find_sessions_in_period(
        self,
        start_date: date,
        end_date: date,
        client_id: UUID | None = None,
        status_filter: list[str] | None = None,
    ) -> list[Row]:
        """
        Retorna sessions com dados do cliente (join explícito — sem relationship()).
        Ordenado por client_id, scheduled_at.
        """
        query = (
            select(
                Session.id,
                Session.client_id,
                Client.full_name.label("client_name"),
                Session.scheduled_at,
                Session.duration_minutes,
                Session.price,
                Session.status,
                Session.notes,
            )
            .join(Client, Session.client_id == Client.id)
            .where(
                Session.scheduled_at >= datetime.combine(start_date, time.min),
                Session.scheduled_at <= datetime.combine(end_date, time.max),
            )
            .order_by(Session.client_id, Session.scheduled_at)
        )

        if client_id:
            query = query.where(Session.client_id == client_id)

        if status_filter:
            query = query.where(Session.status.in_(status_filter))

        result = await self.db.execute(query)
        return result.all()

    async def get_period_summary(
        self,
        start_date: date,
        end_date: date,
        status_filter: list[str] | None = None,
    ) -> Row:
        """
        Retorna total_sessions e total_amount do período.
        Usado para popular o header do relatório e o contexto da IA.
        """
        query = (
            select(
                func.count(Session.id).label("total_sessions"),
                func.coalesce(func.sum(Session.price), 0).label("total_amount"),
            )
            .where(
                Session.scheduled_at >= datetime.combine(start_date, time.min),
                Session.scheduled_at <= datetime.combine(end_date, time.max),
            )
        )

        if status_filter:
            query = query.where(Session.status.in_(status_filter))

        result = await self.db.execute(query)
        return result.one()
```

**Nota:** O repository usa join explícito entre `sessions` e `clients` para evitar N+1 queries.
Sem `relationship()` — ADR-006. O RLS ativo em `sessions` garante que só dados do tenant
corrente são retornados.

---

## Service a Implementar (`reports/service.py`)

```python
class ReportsService:
    def __init__(self, db: AsyncSession) -> None:
        self.repository = ReportsRepository(db)
        self.ai = AIService()

    async def generate_billing_report(
        self,
        professional: Professional,
        request: BillingReportRequest,
    ) -> BillingReportResponse:
        # 1. Buscar sessões do período
        rows = await self.repository.find_sessions_in_period(
            start_date=request.start_date,
            end_date=request.end_date,
            client_id=request.client_id,
            status_filter=request.status_filter,
        )

        # 2. Agregar por cliente (em Python — sem GROUP BY no banco para flexibilidade)
        clients_map: dict[UUID, ClientBillingEntry] = {}
        total_amount = Decimal("0")

        for row in rows:
            entry = SessionEntry(
                session_id=row.id,
                client_id=row.client_id,
                client_name=row.client_name,
                scheduled_at=row.scheduled_at,
                duration_minutes=row.duration_minutes,
                price=str(row.price),
                status=row.status,
                notes=row.notes,
            )

            if row.client_id not in clients_map:
                clients_map[row.client_id] = ClientBillingEntry(
                    client_id=row.client_id,
                    client_name=row.client_name,
                    session_count=0,
                    total_amount="0",
                    sessions=[],
                )

            client_entry = clients_map[row.client_id]
            client_entry.sessions.append(entry)
            client_entry.session_count += 1
            client_total = Decimal(client_entry.total_amount) + row.price
            client_entry.total_amount = str(client_total)
            total_amount += row.price

        # 3. Gerar insights da IA (com degradação graceful)
        ai_insights: str | None = None
        if rows:  # só chama a IA se há dados no período
            try:
                ai_insights = await self._generate_ai_insights(
                    professional=professional,
                    rows=rows,
                    total_sessions=len(rows),
                    total_amount=total_amount,
                    period_start=request.start_date,
                    period_end=request.end_date,
                )
            except ExternalServiceError:
                # Falha da IA não deve impedir o relatório de ser gerado
                ai_insights = None

        return BillingReportResponse(
            period_start=request.start_date,
            period_end=request.end_date,
            total_sessions=len(rows),
            total_amount=str(total_amount),
            clients=list(clients_map.values()),
            ai_insights=ai_insights,
            generated_at=datetime.utcnow(),
        )

    async def _generate_ai_insights(
        self,
        professional: Professional,
        rows: list[Row],
        total_sessions: int,
        total_amount: Decimal,
        period_start: date,
        period_end: date,
    ) -> str:
        # Montar contexto estruturado para a IA — compacto, sem dados desnecessários
        no_show_count = sum(1 for r in rows if r.status == "no_show")
        cancelled_count = sum(1 for r in rows if r.status == "cancelled")

        # Clientes com mais de 1 no_show no período
        no_show_by_client: dict[str, int] = {}
        for row in rows:
            if row.status == "no_show":
                no_show_by_client[row.client_name] = (
                    no_show_by_client.get(row.client_name, 0) + 1
                )

        context = f"""
Período: {period_start} a {period_end}
Total de sessões realizadas: {total_sessions}
Total faturado: R$ {total_amount}
Faltas (no_show): {no_show_count}
Cancelamentos: {cancelled_count}

Clientes com faltas no período:
{chr(10).join(f"- {name}: {count} falta(s)" for name, count in no_show_by_client.items()) or "Nenhum"}

Clientes atendidos no período:
{chr(10).join(f"- {name}" for name in dict.fromkeys(r.client_name for r in rows))}
"""

        system = PROMPTS["report_insights"].format(
            professional_name=professional.full_name,
            specialty=professional.specialty or "profissional",
        )

        return await self.ai.complete(system=system, message=context)
```

---

## Router a Implementar (`reports/router.py`)

### Endpoint planejado

```
GET  /reports/billing     → BillingReportResponse
```

```python
router = APIRouter(prefix="/reports", tags=["reports"])

@router.get("/billing", response_model=BillingReportResponse)
async def get_billing_report(
    start_date: date = Query(..., description="Início do período (YYYY-MM-DD)"),
    end_date: date = Query(..., description="Fim do período (YYYY-MM-DD)"),
    client_id: UUID | None = Query(default=None),
    status_filter: list[str] = Query(
        default=["completed"],
        description="Status das sessões a incluir"
    ),
    db: TenantSession = ...,
    professional_id: CurrentProfessionalId = ...,
):
    # Buscar profissional para passar à IA (bio, specialty, name)
    professionals_repo = ProfessionalsRepository(db)
    professional = await professionals_repo.find_by_id(UUID(professional_id))
    if not professional:
        raise NotFoundError("Professional not found")

    service = ReportsService(db)
    return await service.generate_billing_report(
        professional=professional,
        request=BillingReportRequest(
            start_date=start_date,
            end_date=end_date,
            client_id=client_id,
            status_filter=status_filter,
        ),
    )
```

### Endpoints futuros (pós-MVP)

```
GET  /reports/billing/export/pdf  → PDF do relatório de cobrança
GET  /reports/clients/{id}/history → Histórico completo de um cliente
GET  /reports/summary/monthly      → Resumo financeiro mensal
```

---

## Prompt da IA (`ai/prompts.py`)

```python
PROMPTS["report_insights"] = """
Você é um assistente analítico para {professional_name}, {specialty}.

Analise os dados do período e forneça observações contextuais concisas:
- Padrões de faltas ou cancelamentos por cliente
- Clientes com comportamento fora do padrão
- Tendências financeiras relevantes (ex: receita abaixo do esperado por faltas)
- Alertas pontuais que merecem atenção

Seja direto e objetivo. Máximo 4 observações curtas.
Use linguagem simples, como se fosse um colega comentando os dados.
Sem jargão técnico ou financeiro complexo.
Não repita os números brutos — comente o que eles significam.
"""
```

---

## Decisões de Design

### Por que agregar no Python e não no banco (GROUP BY)?

- Flexibilidade: a estrutura `ClientBillingEntry` com lista de sessões aninhadas
  (`sessions: list[SessionEntry]`) seria complexa de montar com GROUP BY + JSON_AGG
- Testabilidade: a lógica de agregação fica no service, testável sem banco
- Volume: um profissional raramente tem mais de 200 sessões em um período — custo
  de processamento em Python é irrelevante

Para relatórios de alta cardinalidade (N profissionais, dashboard administrativo),
GROUP BY no banco seria preferível. Para o MVP single-tenant por request, Python é suficiente.

### Por que `ai_insights: str | None` e não `ai_insights: str`?

**Degradação graceful:** a IA pode estar indisponível (timeout, rate limit, erro da
Anthropic). O relatório financeiro tem valor independente dos insights — o profissional
deve conseguir ver seus números mesmo quando a IA falha. Lançar erro por falha de IA
num endpoint de relatório seria uma decisão equivocada de prioridade.

O frontend exibe os insights quando presentes e omite a seção quando `null`.

### Por que `total_amount` como `str` e não `float`?

Consistência com o padrão do projeto: `NUMERIC(10,2)` no banco → `Decimal` no Python →
`str` no JSON. Nunca `float` para valores monetários (ADR-010).

### Por que não há modelo próprio para `Report`?

O relatório é uma **view calculada em tempo real** dos dados de `sessions` e `clients`.
Não há valor em persisti-lo — o profissional pode gerar o mesmo relatório do mesmo período
quantas vezes quiser com resultado idêntico (exceto pelos insights da IA, que variam).

Pós-MVP: se houver necessidade de histórico de relatórios gerados (ex: "relatório enviado
ao contador em 31/01"), uma tabela `report_snapshots` pode ser adicionada sem breaking change.

---

## Ordem de Implementação TDD

```
Pré-requisito: módulo agenda implementado (precisa de sessions com dados)

1. reports/schemas.py
   → testes: BillingReportRequest (validação de datas, range máximo)
             BillingReportResponse (serialização, total_amount como str)

2. reports/repository.py
   → testes: find_sessions_in_period (filtros de data, cliente, status)
             get_period_summary (count e sum corretos)
             RLS: sessões de outro tenant não aparecem

3. reports/service.py (mock de AIService)
   → testes: agregação por cliente correta
             total_amount calculado corretamente
             ai_insights=None quando AIService lança ExternalServiceError
             relatório vazio para período sem sessões

4. reports/router.py
   → testes: GET /reports/billing com parâmetros válidos
             validação de datas inválidas (422)
             TenantSession: sem JWT retorna 401
```

---

## Testes — Cenários Críticos

| Cenário | Comportamento esperado |
|---|---|
| Período sem sessões | `total_sessions=0`, `clients=[]`, `ai_insights=None` |
| Falha da IA | Relatório retornado com `ai_insights=None` — sem 502 |
| `client_id` de outro tenant | RLS retorna 0 sessões — relatório vazio, sem erro |
| `status_filter=["no_show"]` | Apenas sessões `no_show` incluídas |
| `price=null` em sessão | `coalesce(sum(price), 0)` — sem erro de agregação |
| Período de 366 dias | 422 — `BillingReportRequest.validate_date_range` rejeita |

---

## Referências

- `domains/schema.md` — DDL de `sessions` e `clients` (tabelas consultadas)
- `domains/agenda.md` — `Session` model e status possíveis
- `domains/clients.md` — `Client` model (join para `client_name`)
- `domains/ai.md` — `AIService.complete()`, `PROMPTS["report_insights"]`
- ADR-001 — RLS ativo em `sessions` (garante isolamento no report)
- ADR-006 — sem `relationship()` — join explícito no repository
- ADR-007 — sem `session.commit()` no service
- ADR-010 — `NUMERIC` → `str` no JSON para `price` e `total_amount`
