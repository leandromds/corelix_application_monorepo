# ADR-026 — Observabilidade: Uptime Kuma + Glitchtip + PostHog Cloud

**Data:** 2026-05-05  
**Status:** Aceito  
**Autor:** Solo dev

---

## Contexto

Com o produto indo para produção, é necessário responder a três perguntas operacionais:

1. **A API está no ar?** → Uptime monitoring
2. **Quais erros estão acontecendo?** → Error tracking + APM
3. **Os usuários estão usando o produto?** → Product analytics

A stack deve ser gratuita ou de baixo custo para o MVP, e preferência por dados no Brasil
ou auto-hospedados para LGPD.

---

## Decisão

### Uptime Monitoring: Uptime Kuma (self-hosted)
- Instalado no próprio VPS via Coolify
- Monitora endpoints HTTP, envia alerta por email/Telegram se cair
- Open-source, gratuito, sem coleta de dados externos
- UI web simples para configurar health checks

### Error Tracking + APM: Glitchtip (backend + frontend)
- **Backend:** `sentry-sdk` (Python) inicializado com DSN do Glitchtip
- **Frontend:** `@sentry/react` inicializado com DSN do Glitchtip
- Glitchtip é compatível com o protocolo Sentry — usa os mesmos SDKs
- Self-hosted no VPS via Coolify (plano open-source gratuito)
- Dados ficam no próprio servidor (LGPD)

**Configuração de inicialização:**
- Backend: `sentry_sdk.init()` só executa se `GLITCHTIP_DSN` estiver definida (None em dev = sem erro)
- Frontend: `Sentry.init()` só executa se `VITE_GLITCHTIP_DSN` estiver definida

**APM:** `traces_sample_rate=0.2` — amostra 20% das transações para performance

### Product Analytics: PostHog Cloud
- Inicializado com `VITE_POSTHOG_KEY` (só se definida)
- Session recording habilitado com `maskAllInputs: true` (privacidade)
- Autocapture: cliques e navegação capturados automaticamente
- Eventos customizados nos pontos de valor do produto:
  - `appointment_created` — quando agendamento é criado
  - `client_created` — quando cliente é cadastrado
  - `report_viewed` — quando relatório é gerado
  - `whatsapp_connected` — quando conversa WhatsApp é iniciada
- PostHog Cloud: plano gratuito inclui 1M eventos/mês (suficiente para MVP)
- Dados no PostHog Cloud (EUA) — aceitável para analytics não-sensíveis

---

## Alternativas Consideradas

### Sentry.io (cloud)
- ✅ Melhor DX, mais features
- ❌ Custo em dólar após tier gratuito
- ❌ Dados nos EUA

### Datadog / New Relic
- ✅ Full observability stack integrado
- ❌ Custo alto em dólar
- ❌ Overkill para MVP solo

### Google Analytics para PostHog
- ❌ Sem session replay
- ❌ Sem eventos customizados flexíveis
- ❌ LGPD concerns maiores

---

## Consequências

### Positivas
- Stack zero custo adicional para MVP
- Error tracking em produção desde o primeiro deploy
- Session replay para entender UX issues sem precisar de usuário reportar
- Dados de erros e infraestrutura no próprio servidor (LGPD)

### Negativas / Trade-offs
- Glitchtip self-hosted exige manutenção (atualizações, storage de eventos)
- PostHog Cloud: dados de analytics fora do Brasil (trade-off aceito para MVP)
- Dois SDKs de observability no bundle frontend (~50 KB gzipped combinados)

---

## Trigger de Revisão

- PostHog Cloud: quando atingir 1M eventos/mês → migrar para PostHog self-hosted no VPS
- Glitchtip: se o storage de eventos crescer excessivamente → configurar retenção ou migrar para Sentry.io
