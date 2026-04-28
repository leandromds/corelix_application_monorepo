# 019 - Background Jobs via pgqueuer (Sem Redis)

**Status:** `accepted`

---

## Context

O sistema precisa executar tarefas assíncronas em background:
- Limpeza noturna de refresh tokens expirados
- Geração de sessões a partir de recorrências ativas
- Renovação de tokens WhatsApp antes da expiração
- (Futuro) Envio de lembretes automáticos para clientes

As soluções mais comuns para jobs em Python são:
1. **Celery + Redis** — padrão da indústria para filas de tarefas distribuídas
2. **RQ (Redis Queue)** — mais simples que Celery, ainda requer Redis
3. **pgqueuer** — fila de jobs implementada sobre o próprio PostgreSQL
4. **APScheduler** — scheduler em-processo, sem fila persistente

O projeto já usa PostgreSQL como banco principal. A hospedagem é Railway.

## Decision

Usar **pgqueuer** — fila de jobs construída sobre PostgreSQL, sem Redis.

Jobs implementados (a criar):

| Job | Frequência | Responsabilidade |
|-----|------------|------------------|
| `cleanup_expired_tokens` | Noturno (diário) | `RefreshTokenRepository.delete_expired()` |
| `generate_recurrence_sessions` | Diário | Cria sessões futuras de recorrências ativas |
| `renew_whatsapp_tokens` | A cada 12h | Renova tokens próximos de expirar |

## Rationale

**Por que não Redis + Celery?**

| Critério | Celery + Redis | pgqueuer |
|----------|---------------|----------|
| Infra adicional | Redis obrigatório | Nenhuma — usa PostgreSQL existente |
| Custo Railway | ~$5-10/mês extra (Redis add-on) | Incluso no PostgreSQL já pago |
| Complexidade de setup | Alta (broker, worker, beat scheduler) | Baixa (mesma conexão PostgreSQL) |
| Visibilidade de jobs | Dashboard separado ou Flower | Query SQL direta na tabela de jobs |
| Adequação ao volume | Over-engineered para o MVP | Adequado para dezenas de jobs/dia |
| Consistência transacional | Jobs e dados em sistemas separados | Job e dados na mesma transação |

Para o volume do MVP (dezenas de jobs por dia, não milhares), Redis seria complexidade
e custo sem benefício proporcional.

**Por que pgqueuer especificamente?**
- Usa `LISTEN/NOTIFY` do PostgreSQL para notificações em tempo real — sem polling
- Jobs são registros na tabela `pgqueuer` — auditáveis via SQL
- Suporta `asyncio` nativamente — alinhado com a stack FastAPI async
- Job e dados do domínio podem estar na mesma transação — consistência garantida
- Deploy simples: o worker pgqueuer roda como um processo Python separado

**Por que não APScheduler?**
- APScheduler não tem persistência de fila — se o processo morrer, jobs pendentes se perdem
- Sem retry automático em falhas
- Sem visibilidade de jobs enfileirados ou histórico de execução

## Consequences

**Positivos:**
- Zero infraestrutura adicional — PostgreSQL já existe
- Sem custo extra de Redis no Railway
- Jobs auditáveis diretamente no banco
- Consistência transacional: enfileirar um job e persistir dados na mesma transação
- Setup simples para um dev solo

**Negativos / Trade-offs:**
- PostgreSQL não é especializado em filas — performance degrada com volume muito alto
  (milhões de jobs/dia) — irrelevante para o MVP
- Sem ecossistema rico de plugins como o Celery (rate limiting, canvas, chord, etc.)
- Se o PostgreSQL ficar indisponível, os jobs também param — aceitável pois o banco
  sendo o ponto central de falha já era o caso com a aplicação inteira
- Worker pgqueuer precisa rodar como processo separado no Railway — uma instância adicional

**Limite de escala:** para quando os jobs crescerem acima de milhares por hora, migrar
para Redis + Celery é possível sem mudar a interface dos jobs — pgqueuer usa decorators
que podem ser substituídos.

## Referências

- `pyproject.toml` — dependência `pgqueuer`
- `ADR-011` — renovação de token WhatsApp (caso de uso principal dos jobs)
- `ADR-002` — `delete_expired()` no `RefreshTokenRepository` (job de limpeza)