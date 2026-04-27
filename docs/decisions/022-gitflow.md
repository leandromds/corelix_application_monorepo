# 022 - Gitflow: Estratégia de Branches

**Status:** `accepted`

---

## Context

O projeto é desenvolvido por um dev solo com o objetivo de manter um histórico limpo,
deploys seguros e separação clara entre código em desenvolvimento e código em produção.

Sem uma estratégia de branches definida, é fácil acidentalmente fazer push direto para
`main` (produção), misturar features incompletas com código estável, ou perder rastreabilidade
de quando e por que cada mudança foi feita.

## Decision

Adotar **Gitflow simplificado** com três níveis de branches:

```
main      → produção — nunca recebe push direto
develop   → branch base do dia a dia — integração contínua
feature/* → features individuais — criadas a partir de develop
```

### Fluxo para cada feature

```bash
# 1. Atualizar develop
git checkout develop
git pull origin develop

# 2. Criar branch da feature
git checkout -b feature/nome-da-feature

# 3. Desenvolver com commits atômicos
git add .
git commit -m "feat: descrição do que foi feito"

# 4. Push e abertura de PR
git push origin feature/nome-da-feature
# Abrir PR no GitHub: feature/nome-da-feature → develop

# 5. Merge após revisão (ou auto-aprovação em dev solo)
# PR mergeado via GitHub UI (squash ou merge commit)
```

### Promoção para produção

```bash
# Quando develop estiver estável e testado:
# Abrir PR no GitHub: develop → main
# Merge via GitHub UI
# Railway detecta push em main e faz deploy automático
```

### Regra absoluta

```bash
# NUNCA fazer isso:
git push origin main

# SEMPRE assim:
git push origin feature/nome-da-feature
# Depois abrir PR
```

### Convenção de nomes de branch

| Tipo | Padrão | Exemplo |
|------|--------|---------|
| Feature | `feature/nome-descritivo` | `feature/agenda-module` |
| Correção | `fix/descricao-do-bug` | `fix/rls-policy-null-safe` |
| Documentação | `docs/o-que-foi-documentado` | `docs/adr-restructure` |
| Chore | `chore/descricao` | `chore/update-dependencies` |

### Conventional Commits

Todos os commits seguem o padrão:

```
<tipo>(<escopo opcional>): <descrição curta>

[corpo opcional]

[rodapé opcional]
```

Tipos válidos:
- `feat:` — nova funcionalidade
- `fix:` — correção de bug
- `chore:` — manutenção, atualizações de deps, configs
- `docs:` — documentação
- `test:` — adição ou correção de testes
- `refactor:` — refatoração sem mudança de comportamento

### Pull Request

Ao final de cada feature, gerar:
- **Título:** `feat(módulo): descrição concisa`
- **Descrição:** o que foi implementado, decisões técnicas relevantes, como testar

## Rationale

**Por que não push direto para main?**
- `main` está conectado ao deploy automático no Railway — um push acidental coloca código
  não testado em produção imediatamente
- PRs criam um checkpoint de revisão — mesmo em dev solo, o processo de abrir um PR força
  uma revisão do diff antes do merge

**Por que develop como branch base (e não main)?**
- Permite acumular múltiplas features em `develop` antes de promover para produção
- `main` sempre reflete o estado exato de produção — facilita rollback e diagnóstico
- Features incompletas não ficam em `main` esperando outras features para completar

**Por que feature branches (e não commits diretos em develop)?**
- Cada feature tem seu próprio ciclo de vida — pode ser abandonada sem afetar develop
- Histórico limpo: um PR por feature, com descrição do contexto
- Facilita `git bisect` para encontrar regressões

**Por que conventional commits?**
- Changelogs geráveis automaticamente (`git log --oneline` legível)
- Contexto imediato no histórico: `feat(agenda):` vs `fix(auth):` já diz onde olhar
- Padrão da indústria — qualquer dev novo no projeto entende a convenção

## Consequences

**Positivos:**
- `main` sempre estável e deployável
- Histórico rastreável por feature
- Deploy acidental impossível sem PR
- Conventional commits facilitam geração de changelog e revisão de histórico

**Negativos / Trade-offs:**
- Para um dev solo, o processo de PR pode parecer overhead — mas cria o hábito e
  protege contra deploys acidentais
- Branches de longa duração (`feature/whatsapp-module` com semanas de trabalho) podem
  acumular divergência com `develop` — mitigado com rebase periódico
- Sem CI/CD configurado ainda, o PR é mergeado manualmente — testes devem ser rodados
  localmente antes do merge

**Próximo passo de maturidade:**
Configurar GitHub Actions para rodar `pytest` automaticamente em cada PR aberto contra
`develop` — bloqueando merge se testes falharem.

## Referências

- `CORE.md` — regra "nunca git push origin main"
- `.github/` — (a criar) GitHub Actions para CI automático em PRs