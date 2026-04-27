# 016 - Fila de Requests Durante Refresh de Token

**Status:** `accepted`

---

## Context

O interceptor de response do axios detecta respostas `401 Unauthorized` e inicia
automaticamente um `POST /auth/refresh` para renovar o access token. Em seguida,
retenta o request original com o novo token.

O problema ocorre quando **múltiplos requests falham com 401 simultaneamente** — cenário
comum ao abrir uma página que dispara vários `useEffect` em paralelo (ex: dashboard
carregando agenda + relatório + clientes ao mesmo tempo):

```
Request A → 401 → inicia POST /auth/refresh
Request B → 401 → inicia POST /auth/refresh  ← segundo refresh simultâneo
Request C → 401 → inicia POST /auth/refresh  ← terceiro refresh simultâneo
```

O problema: cada `POST /auth/refresh` **consume e invalida** o refresh token atual,
gerando um novo token. O segundo e terceiro refresh receberão o token já invalidado
pelo primeiro — resultando em logout forçado mesmo com sessão válida.

## Decision

Implementar uma **fila de requests pendentes** com um flag `isRefreshing` em `api.ts`:

```typescript
let isRefreshing = false
let refreshQueue: Array<{
  resolve: (token: string) => void
  reject: (error: unknown) => void
}> = []

function flushQueue(token: string): void {
  refreshQueue.forEach(({ resolve }) => resolve(token))
  refreshQueue = []
}

function rejectQueue(error: unknown): void {
  refreshQueue.forEach(({ reject }) => reject(error))
  refreshQueue = []
}

axiosInstance.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as AxiosRequestConfig & { _retry?: boolean }

    // Não tenta refresh em rotas de auth
    if (SKIP_REFRESH_PATHS.some(path => originalRequest.url?.includes(path))) {
      return Promise.reject(error)
    }

    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        // Já há um refresh em andamento — entra na fila
        return new Promise((resolve, reject) => {
          refreshQueue.push({
            resolve: (token) => {
              originalRequest.headers!.Authorization = `Bearer ${token}`
              resolve(axiosInstance(originalRequest))
            },
            reject,
          })
        })
      }

      originalRequest._retry = true
      isRefreshing = true

      try {
        const { data } = await axiosInstance.post('/auth/refresh')
        setAccessToken(data.access_token)
        flushQueue(data.access_token)       // libera todos na fila com o novo token
        originalRequest.headers!.Authorization = `Bearer ${data.access_token}`
        return axiosInstance(originalRequest)
      } catch (refreshError) {
        rejectQueue(refreshError)           // rejeita toda a fila
        setAccessToken(null)
        // redireciona para login ou emite evento de sessão expirada
        return Promise.reject(refreshError)
      } finally {
        isRefreshing = false
      }
    }

    return Promise.reject(error)
  }
)
```

### `SKIP_REFRESH_PATHS`

Rotas que nunca devem disparar uma tentativa de refresh em caso de 401:

```typescript
const SKIP_REFRESH_PATHS = ['/auth/login', '/auth/register', '/auth/refresh']
```

Sem essa lista, um 401 no próprio `/auth/refresh` causaria um loop infinito de tentativas
de refresh.

## Rationale

**Por que fila (e não simplesmente ignorar requests simultâneos)?**

Ignorar os requests B e C significaria que eles falhariam do ponto de vista da UI —
o dashboard mostraria componentes com erro mesmo com sessão válida. A fila preserva
todos os requests: eles apenas aguardam o refresh terminar e retentam com o novo token.

**Por que `_retry` flag no request original?**

Garante que um request não entre em loop: se ele falha com 401 após o refresh (token
genuinamente inválido ou expirado), não tenta refresh de novo — rejeita imediatamente.

**Por que variáveis de módulo (`isRefreshing`, `refreshQueue`) e não React state?**

Os interceptors vivem fora do React — são registrados no carregamento do módulo e
executam em qualquer momento, independente do ciclo de render. React state não é
acessível fora de componentes/hooks. Variáveis de módulo são lidas no momento da
execução do interceptor.

**Por que `flushQueue` e `rejectQueue`?**

`flushQueue` libera todos os requests pendentes com o novo token — eles retentam em
paralelo, sem serialização desnecessária. `rejectQueue` propaga a falha do refresh para
todos os callers — cada um pode exibir seu próprio estado de erro ou o AuthContext pode
redirecionar para login.

## Consequences

**Positivos:**
- Exatamente um `POST /auth/refresh` por janela de 401 simultâneos — sem invalidação
  prematura de refresh tokens
- Todos os requests pendentes são resolvidos com o novo token — sem perda de dados da UI
- Sem loop infinito — `_retry` flag e `SKIP_REFRESH_PATHS` protegem as rotas de auth

**Negativos / Trade-offs:**
- Complexidade não trivial para uma feature que parece simples
- `refreshQueue` deve ser limpo em caso de logout — se o usuário fizer logout enquanto
  há requests na fila, eles serão rejeitados via `rejectQueue` no catch do refresh
- Requests na fila ficam "pendurados" pelo tempo do refresh (~200-500ms) — aceitável

## Referências

- `src/services/api.ts` — implementação de `isRefreshing`, `refreshQueue`, interceptors
- `ADR-014` — token em variável de módulo (contexto do `_accessToken`)
- `ADR-015` — `isLoading` no AuthContext (complementa o restore de sessão)
- `ADR-002` — decisão geral de auth com JWT + HttpOnly cookie