# ADR-029: Piloto WhatsApp via 360dialog (BSP) — Twilio Shared deprecated

**Status:** Aceita
**Data:** 2026-07-23
**Substitui parcialmente:** ADR-028 (provider de piloto: Twilio Shared → 360dialog)

---

## Contexto

A ADR-028 estabeleceu o `TwilioSharedAccountProvider` como provider de piloto enquanto
a aprovação como **Meta Tech Provider** estava em curso. A aprovação foi negada.

Com o processo Meta encerrado, passou a ser possível avaliar o `TwilioSharedAccountProvider`
como provider definitivo de piloto — e a avaliação revelou um conflito fundamental com o
requisito de produto:

> **Requisito firme:** o profissional usa o WhatsApp Business **dele**.
> A maioria já tem uma base de clientes consolidada naquele número. Mudar de número
> implica perder histórico, contatos e a audiência que levou anos para construir.

O modelo Twilio Shared pressupõe **1 número Corelix → N profissionais**. Isso significa:
- O cliente final vê "Corelix" como remetente, não o profissional.
- O profissional não usa seu próprio número — a premissa do requisito está destruída.
- Migração futura para o número próprio exigiria que o cliente mudasse de contato.

O modelo está **arquiteturalmente incompatível** com o produto. Não é uma limitação
temporária — é uma contradição de design.

**Descoberta sobre 360dialog:**
- É um BSP (Business Solution Provider) Meta homologado.
- Permite onboarding do número do próprio profissional via Embedded Signup.
- Suporta até **3 números sem exigir registro adicional como Tech Provider**.
- Oferece **Coexistence**: o profissional que usa o app WhatsApp Business mantém
  o número, o histórico de conversas e toda a audiência ao migrar para a API.
- Elimina a dependência da aprovação Meta Tech Provider para o piloto.

---

## Decisão

O provider de piloto passa a ser **360dialog com o número do próprio profissional**.

| Provider | Uso | Estado |
|---|---|---|
| `TerminalProvider` | Dev local, testes, demos comerciais | Disponível |
| `Dialog360Provider` | Piloto — número próprio do profissional via 360dialog BSP | **A implementar** |
| `MetaCloudProvider` | Produção final — número próprio via Meta Cloud API direta | Disponível pós-Tech Provider |
| `TwilioSharedAccountProvider` | ~~Piloto~~ | **DEPRECATED** |

O `TwilioSharedAccountProvider` permanece no código para não quebrar o `factory.py`
enquanto o `Dialog360Provider` não estiver implementado e testado. A remoção ocorrerá
em limpeza futura (código + testes + dependência `twilio`).

### Caminho de onboarding 360dialog

```
Profissional (app WhatsApp Business)
    ↓ Coexistence
360dialog Embedded Signup
    ↓ access_token + phone_number_id
WhatsAppAccount(provider_type='dialog360', ...)
    ↓
Dialog360Provider → Meta Cloud API (proxy via 360dialog)
```

Profissionais que já usam o app WhatsApp Business podem migrar sem perder número
nem histórico de conversas via o recurso de Coexistence da 360dialog.

### Destino final inalterado

Meta Cloud API direta (via `MetaCloudProvider`) continua sendo o destino final.
A 360dialog é o caminho para chegar lá enquanto o Tech Provider não está disponível.
Quando (e se) aprovado, os profissionais migram individualmente de Dialog360Provider
para MetaCloudProvider sem interrupção de serviço.

---

## Pré-requisitos operacionais (onboarding 360dialog)

Antes de iniciar o Embedded Signup via 360dialog, o profissional precisa:

1. **Meta Business Manager verificado** — conta comercial com verificação de pessoa
   jurídica concluída no Meta Business Manager.
2. **Site com Business Info válido** — o domínio do site deve estar listado e no ar
   nas informações de negócio do Meta Business Manager.
3. **2FA desabilitado no BSP anterior** — caso o número já esteja conectado a outro
   BSP (Twilio, Zapi, etc.), o 2FA do WhatsApp Business deve estar desativado antes
   da migração para evitar bloqueio do número.
4. **Atenção ao dígito 9 em números brasileiros** — números brasileiros no formato
   `+55 11 9XXXX-XXXX` (com 9° dígito) devem ser registrados exatamente assim.
   Registrar sem o 9 e o cliente enviar com o 9 (ou vice-versa) cria conversas
   duplicadas e falha no roteamento.

---

## Consequências

### Positivas

- Profissional usa o próprio número — requisito de produto satisfeito desde o piloto
- Coexistence: zero perda de histórico, audiência ou contatos ao migrar
- Sem dependência de aprovação Meta — go-to-market desbloqueado
- Até 3 números sem registro adicional como Tech Provider
- Caminho suave para Meta Cloud direto quando Tech Provider for aprovado

### Negativas

- `Dialog360Provider` precisa ser implementado (não existe ainda)
- `TwilioSharedAccountProvider` ficará no código como deprecated por um período
- Custo por número via 360dialog (modelo BSP — verificar pricing atual)
- Dependência de intermediário 360dialog até Tech Provider aprovado

### Riscos monitorados

| Risco | Probabilidade | Mitigação |
|---|---|---|
| 360dialog mudar pricing ou política | Baixa | Abstração permite trocar BSP sem alterar service layer |
| Profissional não ter Business Manager verificado | Alta | Tutorial de onboarding + suporte manual no piloto |
| Numero com 9 dígito registrado errado | Média | Validação no frontend durante onboarding |
| Meta negar Tech Provider definitivamente | Alta | 360dialog como BSP não depende de Tech Provider |

---

## Alternativas consideradas

| Alternativa | Por que descartada |
|---|---|
| Manter Twilio Shared como piloto definitivo | Obriga o profissional a abandonar o número dele — conflito direto com o requisito de produto |
| Esperar aprovação Meta Tech Provider | Aprovação negada; mesmo se retomada, bloqueia receita por tempo indeterminado |
| Outros BSPs (Zapi, WPPConnect, etc.) | Baseados em WhatsApp Web não-oficial — viola TOS Meta, risco de banimento |
| Provider único (TerminalProvider para sempre) | Terminal não é provedor de produção; não valida o produto com clientes reais |

---

## Referências

- ADR-011 — Embedded Signup com número próprio (requisito de produto original)
- ADR-028 — Provider strategy: Terminal + Twilio Shared + Meta (substituído nesta ADR)
- 360dialog Embedded Signup: https://docs.360dialog.com/partner/embedded-signup
- 360dialog Coexistence: https://docs.360dialog.com/waba-api/whatsapp-api/migration
- Meta Cloud API: https://developers.facebook.com/docs/whatsapp/cloud-api
