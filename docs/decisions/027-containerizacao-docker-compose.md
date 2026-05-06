# ADR-027 — Containerização: Docker Compose com serviços separados

**Data:** 2026-05-05  
**Status:** Aceito  
**Autor:** Solo dev

---

## Contexto

O projeto anteriormente usava `Procfile` (formato Railway-specific) para definir os processos.
Com a migração para Coolify (ADR-025), é necessário uma estratégia de containerização portável.

Há dois processos distintos que precisam ser executados:
1. **API FastAPI** — serve requests HTTP, precisa de restart rápido em falhas
2. **Worker pgqueuer** — processa jobs assíncronos (recorrências, cleanup, WhatsApp)

---

## Decisão

**Dockerfile separado por processo** + **`docker-compose.yml` como orquestrador**.

### Estrutura de arquivos

```
apps/api/
├── Dockerfile          # Build da API FastAPI
├── Dockerfile.worker   # Build do worker pgqueuer
└── ...

docker-compose.yml      # Produção (lido pelo Coolify)
docker-compose.dev.yml  # Desenvolvimento local (apenas PostgreSQL)
```

### Por que Dockerfiles separados?

Cada processo tem um `CMD` diferente:
- `Dockerfile`: `uvicorn main:app --host 0.0.0.0 --port 8000`
- `Dockerfile.worker`: `python -m jobs.runner`

Separar os Dockerfiles permite:
- Restart independente por serviço (worker crash não reinicia a API)
- Logs separados por serviço no painel do Coolify
- Futuramente: deploy independente (ex.: atualizar worker sem downtime da API)

### Por que docker-compose.yml e não Coolify-native config?

O `docker-compose.yml` é portável: funciona no Coolify, Railway, Render, qualquer VPS com Docker.
Evita lock-in de formato de plataforma.

### Dependência entre serviços

```yaml
worker:
  depends_on:
    api:
      condition: service_healthy
```

O worker só sobe após a API passar no health check (`/health` retorna 200).
Isso garante que o banco está conectado antes do worker tentar acessar a fila pgqueuer.

### PostgreSQL fora do compose de produção

O PostgreSQL é provisionado e gerenciado pelo Coolify como serviço separado.
Vantagens:
- Backups automáticos pelo Coolify
- Upgrade de versão independente da aplicação
- Evita perda de dados em `docker-compose down -v`

### Otimizações de build

```dockerfile
# Copia pyproject.toml antes do código fonte
COPY pyproject.toml poetry.lock ./
RUN poetry install --no-root --only=main

# Código fonte só copiado depois
COPY . .
```

Docker cache: se apenas o código mudar (sem novo pacote), a camada de `poetry install`
é reusada do cache → builds muito mais rápidos em CI/CD.

---

## Alternativas Consideradas

### Procfile (Railway-specific)
- ✅ Simples, zero config de Docker
- ❌ Não funciona fora do Railway
- ❌ Sem healthcheck nativo
- ❌ Sem controle de dependência entre processos

### Dockerfile único com supervisord
- ✅ Um único container
- ❌ Logs misturados
- ❌ Restart de um processo reinicia o outro
- ❌ Complexidade desnecessária para MVP

### Kubernetes
- ✅ Escalabilidade, rolling deployments
- ❌ Overkill absoluto para MVP solo com 10–50 profissionais
- ❌ Custo e complexidade operacional

---

## Consequências

### Positivas
- Portabilidade total: funciona em qualquer host com Docker
- Restart independente por serviço
- Logs separados por processo no Coolify
- Build otimizado com layer cache do Docker

### Negativas / Trade-offs
- Dois Dockerfiles para manter (mas são quase idênticos)
- `docker-compose.yml` de produção não inclui PostgreSQL — requer que o banco
  exista antes do deploy (provisionado pelo Coolify)

---

## Trigger de Revisão

- Quando houver necessidade de múltiplas instâncias da API (horizontal scaling)
  → migrar para Kubernetes ou serviço de container gerenciado (ECS, Cloud Run)
