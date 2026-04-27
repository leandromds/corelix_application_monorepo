# Domain: clients

> Implementação completa. 76 testes passando (model + repository + service + router).

---

## Responsabilidade

CRUD de clientes do profissional autônomo. Cada cliente pertence a exatamente um profissional
(tenant). RLS ativo — o banco filtra automaticamente por `professional_id` via `app.current_tenant`.

---

## Endpoints

| Método | Path | Auth | Status | Descrição |
|---|---|---|---|---|
| POST | `/api/v1/clients/` | JWT + RLS | 201 | Cria cliente |
| GET | `/api/v1/clients/` | JWT + RLS | 200 | Lista clientes (paginação) |
| GET | `/api/v1/clients/{id}` | JWT + RLS | 200 | Busca cliente por ID |
| PATCH | `/api/v1/clients/{id}` | JWT + RLS | 200 | Atualiza campos (PATCH semântico) |
| DELETE | `/api/v1/clients/{id}` | JWT + RLS | 204 | Soft delete (`is_active = false`) |

Todos os endpoints usam `TenantSession` — RLS ativo em todas as queries.

---

## Schemas (`clients/schemas.py`)

### `ClientCreate`

```python
class ClientCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=255)
    phone: str | None = Field(default=None, max_length=20)
    email: EmailStr | None = None
    notes: str | None = None
    whatsapp_opt_in: bool = False
    email_opt_in: bool = False

    @model_validator(mode="after")
    def at_least_one_contact(self) -> "ClientCreate":
        if not self.phone and not self.email:
            raise ValueError("At least one of phone or email must be provided")
        return self
```

> `model_validator` garante que o cliente tenha ao menos um canal de contato.
> Gotcha: `exc.errors()` do Pydantic v2 inclui `ctx: {'error': ValueError(...)}` não
> JSON-serializable — usar `jsonable_encoder(exc.errors())` no handler de exceção em `main.py`.

### `ClientUpdate`

```python
class ClientUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    phone: str | None = Field(default=None, max_length=20)
    email: EmailStr | None = None
    notes: str | None = None
    whatsapp_opt_in: bool | None = None
    email_opt_in: bool | None = None
```

PATCH semântico: `model_dump(exclude_unset=True)` — apenas os campos enviados são alterados.
Campos enviados como `null` limpam o valor no banco (diferente de `exclude_none=True`).

### `ClientResponse`

```python
class ClientResponse(BaseModel):
    id: UUID
    full_name: str
    phone: str | None
    email: str | None
    notes: str | None
    whatsapp_opt_in: bool
    email_opt_in: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
```

> `professional_id` é explicitamente excluído do response — nunca expor FK de tenant.

---

## Repository (`clients/repository.py`)

```python
class ClientsRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, professional_id: UUID, data: ClientCreate) -> Client:
        client = Client(professional_id=professional_id, **data.model_dump())
        self.db.add(client)
        await self.db.flush()   # materializa id antes do commit
        return client

    async def find_by_id(self, client_id: UUID) -> Client | None:
        result = await self.db.execute(
            select(Client).where(Client.id == client_id)
        )
        return result.scalar_one_or_none()

    async def find_all(
        self,
        skip: int = 0,
        limit: int = 20,
        active_only: bool = True,
    ) -> list[Client]:
        query = select(Client)
        if active_only:
            query = query.where(Client.is_active == True)
        query = query.offset(skip).limit(limit).order_by(Client.created_at.desc())
        result = await self.db.execute(query)
        return result.scalars().all()

    async def find_by_phone(self, phone: str) -> Client | None:
        """Busca apenas clientes ativos — telefone duplicado com inativo é permitido."""
        result = await self.db.execute(
            select(Client).where(Client.phone == phone, Client.is_active == True)
        )
        return result.scalar_one_or_none()

    async def update(self, client: Client, data: dict) -> Client:
        for key, value in data.items():
            setattr(client, key, value)
        await self.db.flush()
        return client

    async def soft_delete(self, client: Client) -> None:
        client.is_active = False
        await self.db.flush()
```

**Nota crítica:** o repository **não filtra por `professional_id`**. O RLS do PostgreSQL
filtra automaticamente via `app.current_tenant`. Adicionar `where(Client.professional_id == ...)`
seria redundante — mas inofensivo se necessário para legibilidade em casos específicos.

---

## Service (`clients/service.py`)

```python
class ClientsService:
    def __init__(self, db: AsyncSession) -> None:
        self.repository = ClientsRepository(db)

    async def create_client(
        self, professional_id: UUID, data: ClientCreate
    ) -> Client:
        # Verifica duplicidade de telefone dentro do tenant
        if data.phone:
            existing = await self.repository.find_by_phone(data.phone)
            if existing:
                raise ConflictError(f"Client with phone {data.phone} already exists")
        return await self.repository.create(professional_id, data)

    async def get_client(self, client_id: UUID) -> Client:
        client = await self.repository.find_by_id(client_id)
        if not client:
            raise NotFoundError(f"Client {client_id} not found")
        return client
    # ↑ NotFoundError via RLS: se o cliente existe mas pertence a outro tenant,
    #   find_by_id retorna None (RLS filtra) — comportamento seguro: sem vazar existência

    async def list_clients(
        self, skip: int = 0, limit: int = 20
    ) -> list[Client]:
        return await self.repository.find_all(skip=skip, limit=limit, active_only=True)

    async def update_client(
        self, client_id: UUID, data: ClientUpdate
    ) -> Client:
        client = await self.get_client(client_id)
        update_data = data.model_dump(exclude_unset=True)

        # Verifica duplicidade de telefone se phone está sendo atualizado
        if "phone" in update_data and update_data["phone"]:
            existing = await self.repository.find_by_phone(update_data["phone"])
            if existing and existing.id != client_id:
                raise ConflictError(
                    f"Client with phone {update_data['phone']} already exists"
                )

        return await self.repository.update(client, update_data)

    async def delete_client(self, client_id: UUID) -> None:
        client = await self.get_client(client_id)
        await self.repository.soft_delete(client)
```

---

## Router (`clients/router.py`)

```python
router = APIRouter(prefix="/clients", tags=["clients"])

@router.post("/", response_model=ClientResponse, status_code=201)
async def create_client(
    data: ClientCreate,
    db: TenantSession,
    professional_id: CurrentProfessionalId,
):
    service = ClientsService(db)
    client = await service.create_client(UUID(professional_id), data)
    return client

@router.get("/", response_model=list[ClientResponse])
async def list_clients(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: TenantSession = ...,
):
    service = ClientsService(db)
    return await service.list_clients(skip=skip, limit=limit)

@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(client_id: UUID, db: TenantSession):
    service = ClientsService(db)
    return await service.get_client(client_id)

@router.patch("/{client_id}", response_model=ClientResponse)
async def update_client(client_id: UUID, data: ClientUpdate, db: TenantSession):
    service = ClientsService(db)
    return await service.update_client(client_id, data)

@router.delete("/{client_id}", status_code=204)
async def delete_client(client_id: UUID, db: TenantSession):
    service = ClientsService(db)
    await service.delete_client(client_id)
```

---

## Model (`clients/models.py`)

```python
class Client(Base, TimestampMixin):
    __tablename__ = "clients"

    professional_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("professionals.id", ondelete="RESTRICT"),
        nullable=False,
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)
    whatsapp_opt_in: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_opt_in: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
```

`ON DELETE RESTRICT` — cliente tem valor histórico (sessões, financeiro, IA).
Sem `relationship()` — ADR-006.

**Índices:**

```sql
-- Acesso por tenant (toda query passa por aqui via RLS)
CREATE INDEX idx_clients_professional_id ON clients(professional_id);

-- Busca por telefone dentro do tenant — justifica find_by_phone() sem filtro de professional_id
-- O índice composto cobre (professional_id, phone) — o RLS já garante o tenant,
-- mas o índice acelera a busca mesmo sem o filtro explícito no repository.
CREATE INDEX idx_clients_phone ON clients(professional_id, phone);
```

O índice composto `(professional_id, phone)` é a razão pela qual `find_by_phone()` é
eficiente mesmo sem um `WHERE professional_id = ?` explícito na query — o PostgreSQL
usa o índice para restringir a busca ao tenant corrente via RLS.

---

## Testes

| Arquivo | Count | Cobertura principal |
|---|---|---|
| `tests/clients/test_model.py` | 3 | Defaults, constraints, RLS policy |
| `tests/clients/test_repository.py` | 19 | create, find_by_id, find_all, find_by_phone, update, soft_delete |
| `tests/clients/test_service.py` | 22 | create (ConflictError), get (NotFoundError), list, update (PATCH), delete |
| `tests/clients/test_router.py` | 32 | POST 201, GET 200/404, PATCH 200, DELETE 204, paginação, RLS isolation |

### Cenários críticos testados

- `create_client` com `phone` duplicado no mesmo tenant → `ConflictError` (409)
- `create_client` com `phone` duplicado em tenant diferente → sucesso (RLS isola)
- `get_client` com ID de outro tenant → `NotFoundError` (404) — RLS retorna `None`
- `update_client` com PATCH enviando `phone=null` → campo é limpo no banco (`exclude_unset`)
- `delete_client` → `is_active=False`, registro permanece no banco
- `list_clients` só retorna `is_active=True` por padrão

---

## Padrões e Gotchas

### `exclude_unset=True` vs `exclude_none=True` em PATCH

Para campos nullable (`phone`, `email`), usar `model_dump(exclude_unset=True)`:

```python
# exclude_unset=True — CORRETO
# Dados enviados: {"phone": null}
# update_data = {"phone": None}  → banco atualiza para NULL ✓

# exclude_none=True — ERRADO para campos nullable
# Dados enviados: {"phone": null}
# update_data = {}  → phone não é atualizado, valor antigo permanece ✗
```

### `min_length` em testes de router

Campos com `min_length=2` (ex: `full_name`) precisam de valores com ao menos 2 caracteres
nos testes. `full_name="A"` gera resposta 422 silenciosa — o cliente não é criado, mas
o teste pode não perceber se não verificar o status code explicitamente.

### RLS vs filtro explícito no repository

O repository **não adiciona** `where(Client.professional_id == professional_id)`.
O RLS do banco filtra automaticamente. Isso significa:

- `find_by_id(uuid)` para ID de outro tenant → retorna `None` (RLS filtra), não erro de FK
- `find_all()` → retorna apenas clientes do tenant ativo
- `find_by_phone(phone)` → busca apenas entre clientes do tenant ativo

O RLS é a segunda barreira (ADR-001) — a primeira barreira seria o filtro explícito, que
foi intencionalmente omitido no repository para manter o código simples e confiar no RLS.

---

## Referências Cruzadas

- `domains/schema.md` — SQL completo da tabela `clients`
- `domains/agenda.md` — `sessions` referencia `clients` com `ON DELETE RESTRICT`
- `domains/whatsapp.md` — `whatsapp_conversations` referencia `clients` com `ON DELETE SET NULL`
- ADR-001 — multi-tenancy RLS (por que repository não filtra por `professional_id`)
- ADR-009 — soft delete com `is_active`
- ADR-021 — testes de isolamento RLS