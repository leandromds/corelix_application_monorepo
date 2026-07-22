# Análise de Conformidade LGPD — Secretária Digital

> Documento gerado em: 2025-07-18
> Base legal: Lei 13.709/2018 (LGPD) + Guias e Notas Técnicas da ANPD
> Severidade: 🔴 Bloqueador (não vai ao ar sem) | 🟡 Importante (MVP) | 🟢 Recomendado (pós-MVP imediato)

---

## 0. Contexto Crítico: Dois Papéis Jurídicos Distintos

Antes de qualquer checklist, é essencial entender que a Secretária Digital **não tem um único papel** perante a LGPD. Ela opera em dois papéis simultaneamente:

| Relação | Papel da Secretária Digital | Papel do Profissional |
|---|---|---|
| Profissional usa a plataforma | **Controlador** | Titular dos dados |
| Profissional insere dados dos clientes dele | **Operador** | Controlador |

**O que isso significa na prática:**

Como **controlador** dos dados dos profissionais (usuários): você determina como e por que trata nome, e-mail, senha, etc. do psicólogo/terapeuta. As obrigações de base legal, direitos dos titulares e política de privacidade são suas.

Como **operador** dos dados dos clientes dos profissionais: você processa nome, telefone, histórico de sessões do "João, cliente da Dra. Ana" por instrução da Dra. Ana. A responsabilidade pela base legal de tratar esses dados é da Dra. Ana (controladora), mas você tem obrigações de segurança, confidencialidade e de não usar esses dados para finalidades próprias.

Isso implica em duas obrigações que **não existem no codebase ainda**:

1. **DPA (Data Processing Agreement)**: contrato entre você (operador) e cada profissional (controlador), documentando que você trata os dados dos clientes deles apenas por instrução deles e com as salvaguardas adequadas.
2. **Os profissionais precisam de base legal própria** para cadastrar dados dos clientes deles na sua plataforma — e você deve orientá-los sobre isso nos Termos de Uso.

---

## 1. Princípios do Tratamento (Art. 6)

### 1.1 Finalidade (Art. 6, I)
> Os dados devem ser tratados para propósitos legítimos, específicos, explícitos e informados ao titular.

| Status | Item |
|---|---|
| ✅ | Dados coletados são exclusivamente administrativos (nome, telefone, e-mail, histórico de sessões e valores). Sem dados clínicos. |
| ✅ | Escopo de dados bem delimitado no design do schema (sem campos de prontuário ou saúde). |
| ❌ | A finalidade **não está documentada nem comunicada** ao titular em nenhuma política pública. |

**Tarefa LGPD-001** 🔴
Criar `docs/politica-de-privacidade.md` (ou página pública) descrevendo:
- Quais dados são coletados de profissionais e com qual finalidade
- Que a plataforma atua como operadora dos dados dos clientes dos profissionais
- Base legal para cada tipo de dado tratado

---

### 1.2 Adequação (Art. 6, II)
> Compatibilidade do tratamento com as finalidades informadas ao titular.

| Status | Item |
|---|---|
| ✅ | Dados de agenda, cobrança e comunicação são diretamente relacionados à finalidade de secretariado. |
| ⚠️ | O uso de IA (Anthropic API) para processar mensagens e gerar relatórios é adequado à finalidade, **mas não está explicitado** que os dados são enviados a um subprocessador externo (Anthropic). |

**Tarefa LGPD-002** 🔴
Documentar na Política de Privacidade que os dados podem ser enviados à Anthropic (API de IA) e à Meta (WhatsApp) como subprocessadores, com a finalidade de execução do serviço.

---

### 1.3 Necessidade / Minimização (Art. 6, III)
> Limitação ao mínimo necessário para a realização das finalidades.

| Status | Item |
|---|---|
| ✅ | Schema coleta apenas: nome, telefone, e-mail, datas de sessão, valores, status de consentimento (opt-in). |
| ✅ | Sem campos supérfluos identificados no schema atual. |
| ⚠️ | `whatsapp_conversations` armazena o conteúdo completo das mensagens. Verificar se é necessário armazenar o histórico integral ou apenas metadados. |

**Tarefa LGPD-003** 🟡
Definir e implementar política de retenção de mensagens WhatsApp: após N dias (ex: 90 dias após última sessão), o conteúdo das mensagens pode ser expurgado mantendo apenas metadados (data, direção, tipo). Implementar via `jobs/tasks/cleanup.py`.

---

### 1.4 Livre Acesso (Art. 6, IV) + Direito de Acesso (Art. 18, II)
> O titular deve ter acesso facilitado e gratuito aos seus dados.

| Status | Item |
|---|---|
| ✅ | `GET /professionals/me` — profissional acessa seus próprios dados. |
| ❌ | **Não existe endpoint** para o profissional baixar todos os dados dos clientes dele em formato portável (JSON/CSV). |
| ❌ | **Não existe mecanismo** para um cliente dos profissionais solicitar seus próprios dados (eles são titulares dos dados que o profissional cadastrou sobre eles). |

**Tarefa LGPD-004** 🔴
Implementar `GET /professionals/me/data-export` — retorna JSON com todos os dados do profissional (perfil, clientes, sessões, configurações) para exercício do direito de portabilidade. Compactar em ZIP se necessário.

**Tarefa LGPD-005** 🟡
Documentar no DPA (contrato com profissionais) que é **responsabilidade do profissional** atender solicitações de acesso de seus próprios clientes (pois ele é o controlador desses dados). A plataforma apenas provê a infraestrutura.

---

### 1.5 Qualidade dos Dados (Art. 6, V)
> Exatidão, clareza, relevância e atualização dos dados.

| Status | Item |
|---|---|
| ✅ | `PATCH /clients/{id}` — permite correção de dados incompletos ou desatualizados. |
| ✅ | `PATCH /professionals/me` — profissional pode atualizar seus dados. |
| ✅ | `updated_at` via mixin em todas as entidades — rastreabilidade de modificações. |

Sem pendências técnicas. ✅

---

### 1.6 Transparência (Art. 6, VI)
> Informações claras, precisas e facilmente acessíveis sobre o tratamento.

| Status | Item |
|---|---|
| ❌ | **Não existe Política de Privacidade** pública acessível. |
| ❌ | **Não existe Política de Cookies** (frontend usa cookies HttpOnly para refresh token). |
| ❌ | **Não existe Aviso de Privacidade** no fluxo de cadastro do profissional. |
| ❌ | **Não existe banner/aceite** de termos no momento do registro. |

**Tarefa LGPD-006** 🔴
Adicionar ao `RegisterPage.tsx` checkbox obrigatório com link para Política de Privacidade e Termos de Uso. Sem aceite, o formulário não avança. Gravar aceite com timestamp no banco (campo `terms_accepted_at TIMESTAMPTZ` na tabela `professionals`).

**Tarefa LGPD-007** 🔴
Criar página pública `/privacidade` e `/termos` acessíveis sem login.

**Tarefa LGPD-008** 🟡
Adicionar aviso de cookies no frontend (o refresh token em HttpOnly cookie precisa estar documentado na política de cookies, mesmo sendo essencial ao funcionamento).

---

### 1.7 Segurança (Art. 6, VII) + Art. 46
> Medidas técnicas e administrativas aptas a proteger os dados pessoais.

| Status | Item |
|---|---|
| ✅ | RLS no PostgreSQL (dupla barreira de isolamento entre tenants). |
| ✅ | Senhas com bcrypt (fator de custo adequado). |
| ✅ | JWT com expiração curta (15min) + refresh token revogável no banco. |
| ✅ | Cookie HttpOnly + Secure em produção (ADR-017). |
| ✅ | CORS com origens explícitas, sem wildcard (ADR-018). |
| ✅ | UUID PKs (anti-enumeração de IDs). |
| ✅ | Mesma mensagem de erro para e-mail/senha inválidos (ADR-012, anti-enumeração). |
| ⚠️ | `audit_logs` está no schema mas **o módulo não foi implementado**. |
| ❌ | **Dados pessoais em plaintext** no banco (nome, telefone, e-mail de clientes). Criptografia em nível de campo não implementada. |
| ❌ | **ENCRYPTION_KEY** existe como variável de ambiente mas não há evidência de uso para encriptar campos sensíveis. |
| ❌ | **Sem rate limiting** nos endpoints de autenticação (brute force em `/auth/login`). |
| ❌ | **Sem processo documentado** de resposta a incidentes de segurança. |

**Tarefa LGPD-009** 🔴
Implementar `audit_logs` — registrar pelo menos: login/logout, criação/edição/exclusão de clientes e sessões, exportação de dados, alteração de configurações de WhatsApp. Campos mínimos: `id`, `professional_id`, `action`, `entity_type`, `entity_id`, `ip_address`, `user_agent`, `created_at`.

**Tarefa LGPD-010** 🟡
Implementar rate limiting em `POST /auth/login` e `POST /auth/refresh` via middleware ou biblioteca (ex: `slowapi`). Limite sugerido: 5 tentativas/minuto por IP.

**Tarefa LGPD-011** 🟡
Decisão de design: **criptografia de campos sensíveis em nível de coluna** (ex: telefone dos clientes). Trade-off: impossibilita queries de busca por telefone sem descriptografar. Avaliar se `ENCRYPTION_KEY` já no `.env` será usado para isso ou se o isolamento via RLS + bcrypt de acesso é suficiente para o MVP. Documentar a decisão como ADR-025.

**Tarefa LGPD-012** 🟡
Criar `docs/plano-de-resposta-a-incidentes.md` com: definição de incidente, papéis, fluxo de notificação, prazo de 72h para comunicar à ANPD (Art. 48), e template de comunicação aos titulares afetados.

---

### 1.8 Prevenção (Art. 6, VIII)
> Adoção de medidas para prevenir a ocorrência de danos.

| Status | Item |
|---|---|
| ✅ | Soft delete com `is_active` em vez de DELETE físico — evita perda acidental de dados. |
| ✅ | `ON DELETE RESTRICT` em entidades com valor histórico — evita deleção em cascata acidental. |
| ❌ | **Sem DPIA (Relatório de Impacto à Proteção de Dados Pessoais)** — obrigatório para tratamento por IA (Art. 38 + Guia ANPD sobre IA). |

**Tarefa LGPD-013** 🟡
Elaborar RIPD/DPIA documentando: categorias de dados tratados pela IA, finalidade, riscos identificados, medidas mitigadoras. Não precisa ser um documento complexo — uma página estruturada em `docs/ripd.md` já atende para o porte atual.

---

### 1.9 Não Discriminação (Art. 6, IX)
> Impossibilidade de realização do tratamento para fins discriminatórios ilícitos ou abusivos.

| Status | Item |
|---|---|
| ✅ | Dados tratados são exclusivamente administrativos. Sem categorias especiais de dados (saúde, raça, opinião política, etc.). |
| ✅ | IA utilizada para automação de tarefas (lembretes, relatórios financeiros), não para decisões sobre titulares. |

Sem pendências. ✅

---

### 1.10 Responsabilização (Art. 6, X) + Art. 37
> Demonstração de conformidade pelo controlador.

| Status | Item |
|---|---|
| ❌ | **Sem registro (ROPA)** das atividades de tratamento de dados. |
| ❌ | **Sem encarregado (DPO)** designado e publicado (Art. 41). |

**Tarefa LGPD-014** 🟡
Criar `docs/ropa.md` — Registro de Operações de Tratamento listando: finalidade, base legal, categorias de dados, categorias de titulares, retenção, destinatários, transferências internacionais. Uma tabela por operação de tratamento.

**Tarefa LGPD-015** 🟡
Designar formalmente um encarregado (pode ser o próprio fundador no início). Publicar o contato do encarregado na Política de Privacidade. Requisito do Art. 41 — a ANPD pode regulamentar exceções para pequenas empresas, mas por segurança publique o contato.

---

## 2. Bases Legais para Tratamento (Art. 7)

| Dado | Titular | Base Legal Aplicável | Status |
|---|---|---|---|
| Nome, e-mail, senha do profissional | Profissional | Execução de contrato (Art. 7, V) | ⚠️ Contrato não formalizado |
| Nome, telefone, e-mail do cliente do profissional | Cliente do profissional | Execução de contrato ou consentimento — **responsabilidade do profissional** | ⚠️ Não orientado nos Termos |
| Histórico de sessões e valores | Cliente do profissional | Execução de contrato ou legítimo interesse — **responsabilidade do profissional** | ⚠️ Não orientado nos Termos |
| Mensagens WhatsApp | Cliente do profissional | Consentimento via `whatsapp_opt_in` | ✅ Campo existe, ⚠️ fluxo de coleta não implementado |
| Logs de auditoria | Profissional | Legítimo interesse — segurança e compliance | ❌ Módulo não implementado |

**Tarefa LGPD-016** 🔴
Formalizar **Termos de Uso** que estabeleçam:
- A relação contratual com o profissional (base legal Art. 7, V para dados do profissional)
- Que o profissional é controlador dos dados de seus clientes e deve ter sua própria base legal
- As obrigações do profissional perante seus clientes (informar sobre uso da plataforma)

**Tarefa LGPD-017** 🔴
Implementar fluxo de coleta de `whatsapp_opt_in` — quando a IA manda a primeira mensagem a um cliente novo via WhatsApp, deve enviar aviso de privacidade e aguardar consentimento explícito antes de armazenar conversas. O campo já existe no banco; falta o fluxo.

---

## 3. Direitos dos Titulares (Arts. 17–22)

| Direito | Artigo | Status | Endpoint |
|---|---|---|---|
| Confirmação de existência de tratamento | Art. 18, I | ⚠️ | Sem endpoint dedicado; inferível via `/professionals/me` |
| Acesso aos dados | Art. 18, II | ⚠️ | `/professionals/me` existe; exportação completa não |
| Correção de dados | Art. 18, III | ✅ | `PATCH /professionals/me`, `PATCH /clients/{id}` |
| Anonimização ou eliminação de dados desnecessários | Art. 18, IV | ❌ | Soft delete não elimina; sem processo de anonimização |
| Portabilidade | Art. 18, V | ❌ | Sem endpoint de exportação estruturada |
| Eliminação dos dados tratados com consentimento | Art. 18, VI | ❌ | Sem fluxo de exclusão definitiva de conta |
| Informação sobre compartilhamento | Art. 18, VII | ❌ | Não documentado publicamente |
| Informação sobre possibilidade de não consentir | Art. 18, VIII | ❌ | Sem aviso no cadastro |
| Revogação do consentimento | Art. 18, IX | ⚠️ | Campo `whatsapp_opt_in` existe; sem endpoint para o titular revogar |
| Revisão de decisões automatizadas por IA | Art. 20 | ⚠️ | IA usada para automação, não decisões sobre titulares — mas deve ser documentado |

**Tarefa LGPD-018** 🔴
Implementar **fluxo de exclusão de conta** (`DELETE /professionals/me/account`):
1. Anonimizar dados pessoais do profissional (nome → "Profissional Removido", e-mail → UUID, telefone → NULL)
2. Anonimizar dados dos clientes associados (nome → "Cliente Removido", telefone → NULL, e-mail → NULL)
3. Manter registros de sessões/valores anonimizados para integridade histórica
4. Revogar todos os refresh tokens
5. Desconectar WhatsApp Business
6. Registrar em audit_log

> **Atenção ao conflito com ADR-009 (soft delete):** a LGPD exige eliminação real quando o titular solicita. A solução é anonimização — o registro permanece (para integridade referencial), mas todos os campos identificadores são sobrescritos. Isso não viola a ADR-009 porque estamos preservando o registro histórico sem dados pessoais.

**Tarefa LGPD-019** 🔴
Implementar `POST /clients/{id}/forget` — anonimiza um cliente específico a pedido do profissional (que é o controlador dos dados desse cliente). Mesma estratégia: anonimizar campos de PII, manter histórico de sessões com valores.

**Tarefa LGPD-020** 🟡
Implementar `GET /professionals/me/data-export` — retorna ZIP com:
- `profile.json` (dados do profissional)
- `clients.json` (lista de clientes com campos PII)
- `sessions.json` (histórico completo)
- `whatsapp_conversations.json` (mensagens nos últimos N dias)

**Tarefa LGPD-021** 🟡
Implementar `PATCH /clients/{id}/consent` — endpoint para o profissional registrar revogação de consentimento de comunicação de um cliente (`whatsapp_opt_in: false`, `email_opt_in: false`). Job automático deve parar envios para esse cliente.

---

## 4. Transferência Internacional de Dados (Arts. 33–36)

A aplicação transfere dados para fora do Brasil em três pontos:

| Destino | Dado Transferido | País | Adequação |
|---|---|---|---|
| **Anthropic API** | Mensagens WhatsApp + contexto de sessões (para IA processar) | EUA | ⚠️ EUA não reconhecido pela ANPD como adequado — exige cláusulas contratuais ou consentimento |
| **Railway** | Banco de dados completo (hospedagem) | EUA | ⚠️ Mesma situação — Railway tem DPA disponível |
| **Meta Cloud API** | Mensagens WhatsApp | EUA | ⚠️ Meta tem DPA e SCCs disponíveis |

**Tarefa LGPD-022** 🔴
Assinar/aceitar os **DPAs (Data Processing Agreements)** de:
- Railway: disponível no dashboard, seção Legal
- Meta: incluído automaticamente nos Termos da API
- Anthropic: disponível em console.anthropic.com → Legal

Documentar esses contratos em `docs/subprocessadores.md`.

**Tarefa LGPD-023** 🔴
Informar na Política de Privacidade que dados são transferidos para os EUA para fins de processamento (IA, hospedagem, WhatsApp), com quais salvaguardas (cláusulas contratuais padrão via DPAs dos subprocessadores).

**Tarefa LGPD-024** 🟡
Avaliar se é possível **minimizar o que é enviado à Anthropic**: enviar apenas o contexto mínimo necessário para cada interação, sem histórico completo. Implementar em `ai/prompts.py` como boa prática de minimização + redução de custo de tokens.

---

## 5. Notificação de Incidentes (Art. 48)

> Em caso de incidente de segurança com dados pessoais, o controlador deve comunicar à ANPD e aos titulares afetados em **prazo razoável** (interpretado como 72 horas pela ANPD).

| Status | Item |
|---|---|
| ❌ | Sem processo documentado de detecção e classificação de incidentes |
| ❌ | Sem template de comunicação à ANPD |
| ❌ | Sem template de comunicação aos titulares afetados |
| ❌ | Sem sistema de alertas para detecção de acesso anômalo |

**Tarefa LGPD-025** 🟡
Criar `docs/plano-resposta-incidentes.md` com:
- Definição de incidente (o que conta e o que não conta)
- Classificação de severidade (baixa, média, alta)
- Fluxo de resposta em 72h
- Template de comunicação à ANPD (formulário em gov.br/anpd)
- Template de e-mail/WhatsApp para titulares afetados
- Contatos de emergência

**Tarefa LGPD-026** 🟢
Adicionar alertas de anomalia nos `audit_logs`: múltiplos logins falhos, acesso fora de padrão geográfico, exportação massiva de dados.

---

## 6. Crianças e Adolescentes (Art. 14)

| Status | Item |
|---|---|
| ⚠️ | O produto é B2B para profissionais adultos. Porém, clientes de psicólogos/terapeutas **podem ser menores de idade**. |
| ❌ | Sem verificação de que o cliente cadastrado é maior de idade ou que há consentimento dos responsáveis. |

**Tarefa LGPD-027** 🟡
Adicionar nos Termos de Uso a orientação de que o profissional, ao cadastrar clientes menores de idade, é responsável por obter consentimento dos pais/responsáveis, conforme Art. 14 da LGPD. A plataforma não coleta dados de menores diretamente.

---

## 7. Resumo Executivo

### Por Severidade

**🔴 Bloqueadores (8 tarefas — não vai ao ar sem estas)**

| ID | Tarefa |
|---|---|
| LGPD-001 | Política de Privacidade pública |
| LGPD-002 | Documentar subprocessadores (Anthropic, Meta, Railway) |
| LGPD-006 | Aceite de Termos no cadastro com timestamp no banco |
| LGPD-007 | Páginas públicas `/privacidade` e `/termos` |
| LGPD-016 | Termos de Uso formalizando relação controlador/operador |
| LGPD-017 | Fluxo de consentimento WhatsApp antes da primeira mensagem |
| LGPD-018 | Endpoint de exclusão/anonimização de conta do profissional |
| LGPD-022 | Assinar DPAs com Railway, Meta e Anthropic |
| LGPD-023 | Transferências internacionais na Política de Privacidade |

**🟡 Importantes (10 tarefas — devem estar no MVP)**

| ID | Tarefa |
|---|---|
| LGPD-003 | Política de retenção de mensagens WhatsApp (cleanup job) |
| LGPD-009 | Módulo `audit_logs` implementado |
| LGPD-010 | Rate limiting em endpoints de autenticação |
| LGPD-011 | Decisão sobre criptografia em nível de campo (ADR-025) |
| LGPD-012 | Plano de resposta a incidentes |
| LGPD-013 | RIPD/DPIA para tratamento por IA |
| LGPD-014 | ROPA (Registro de Operações de Tratamento) |
| LGPD-015 | Designar e publicar contato do Encarregado (DPO) |
| LGPD-019 | Endpoint `POST /clients/{id}/forget` (anonimização de cliente) |
| LGPD-020 | Endpoint de exportação de dados (portabilidade) |
| LGPD-021 | Endpoint de revogação de consentimento de comunicação |
| LGPD-025 | Plano de resposta a incidentes documentado |
| LGPD-027 | Orientação sobre menores de idade nos Termos |

**🟢 Recomendados (2 tarefas — pós-MVP imediato)**

| ID | Tarefa |
|---|---|
| LGPD-024 | Minimização de contexto enviado à Anthropic |
| LGPD-026 | Alertas de anomalia em audit_logs |

---

### O Que Já Está Conforme ✅

- Minimização de dados: apenas dados administrativos, sem dados clínicos
- Soft delete preservando integridade histórica
- Isolamento de tenants via RLS (segurança técnica)
- Senhas com bcrypt, JWT com expiração curta
- Revogação de refresh tokens (controle de sessão)
- Cookie HttpOnly + Secure em produção
- CORS sem wildcard
- Anti-enumeração no login
- Campos `whatsapp_opt_in` e `email_opt_in` no schema de clientes
- `PATCH` endpoints para correção de dados (direito Art. 18, III)
- UUID PKs (sem enumeração de IDs sequenciais)
- HTTPS via Railway (criptografia em trânsito)

---

## 8. Ordem de Implementação Sugerida

```
Sprint LGPD-1 (antes do deploy)
├── LGPD-022 — Assinar DPAs (Railway, Meta, Anthropic) → 30min cada
├── LGPD-001 + LGPD-007 — Escrever e publicar Política de Privacidade + Termos → 1 dia
├── LGPD-016 — Termos de Uso com relação controlador/operador → incluso acima
├── LGPD-006 — Checkbox de aceite no RegisterPage com timestamp → 2h
├── LGPD-023 + LGPD-002 — Subprocessadores e transferências na Política → incluso acima
└── LGPD-017 — Fluxo de opt-in WhatsApp na primeira mensagem → 4h

Sprint LGPD-2 (semana 1 pós-lançamento)
├── LGPD-009 — Módulo audit_logs (modelo + repository + service + testes) → 1 dia
├── LGPD-018 — Endpoint exclusão/anonimização de conta → 1 dia
├── LGPD-019 — Endpoint forget de cliente individual → 4h
├── LGPD-020 — Endpoint data-export (portabilidade) → 1 dia
└── LGPD-010 — Rate limiting em auth endpoints → 2h

Sprint LGPD-3 (semana 2 pós-lançamento)
├── LGPD-011 — ADR-025: decisão sobre criptografia de campos → 2h (decisão) + implementação
├── LGPD-013 — RIPD/DPIA → 4h (documento)
├── LGPD-014 — ROPA → 4h (documento)
├── LGPD-015 — Publicar contato do Encarregado → 30min
├── LGPD-021 — Endpoint revogação de consentimento → 2h
├── LGPD-003 — Política de retenção de mensagens + cleanup job → 4h
└── LGPD-027 — Menores de idade nos Termos → incluso na revisão dos Termos
```

---

*Documento deve ser revisado a cada 6 meses ou quando houver mudança relevante no produto, nas integrações ou na regulamentação da ANPD.*
