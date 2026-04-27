# Domain: core/

Módulo de infraestrutura compartilhada. Nenhum outro módulo é importado por `core/` —
o fluxo de dependência é sempre `módulos → core`, nunca o inverso.

---

## Arquivos

### `core/config.py`

`Settings` via `pydantic-settings`. Lê variáveis do `.env` com validação de tipos em startup.
Fail-fast: se uma variável obrigatória estiver ausente, a aplicação não sobe.

```python
class Settings(BaseSettings):
    # Banco
    DATABASE_URL: str
    TEST_DATABASE_URL: str

    # JWT
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15

    # Refresh Token
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # WhatsApp Business API (Meta Cloud API)
    WHATSAPP_VERIFY_TOKEN: str
    WHATSAPP_APP_SECRET: str    # para verificar assinatura HMAC dos webhooks

    # Aplicação
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    # CORS (aceita string CSV ou lista)
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Criptografia (para dados sensíveis em repouso — ex: whatsapp_access_token)
    ENCRYPTION_KEY: str    # Fernet key — obrigatório

    # IA
    ANTHROPIC_API_KEY: str

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()
```

Uso em todo o projeto via `from core.config import settings`.

---

### `core/database.py`

Engine async + sessão + contexto de tenant.

```python
engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

async def set_tenant_context(session: AsyncSession, tenant_id: UUID) -> None:
    # PostgreSQL não suporta bind params em SET — UUID validado pelo tipo Python
    await session.execute(
        text(f"SET LOCAL app.current_tenant = '{tenant_id}'")
    )

async def clear_tenant_context(session: AsyncSession) -> None:
    """Remove o tenant context via RESET app.current_tenant (útil em testes)."""

async def check_database_connection() -> bool:
    """Verifica se o banco está saudável — usado no endpoint /health."""

async def init_db() -> None:
    """Cria tabelas via create_all (apenas testes — produção usa Alembic)."""

# async_session_maker: alias do async_sessionmaker configurado com o engine
```

**Regra:** `get_db()` é o único lugar onde `session.commit()` é chamado. Ver ADR-007.

---

### `core/mixins.py`

```python
class TimestampMixin:
    """Para entidades editáveis — created_at + updated_at."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False
    )

class CreatedAtMixin:
    """Para registros imutáveis — apenas created_at."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
```

| Mixin | Usado em |
|---|---|
| `TimestampMixin` | `Professional`, `Client`, `AvailabilitySlot`, `Session`, `Recurrence`, `WhatsAppConversation` |
| `CreatedAtMixin` | `RefreshToken`, `BlockedPeriod`, `AuditLog`, `WhatsAppMessage` (usa `sent_at` próprio) |

---

### `core/security.py`

```python
# Hashing de senha
def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

# JWT
def create_access_token(subject: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": subject, "exp": expire}, settings.SECRET_KEY, settings.ALGORITHM)

def decode_access_token(token: str) -> str:
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    return payload["sub"]  # professional_id como string UUID

# Refresh Token
def generate_refresh_token() -> tuple[str, str]:
    """Retorna (raw_token, hashed_token). Armazenar apenas o hash."""
    raw = secrets.token_urlsafe(64)
    hashed = hashlib.sha256(raw.encode()).hexdigest()
    return raw, hashed

def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()
```

**Nota:** `bcrypt` fixado em `>=3.2,<4` por incompatibilidade com passlib 1.7.4 (ADR-013).

---

### `core/exceptions.py`

Hierarquia de exceções com HTTP status codes mapeados em `main.py`:

```python
class AppException(Exception):
    pass

class AuthenticationError(AppException): ...   # 401
class AuthorizationError(AppException): ...    # 403
class NotFoundError(AppException): ...         # 404
class ValidationError(AppException): ...       # 422
class ConflictError(AppException): ...         # 409
class ExternalServiceError(AppException): ...  # 502
class RateLimitError(AppException): ...        # 429
class DatabaseError(AppException): ...         # 500
```

Exception handlers em `main.py` capturam `AppException` e retornam JSON com o formato:
```json
{"error": {"message": "...", "detail": {...}}}
```

**Gotcha:** `exc.errors()` do Pydantic v2 inclui `ctx: {'error': ValueError(...)}` que não é
JSON-serializable. Usar `jsonable_encoder(exc.errors())` no `validation_exception_handler`.

---

### `core/deps.py`

Três tipos de dependência FastAPI para compor o nível de acesso:

```python
# Sessão pura — rotas públicas (login, register, webhook)
DbSession = Annotated[AsyncSession, Depends(get_db)]

# Extrai e valida o JWT — retorna professional_id como string
CurrentProfessionalId = Annotated[str, Depends(get_current_professional_id)]

# get_db + JWT + SET LOCAL — rotas protegidas com isolamento de tenant
TenantSession = Annotated[AsyncSession, Depends(get_tenant_db)]
```

Uso nos routers:

```python
# Rota pública
@router.post("/auth/login")
async def login(data: LoginRequest, db: DbSession): ...

# Rota protegida (JWT obrigatório, RLS ativo)
@router.get("/professionals/me")
async def get_me(db: TenantSession, professional_id: CurrentProfessionalId): ...
```

Ver ADR-003 para o raciocínio completo.

---

### `core/models.py`

```python
class AuditLog(Base, CreatedAtMixin):
    __tablename__ = "audit_logs"

    professional_id: Mapped[UUID | None]   # SET NULL — profissional pode ser deletado
    action: Mapped[str]                    # ex: "client.created", "session.cancelled"
    entity: Mapped[str]                    # ex: "client", "session"
    entity_id: Mapped[UUID | None]
    old_data: Mapped[dict | None]          # JSONB snapshot antes da alteração
    new_data: Mapped[dict | None]          # JSONB snapshot após a alteração
    ip_address: Mapped[str | None]         # VARCHAR(45) — suporta IPv6
    user_agent: Mapped[str | None]
```

Sem RLS — acesso controlado pelo service layer. Sem `updated_at` — imutável por definição.

---

## Testes

| Arquivo | Testes | O que cobre |
|---|---|---|
| `tests/core/test_security.py` | 17 | `hash_password`, `verify_password`, JWT create/decode, refresh token generate/hash |
| `tests/core/test_deps.py` | 6 | `DbSession`, `CurrentProfessionalId`, `TenantSession` — includes token inválido |

---

## Constraints e Gotchas

- **Nunca importar módulos de domínio em `core/`** — apenas stdlib, FastAPI, SQLAlchemy, Pydantic
- **`set_tenant_context()` sempre via f-string** — não via bind params (ADR-008)
- **`session.commit()` apenas em `get_db()`** — nunca no service layer (ADR-007)
- **`settings` é singleton** — importado diretamente, não recriado por request
- **`Base` define apenas `id`** — timestamps são opt-in via mixin, não herança obrigatória