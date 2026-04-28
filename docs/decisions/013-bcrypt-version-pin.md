# 013 - bcrypt Fixado em `<4` (Compatibilidade com passlib)

**Status:** `accepted`

---

## Context

O projeto usa `passlib 1.7.4` para hashing de senhas com bcrypt. Durante o setup inicial,
instalar `bcrypt` sem restrição de versão resulta em `bcrypt 4.x+` — que introduziu uma
breaking change na API interna utilizada pelo passlib.

O erro manifestado:

```
AttributeError: module 'bcrypt' has no attribute '__about__'
```

ou em versões mais recentes do bcrypt 4.x:

```
bcrypt: (trapped) error reading bcrypt version
AttributeError: module 'bcrypt' has no attribute '__version__'
```

O passlib 1.7.4 é a última versão mantida da biblioteca — o projeto foi arquivado e não
receberá atualizações de compatibilidade. Trocar o passlib por outra biblioteca quebraria
os hashes já armazenados no banco em produção.

## Decision

Fixar o `bcrypt` em `>=3.2,<4` no `pyproject.toml`:

```toml
[tool.poetry.dependencies]
passlib = {extras = ["bcrypt"], version = "^1.7.4"}
bcrypt = ">=3.2,<4"
```

A versão mínima `3.2` garante compatibilidade com Python 3.11+.

## Rationale

- **Sem breaking change no banco:** os hashes bcrypt gerados por passlib 1.7.4 + bcrypt 3.x
  são válidos e compatíveis — não exigem migração de dados.
- **Sem mudança de API:** `hash_password()` e `verify_password()` em `core/security.py`
  continuam funcionando sem alteração.
- **Alternativa avaliada e descartada:** substituir passlib por `bcrypt` direto ou `argon2-cffi`
  exigiria migrar todos os hashes existentes no banco — inaceitável em produção sem um plano
  de migração incremental.

## Consequences

**Positivos:**
- Sem erros em runtime relacionados a incompatibilidade de versão
- Lock file (`poetry.lock`) garante que todos os ambientes usam a mesma versão

**Negativos / Trade-offs:**
- Fica preso em bcrypt 3.x — atualizações de segurança do bcrypt 4.x não são aplicadas
- Dívida técnica: passlib está arquivado — migração futura inevitável

**Plano de migração futura (pós-MVP):**
1. Adicionar `argon2-cffi` como nova biblioteca de hash
2. Na próxima autenticação bem-sucedida de cada usuário, re-hashear a senha com argon2
   e salvar o novo hash (`lazy migration`)
3. Remover passlib e a constraint `bcrypt < 4` após todos os usuários migrarem

## Referências

- `apps/api/pyproject.toml` — constraint `bcrypt = ">=3.2,<4"`
- `core/security.py` — `hash_password()`, `verify_password()`
- `ADR-002` — decisão de auth com JWT + refresh token (contexto do uso de bcrypt)