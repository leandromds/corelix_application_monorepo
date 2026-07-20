# 012 - Anti-Enumeração no Login

**Status:** `accepted`

---

## Context

O endpoint de login precisa verificar duas condições em sequência:
1. O email existe no banco?
2. A senha corresponde ao hash armazenado?

A implementação ingênua retornaria mensagens de erro distintas para cada caso:
- `"Email not found"` → o atacante sabe que o email não está cadastrado
- `"Wrong password"` → o atacante sabe que o email **está** cadastrado e pode tentar força bruta

Essa distinção é chamada de **user enumeration** — permite que um atacante construa uma lista
de emails cadastrados na plataforma fazendo requests em massa. Para um SaaS B2B de saúde, expor
quais profissionais estão cadastrados é uma violação de privacidade relevante.

## Decision

O endpoint de login retorna **a mesma mensagem de erro** para email inexistente e senha incorreta:

```python
# auth/service.py
async def login(self, email: str, password: str) -> tuple[str, str]:
    professional = await self.professionals_repo.find_by_email(email)

    if professional is None or not verify_password(password, professional.password_hash):
        raise AuthenticationError("Invalid credentials")

    # ...
```

A mensagem `"Invalid credentials"` não revela qual das duas condições falhou.

**Detalhe crítico:** mesmo quando o email não existe, `verify_password()` **não é chamado**
(por causa do curto-circuito do `or`). Isso é correto do ponto de vista lógico, mas cria
um **timing side-channel**: a ausência do hash bcrypt torna a resposta para email inválido
mais rápida do que para senha errada (bcrypt é intencionalmente lento).

Para o MVP, esse timing side-channel é aceito como risco residual. Uma mitigação futura é
executar um `verify_password` dummy quando o profissional não é encontrado:

```python
# Mitigação futura (não implementada no MVP)
DUMMY_HASH = hash_password("dummy-constant-value")

professional = await self.professionals_repo.find_by_email(email)
if professional is None:
    verify_password("irrelevant", DUMMY_HASH)  # consume tempo de bcrypt
    raise AuthenticationError("Invalid credentials")

if not verify_password(password, professional.password_hash):
    raise AuthenticationError("Invalid credentials")
```

## Rationale

- **Privacidade dos usuários:** no contexto de saúde e bem-estar, saber que uma pessoa
  específica usa a plataforma pode ser sensível — mesmo sem acesso aos dados dela.
- **Compliance:** LGPD exige proteção de dados pessoais. Emails cadastrados são dados pessoais.
- **Simplicidade:** uma única mensagem de erro é mais fácil de manter e menos propensa a
  inconsistências entre diferentes caminhos de código.
- **Padrão da indústria:** todas as plataformas sérias de autenticação usam essa abordagem
  (GitHub, Google, etc. retornam "incorrect username or password" sem distinção).

## Consequences

**Positivos:**
- Atacantes não conseguem enumerar emails cadastrados via tentativa e erro
- UX minimamente impactada: usuários legítimos que erram o email sabem que precisam verificar
  os dados — a mensagem não precisa dizer qual campo está errado
- Consistência: o mesmo erro é retornado independente do caminho de falha

**Negativos / Trade-offs:**
- UX levemente pior para usuários que erraram o email sem perceber — eles podem tentar
  várias senhas antes de perceber que o email está errado (mitigável com "esqueci minha senha")
- Timing side-channel residual no MVP (velocidade de resposta varia entre email inválido
  e senha errada) — aceito como risco baixo para o estágio atual

**Futuro:**
- Implementar dummy `verify_password` para neutralizar o timing side-channel
- Rate limiting por IP e por email no endpoint de login (ver ADR-019 e middleware planejado)
- Considerar CAPTCHA após N tentativas falhas consecutivas

## Referências

- `auth/service.py` — implementação de `AuthService.login()`
- `core/security.py` — `verify_password()` e `hash_password()`
- `core/exceptions.py` — `AuthenticationError`
