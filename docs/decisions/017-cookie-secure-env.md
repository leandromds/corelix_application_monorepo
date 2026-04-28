# 017 - Cookie `secure` Controlado pelo Ambiente

**Status:** `accepted`

---

## Context

O refresh token é enviado ao browser como um HttpOnly cookie com o flag `secure=True`,
que instrui o browser a **nunca enviar o cookie em conexões HTTP** — apenas HTTPS.

Em produção, isso é o comportamento correto e obrigatório. Mas durante o desenvolvimento
local, o frontend (Vite) e o backend (uvicorn) se comunicam via HTTP (`http://localhost`).
Com `secure=True` hardcoded, o cookie é definido pelo servidor mas rejeitado pelo browser
em qualquer request HTTP — o Vite proxy não consegue transmiti-lo.

O resultado prático: o refresh token nunca chega ao frontend em desenvolvimento, tornando
o fluxo de autenticação completamente inoperante localmente.

## Decision

O flag `secure` do cookie é controlado pela variável de ambiente `ENVIRONMENT`:

```python
# auth/router.py
response.set_cookie(
    key="refresh_token",
    value=raw_token,
    httponly=True,
    secure=settings.is_production,   # False em dev, True em prod
    samesite="strict",
    max_age=30 * 24 * 60 * 60,
)
```

```python
# core/config.py
class Settings(BaseSettings):
    ENVIRONMENT: str = "development"

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"
```

`.env` em desenvolvimento:
```
ENVIRONMENT=development
```

Railway (produção):
```
ENVIRONMENT=production
```

## Rationale

**Por que não usar `secure=False` fixo?**
Em produção, um cookie sem `secure` pode ser transmitido sobre HTTP — se o browser
fizer um request HTTP (redirect, mixed content), o token viajaria em claro. Isso
anula a proteção do HttpOnly. `secure=True` em produção é não-negociável.

**Por que não usar HTTPS localmente (self-signed cert)?**
- Exige configuração de certificado no Vite + uvicorn + browser (trust store)
- Gera fricção de setup para um dev solo
- O risco real de interceptação em localhost é zero — sem ganho de segurança real
- Prolonga desnecessariamente o ciclo de desenvolvimento

**Por que `samesite="strict"` é mantido em desenvolvimento?**
`samesite` controla envio cross-site — não tem relação com HTTP/HTTPS. Mantê-lo
em desenvolvimento garante que o comportamento testado localmente é idêntico ao
de produção nesse aspecto.

**Por que `is_production` como propriedade do Settings (e não verificação inline)?**
Centraliza a lógica de "estou em produção?" em um único lugar — reutilizável em
qualquer parte do código que precise se comportar diferente por ambiente (ex: CORS
origins, logging level, email sending).

## Consequences

**Positivos:**
- Desenvolvimento funciona nativamente sem configuração extra de HTTPS
- Produção mantém `secure=True` — sem degradação de segurança
- Configuração explícita via variável de ambiente — sem "magic" de detecção automática

**Negativos / Trade-offs:**
- Dev precisa garantir que `ENVIRONMENT=development` no `.env` local — se esquecido
  e `ENVIRONMENT=production` for usado localmente, o cookie não funciona em HTTP
- A distinção `is_production` deve ser usada **somente** para comportamentos onde a
  diferença de ambiente é intencional — não como escape hatch para "desabilitar segurança"

**Ambientes intermediários (staging):**
Se um ambiente de staging usar HTTPS, deve ter `ENVIRONMENT=production` para que o
cookie funcione corretamente. O nome `is_production` é uma simplificação — semanticamente
significa "ambiente com HTTPS", não necessariamente o ambiente de produção real.
Um refinamento futuro pode ser `ENVIRONMENT=staging` com comportamento igual a `production`.

## Referências

- `auth/router.py` — `response.set_cookie(secure=settings.is_production)`
- `core/config.py` — `Settings.is_production` property
- `.env.example` — `ENVIRONMENT=development`
- `ADR-002` — decisão geral sobre o cookie de refresh token