# ADR-025 — Infraestrutura: Hostinger KVM 2 + Coolify self-hosted

**Data:** 2026-05-05  
**Status:** Aceito  
**Autor:** Solo dev

---

## Contexto

O projeto estava planejado para deploy no Railway (PaaS gerenciado). O Railway oferece boa DX
mas tem custo variável em dólar, sem garantia de preço para crescimento, e lock-in por
`Procfile` e variáveis de plataforma.

Com o produto chegando perto de deploy real (MVP para 10–50 profissionais), foi necessário
decidir o ambiente de produção com critérios concretos.

### Requisitos

- Custo fixo e previsível em reais (sem variação de câmbio)
- LGPD: dados no Brasil (servidores em São Paulo)
- Suporte a Docker Compose nativo (portabilidade)
- PostgreSQL gerenciado ou instalável no próprio servidor
- Deploy automático via git push
- RAM suficiente para: API, worker pgqueuer, PostgreSQL, Coolify, Uptime Kuma, Glitchtip

---

## Decisão

**Hostinger VPS KVM 2** como servidor + **Coolify** como PaaS self-hosted.

### Especificações do servidor

| Recurso | Valor |
|---------|-------|
| RAM | 8 GB |
| vCPU | 4 cores |
| Storage | 100 GB NVMe |
| Localização | São Paulo, BR |
| Custo | ~R$ 56/mês |

### Coolify

Coolify é um PaaS open-source auto-hospedado. Instalado no próprio VPS, ele:
- Lê `docker-compose.yml` do repositório git
- Faz deploy automático em git push (webhook)
- Gerencia variáveis de ambiente pelo painel web
- Provisiona PostgreSQL como serviço separado (sem entrar no compose da app)
- Não adiciona custo (gratuito, open-source)

---

## Alternativas Consideradas

### Railway
- ✅ DX excelente, zero config
- ❌ Custo em dólar (R$ 150–300+/mês a longo prazo)
- ❌ Lock-in: `Procfile`, variáveis de plataforma, sem docker-compose nativo

### Render
- ✅ Plano gratuito, boa DX
- ❌ Free tier tem cold starts (inadequado para API de produção)
- ❌ Custo em dólar nos planos pagos

### VPS puro (sem PaaS)
- ✅ Controle total
- ❌ Deploy manual (sem git push → deploy)
- ❌ Sem painel de variáveis de ambiente
- ❌ Manutenção de Nginx, SSL, etc. manualmente

---

## Consequências

### Positivas
- Custo fixo em reais, sem surpresas
- Dados no Brasil (LGPD)
- Docker Compose padrão: portável para qualquer host
- Coolify gerencia SSL (Let's Encrypt), reverse proxy (Traefik), deploys

### Negativas / Trade-offs
- **Responsabilidade operacional:** atualizações do Coolify, segurança do VPS e backups são responsabilidade do dev
- **Single point of failure:** um único servidor (sem redundância no MVP)
- **Escalabilidade manual:** para crescer além do KVM 2, é necessário migrar manualmente para um servidor maior

---

## Trigger de Revisão

Reavaliar quando:
- Atingir ~200 profissionais ativos (uso de memória próximo de 7 GB)
- Incidente crítico de segurança no VPS
- Custo operacional de manutenção ultrapassar o benefício vs. Railway/Render
