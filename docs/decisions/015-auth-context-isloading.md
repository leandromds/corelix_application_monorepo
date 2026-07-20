# 015 - AuthContext: `isLoading` Começa `true`

**Status:** `accepted`

---

## Context

O `AuthContext` gerencia o estado de autenticação no frontend. No primeiro render da aplicação,
antes de qualquer `useEffect` executar, o estado inicial é:

```typescript
const [professional, setProfessional] = useState<ProfessionalResponse | null>(null)
```

`professional === null` implica `isAuthenticated = false`.

O `ProtectedRoute` usa `isAuthenticated` para decidir se redireciona para `/login`:

```typescript
if (!isAuthenticated) return <Navigate to="/login" replace />
```

**O problema:** se o usuário tem um cookie de refresh token válido, a sessão será restaurada
em ~200ms via `POST /auth/refresh → GET /professionals/me`. Mas no render inicial, antes
desse restore terminar, `isAuthenticated` é `false` — e o `ProtectedRoute` redireciona
imediatamente para `/login`.

O usuário vê um flash de `/login` antes de ser redirecionado de volta para `/dashboard`.
Em conexões lentas, pode até ficar preso na tela de login mesmo com sessão válida.

## Decision

`isLoading` começa `true` e só muda para `false` quando o restore de sessão termina
— seja com sucesso (sessão restaurada) ou com falha (usuário não autenticado):

```typescript
const [isLoading, setIsLoading] = useState<boolean>(true)  // ← true no mount
const [professional, setProfessional] = useState<ProfessionalResponse | null>(null)

useEffect(() => {
  const restoreSession = async () => {
    try {
      const data = await api.post('/auth/refresh')
      setAccessToken(data.access_token)
      const me = await api.get('/professionals/me')
      setProfessional(me)
    } catch {
      // sem cookie ou token inválido — usuário não autenticado
      setProfessional(null)
    } finally {
      setIsLoading(false)  // ← só aqui — após sucesso OU falha
    }
  }

  restoreSession()
}, [])
```

`ProtectedRoute` e `PublicRoute` verificam `isLoading` antes de qualquer decisão:

```typescript
// ProtectedRoute
if (isLoading) return <Spinner />           // aguarda o restore
if (!isAuthenticated) return <Navigate to="/login" replace />
return children

// PublicRoute
if (isLoading) return null                  // sem render — evita flash de formulário
if (isAuthenticated) return <Navigate to="/dashboard" replace />
return children
```

## Rationale

**Por que `true` e não `false` como valor inicial?**

O valor inicial representa o estado *antes* de qualquer verificação. Nesse momento, a
aplicação genuinamente não sabe se o usuário está autenticado — pode ter um cookie válido,
expirado, ou nenhum. `isLoading: true` é semanticamente correto: "ainda estou verificando".

**Por que `finally` e não apenas o bloco `try`?**

Se o `setIsLoading(false)` estivesse apenas no `try`, uma falha de rede no restore (que
não é `401` mas sim timeout ou erro de servidor) deixaria `isLoading` como `true` para
sempre — a aplicação ficaria travada exibindo o spinner indefinidamente. O `finally`
garante que `isLoading` sempre muda para `false`, independente do resultado.

**Analogia frontend:** é o mesmo padrão de `isLoading` em qualquer `useEffect` que faz
fetch — você não renderiza o componente antes de saber o que vai renderizar.

## Consequences

**Positivos:**
- Zero flash de redirect para usuários com sessão válida
- UX consistente no reload: usuário vai direto para onde estava
- `ProtectedRoute` e `PublicRoute` funcionam corretamente em todos os cenários:
  sessão válida, sessão expirada, nunca logado

**Negativos / Trade-offs:**
- Toda visita à aplicação inicia com uma tentativa de `POST /auth/refresh` — request
  de rede obrigatório antes do primeiro render útil
- O spinner do `ProtectedRoute` fica visível por ~200ms em toda navegação inicial —
  aceitável e esperado pelo usuário
- `PublicRoute` retorna `null` (nada renderizado) durante o `isLoading` — evita flash
  do formulário de login antes do redirect para `/dashboard`

## Referências

- `src/contexts/AuthContext.tsx` — implementação de `isLoading`, `restoreSession`, `finally`
- `src/components/ProtectedRoute.tsx` — uso de `isLoading` antes de verificar `isAuthenticated`
- `src/components/PublicRoute.tsx` — retorna `null` durante `isLoading`
- `ADR-014` — token em variável de módulo (complementa o restore de sessão)
- `ADR-016` — fila de requests durante refresh (evita N refreshes simultâneos)