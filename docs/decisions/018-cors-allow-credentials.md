# 018 - CORS: `allow_credentials=True` com Origens Explícitas

**Status:** `accepted`

---

## Context

O sistema usa cookies HttpOnly para o refresh token (ADR-002). Para que o browser envie
cookies e headers de autenticação em requests cross-origin (frontend em `localhost:5173`
chamando a API em `localhost:8000`, ou domínio de produção diferente), o servidor precisa
configurar o CORS corretamente.

A configuração padrão do FastAPI CORS middleware usa `allow_origins=["*"]` (wildcard) —
que parece conveniente, mas é **incompatível** com `allow_credentials=True`.

## Decision

CORS configurado em `main.py` com:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,   # lista explícita, nunca "*"
    allow_credentials=True,                   # obrigatório para cookies HttpOnly
    allow_methods=["*"],
    allow_headers=["*"],
)
```

`settings.allowed_origins` é lido do `.env`:

```
# .env
ALLOWED_ORIGINS=http://localhost:5173,https://app.corelix.com.br
```

**Nunca usar `allow_origins=["*"]` com `allow_credentials=True`.**

## Rationale

**Por que `allow_credentials=True` é obrigatório?**

O axios está configurado com `withCredentials: true` em todas as instâncias
(`src/services/api.ts`). Sem `allow_credentials=True` no servidor, o browser bloqueia
qualquer request com credenciais para origens diferentes — o cookie de refresh token
nunca chega ao servidor.

**Por que `allow_origins=["*"]` é incompatível com `allow_credentials=True`?**

É uma restrição da especificação CORS (RFC 6454 + Fetch Standard). O browser se recusa
a enviar credenciais (cookies, headers de autorização) para uma origem que o servidor
declarou aceitar de forma irrestrita com `*`. A razão é segurança: wildcard + credenciais
permitiria que qualquer site malicioso fizesse requests autenticados em nome do usuário.

O FastAPI lança erro explícito se você tentar combinar os dois:

```
ValueError: Cannot use allow_credentials=True with allow_origins=["*"]
```

**Por que origens em variável de ambiente (e não hardcoded)?**

- Desenvolvimento usa `http://localhost:5173` (Vite dev server)
- Produção usa `https://app.corelix.com.br`
- Testes de staging podem usar uma origem diferente

Hardcodar as origens exigiria um build diferente por ambiente. Com `settings.allowed_origins`,
o mesmo código roda em todos os ambientes com apenas uma mudança de `.env`.

**Por que `allow_methods=["*"]` e `allow_headers=["*"]` são seguros aqui?**

O controle de acesso real é feito por autenticação (JWT) e autorização (RLS) — não por
restrição de métodos HTTP ou headers. Limitar métodos CORS a `["GET", "POST"]` não
adicionaria segurança real e quebraria rotas PATCH e DELETE.

## Consequences

**Positivos:**
- Cookies HttpOnly e headers `Authorization` funcionam corretamente em requests cross-origin
- Configuração por ambiente via `.env` — sem mudança de código entre dev e produção
- Erro explícito do FastAPI se `allow_origins=["*"]` for combinado com `allow_credentials=True`

**Negativos / Trade-offs:**
- `ALLOWED_ORIGINS` deve ser configurado corretamente em cada ambiente — esquecê-lo em
  produção bloqueia todos os requests do frontend
- Adicionar uma nova origem (ex: app mobile via WebView, staging) exige atualizar a
  variável de ambiente e reiniciar o servidor
- Origens mal configuradas (ex: trailing slash em `http://localhost:5173/`) causam falhas
  silenciosas de CORS — o browser bloqueia sem mensagem clara no servidor

## Referências

- `apps/api/main.py` — configuração do `CORSMiddleware`
- `core/config.py` — `Settings.allowed_origins` (lista parseada do `.env`)
- `src/services/api.ts` — `withCredentials: true` em todas as instâncias axios
- `ADR-002` — decisão de auth com cookie HttpOnly (contexto do CORS)
- `.env.example` — `ALLOWED_ORIGINS=http://localhost:5173`
