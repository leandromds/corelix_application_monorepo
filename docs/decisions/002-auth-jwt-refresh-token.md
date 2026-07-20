# 002 - Autenticação: JWT + Refresh Token via HttpOnly Cookie

**Status:** `accepted`

---

## Context

O sistema precisa autenticar profissionais de forma segura em um SaaS B2B.
Requisitos:
- Sessões longas (profissional não pode logar todo dia)
- Logout global (revogar acesso em todos os dispositivos)
- Proteção contra XSS e CSRF
- Dev solo — sem complexidade operacional de sessões server-side ou OAuth externo

## Decision

- **Access Token:** JWT assinado (HS256), expira em **15 minutos**, retornado no **body** da resposta
- **Refresh Token:** UUID gerado via `secrets.token_urlsafe(64)`, armazenado no banco como **hash SHA-256**, enviado e recebido exclusivamente via **HttpOnly cookie** (`secure`, `samesite=strict`)
- O token raw **nunca** aparece no body da resposta
- Logout global revoga todos os `refresh_tokens` do profissional no banco
- CORS configurado com `allow_credentials=True` e origens explícitas (nunca wildcard `*`)

### Cookie de refresh token

```python
response.set_cookie(
    key="refresh_token",
    value=raw_token,       # UUID — nunca o hash
    httponly=True,         # inacessível ao JavaScript
    secure=True,           # HTTPS only em produção
    samesite="strict",     # não enviado em requests cross-site
    max_age=30*24*60*60    # 30 dias
)
```

### Endpoints de auth

| Método | Path | Auth | Descrição |
|--------|------|------|-----------|
| POST | `/auth/register` | Pública | Cria conta → `ProfessionalResponse` (201) |
| POST | `/auth/login` | Pública | `access_token` no body + `refresh_token` em cookie |
| POST | `/auth/refresh` | Cookie | Renova `access_token` usando o cookie |
| POST | `/auth/logout` | Cookie | Revoga token atual + limpa cookie (idempotente) |
| POST | `/auth/logout-all` | JWT | Revoga todos os tokens do profissional |

## Rationale

**Por que JWT de curta duração + refresh token (e não sessão server-side)?**
- JWT stateless reduz carga no banco para cada request autenticado
- Refresh token revogável no banco dá controle de logout global — o que sessões puramente stateless não oferecem
- Não depende de Redis ou cache externo — o banco já está presente

**Por que HttpOnly cookie (e não localStorage ou memory)?**
- `localStorage` é acessível via JavaScript → vulnerável a XSS
- `sessionStorage` se perde ao fechar a aba — inaceitável para UX profissional
- Cookie HttpOnly é inacessível ao JS, `samesite=strict` bloqueia CSRF
- `withCredentials: true` no axios garante que o cookie trafega normalmente

**Por que hash SHA-256 no banco?**
- Se o banco for comprometido, o token raw não está exposto
- O hash é determinístico — basta `hashlib.sha256(token.encode()).hexdigest()` para verificar

**Por que sem OAuth de terceiros no MVP?**
- Aumentaria a complexidade de setup (configurar Google/GitHub App)
- O público-alvo (profissionais autônomos) não espera SSO
- Pode ser adicionado pós-MVP sem breaking changes

## Consequences

**Positivos:**
- Proteção robusta contra XSS e CSRF com configuração padrão
- Logout global funcional via revogação no banco
- Sem dependências externas além do PostgreSQL já usado

**Negativos / Trade-offs:**
- `CORS allow_credentials=True` exige origens explícitas — wildcard `*` é incompatível
- Cookie `secure=True` exige HTTPS em produção — deve ser `secure=settings.is_production` em dev (ver ADR-017)
- Testes com httpx precisam de `base_url="https://testserver"` — httpx não envia cookies `Secure` para `http://` (ver ADR-021)
- Passlib 1.7.4 incompatível com bcrypt 4.x+ — fixado em `<4` (ver ADR-013)

**Futuro:**
- Job noturno (`pgqueuer`) deve chamar `delete_expired()` no `RefreshTokenRepository` para limpar tokens expirados
- `device_info` no refresh_token está pronto para suportar "gerenciar sessões ativas" no dashboard