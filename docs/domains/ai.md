# Domain: ai/

> Módulo transversal de IA. Implementado. Chamado pelo service layer de outros módulos — não possui router próprio.

---

## Responsabilidade

A IA não é um módulo isolado com endpoints — é um **serviço chamado pelo service layer** de outros módulos nos pontos onde agrega valor real. O princípio guia é: a IA entra onde um assistente humano experiente diria "repara nesse detalhe".

Pontual, intencional, nunca decorativo.

---

## Arquivos

### `ai/service.py`

```python
class AIService:
    def __init__(self) -> None:
        self.client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.model = "claude-sonnet-4-5"

    async def complete(self, system: str, message: str) -> str:
        """Single-turn completion — para respostas pontuais (relatório, insights)."""
        response = await asyncio.to_thread(
            self.client.messages.create,
            model=self.model,
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": message}],
        )
        return response.content[0].text

    async def complete_with_history(
        self,
        system: str,
        messages: list[dict[str, str]],
    ) -> str:
        """Multi-turn completion — para conversas WhatsApp com histórico."""
        response = await asyncio.to_thread(
            self.client.messages.create,
            model=self.model,
            max_tokens=1024,
            system=system,
            messages=messages,  # [{"role": "user"|"assistant", "content": "..."}]
        )
        return response.content[0].text
```

**Nota sobre `asyncio.to_thread`:** o cliente Python da Anthropic é síncrono. O `asyncio.to_thread` executa a chamada bloqueante em uma thread separada, sem bloquear o event loop do FastAPI.

---

### `ai/prompts.py`

Registry centralizado de prompts. Todos os prompts do sistema vivem aqui — nunca inline nos services.

```python
PROMPTS: dict[str, str] = {
    "whatsapp_secretary": """
Você é a secretária digital de {professional_name}, {specialty}.
{bio}

Você atende os clientes pelo WhatsApp de forma profissional, cordial e eficiente.

Responsabilidades:
- Confirmar, reagendar e cancelar sessões
- Responder dúvidas sobre horários disponíveis e valores
- Encaminhar questões complexas para o profissional

Não discuta temas clínicos ou técnicos da área de atuação do profissional.
Quando não souber responder, diga que vai verificar com o profissional.

Informações atuais:
- Duração padrão da sessão: {session_duration} minutos
- Valor da sessão: R$ {session_price}
""",

    "report_insights": """
Você é um assistente analítico para {professional_name}, {specialty}.

Analise os dados do período e forneça observações contextuais concisas:
- Padrões de faltas ou cancelamentos
- Clientes com alta frequência ou mudanças no padrão
- Alertas de recorrências próximas do fim
- Tendências financeiras relevantes

Seja direto e objetivo. Máximo 3-5 observações. Sem jargão técnico.
Use linguagem que o próprio profissional usaria ao falar sobre sua agenda.
""",
}
```

**Regra:** ao adicionar um novo ponto de uso da IA, criar uma nova entrada no `PROMPTS` dict antes de implementar o service. O registry serve como inventário do uso de IA no sistema.

---

## Pontos de Uso da IA no Sistema

| Módulo chamador | Prompt | Método | Quando |
|---|---|---|---|
| `whatsapp/service.py` | `whatsapp_secretary` | `complete_with_history()` | A cada mensagem inbound recebida no webhook, quando `mode == "ai"` |
| `reports/service.py` | `report_insights` | `complete()` | Ao gerar relatório de cobrança do período |
| `agenda/service.py` | *(a criar)* | `complete()` | Sugestão de horários baseada em padrão histórico |
| `dashboard/service.py` | *(a criar)* | `complete()` | Insights pontuais para o profissional |

---

## Padrão de Uso nos Services

```python
# Exemplo: whatsapp/service.py
from ai.service import AIService
from ai.prompts import PROMPTS

class WhatsAppService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.ai = AIService()

    async def handle_inbound_message(
        self,
        professional: Professional,
        conversation: WhatsAppConversation,
        message_content: str,
    ) -> str:
        # 1. Buscar histórico da conversa para contexto
        history = await self._get_conversation_history(conversation.id)

        # 2. Montar system prompt com dados do profissional
        system = PROMPTS["whatsapp_secretary"].format(
            professional_name=professional.full_name,
            specialty=professional.specialty or "profissional",
            bio=professional.bio or "",
            session_duration=professional.session_duration,
            session_price=professional.session_price or "a consultar",
        )

        # 3. Montar histórico no formato Anthropic
        messages = [
            {"role": msg.direction == "inbound" and "user" or "assistant",
             "content": msg.content}
            for msg in history
        ]
        messages.append({"role": "user", "content": message_content})

        # 4. Obter resposta da IA
        ai_response = await self.ai.complete_with_history(system, messages)

        return ai_response
```

---

## Economia de Tokens

Princípio: cada chamada deve ter propósito claro e escopo limitado.

- `complete()` para respostas pontuais (relatório, insights): sem histórico, input estruturado
- `complete_with_history()` para WhatsApp: histórico truncado para as últimas N mensagens relevantes
- Prompts parametrizados (`{professional_name}`, `{bio}`) — contexto injetado no runtime, não hardcoded
- `max_tokens=1024` como default — suficiente para respostas conversacionais; relatórios podem precisar de mais

**Limite de histórico (a implementar):** o histórico de conversa enviado para a IA deve ser truncado para evitar context overflow. Sugestão: últimas 20 mensagens ou últimos 7 dias, o que vier primeiro.

---

## Tratamento de Erros

Chamadas à API da Anthropic podem falhar por:
- Timeout de rede
- Rate limit da API
- Erro interno da Anthropic

Todos esses casos devem lançar `ExternalServiceError` (de `core/exceptions.py`), que é mapeado para HTTP 502 em `main.py`. O sistema não deve travar por falha da IA — degradação graceful é preferível.

```python
async def complete(self, system: str, message: str) -> str:
    try:
        response = await asyncio.to_thread(...)
        return response.content[0].text
    except anthropic.APIError as e:
        raise ExternalServiceError(f"Anthropic API error: {e}") from e
```

---

## Constraints e Decisões

- **IA sem router próprio** — não há endpoints de IA expostos diretamente. Todo acesso é indireto via outros módulos
- **Prompts centralizados em `ai/prompts.py`** — nunca inline nos services. Facilita revisão, versionamento e auditoria do comportamento da IA
- **Toda saída da IA é sugestão** — o sistema nunca executa ações automaticamente com base apenas na IA sem confirmação do profissional (exceto respostas WhatsApp no modo `ai`)
- **Sem streaming no MVP** — `create()` síncrono + `asyncio.to_thread`. Streaming pode ser adicionado para o chat do dashboard no pós-MVP
- **Modelo fixo no código** — `claude-sonnet-4-5` hardcoded. Tornável configurável via `Settings` se necessário no futuro

---

## Referências

- `ai/service.py` — `AIService.complete()`, `AIService.complete_with_history()`
- `ai/prompts.py` — `PROMPTS` registry
- `core/exceptions.py` — `ExternalServiceError` para falhas da API
- `core/config.py` — `Settings.ANTHROPIC_API_KEY`
- `domains/whatsapp.md` — uso primário de `complete_with_history()`
- ADR-011 — modelo de integração WhatsApp (contexto do uso de IA no WhatsApp)