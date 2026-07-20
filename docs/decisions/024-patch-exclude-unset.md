# 024 - PATCH Semântico: `exclude_unset=True` em vez de `exclude_none=True`

**Status:** `accepted`

---

## Context

Endpoints PATCH permitem atualização parcial de um recurso — apenas os campos enviados
pelo cliente devem ser alterados. O Pydantic oferece dois mecanismos para serializar
apenas os campos relevantes ao chamar `model_dump()`:

- `exclude_unset=True` → exclui campos que **não foram enviados** no payload
- `exclude_none=True` → exclui campos cujo valor é **`None`** (independente de terem sido enviados ou não)

A diferença parece sutil, mas tem impacto crítico em campos **nullable** — campos que
podem legitimamente ter valor `None` no banco (ex: `phone`, `email`, `notes`, `bio`).

### O problema com `exclude_none=True`

```python
# Schema PATCH
class ClientUpdate(BaseModel):
    full_name: str | None = None
    phone: str | None = None      # nullable — pode ser limpo intencionalmente
    email: str | None = None      # nullable — pode ser limpo intencionalmente
    notes: str | None = None

# Cliente atual no banco: phone="(11) 9999-9999", email="joao@email.com"
# Request PATCH enviado: {"phone": null}   ← intenção: limpar o telefone

data = ClientUpdate(**{"phone": None})

# Com exclude_none=True — ERRADO
data.model_dump(exclude_none=True)
# → {}  ← phone foi ignorado! Banco não é atualizado.

# Com exclude_unset=True — CORRETO
data.model_dump(exclude_unset=True)
# → {"phone": None}  ← phone incluído com None. Banco atualiza para NULL. ✓
```

O `exclude_none=True` torna impossível limpar um campo nullable via PATCH — o cliente
não tem como sinalizar "quero setar este campo para NULL". A API aceita o request com 200
mas silenciosamente ignora a intenção do chamador.

---

## Decision

Todos os endpoints PATCH do projeto usam **`model_dump(exclude_unset=True)`** para
extrair os campos a atualizar.

```python
# service.py — padrão obrigatório em todos os módulos
async def update_client(self, client_id: UUID, data: ClientUpdate) -> Client:
    client = await self.get_client(client_id)
    update_data = data.model_dump(exclude_unset=True)   # ← sempre exclude_unset
    return await self.repository.update(client, update_data)

# repository.py
async def update(self, entity: Client, data: dict) -> Client:
    for key, value in data.items():
        setattr(entity, key, value)   # value pode ser None — atualiza para NULL
    await self.db.flush()
    return entity
```

### Comportamentos resultantes

| Payload enviado | `exclude_unset` result | Ação no banco |
|---|---|---|
| `{"full_name": "João"}` | `{"full_name": "João"}` | Atualiza apenas `full_name` |
| `{"phone": null}` | `{"phone": None}` | Seta `phone = NULL` |
| `{"phone": null, "email": "a@b.com"}` | `{"phone": None, "email": "a@b.com"}` | Atualiza ambos |
| `{}` (payload vazio) | `{}` | Nenhum campo alterado |
| `{"full_name": "João", "email": null}` | `{"full_name": "João", "email": None}` | Atualiza `full_name`, limpa `email` |

### Exceção: `update_profile` de profissionais

`ProfessionalsService.update_profile()` usa `exclude_none=True` em vez de `exclude_unset=True`.
Isso é intencional porque `UpdateProfileRequest` não tem campos obrigatoriamente nullable
na semântica de negócio — o profissional não tem caso de uso para limpar `full_name` via PATCH.

Se esse comportamento mudar (ex: permitir limpar `bio` intencionalmente), migrar para
`exclude_unset=True` também no `update_profile`.

---

## Rationale

**Semântica correta de PATCH (RFC 7396 — JSON Merge Patch):**
O RFC define que em um PATCH, um campo com valor `null` no payload significa "remover
este campo" (ou setar para NULL em bancos relacionais). Campos ausentes significam
"não alterar". `exclude_unset=True` implementa exatamente essa semântica.

**`exclude_none` viola o princípio do menor espanto:**
Um dev que envia `PATCH /clients/123 {"phone": null}` esperando limpar o telefone e
recebe `200 OK` mas o campo não muda terá um bug difícil de rastrear. A API mente sobre
o resultado da operação.

**Aplicabilidade em todos os módulos:**
Este padrão deve ser seguido em **todo endpoint PATCH** do projeto:
- `clients/service.py` → `update_client()`
- `agenda/service.py` → `update_session()`, `update_slot()`, `update_recurrence()`
- `professionals/service.py` → `update_profile()` *(exceção documentada acima)*
- Quaisquer novos módulos com endpoints PATCH

---

## Consequences

**Positivos:**
- Clientes da API podem limpar campos nullable via PATCH — comportamento RFC-correto
- Nenhuma diferença de comportamento para campos obrigatórios (non-nullable)
- Payload vazio (`{}`) é inofensivo — não altera nada, sem efeito colateral

**Negativos / Trade-offs:**
- Dev que não conhece a distinção pode usar `exclude_none` por hábito — especialmente
  quem vem de projetos onde todos os campos são non-nullable
- Requer que os testes verifiquem explicitamente o caso `campo=null` para garantir
  que o campo é limpo (não apenas que o request retorna 200)

**Teste obrigatório por módulo:**

```python
# test_service.py — cenário crítico a incluir em todo módulo com PATCH
async def test_update_clears_nullable_field(db_session, test_professional):
    client = await create_test_client(db_session, phone="(11) 9999-9999")

    update_data = ClientUpdate(phone=None)   # intenção: limpar telefone
    # phone está em exclude_unset? Não — foi explicitamente setado como None
    assert update_data.model_dump(exclude_unset=True) == {"phone": None}

    updated = await service.update_client(client.id, update_data)
    assert updated.phone is None   # ← confirma que o campo foi limpo
```

---

## Referências

- `clients/service.py` — `update_client()` como implementação de referência
- `clients/schemas.py` — `ClientUpdate` com campos nullable
- `professionals/service.py` — `update_profile()` (exceção com `exclude_none`)
- `domains/clients.md` — seção "Padrões e Gotchas"
- `domains/agenda.md` — schemas de update com campos nullable (`SessionUpdate`, etc.)
- RFC 7396 — JSON Merge Patch (semântica de `null` em PATCH)