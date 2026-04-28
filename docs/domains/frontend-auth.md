# Domain: frontend/auth

> Implementação completa. Build limpo (tsc --noEmit + vite build: zero erros).

---

## Visão Geral

O frontend gerencia autenticação via `AuthContext` + interceptors axios. O access token
vive em memória (variável de módulo), o refresh token viaja exclusivamente via HttpOnly
cookie. Nenhum dado de autenticação toca `localStorage` ou React state direto.

---

## Fluxos de Autenticação

### Registro

```
RegisterPage
  → useAuth().register(data)
    → POST /auth/register          → 201 ProfessionalResponse
    → POST /auth/login             → 200 { access_token } + Set-Cookie: refresh_token
    → setAccessToken(access_token)
    → GET /professionals/me        → 200 ProfessionalResponse
    → setProfessional(data)
    → isLoading=false
      → PublicRoute vê isAuthenticated=true → <Navigate to="/dashboard" />
```

### Login

```
LoginPage
  → useAuth().login(email, password)
    → POST /auth/login             → 200 { access_token } + Set-Cookie: refresh_token
    → setAccessToken(access_token)
    → GET /professionals/me        → 200 ProfessionalResponse
    → setProfessional(data)
      → PublicRoute vê isAuthenticated=true → <Navigate to="/dashboard" />
```

### Restore de Sessão (reload de página)

```
App mount
  → AuthProvider useEffect
    → POST /auth/refresh           → 200 { access_token }   (usa HttpOnly cookie)
    → setAccessToken(access_token)
    → GET /professionals/me        → 200 ProfessionalResponse
    → setProfessional(data)
    → setIsLoading(false)          ← no finally — sempre executa
      → ProtectedRoute libera children
```

### Logout

```
DashboardPage
  → useAuth().logout()
    → POST /auth/logout            → 204 (revoga token + limpa cookie no servidor)
    → setAccessToken(null)
    → setProfessional(null)
    → (em finally — mesmo em erro de rede)
      → ProtectedRoute vê isAuthenticated=false → <Navigate to="/login" />
```

### Renovação Automática de Token (401)

```
Qualquer request → 401
  → interceptor response
  → isRefreshing=false?
      → isRefreshing=true
      → POST /auth/refresh
      → setAccessToken(novo_token)
      → flushQueue(novo_token)      ← libera requests pendentes
      → retenta request original
  → isRefreshing=true?
      → entra na refreshQueue
      → aguarda flushQueue()
      → retenta com novo token
```

---

## Arquivos

### `src/services/api.ts`

Instância axios central. Todas as chamadas da aplicação passam por aqui.

**Configuração base:**
```typescript
export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL,  // ex: /api/v1
  withCredentials: true,                   // obrigatório para o cookie HttpOnly trafegar
})
```

**Token em variável de módulo** (não React state — ver ADR-014):
```typescript
let _accessToken: string | null = null

export function setAccessToken(token: string | null): void {
  _accessToken = token
}
```

**Interceptor de request** — injeta Bearer token:
```typescript
api.interceptors.request.use((config) => {
  if (_accessToken) {
    config.headers.Authorization = `Bearer ${_accessToken}`
  }
  return config
})
```

**Interceptor de response** — renova token em 401:
```typescript
const SKIP_REFRESH_PATHS = ['/auth/login', '/auth/register', '/auth/refresh']

let isRefreshing = false
let refreshQueue: Array<{ resolve: (t: string) => void; reject: (e: unknown) => void }> = []

api.interceptors.response.use(
  (res) => res,
  async (error: AxiosError) => {
    const req = error.config as AxiosRequestConfig & { _retry?: boolean }

    if (SKIP_REFRESH_PATHS.some(p => req.url?.includes(p))) {
      return Promise.reject(error)
    }

    if (error.response?.status === 401 && !req._retry) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          refreshQueue.push({
            resolve: (token) => {
              req.headers!.Authorization = `Bearer ${token}`
              resolve(api(req))
            },
            reject,
          })
        })
      }

      req._retry = true
      isRefreshing = true

      try {
        const { data } = await api.post('/auth/refresh')
        setAccessToken(data.access_token)
        refreshQueue.forEach(({ resolve }) => resolve(data.access_token))
        refreshQueue = []
        req.headers!.Authorization = `Bearer ${data.access_token}`
        return api(req)
      } catch (err) {
        refreshQueue.forEach(({ reject }) => reject(err))
        refreshQueue = []
        setAccessToken(null)
        return Promise.reject(err)
      } finally {
        isRefreshing = false
      }
    }

    return Promise.reject(error)
  }
)
```

---

### `src/contexts/AuthContext.tsx`

```typescript
interface AuthContextValue {
  professional: ProfessionalResponse | null
  isLoading: boolean                          // true até restore terminar — ADR-015
  isAuthenticated: boolean                    // derived: professional !== null
  login: (email: string, password: string) => Promise<void>
  register: (data: RegisterRequest) => Promise<void>
  logout: () => Promise<void>
}
```

**Restore de sessão no mount:**
```typescript
const didAttemptRestore = useRef(false)   // guard contra StrictMode double-invocation

useEffect(() => {
  if (didAttemptRestore.current) return
  didAttemptRestore.current = true

  const restoreSession = async () => {
    try {
      const { data } = await api.post<AccessTokenResponse>('/auth/refresh')
      setAccessToken(data.access_token)
      const { data: me } = await api.get<ProfessionalResponse>('/professionals/me')
      setProfessional(me)
    } catch {
      setProfessional(null)
    } finally {
      setIsLoading(false)   // ADR-015: sempre false após tentativa, sucesso ou falha
    }
  }

  restoreSession()
}, [])
```

**Por que `useRef` e não `let called = false`?**
`useRef` persiste entre as duas invocações do `useEffect` no StrictMode do React 18.
Uma variável `let` local seria recriada a cada invocação — não funcionaria como guard.

**Logout com `finally`:**
```typescript
const logout = async () => {
  try {
    await api.post('/auth/logout')
  } finally {
    // Sempre limpa o estado local — mesmo em erro de rede
    // O usuário não pode ficar "preso" autenticado por falha de rede no logout
    setAccessToken(null)
    setProfessional(null)
  }
}
```

---

### `src/hooks/useAuth.ts`

```typescript
export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error(
      'useAuth() deve ser usado dentro de <AuthProvider>. ' +
      'Verifique se o componente está dentro da árvore do AuthProvider.'
    )
  }
  return context
}
```

Erro descritivo — facilita diagnóstico quando o hook é usado fora do provider.

---

### `src/components/ProtectedRoute.tsx`

```typescript
export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth()

  if (isLoading) return <Spinner />                           // aguarda restore
  if (!isAuthenticated) return <Navigate to="/login" replace />
  return <>{children}</>
}
```

---

### `src/components/PublicRoute.tsx`

```typescript
export function PublicRoute({ children }: { children: ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth()

  if (isLoading) return null                                  // sem flash do formulário
  if (isAuthenticated) return <Navigate to="/dashboard" replace />
  return <>{children}</>
}
```

**Por que `null` e não `<Spinner />`?**
`ProtectedRoute` mostra spinner porque o usuário está esperando acessar conteúdo protegido.
`PublicRoute` retorna `null` porque se o usuário já está autenticado, não deve nem ver o
formulário de login — evita o flash de "formulário aparece → redirect".

---

### `src/App.tsx`

```typescript
function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route
            path="/login"
            element={
              <PublicRoute>
                <LoginPage />
              </PublicRoute>
            }
          />
          <Route
            path="/register"
            element={
              <PublicRoute>
                <RegisterPage />
              </PublicRoute>
            }
          />
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <DashboardPage />
              </ProtectedRoute>
            }
          />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
```

---

### `src/types/auth.ts`

Espelham os schemas do backend. Atualize quando os schemas Pydantic mudarem.

```typescript
export interface ProfessionalResponse {
  id: string
  email: string
  full_name: string
  specialty: string | null
  bio: string | null
  session_duration: number
  session_price: string | null   // NUMERIC → string no JSON (ver ADR-010)
  phone: string | null
  is_active: boolean
  created_at: string
}

export interface LoginRequest {
  email: string
  password: string
}

export interface RegisterRequest {
  email: string
  password: string
  full_name: string
  specialty?: string
  bio?: string
}

export interface AccessTokenResponse {
  access_token: string
  token_type: string
}
```

---

## Redirect Implícito Pós-Login

As páginas de Login e Registro **não chamam `navigate()`** após o submit bem-sucedido.
Quem faz o redirect é o `PublicRoute`:

```
login() resolve → setProfessional(data) → React re-render
  → PublicRoute: isAuthenticated=true → <Navigate to="/dashboard" replace />
```

**Por que essa abordagem?**
- Centraliza a lógica de redirect no guard — não nos formulários
- Cada formulário novo não precisa saber para onde redirecionar após o login
- Consistente: o mesmo mecanismo funciona para login manual e restore de sessão

---

## Variáveis de Ambiente

```bash
# apps/web/.env.example
VITE_API_URL=/api/v1
```

Em desenvolvimento, o Vite proxy redireciona `/api/v1` para `http://localhost:8000/api/v1`
(configurado em `vite.config.ts`). Em produção, `VITE_API_URL` deve ser a URL completa da API.

```typescript
// vite.config.ts
export default defineConfig({
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
```

---

## Decisões e Gotchas

| Gotcha | Solução |
|--------|---------|
| Interceptors capturam closure stale com React state | Token em variável de módulo `_accessToken` (ADR-014) |
| Flash de redirect para /login no reload com sessão válida | `isLoading: true` no mount (ADR-015) |
| N refreshes simultâneos invalidam o token | `isRefreshing` flag + `refreshQueue` (ADR-016) |
| StrictMode invoca `useEffect` duas vezes | `useRef` guard `didAttemptRestore` |
| Cookie Secure bloqueado em dev HTTP | `secure=settings.is_production` no backend (ADR-017) |
| `session_price` como number no TypeScript | Deve ser `string` — NUMERIC vira string no JSON (ADR-010) |
| `register()` faz login automático | Chama `POST /auth/login` internamente após `POST /auth/register` |

---

## Referências Cruzadas

- ADR-002 — decisão de auth com JWT + HttpOnly cookie
- ADR-014 — token em variável de módulo
- ADR-015 — isLoading começa true
- ADR-016 — fila de requests durante refresh
- ADR-017 — cookie secure por ambiente
- ADR-018 — CORS com allow_credentials
- `domains/auth.md` — contraparte backend desta implementação