# Domain: agenda

> Status: **skeleton criado** — modelos implementados, stubs de schemas/repository/service/router existem.
> Implementação TDD a iniciar (Red → Green → Refactor).
> Branch: `feature/agenda-module`

---

## Responsabilidades

Gestão completa da agenda do profissional:
- Configuração de horários disponíveis por dia da semana (`availability_slots`)
- Bloqueio de períodos específicos (férias, feriados, indisponibilidade) (`blocked_periods`)
- Agendamento de sessões únicas e recorrentes (`sessions`, `recurrences`)
- Validação de conflitos de horário
- Cancelamento em massa de sessões futuras

---

## Modelos (implementados em `agenda/models.py`)

```python
class AvailabilitySlot(Base, TimestampMixin):
    __tablename__ = "availability_slots"
    professional_id: Mapped[UUID]
    day_of_week: Mapped[int]      # 0=domingo, 6=sábado
    start_time: Mapped[time]      # TIME — padrão semanal, não momento específico
    end_time: Mapped[time]
    is_active: Mapped[bool]

class BlockedPeriod(Base, CreatedAtMixin):
    __tablename__ = "blocked_periods"
    professional_id: Mapped[UUID]
    start_datetime: Mapped[datetime]   # TIMESTAMPTZ — período específico no tempo
    end_datetime: Mapped[datetime]
    reason: Mapped[str | None]
    notify_clients: Mapped[bool]       # DEFAULT TRUE — opt-out

class Recurrence(Base, TimestampMixin):
    __tablename__ = "recurrences"
    professional_id: Mapped[UUID]
    client_id: Mapped[UUID]
    frequency: Mapped[str]            # weekly | biweekly | monthly
    interval: Mapped[int]             # DEFAULT 1
    day_of_week: Mapped[int | None]   # obrigatório para weekly/biweekly
    start_date: Mapped[date]          # DATE — período de validade
    end_date: Mapped[date | None]     # NULL = sem fim
    session_duration: Mapped[int]
    session_price: Mapped[Decimal]
    is_active: Mapped[bool]

class Session(Base, TimestampMixin):
    __tablename__ = "sessions"
    professional_id: Mapped[UUID]
    client_id: Mapped[UUID]
    recurrence_id: Mapped[UUID | None]   # SET NULL se recorrência encerrada
    scheduled_at: Mapped[datetime]       # TIMESTAMPTZ
    duration_minutes: Mapped[int]
    price: Mapped[Decimal]               # congelado no momento do agendamento
    status: Mapped[str]                  # scheduled | completed | cancelled | no_show
    notes: Mapped[str | None]
```

---

## Schemas a Implementar (`agenda/schemas.py`)

> ✅ **Schemas já alinhados ao spec:** `agenda/schemas.py` foi atualizado para usar os nomes
> corretos (`AvailabilitySlotCreate`, `AvailabilitySlotUpdate`, `AvailabilitySlotResponse`,
> `BlockedPeriodCreate`, `BlockedPeriodResponse`, `RecurrenceCreate`, `RecurrenceResponse`,
> `SessionCreate`, `SessionUpdate`, `SessionResponse`) com validators de campo.
> O TDD deve partir desses schemas para implementar repository e service.

### AvailabilitySlot

```python
class AvailabilitySlotCreate(BaseModel):
    day_of_week: int = Field(ge=0, le=6)
    start_time: time
    end_time: time

    @model_validator(mode="after")
    def validate_time_range(self) -> "AvailabilitySlotCreate":
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self

# UNIQUE constraint no banco: (professional_id, day_of_week, start_time)
# O service deve verificar duplicidade antes do INSERT e lançar ConflictError.
# Dois slots no mesmo dia com start_times diferentes são permitidos (ex: manhã e tarde).

class AvailabilitySlotUpdate(BaseModel):
    start_time: time | None = None
    end_time: time | None = None
    is_active: bool | None = None

class AvailabilitySlotResponse(BaseModel):
    id: UUID
    day_of_week: int
    start_time: time
    end_time: time
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
```

### BlockedPeriod

```python
class BlockedPeriodCreate(BaseModel):
    start_datetime: datetime
    end_datetime: datetime
    reason: str | None = Field(default=None, max_length=255)
    notify_clients: bool = True

    @model_validator(mode="after")
    def validate_date_range(self) -> "BlockedPeriodCreate":
        if self.end_datetime <= self.start_datetime:
            raise ValueError("end_datetime must be after start_datetime")
        return self

class BlockedPeriodResponse(BaseModel):
    id: UUID
    start_datetime: datetime
    end_datetime: datetime
    reason: str | None
    notify_clients: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
```

### Recurrence

```python
class RecurrenceCreate(BaseModel):
    client_id: UUID
    frequency: Literal["weekly", "biweekly", "monthly"]
    interval: int = Field(default=1, gt=0)
    day_of_week: int | None = Field(default=None, ge=0, le=6)
    start_date: date
    end_date: date | None = None
    session_duration: int = Field(gt=0)
    session_price: Decimal = Field(gt=0, decimal_places=2)

    @model_validator(mode="after")
    def validate_recurrence(self) -> "RecurrenceCreate":
        if self.frequency in ("weekly", "biweekly") and self.day_of_week is None:
            raise ValueError("day_of_week is required for weekly and biweekly frequencies")
        if self.end_date and self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date")
        return self

class RecurrenceResponse(BaseModel):
    id: UUID
    client_id: UUID
    frequency: str
    interval: int
    day_of_week: int | None
    start_date: date
    end_date: date | None
    session_duration: int
    session_price: str       # NUMERIC → string no JSON
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
```

### Session

```python
class SessionCreate(BaseModel):
    client_id: UUID
    recurrence_id: UUID | None = None
    scheduled_at: datetime
    duration_minutes: int = Field(gt=0)
    price: Decimal = Field(gt=0, decimal_places=2)
    notes: str | None = None

class SessionUpdate(BaseModel):
    scheduled_at: datetime | None = None
    duration_minutes: int | None = Field(default=None, gt=0)
    price: Decimal | None = Field(default=None, gt=0, decimal_places=2)
    status: Literal["scheduled", "completed", "cancelled", "no_show"] | None = None
    notes: str | None = None

class SessionResponse(BaseModel):
    id: UUID
    client_id: UUID
    recurrence_id: UUID | None
    scheduled_at: datetime
    duration_minutes: int
    price: str               # NUMERIC → string no JSON
    status: str
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
```

---

## Repository a Implementar (`agenda/repository.py`)

### `AvailabilitySlotsRepository`

```python
async def create(professional_id: UUID, data: AvailabilitySlotCreate) -> AvailabilitySlot
async def find_by_id(slot_id: UUID) -> AvailabilitySlot | None
async def find_all(active_only: bool = True) -> list[AvailabilitySlot]
async def find_by_day(day_of_week: int) -> list[AvailabilitySlot]
async def find_by_day_and_time(
    day_of_week: int, start_time: time
) -> AvailabilitySlot | None
# ↑ usado pelo service para verificar duplicidade antes do INSERT
# Equivale a checar a UNIQUE constraint (professional_id, day_of_week, start_time)
# em Python antes de chegar ao banco — retorna erro amigável em vez de IntegrityError
async def update(slot: AvailabilitySlot, data: dict) -> AvailabilitySlot
async def soft_delete(slot: AvailabilitySlot) -> None
```

Implementação de `find_by_day_and_time`:

```python
async def find_by_day_and_time(
    self, day_of_week: int, start_time: time
) -> AvailabilitySlot | None:
    result = await self.db.execute(
        select(AvailabilitySlot).where(
            AvailabilitySlot.day_of_week == day_of_week,
            AvailabilitySlot.start_time == start_time,
            AvailabilitySlot.is_active == True,
        )
    )
    return result.scalar_one_or_none()
```

### `BlockedPeriodsRepository`

```python
async def create(professional_id: UUID, data: BlockedPeriodCreate) -> BlockedPeriod
async def find_by_id(period_id: UUID) -> BlockedPeriod | None
async def find_all() -> list[BlockedPeriod]
async def find_overlapping(start: datetime, end: datetime) -> list[BlockedPeriod]
async def delete(period: BlockedPeriod) -> None   # hard delete — sem valor histórico
```

### `RecurrencesRepository`

```python
async def create(professional_id: UUID, data: RecurrenceCreate) -> Recurrence
async def find_by_id(recurrence_id: UUID) -> Recurrence | None
async def find_all(active_only: bool = True) -> list[Recurrence]
async def find_active_by_client(client_id: UUID) -> list[Recurrence]
async def update(recurrence: Recurrence, data: dict) -> Recurrence
async def deactivate(recurrence: Recurrence) -> None   # is_active = False
```

### `SessionsRepository`

```python
async def create(professional_id: UUID, data: SessionCreate) -> Session
async def find_by_id(session_id: UUID) -> Session | None
async def find_all(skip: int = 0, limit: int = 50) -> list[Session]
async def find_by_client(client_id: UUID) -> list[Session]
async def find_scheduled_between(start: datetime, end: datetime) -> list[Session]
async def find_conflicting(scheduled_at: datetime, duration_minutes: int) -> list[Session]
async def update(session: Session, data: dict) -> Session
async def cancel_future_by_recurrence(recurrence_id: UUID) -> int   # retorna count
```

---

## Service a Implementar (`agenda/service.py`)

### Regras de negócio críticas

#### Criação de availability slot (ConflictError por UNIQUE)

```python
async def create_availability_slot(
    self, professional_id: UUID, data: AvailabilitySlotCreate
) -> AvailabilitySlot:
    # Verifica a UNIQUE constraint (professional_id, day_of_week, start_time)
    # antes do INSERT para retornar ConflictError em vez de IntegrityError do banco
    existing = await self.slots_repo.find_by_day_and_time(
        day_of_week=data.day_of_week,
        start_time=data.start_time,
    )
    if existing:
        raise ConflictError(
            f"Availability slot already exists for "
            f"day_of_week={data.day_of_week} at {data.start_time}"
        )
    return await self.slots_repo.create(professional_id, data)
```

> **Nota:** a UNIQUE constraint no banco `(professional_id, day_of_week, start_time)`
> ainda serve como barreira final — a verificação no service é para UX (mensagem clara),
> não para substituir a constraint.

#### Validação de conflito de horário

Antes de criar ou reagendar uma sessão, verificar se o horário não conflita com:
1. Uma sessão `status='scheduled'` no mesmo intervalo de tempo
2. Um `blocked_period` que cobre o horário solicitado

```python
async def _check_session_conflict(
    scheduled_at: datetime,
    duration_minutes: int,
    exclude_session_id: UUID | None = None
) -> None:
    session_end = scheduled_at + timedelta(minutes=duration_minutes)

    # Verifica sessões existentes
    conflicting = await self.sessions_repo.find_conflicting(scheduled_at, duration_minutes)
    if exclude_session_id:
        conflicting = [s for s in conflicting if s.id != exclude_session_id]
    if conflicting:
        raise ConflictError("Schedule conflict: another session exists at this time")

    # Verifica períodos bloqueados
    blocked = await self.blocked_repo.find_overlapping(scheduled_at, session_end)
    if blocked:
        raise ConflictError("Schedule conflict: professional is not available at this time")
```

#### Cancelamento em massa ao encerrar recorrência

```python
async def deactivate_recurrence(recurrence_id: UUID) -> int:
    recurrence = await self._get_recurrence_or_404(recurrence_id)
    await self.recurrences_repo.deactivate(recurrence)
    cancelled_count = await self.sessions_repo.cancel_future_by_recurrence(recurrence_id)
    return cancelled_count   # retorna quantas sessões futuras foram canceladas
```

#### Congelamento de preço na sessão

O `price` na sessão é sempre o preço no momento do agendamento — nunca referenciar
`session_price` da recorrência ou do profissional depois da criação.

```python
async def create_session(data: SessionCreate) -> Session:
    # price já vem no SessionCreate — responsabilidade do chamador definir o valor
    # (pode ser o session_price do profissional, da recorrência, ou negociado)
    await self._check_session_conflict(data.scheduled_at, data.duration_minutes)
    return await self.sessions_repo.create(self.professional_id, data)
```

---

## Router a Implementar (`agenda/router.py`)

### Endpoints planejados

#### Availability Slots

```
POST   /agenda/slots/          → 201 AvailabilitySlotResponse
GET    /agenda/slots/          → list[AvailabilitySlotResponse]
GET    /agenda/slots/{id}      → AvailabilitySlotResponse
PATCH  /agenda/slots/{id}      → AvailabilitySlotResponse
DELETE /agenda/slots/{id}      → 204 (soft delete)
```

#### Blocked Periods

```
POST   /agenda/blocked/        → 201 BlockedPeriodResponse
GET    /agenda/blocked/        → list[BlockedPeriodResponse]
GET    /agenda/blocked/{id}    → BlockedPeriodResponse
DELETE /agenda/blocked/{id}    → 204 (hard delete)
```

#### Recurrences

```
POST   /agenda/recurrences/           → 201 RecurrenceResponse
GET    /agenda/recurrences/           → list[RecurrenceResponse]
GET    /agenda/recurrences/{id}       → RecurrenceResponse
PATCH  /agenda/recurrences/{id}       → RecurrenceResponse
DELETE /agenda/recurrences/{id}       → 200 {"cancelled_sessions": N}
```

#### Sessions

```
POST   /agenda/sessions/              → 201 SessionResponse
GET    /agenda/sessions/              → list[SessionResponse] (paginado)
GET    /agenda/sessions/{id}          → SessionResponse
PATCH  /agenda/sessions/{id}          → SessionResponse
GET    /agenda/sessions/today         → list[SessionResponse]
GET    /agenda/sessions/upcoming      → list[SessionResponse]
```

Todos os endpoints usam `TenantSession` — RLS ativo (ver ADR-003).

---

## Ordem de Implementação TDD

```
1. agenda/schemas.py
   → testes: validação de model_validator (conflito de horário no schema, frequência + day_of_week)

2. agenda/repository.py (AvailabilitySlots + BlockedPeriods)
   → testes: CRUD, find_overlapping, find_by_day

3. agenda/repository.py (Recurrences + Sessions)
   → testes: find_conflicting (usa índice parcial WHERE status='scheduled'),
             cancel_future_by_recurrence

4. agenda/service.py
   → testes: _check_session_conflict (sessão sobreposta, blocked_period sobreposto),
             create_session (sucesso, conflict), deactivate_recurrence (cascade cancel)

5. agenda/router.py
   → testes: todos os endpoints, status codes, RLS (TenantSession), paginação
```

---

## Decisões de Design Explícitas

Estas decisões devem estar documentadas mesmo que a resposta seja "permitir" — ausência
de documentação é interpretada como esquecimento, não como decisão consciente.

### Sessão fora do availability_slot — **permitido no MVP**

**Decisão:** o sistema **não valida** se o horário de uma sessão cabe dentro de um
`availability_slot` ativo ao criar ou reagendar.

**Rationale:** profissionais autônomos fazem exceções frequentes — encaixe de emergência,
cliente especial, sessão remarcada para horário atípico. Forçar essa validação criaria
fricção desnecessária no MVP e exigiria lógica complexa (sobreposição de intervalos de
TIME com janela de TIMESTAMPTZ da sessão, considerando duração).

**O que o availability_slot faz:** serve como configuração de disponibilidade padrão
para o bot do WhatsApp sugerir horários e para o dashboard exibir a agenda típica do
profissional. Não é um bloqueio rígido de agendamento.

**Pós-MVP:** pode ser adicionado como validação opcional configurável pelo profissional
(`enforce_availability: bool` nas configurações). Quando `True`, o service verifica
sobreposição antes de criar a sessão.

---

### Sessão no passado — **permitida no MVP**

**Decisão:** o sistema **não valida** se `scheduled_at` está no futuro ao criar uma
sessão. Sessões com `scheduled_at` no passado são aceitas.

**Rationale:** profissionais que começam a usar o sistema no meio da agenda precisam
registrar sessões retroativamente para manter o histórico financeiro completo. Bloquear
datas passadas tornaria impossível a importação de dados históricos.

**Contexto de uso legítimo de data passada:**
- Importação de histórico ao onboarding
- Registro manual de sessão realizada fora do sistema
- Correção de agendamento após a sessão acontecer

**Pós-MVP:** pode ser adicionado um **aviso** (não erro) ao criar sessão no passado —
`{"warning": "scheduled_at is in the past"}` junto do `201 Created`. Não um bloqueio.

---

### Regras de ON DELETE nas tabelas de agenda

| Tabela | FK para | ON DELETE | Motivo |
|---|---|---|---|
| `availability_slots` | `professionals` | `CASCADE` | Configuração de disponibilidade sem sentido sem o profissional |
| `blocked_periods` | `professionals` | `CASCADE` | Bloqueio sem sentido sem o profissional |
| `sessions` | `professionals` | `RESTRICT` | Valor histórico e legal — sessões são registros financeiros |
| `sessions` | `clients` | `RESTRICT` | Sessão sem cliente perde rastreabilidade — soft delete o cliente em vez de deletar |
| `sessions` | `recurrences` | `SET NULL` | Sessão persiste se a recorrência for encerrada — histórico não pode ser perdido |
| `recurrences` | `professionals` | `RESTRICT` | Série histórica de sessões tem valor independente |
| `recurrences` | `clients` | `RESTRICT` | Série de sessões sem cliente perde rastreabilidade |

**Regra de ouro para agenda:** se deletar o pai quebraria o histórico financeiro do
profissional, usar `RESTRICT`. Se o filho não tem valor sem o pai, usar `CASCADE`.
`SET NULL` apenas quando o vínculo pode ser removido sem perder o registro.

---

## Constraints e Gotchas

- **`TIME` vs `TIMESTAMPTZ`:** `availability_slots` usa `TIME` (padrão semanal recorrente).
  `sessions` e `blocked_periods` usam `TIMESTAMPTZ` (momento específico). Não confundir.
- **`day_of_week` opcional:** nullable em `recurrences` para frequência `monthly` —
  mas obrigatório para `weekly` e `biweekly`. Validar no `model_validator`.
- **Índice parcial em `sessions`:** `WHERE status = 'scheduled'` — `find_conflicting()`
  deve filtrar por `status = 'scheduled'` para aproveitar o índice.
- **`price` congelado:** nunca atualizar `price` de sessões existentes ao mudar o preço
  do profissional ou da recorrência. O valor histórico é parte do registro financeiro.
- **`cancel_future_by_recurrence`:** deve cancelar apenas sessões com
  `scheduled_at > NOW()` e `status = 'scheduled'` — não sessões passadas ou já
  canceladas/concluídas.
- **RLS + `recurrence_id`:** `recurrence_id` é uma FK para `recurrences` que também tem
  RLS. O banco não valida se a `recurrence_id` pertence ao tenant — essa validação deve
  ocorrer no service layer antes de criar a sessão.
- **`session_price` em `RecurrenceResponse` é `str`** — NUMERIC → string no JSON,
  igual ao padrão do projeto (ADR-010).

---

## Referências

- `domains/schema.md` — DDL completo de `availability_slots`, `blocked_periods`, `sessions`, `recurrences`
- `domains/clients.md` — `client_id` referenciado em `sessions` e `recurrences`
- ADR-001 — RLS nas 4 tabelas do módulo
- ADR-005 — TDD: implementar na ordem schemas → repository → service → router
- ADR-009 — soft delete em `availability_slots` e `recurrences`
- ADR-010 — `NUMERIC` → `str` no JSON para campos de preço
- `STATE.json` — status atual e próximos passos