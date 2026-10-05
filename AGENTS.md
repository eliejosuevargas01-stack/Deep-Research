# AGENTS.md — Mapa de Documentação e Agentes Deep Research Engine

> Gerado automaticamente pelo Reversa Framework  
> Data: 2026-10-05  
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
| `architecture.md` | Topologia, componentes, fluxo de vida da pesquisa | `/reversa` (Archaeologist + Architect) | Forward Planner, Coding Agent, DevOps |
| `domain.md` | Modelo de domínio + 8 entidades + restrições | `/reversa` (Archaeologist + Data Master) | Backend Workers, Auditor, DB Migrations |
| `code-analysis.md` | Estrutura de módulos, padrões, débito técnico | `/reversa` (Inspector) | Refactor Agent, Quality Agent |
| `discovery_report.md` | Mapeamento quantitativo de arquivos/LOC | Scout (esta sessão) | Forward Planner |

---

### ⚙️ Ciclo Forward — `_reversa_forward/`
| Arquivo | Descrição | Fase | Status |
|---------|-----------|------|--------|
| `requirements.md` | Requisitos modularização backend (REQ-01 a REQ-07) | Requirements | ✅ Aprovado |
| `requirements-audit.md` | Quality Audit de clareza/completude | Quality | ✅ Aprovado |
| `roadmap.md` | 4 fases, 5 semanas, riscos priorizados | Planning | ✅ Pronto |
| `actions.md` | 13 tarefas atômicas T001–T013 com checkboxes | Actions | 🔄 Próximo |
| `quality.md` | *(a gerar)* Critérios de qualidade por agente | Quality | ⏳ Pendente |

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
| Arquivo | Descrição |
|---------|-----------|
| `test_backend.py` | **2.226 LOC** — Testes integração + unitários mistos (alvo: separar) |
| `test_e2e_criteria.py` | Teste E2E completo baseado em CRITERIA.md |
| `test_postgres.py` | Fixtures de banco isolado para testes |

---

### 🗄️ Migrações — `alembic/versions/`
| Versão | Descrição |
|--------|-----------|
| `0001_initial.py` | Schema inicial (Research, Points, Evidences, Events, Reports, AuditTrails, AdminSessions, AppSettings) |
| `0002_audit_trails.py` | Tabela audit_trails + índices |
| `0003_settings_callback_and_base_url.py` | Callback URL global + openai_base_url em AppSettings |

---

### 🔧 Código Fonte — `app/`
| Módulo | Arquivos Principais | Responsabilidade |
|--------|---------------------|------------------|
| `core/` | `config.py`, `security.py` | Settings Pydantic, Auth JWT Cookie + CSRF |
| `db/` | `database.py` | Engine async SQLAlchemy + session management |
| `models/` | `domain_models.py` | 8 tabelas Declarative Base |
| `schemas/` | `__init__.py` | Pydantic schemas request/response |
| `routers/` | `auth.py`, `research.py`, `settings.py` | Endpoints FastAPI |
| `services/` | `research.py` (591 LOC), `llm.py`, `audit.py`, `crypto.py`, `settings.py`, `webhook.py` | **Lógica de negócio — alvo principal de modularização** |
| `tools/` | `search_pipeline.py`, `outbound.py` | Busca multi-provedor + SSRF Guard |
| `prompts/` | `__init__.py`, `personas.json` | Templates de prompt (em migração para `.md`) |

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
│                    REVERSA FORWARD ATUAL                        │
├─────────────────────────────────────────────────────────────────┤
│  ✅ DISCOVERY (scout)         → _reversa_sdd/discovery_report.md│
│  ✅ ARCHITECTURE (archaeolog) → _reversa_sdd/architecture.md    │
│  ✅ DOMAIN (data-master)      → _reversa_sdd/domain.md          │
│  ✅ CODE-ANALYSIS (inspector) → _reversa_sdd/code-analysis.md   │
│  ✅ PRINCIPLES                → .reversa/principles.md          │
│  ✅ REQUIREMENTS              → _reversa_forward/requirements.md│
│  ✅ QUALITY AUDIT             → _reversa_forward/requirements-audit.md│
│  ✅ ROADMAP                   → _reversa_forward/roadmap.md     │
│  ✅ ACTIONS (T001–T013)       → _reversa_forward/actions.md     │
│  ⏳ CODING                    → app/services/workers/ + tests/  │
│  ⏳ SYNC                      → specs atualizadas               │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📋 Próximas Ações Imediatas (do `actions.md`)

| ID | Tarefa | Responsável | Status |
|----|--------|-------------|--------|
| **T001–T009** | Modularização dos workers e agentes em `app/services/workers/` | Coding Agent | ✅ Concluído |
| **T010** | Refatorar `research.py` orquestrador (< 200 LOC) | Coding Agent | ⬜ Pendente |
| **T011** | Teste E2E integração completa | QA Specialist | ⬜ Pendente |
| **T012** | CI/CD GitHub Actions + cobertura ≥ 80% | DevOps | ⬜ Pendente |
| **T013** | Smoke test `docker-compose up` + docs | DevOps | ⬜ Pendente |

---

## 🔗 Como Navegar

- **Iniciar implementação**: Leia `actions.md` → execute `T001`
- **Entender arquitetura**: Leia `architecture.md` + `domain.md`
- **Ver contratos de API**: Leia `contracts.md` + `app/routers/*.py`
- **Executar testes**: `pytest tests/ -x --tb=short` (requer venv)
- **Subir stack**: `docker-compose up -d` → `http://localhost:8000/docs`
- **Atualizar este mapa**: Rode `/reversa-docs` após mudanças significativas

---

> **Nota**: Este arquivo é a "tabela de conteúdo" viva do projeto. Agentes devem consultá-lo para entender contexto antes de executar tarefas.