# AGENTS.md — Mapa de Documentação e Agentes Deep Research Engine

> Gerado automaticamente pelo Reversa Framework  
> Data: 2026-10-21  
> Mantido pelo ciclo forward: `/reversa-docs` atualiza este mapa

---

## 📚 Índice Mestre de Documentação

### 🎯 Documentos Canônicos (Raiz do Projeto)
| Arquivo | Descrição | Localização | Agentes Relacionados |
|---------|-----------|-------------|---------------------|
| `GOAL.md` | Objetivo de alto nível + regras de aceitação | `/root/projects/deep-research/GOAL.md` | Orchestrator, QA |
| `plan.md` | Plano executivo detalhado (fases, tarefas, critérios) | `/root/projects/deep-research/plan.md` | Orchestrator, Forward Planner |
| `workflow.md` | Fluxo de trabalho cognitivo 4 fases | `/root/projects/deep-research/workflow.md` | Scout, Workers, Auditor, Writer |
| `contracts.md` | Contratos de API, eventos SSE, schemas | `/root/projects/deep-research/contracts.md` | Backend, Frontend, QA |
| `QA_MATRIX.md` | Matriz de critérios de qualidade por fase | `/root/projects/deep-research/QA_MATRIX.md` | Auditor, QA Specialist |
| `TASKS.md` | Lista de tarefas atômicas (ID, status, dono) | `/root/projects/deep-research/TASKS.md` | Orchestrator, Coding Agent |
| `README.md` | Visão geral + instruções de execução | `/root/projects/deep-research/README.md` | Onboarding, DevOps |

---

### 🔬 Especificações Reversa (SDD) — `_reversa_sdd/`
| Arquivo | Descrição | Gerado Por | Consumido Por |
|---------|-----------|------------|---------------|
| `prd.md` | PRD canônico do módulo de briefing e pipeline (backend) | `/reversa-spec-sdd` | Reviewer, Coding Agent, Forward Planner |
| `sdd/briefing.md` | Spec auditável do módulo de briefing backend | `/reversa-spec-sdd` | Reviewer, Coding Agent, DevOps |
| `addenda/001-modulo-briefing.md` | Adendo de convergência da Feature 001 | `/reversa-sync` | Reviewer, Forward Planner |
| `addenda/002-investigacao-personas.md` | Adendo de convergência da Feature 002 (Investigação) | `/reversa-sync` | Reviewer, Forward Planner |
| `addenda/003-modulo-auditoria.md` | Adendo de convergência da Feature 003 (Auditoria Factual) | `/reversa-sync` | Reviewer, Forward Planner |
| `addenda/004-modulo-redator-webhook.md` | Adendo de convergência da Feature 004 (Redator & Webhook) | `/reversa-sync` | Reviewer, Forward Planner |
| `addenda/005-convergencia-pipeline.md` | Adendo de convergência da Feature 005 (Convergência Total) | `/reversa-sync` | Reviewer, Forward Planner |
| `addenda/diretrizes-20261019-workers-jina-briefing.md` | Diretrizes mandatórias de coleta, teto e briefing síncrono | Usuário / Stakeholders | Orchestrator, Coding Agent |
| `confidence-report.md` | Relatório global de confiança (100% 🟢 CONFIRMADO) | `/reversa-reviewer` | Orchestrator, QA Specialist, Stakeholders |
| `questions.md` | Questões críticas e alinhamentos para validação humana | `/reversa-reviewer` | Usuário / Stakeholders |
| `gaps.md` | Inventário de lacunas categorizadas por severidade | `/reversa-reviewer` | Orchestrator, Forward Planner |
| `traceability/bugs.md` | Matriz de rastreabilidade de correções de bugs | `/reversa-debugger` | Orchestrator, QA Specialist |

---

### ⚙️ Ciclo Forward — `_reversa_forward/`
| Feature | Descrição | Status | Artefatos Principais |
|---------|-----------|--------|----------------------|
| `001-modulo-briefing/` | Módulo de Briefing (Backend) — geração, validação e persistência | ✅ Concluído (T001–T028 + E001) | `requirements.md`, `roadmap.md`, `actions.md`, `legacy-impact.md`, `regression-watch.md` |
| `002-investigacao-personas/` | Investigação Paralela por 4 Personas (Workers LiteLLM + Jina Search) | ✅ Concluído (C1–C8) | `requirements.md`, `roadmap.md`, `actions.md`, `interfaces/`, `legacy-impact.md` |
| `003-modulo-auditoria/` | Módulo de Auditoria Factual e Verificação de Citações Verbatim | ✅ Concluído (A1–A6) | `requirements.md`, `roadmap.md`, `actions.md`, `legacy-impact.md` |
| `004-modulo-redator-webhook/` | Módulo Redator Editorial e Despacho Assíncrono Webhook | ✅ Concluído (T051–T062) | `requirements.md`, `roadmap.md`, `actions.md`, `legacy-impact.md`, `regression-watch.md` |
| `005-convergencia-pipeline/` | Convergência Total: 10 corpos Jina, merge por rodada, teto de 4 retries, guardrails flexíveis e briefing síncrono | ✅ Concluído (T001–T031) | `requirements.md`, `roadmap.md`, `actions.md`, `legacy-impact.md`, `regression-watch.md`, `interfaces/` |

---

### 🏗️ Configuração Reversa — `.reversa/`
| Arquivo | Descrição |
|---------|-----------|
| `config.toml` | Layout specs feature-folder, granularidade feature |
| `state.json` | User, language, output folder |
| `soul.md` | Alma do projeto (resumo arquitetural extraído) |
| `principles.md` | 4 princípios ativos: Verbatim Citation, Privacy, Graceful Degradation, Safe Concurrency |
| `reversa-config.json` | Versão, paths permitidos, telemetria |

---

### 🎨 Frontend — `frontend/`
| Arquivo | Descrição |
|---------|-----------|
| `PLAN.md` | Plano específico do frontend (componentes, rotas, estado) |
| `src/main.tsx` | **Monolítico (~95KB)** — alvo de refactoring futuro |
| `src/api.ts` | Cliente API + SSE + tipos de resposta |
| `src/types.ts` | Tipos TypeScript compartilhados |
| `src/routes.ts` | Rotas React Router |
| `src/research-utils.ts` | Utilitários de formatação/validação |
| `src/style.css` | Tailwind + tokens dark mode (estilo Linear) |

---

### 🤖 Prompts dos Agentes — `app/prompts/`
| Arquivo | Descrição |
|---------|-----------|
| `personas.json` | Configuração das 4 personas (system prompt + parâmetros) |
| `scout.md` | *(a criar)* Template do ScoutWorker |
| `historian.md` | *(a criar)* Template do HistorianWorker |
| `skeptic.md` | *(a criar)* Template do SkepticWorker |
| `pragmatist.md` | *(a criar)* Template do PragmatistWorker |
| `futurist.md` | *(a criar)* Template do FuturistWorker |
| `writer.md` | *(a criar)* Template do WriterAgent |

---

### 🧪 Testes — `tests/`
| Arquivo / Diretório | Descrição | Status / Cobertura |
|---------------------|-----------|-------------------|
| `test_backend.py` | Testes de integração + unitários legados da API | Cobertura base FastAPI |
| `test_e2e_criteria.py` | Teste E2E completo baseado em CRITERIA.md | Integração funcional |
| `test_postgres.py` | Fixtures de banco isolado para testes | Infraestrutura de teste |
| `tests/investigation/` | Suíte completa de investigação (jina tool, workers, schemas, round storage, migração, runtime regressions, e2e) | 104 passed (100% GREEN) |
| `tests/audit/` | Suíte de auditoria factual e validação de merge CAS (`test_audit_api.py`, `test_audit_round_merge.py`) | 22 passed (100% GREEN) |
| `tests/unit/test_pipeline_writer_convergence.py` | Suíte de convergência do Writer (guardrails de limitação e proposta didática) | 17 passed (100% GREEN) |
| `tests/test_briefing_*.py` | Suíte de briefing HTTP síncrono e decisão única (api, boundaries, lifecycle) | 23 passed, 162 subtestes (100% GREEN) |
| `tests/integration/` | Integração ponta a ponta (`test_pipeline_convergence_http.py`, `test_full_pipeline.py`) | 2 passed (100% GREEN) |

---

### 🗄️ Migrações — `alembic/versions/`
| Versão | Descrição |
|--------|-----------|
| `0001_initial.py` | Schema inicial (Research, Points, Evidences, Events, Reports, AuditTrails, AdminSessions, AppSettings) |
| `0002_audit_trails.py` | Tabela audit_trails + índices |
| `0003_settings_callback_and_base_url.py` | Callback URL global + openai_base_url em AppSettings |
| `0004_jina_base_url.py` | Configuração de jina_base_url em AppSettings |
| `0005_jina_proxy_worker.py` | Configurações de proxy e timeouts para workers Jina |
| `0006_briefing_storage.py` | Tabela briefings e persistência de pontos e temas |
| `0007_investigation_step_results_and_status.py` | Tabela research_step_results e status refinados de investigação |
| `0008_investigation_rounds_and_merges.py` | Colunas investigation_round, round, constraints únicas e tabela investigation_merges |

---

### 🔧 Código Fonte — `app/`
| Módulo | Arquivos Principais | Responsabilidade |
|--------|---------------------|------------------|
| `core/` | `config.py`, `security.py` | Settings Pydantic, Auth JWT Cookie + CSRF |
| `db/` | `database.py` | Engine async SQLAlchemy + session management |
| `models/` | `domain_models.py` | 9 tabelas Declarative Base mapeadas |
| `schemas/` | `__init__.py` | Pydantic schemas base request/response |
| `routers/` | `auth.py`, `research.py`, `settings.py` | Endpoints FastAPI HTTP/SSE |
| `briefing/` | `router.py`, `service.py`, `domain.py`, `schemas.py`, `serp_client.py` | Módulo de briefing síncrono e decisão única |
| `investigation/` | `router.py`, `service.py`, `storage.py`, `worker.py`, `tools.py`, `schemas.py` | Investigação concorrente por 4 personas, barreira de merge e Jina tool com parser HTML |
| `audit/` | `router.py`, `service.py`, `domain.py`, `schemas.py` | Auditoria factual sobre snapshot committed de merge com teto de 4 tentativas (`AUDIT_CAVEAT`) |
| `services/pipeline/` | `writer.py`, `constants.py` | Redator editorial unificado com guardrails de notas de limitação e proposta didática |
| `services/` | `research.py` (adaptador modular topológico), `search.py`, `crypto.py`, `settings.py`, `webhook.py` (anti-SSRF) | Orquestração do ciclo de vida, busca com HTMLParser e despacho seguro de eventos |
| `tools/` | `outbound.py` (SSRF Guard), `search_pipeline.py` | Utilitários de rede e segurança outbound |
| `prompts/` | `__init__.py`, `personas.json` | Configurações e templates de personas especialistas |

---

## 🤖 Agentes Reversa Disponíveis

### Ciclo Reversa (Extração Legado → `_reversa_sdd/`)
| Agente | Comando | Saída | Entrada |
|--------|---------|-------|---------|
| **Scout** | `/reversa-scout` | Mapeamento quantitativo | Código fonte |
| **Archaeologist** | `/reversa-archaeologist` | Análise profunda módulo a módulo | Código fonte |
| **Architect** | `/reversa-architect` | `architecture.md` | Análise do Archaeologist |
| **Data Master** | `/reversa-data-master` | `domain.md` (modelo de dados) | Models + Migrations |
| **Inspector** | `/reversa-inspector` | `code-analysis.md` | Código fonte |
| **Detective** | `/reversa-detective` | Conhecimento implícito de negócio | Logs, código, docs |

### Ciclo Forward (Evolução → `_reversa_forward/`)
| Agente | Comando | Entrada | Saída |
|--------|---------|---------|-------|
| **Requirements** | `/reversa-requirements` | SDD + Princípios + Gaps | `requirements.md` |
| **Quality** | `/reversa-quality` | Requirements | `requirements-audit.md` |
| **Planner** | `/reversa-plan` | Requirements aprovados | `roadmap.md` |
| **ToDo** | `/reversa-to-do` | Roadmap | `actions.md` (T001+) |
| **Coding** | `/reversa-coding` | Actions + Legacy | Código implementado + `progress.jsonl` |
| **Sync** | `/reversa-sync` | Código final + SDD | Specs sincronizadas |

### Migração (Legado → Novo)
| Agente | Comando | Saída |
|--------|---------|-------|
| **Paradigm Advisor** | `/reversa-paradigm-advisor` | `paradigm_decision.md` |
| **Strategist** | `/reversa-strategist` | `migration_strategy.md` |
| **Curator** | `/reversa-curator` | `target_domain_model.md` |
| **Designer** | `/reversa-designer` | `target_architecture.md` |
| **Inspector (Mig)** | `/reversa-inspector` | `parity_specs.md` |

### Documentação
| Agente | Comando | Saída |
|--------|---------|-------|
| **Docs Mapper** | `/reversa-docs-mapper` | Estrutura do site |
| **Docs Analyst** | `/reversa-docs-analyst` | Páginas de dados |
| **Docs Storyteller** | `/reversa-docs-storyteller` | Glossário interativo |
| **Docs Publisher** | `/reversa-docs-publisher` | `index.html` final |

---

## 🔄 Fluxo de Trabalho Atual

```
┌─────────────────────────────────────────────────────────────────┐
│                    REVERSA FORWARD CONCLUÍDO                    │
├─────────────────────────────────────────────────────────────────┤
│  ✅ 001-modulo-briefing       → Briefing síncrono e persistido  │
│  ✅ 002-investigacao-personas → Investigação por 4 personas     │
│  ✅ 003-modulo-auditoria      → Auditoria factual por merge     │
│  ✅ 004-modulo-redator-webhook→ Redator com anti-alucinação     │
│  ✅ 005-convergencia-pipeline → Coleta 10 Jina, merge atômico,  │
│                                 teto de 4 retries, guardrails   │
│                                 flexíveis e briefing síncrono   │
│  ✅ MATRIZ DE TESTES          → 172 passed, 162 subtestes (GREEN│
│  ✅ SPEC SYNC                 → _reversa_sdd/addenda/005-*.md   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📋 Status Atual de Entregas

| Feature / Frente | Responsável | Status | Evidências Principais |
|------------------|-------------|--------|-----------------------|
| **Feature 001 (Briefing)** | Time Forward | ✅ Concluído | T001–T028 + E001 aprovados |
| **Feature 002 (Investigação)** | Time Forward | ✅ Concluído | C1–C8 aprovados |
| **Feature 003 (Auditoria)** | Time Forward | ✅ Concluído | A1–A6 aprovados |
| **Feature 004 (Redator & Webhook)** | Time Forward | ✅ Concluído | T051–T062 aprovados |
| **Feature 005 (Convergência Pipeline)** | Time Forward | ✅ Concluído | T001–T031 aprovados (100% GREEN) |
| **CI/CD e Automação de Testes** | QA / DevOps | ✅ Ativo | Matriz com 172 testes e 162 subtestes |

---

## 🔗 Como Navegar

- **Ver contratos da API**: Leia `contracts.md` e `_reversa_forward/005-convergencia-pipeline/interfaces/pipeline-http.md`
- **Executar suíte completa**: `pytest tests/ -p no:cacheprovider` (requer venv)
- **Ver adendos de especificação**: Consulte `_reversa_sdd/addenda/`
- **Entender arquitetura**: Leia `architecture.md` + `domain.md`
- **Ver contratos de API**: Leia `contracts.md` + `app/routers/*.py`
- **Executar testes**: `pytest tests/ -x --tb=short` (requer venv)
- **Subir stack**: `docker-compose up -d` → `http://localhost:8000/docs`
- **Atualizar este mapa**: Rode `/reversa-docs` após mudanças significativas

---

> **Nota**: Este arquivo é a "tabela de conteúdo" viva do projeto. Agentes devem consultá-lo para entender contexto antes de executar tarefas.