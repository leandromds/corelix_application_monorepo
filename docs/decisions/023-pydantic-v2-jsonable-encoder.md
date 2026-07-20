# 023 - Pydantic v2: `jsonable_encoder` no Handler de Validação

**Status:** `accepted`

---

## Context

O FastAPI registra um handler padrão para `RequestValidationError` (erros de validação
do Pydantic) que serializa os erros via `exc.errors()` e retorna um JSON 422.

Em Pydantic v1, `exc.errors()` retornava uma lista de dicts simples — todos os valores
eram JSON-serializable por padrão.

Em **Pydantic v2**, quando um `model_validator` (modo `"after"` ou `"before"`) levanta
um `ValueError`, o Pydantic inclui o objeto `ValueError` original no campo `ctx` do erro:

```python
# O que exc.errors() retorna em Pydantic v2 com model_validator
[
    {
        "type": "value_error",
        "loc": (),
        "msg": "Value error, at least one of phone or email must be provided",
        "input": {...},
        "ctx": {
            "error": ValueError("at least one of phone or email must be provided")
            # ↑ objeto Python — NÃO é JSON-serializable
        },
        "url": "..."
    }
]
```

Ao tentar serializar esse dict via `json.dumps()` (ou `JSONResponse(content=...)`),
o Python lança:

```
TypeError: Object of type ValueError is not JSON serializable
```

O resultado é um erro 500 Internal Server Error quando o cliente envia dados que
falham a validação de um `model_validator` — exatamente o oposto do comportamento
esperado (422 com mensagem descritiva).

O problema afeta especificamente:
- `clients/schemas.py` — `ClientCreate.at_least_one_contact()` (`model_validator`)
- Qualquer futuro schema que use `model_validator` e levante `ValueError`

## Decision

Substituir a serialização direta de `exc.errors()` por `jsonable_encoder(exc.errors())`
no handler de `RequestValidationError` em `main.py`:

```python
# main.py
from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

app = FastAPI()

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": jsonable_encoder(exc.errors())},
        # ↑ jsonable_encoder converte ValueError (e outros objetos não-serializáveis)
        #   para sua representação string antes de serializar para JSON
    )
```

`jsonable_encoder` do FastAPI percorre recursivamente a estrutura de dados e converte
objetos não-serializáveis para tipos JSON-compatíveis. Para um `ValueError`, ele chama
`str(error)` — produzindo a mensagem de erro como string.

## Rationale

**Por que `jsonable_encoder` (e não limpar o `ctx` manualmente)?**

Remover o campo `ctx` manualmente antes de serializar:

```python
# Alternativa — mais frágil
errors = exc.errors()
for error in errors:
    error.pop("ctx", None)
return JSONResponse(status_code=422, content={"detail": errors})
```

Essa abordagem perde informação: `ctx` pode conter dados úteis além do `ValueError`
(como o valor máximo em erros de `max_length`, o valor mínimo em `ge`, etc.). O cliente
perde contexto para exibir mensagens de erro precisas.

`jsonable_encoder` preserva o `ctx` inteiro, apenas tornando seus valores serializáveis
— o cliente recebe toda a informação disponível.

**Por que esse problema não aparece com `Field(...)` validators?**

Validators declarados via `Field(min_length=2, ge=0, ...)` geram erros cujo `ctx`
contém apenas valores primitivos (inteiros, strings) — já são JSON-serializable.
O `ctx: {'error': ValueError(...)}` é exclusivo de `model_validator` que levanta
`ValueError` explicitamente.

**Por que Pydantic v2 mudou esse comportamento?**

Em Pydantic v2, `model_validator` e `field_validator` podem levantar qualquer exceção
Python (não apenas `ValueError`) — e o Pydantic os captura e os inclui no `ctx` para
preservar o contexto completo do erro. É uma feature de rastreabilidade, não um bug —
mas exige que o serializador saiba lidar com objetos arbitrários.

## Consequences

**Positivos:**
- Erros de validação de `model_validator` retornam 422 com mensagem descritiva —
  comportamento correto e esperado pelo cliente
- `ctx` completo é preservado na resposta — cliente tem toda a informação para
  exibir mensagens de erro precisas
- Solução global: um único handler cobre todos os `model_validator` atuais e futuros
- Sem mudança nos schemas — a correção é pontual no exception handler

**Negativos / Trade-offs:**
- `jsonable_encoder` tem custo de processamento levemente maior que serialização direta —
  irrelevante para respostas de erro (path não crítico de performance)
- Comportamento implícito: devs que adicionam `model_validator` não precisam saber desse
  detalhe — mas quem debugar o handler precisa entender o motivo

**Regra de manutenção:** o handler customizado em `main.py` deve ser mantido mesmo que
o FastAPI atualize seu handler padrão — a compatibilidade do `jsonable_encoder` com
erros de `model_validator` é uma garantia explícita desta decisão.

## Referências

- `apps/api/main.py` — `validation_exception_handler`
- `clients/schemas.py` — `ClientCreate.at_least_one_contact()` (primeiro caso afetado)
- `domains/agenda.md` — schemas futuros com `model_validator` (mesma situação)
- [Pydantic v2 docs — Validators](https://docs.pydantic.dev/latest/concepts/validators/)