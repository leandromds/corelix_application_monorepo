# 014 - Token de Acesso Frontend em Variável de Módulo

**Status:** `accepted`

---

## Context

O frontend precisa armazenar o access token JWT para injetá-lo no header `Authorization`
de cada request autenticado. A questão central é: **onde guardar esse valor?**

As opções avaliadas foram:

1. `localStorage` / `sessionStorage` — persistência no browser
2. React state (`useState`) — estado do componente/contexto
3. Variável de módulo em `api.ts` — escopo de módulo JavaScript
4. `useRef` no AuthProvider — ref do React

O sistema usa interceptors do axios registrados **uma única vez** no momento em que o
módulo `api.ts` é carregado. Esse é o ponto crítico que determina a escolha.

## Decision

O access token é armazenado em uma **variável de módulo privada** em `src/services/api.ts`:

```typescript
// src/services/api.ts
let _accessToken: string | null = null

export function setAccessToken(token: string | null): void {
  _accessToken = token
}

export function getAccessToken(): string | null {
  return _accessToken
}

// Interceptor registrado UMA VEZ no carregamento do módulo
axiosInstance.interceptors.request.use((config) => {
  if (_accessToken) {
    config.headers.Authorization = `Bearer ${_accessToken}`
  }
  return config
})
```

O `AuthContext` chama `setAccessToken()` nos eventos de login, refresh e logout —
mas o token em si nunca é React state.

## Rationale

**Por que não `localStorage` / `sessionStorage`?**
- `localStorage` e `sessionStorage` são acessíveis via `window.localStorage` no console
  do browser e por qualquer script JavaScript na página — incluindo scripts injetados por XSS
- O refresh token já está seguro num HttpOnly cookie. O access token (15min) em memória
  é o segundo nível de proteção — expô-lo no storage anularia parte dessa defesa

**Por que não React state (`useState`)?**

Este é o ponto central da decisão. Interceptors axios são registrados com uma closure sobre
o valor no momento do registro:

```typescript
// Se token fosse useState — PROBLEMA
const [token, setToken] = useState<string | null>(null)

axiosInstance.interceptors.request.use((config) => {
  // "token" aqui é o valor capturado no closure do momento do registro: null
  // Atualizações via setToken() NÃO afetam essa closure
  if (token) { ... }
})
```

Quando o interceptor é registrado (no mount do componente ou no carregamento do módulo),
ele captura o valor de `token` naquele instante — `null`. Chamadas futuras a `setToken()`
atualizam o estado do React, mas a closure do interceptor **permanece apontando para o
valor original `null`** para sempre.

Resultado prático: nenhum request enviaria o token JWT, mesmo após login bem-sucedido.

**Analogia frontend:** é o mesmo problema de `useCallback` com array de dependências vazio
que captura um valor stale de uma prop. A variável de módulo resolve o problema porque é
lida **no momento da execução** do interceptor — não no momento do registro.

**Por que não `useRef`?**
- `useRef` só existe dentro do contexto React — não é acessível fora de componentes
- O módulo `api.ts` é plain JavaScript/TypeScript, sem acesso ao React runtime
- Variável de módulo é mais simples e igualmente eficaz

**Por que variável de módulo é segura?**
- Não persiste entre reloads de página (diferente de `localStorage`) — o token some ao fechar/recarregar
- Não é acessível via `window` ou APIs do browser
- O restore de sessão no `AuthContext` repovoatela a variável via `POST /auth/refresh` + cookie

## Consequences

**Positivos:**
- Interceptors axios funcionam corretamente — leem o valor atual a cada request
- Token não persiste no browser — sem risco de token stale em localStorage
- Sem acesso via JavaScript externo — proteção contra XSS para o access token
- Simples de implementar e raciocinar

**Negativos / Trade-offs:**
- Token some em qualquer reload de página — o `AuthContext` precisa restaurar a sessão
  no mount via `POST /auth/refresh` (usando o HttpOnly cookie)
- O delay de ~200ms do restore gera um estado `isLoading=true` inicial — ver ADR-015
- Múltiplas tabs não compartilham o token em memória — cada tab faz seu próprio restore
- Não há acesso ao token fora do módulo `api.ts` sem chamar `getAccessToken()` explicitamente

**Regra de ouro:**
> O access token nunca toca `localStorage`, `sessionStorage` ou React state.
> Só existe em `_accessToken` (variável de módulo em `api.ts`) e em trânsito no header HTTP.

## Referências

- `src/services/api.ts` — implementação de `_accessToken`, `setAccessToken()`, interceptors
- `src/contexts/AuthContext.tsx` — chama `setAccessToken()` em login, refresh e logout
- `ADR-002` — decisão geral de autenticação (JWT + HttpOnly cookie)
- `ADR-015` — `isLoading: true` no mount para evitar flash de redirect
- `ADR-016` — fila de requests durante refresh de token