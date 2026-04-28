# Domain: auth + professionals

> Implementação completa. Todos os testes passando (74 testes Green).

---

## Responsabilidades

| Módulo | Responsabilidade |
|---|---|
| `auth/` | Login, logout, refresh token, logout global |
| `professionals/` | Registro, perfil, atualização de dados |

Os dois módulos são co-dependentes: `auth/schemas.py` re-exporta tipos de `professionals/schemas.py`
(single source of truth). `auth/service.py` depende de `ProfessionalsRepository` para validar
credenciais.

---

## Endpoints

| Método | Path | Auth | Status | Descrição |
|---|---|---|---|---|
| POST | `/api/v1/auth/register` | Pública | 201 | Cria conta → `ProfessionalResponse` |
| POST | `/api/v1/auth/login` | Pública | 200 | `access_token` no body + cookie |
| POST | `/api/v1/auth/refresh` | Cookie | 200 | Renova `access_token` |
| POST | `/api/v1/auth/logout` | Cookie | 204 | Revoga token atual + limpa cookie |
| POST | `/api/v1/auth/logout-all` | JWT + RLS | 204 | Revoga todos os tokens |
| GET | `/api/v1/professionals/me` | JWT + RLS | 200 | Perfil do profissional autenticado |
| PATCH | `/api/v1/professionals/me` | JWT + RLS | 200 | Atualiza perfil (PATCH semântico) |

---

## Schemas (`professionals/schemas.py` + `auth/schemas.py`)

### `RegisterRequest`
```python
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=2, max_length=255)
    specialty: str | None = Field(default=None, max_length=255)
    bio: str | None = None
```

### `LoginRequest`
```python
class LoginRequest(BaseModel):
    email: EmailStr
    password: str
```

### `AccessTokenResponse`
```python
class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
```

### `ProfessionalResponse`
```python
class ProfessionalResponse(BaseModel):
    id: UUID
    email: str
    full_name: str
    specialty: str | None
    bio: str | None
    session_duration: int
    session_price: str | None   # NUMERIC → string no JSON
    phone: str | None
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
```

> `password_hash` nunca aparece em nenhum schema de resposta.

### `UpdateProfileRequest`
```python
class UpdateProfileRequest(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    specialty: str | None = None
    bio: str | None = None
    session_duration: int | None = Field(default=None, gt=0)
    session_price: Decimal | None = None
    phone: str | None = Field(default=None, max_length=20)
```

---

## Repository

### `ProfessionalsRepository` (`professionals/repository.py`)

| Método | Descrição |
|---|---|
| `create(data: RegisterRequest)` | Insere novo profissional com `password_hash` já hasheado |
| `find_by_email(email: str)` | Busca por email — retorna `None` se não encontrado |
| `find_by_id(professional_id: UUID)` | Busca por PK |
| `update(professional, data: dict)` | Atualiza campos passados — recebe dict do `model_dump(exclude_unset=True)` |

### `RefreshTokenRepository` (`auth/repository.py`)

| Método | Descrição |
|---|---|
| `create(professional_id, token_hash, device_info, expires_at)` | Insere refresh token |
| `find_by_hash(token_hash: str)` | Busca token por SHA-256 hash |
| `revoke(token: RefreshToken)` | Seta `revoked=True` |
| `revoke_all(professional_id: UUID)` | Revoga todos os tokens do profissional |
| `delete_expired()` | Remove tokens expirados — retorna count (para job noturno) |

---

## Service

### `ProfessionalsService` (`professionals/service.py`)

```python
async def register(data: RegisterRequest) -> Professional:
    # Verifica se email já existe → ConflictError se duplicado
    # hash_password(data.password) antes de criar
    # Retorna Professional criado

async def get_by_id(professional_id: UUID) -> Professional:
    # NotFoundError se não existe

async def update_profile(professional: Professional, data: UpdateProfileRequest) -> Professional:
    # PATCH semântico: model_dump(exclude_unset=True)
    # Só atualiza campos enviados — ignora campos ausentes
    # Usa exclude_none=False: campos enviados como null são atualizados para NULL
```

### `AuthService` (`auth/service.py`)

```python
async def login(email: str, password: str) -> tuple[str, str]:
    # Anti-enumeração: mesma mensagem para email inválido e senha errada (ADR-012)
    # Retorna (access_token_jwt, raw_refresh_token)

async def refresh_access_token(raw_token: str) -> tuple[str, str]:
    # hash_refresh_token(raw_token) → busca no banco
    # Verifica: não revogado, não expirado
    # Revoga o token atual (rotação de token)
    # Cria novo refresh token
    # Retorna (novo_access_token, novo_raw_refresh_token)

async def logout(raw_token: str) -> None:
    # Idempotente: se token não encontrado, não lança erro
    # Revoga o token se encontrado

async def logout_all(professional_id: UUID) -> None:
    # Revoga todos os refresh_tokens do profissional
    # Usado quando JWT está presente (TenantSession)
```

---

## Router — Detalhes de Implementação

### Cookie de refresh token

```python
# auth/router.py
def _set_refresh_cookie(response: Response, raw_token: str) -> None:
    response.set_cookie(
        key="refresh_token",
        value=raw_token,
        httponly=True,
        secure=settings.is_production,   # ADR-017
        samesite="strict",
        max_age=30 * 24 * 60 * 60,
    )

def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key="refresh_token", httponly=True, samesite="strict")
```

### Leitura do cookie

```python
@router.post("/refresh")
async def refresh(
    refresh_token: str = Cookie(default=None),   # FastAPI lê o HttpOnly cookie
    db: DbSession = ...,
):
    if not refresh_token:
        raise AuthenticationError("Missing refresh token")
    ...
```

### Logout é idempotente

```python
@router.post("/logout", status_code=204)
async def logout(response: Response, refresh_token: str = Cookie(default=None), ...):
    if refresh_token:
        await auth_service.logout(refresh_token)
    _clear_refresh_cookie(response)   # sempre limpa o cookie, mesmo sem token
```

---

## Modelo (`professionals/models.py`, `auth/models.py`)

```python
class Professional(Base, TimestampMixin):
    __tablename__ = "professionals"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    specialty: Mapped[str | None] = mapped_column(String(255))
    bio: Mapped[str | None] = mapped_column(Text)
    session_duration: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    session_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    phone: Mapped[str | None] = mapped_column(String(20))
    whatsapp_phone_number: Mapped[str | None] = mapped_column(String(20))
    whatsapp_phone_id: Mapped[str | None] = mapped_column(String(100))
    whatsapp_access_token: Mapped[str | None] = mapped_column(Text)
    whatsapp_connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    whatsapp_token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class RefreshToken(Base, CreatedAtMixin):
    __tablename__ = "refresh_tokens"

    professional_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("professionals.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    device_info: Mapped[str | None] = mapped_column(String(255))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
```

> `ON DELETE CASCADE` em `refresh_tokens.professional_id` — token sem profissional não
> tem valor. Sem `updated_at` — `RefreshToken` é imutável (apenas `revoked` muda, setado
> direto, não via `updated_at`).

---

## Fluxo de Segurança do Token

```
login():
  raw_token = secrets.token_urlsafe(64)   # 64 bytes → 86 chars base64url
  token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
  RefreshToken(token_hash=token_hash, ...)  # banco armazena o hash
  Cookie(value=raw_token)                  # browser recebe o token puro

refresh():
  raw_token ← HttpOnly cookie
  token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
  db_token = find_by_hash(token_hash)      # busca pelo hash
  # valida: não revogado, não expirado
  revoke(db_token)                         # rotação: invalida o token atual
  new_raw, new_hash = generate_refresh_token()
  RefreshToken(token_hash=new_hash, ...)   # novo token no banco
  Cookie(value=new_raw)                    # novo token para o browser
```

---

## Testes

| Arquivo | Count | Cobertura principal |
|---|---|---|
| `tests/professionals/test_model.py` | 5 | Constraints, defaults, unicidade de email |
| `tests/auth/test_model.py` | 3 | RefreshToken: hash, revoked, expires_at |
| `tests/professionals/test_repository.py` | 8 | CRUD, find_by_email, find_by_id |
| `tests/auth/test_repository.py` | 9 | create, find_by_hash, revoke, revoke_all, delete_expired |
| `tests/professionals/test_service.py` | 10 | register (ConflictError), get_by_id, update_profile |
| `tests/auth/test_service.py` | 14 | login, refresh, logout, logout_all, anti-enumeração |
| `tests/professionals/test_router.py` | 9 | GET /me, PATCH /me |
| `tests/auth/test_router.py` | 16 | register, login, refresh, logout, logout-all |

---

## Decisões e Gotchas

- `auth/schemas.py` re-exporta de `professionals/schemas.py` — single source of truth para
  `RegisterRequest` e `ProfessionalResponse`
- Login: anti-enumeração (ADR-012) — `if professional is None or not verify_password(...):`
  mesma exception para ambos os casos
- `update_profile` usa `exclude_unset=True` — campos não enviados não são alterados; campos
  enviados como `null` são limpos (diferente de `exclude_none=True`)
- `logout` é idempotente — token já revogado ou inexistente não lança erro
- `logout-all` exige `TenantSession` (JWT válido) — não apenas o cookie
- `session_price` é `NUMERIC` no banco → `str` no JSON → `str` nos tipos TypeScript

## Referências Cruzadas

- ADR-002 — decisão de auth com JWT + cookie
- ADR-003 — TenantSession para rotas protegidas
- ADR-007 — nunca commit no service layer
- ADR-012 — anti-enumeração no login
- ADR-013 — bcrypt fixado em <4
- `domains/frontend-auth.md` — contraparte frontend desta implementação