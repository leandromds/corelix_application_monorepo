# 011 - WhatsApp: Embedded Signup por Profissional

**Status:** `accepted`

---

## Context

O produto precisa integrar WhatsApp para que a IA possa atender clientes dos profissionais
automaticamente. As opções avaliadas foram:

1. **Número único da plataforma:** todos os profissionais compartilhariam um único número
   WhatsApp da Corelix. Clientes receberiam mensagens de "Corelix" — sem identidade do
   profissional.

2. **Número próprio por profissional via Embedded Signup:** cada profissional conecta seu
   próprio número ao sistema via OAuth da Meta (Embedded Signup). A Corelix atua como
   Tech Provider registrada na Meta.

O profissional autônomo já se comunica com seus clientes via WhatsApp pessoal. Os clientes
conhecem e confiam naquele número. Uma mensagem de um número desconhecido ("Corelix") seria
percebida como spam e teria taxa de abertura muito menor.

## Decision

Cada profissional conecta **seu próprio número WhatsApp** ao sistema via **Embedded Signup**
(fluxo OAuth da Meta). A Corelix está registrada como **Tech Provider** na Meta Business Platform.

**Modelo de operação:**
- O profissional conecta seu número via fluxo OAuth na UI da Corelix
- O `whatsapp_access_token` é armazenado criptografado no banco (coluna na tabela `professionals`)
- A Cloud API opera em modo dual: o profissional continua usando o WhatsApp normalmente
  no celular enquanto a IA responde automaticamente via API
- O campo `mode` em `whatsapp_conversations` controla quem está respondendo:
  - `ai` → a secretária digital responde automaticamente
  - `handoff` → o profissional assumiu a conversa manualmente via dashboard

**Número da plataforma:**
A Corelix mantém um número próprio exclusivo para o **bot institucional** — onboarding,
suporte e comunicações da plataforma. Esse número nunca é o número de nenhum profissional.

**Renovação de token:**
O `whatsapp_access_token` expira. Um job `pgqueuer` monitora `whatsapp_token_expires_at`
e renova o token antes da expiração.

### Campos relevantes em `professionals`

```sql
whatsapp_phone_number     VARCHAR(20),    -- número conectado
whatsapp_phone_id         VARCHAR(100),   -- ID do número na Meta API
whatsapp_access_token     TEXT,           -- token criptografado (AES-256)
whatsapp_connected_at     TIMESTAMPTZ,    -- quando conectou
whatsapp_token_expires_at TIMESTAMPTZ,   -- deadline para renovação
```

## Rationale

**Por que número próprio do profissional?**
- Clientes reconhecem o número — taxa de resposta muito maior
- Não exige que o cliente salve um número novo
- O profissional não perde o histórico de conversas existente no celular
- Confiança: mensagem da "Dra. Ana" vs "Corelix Secretaria Digital"

**Por que Embedded Signup (e não WABA manual)?**
- Fluxo de conexão dentro da UI da Corelix — sem necessidade de o profissional acessar
  o Meta Business Manager diretamente
- Tech Provider: a Corelix é a entidade registrada na Meta, gerenciando múltiplas contas
  de profissionais sob um único app da Meta
- Renovação de token automatizável — o token OAuth pode ser renovado programaticamente
  sem intervenção do profissional

**Por que o profissional pode usar o sistema antes de conectar o WhatsApp?**
- A agenda, o CRM e os relatórios têm valor independente do WhatsApp
- Reduz fricção no onboarding — profissional experimenta o produto antes de conectar
  o canal principal
- Campos `whatsapp_*` são nullable — sistema não quebra sem eles

## Consequences

**Positivos:**
- Identidade preservada — clientes interagem com o número que já conhecem
- Experiência fluida — profissional continua usando o WhatsApp normalmente
- Handoff natural — profissional pode retomar conversas via dashboard

**Negativos / Trade-offs:**
- Requer que a Corelix seja aprovada como Tech Provider na Meta — processo burocrático
- `whatsapp_access_token` armazenado no banco exige criptografia AES-256 em repouso
- Renovação de token exige job background (`pgqueuer`) — complexidade operacional
- Cada profissional precisa passar pelo fluxo OAuth uma vez — fricção no onboarding
- Modo dual (celular + API simultâneos) pode causar race conditions em conversas ativas —
  mitigado pelo campo `mode` que sinaliza quem está no controle

## Referências

- `whatsapp/models.py` — `WhatsAppConversation` (campo `mode`), `WhatsAppMessage`
- `professionals/models.py` — campos `whatsapp_*`
- `domains/whatsapp.md` — detalhes de implementação do módulo WhatsApp
- `ADR-019` — pgqueuer para jobs de renovação de token