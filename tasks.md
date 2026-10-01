# Deep Research Engine - Task Breakdown (Tarefas Atômicas)

Resumo:
* **Total de Ações:** 21
* **Total de Ações Paralelizáveis:** 8 (workers, testes por fase, instalação de dependências)
* **Maior cadeia de dependência:** P0 → P1 → P2 → P3 → P4 → P5 → P6 (7 fases sequenciais)

## Phase 0 - Project Scaffold & Dependency Setup

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Status |
|----|-----------|--------------|-------------|--------------|--------|
| T001 | Criar estrutura de pastas base (`app/api/`, `app/engine/`, `app/tools/`, `app/models/`) | — | Paralelo com: [T002, T003] | `app/` | [ ] |
| T002 | Atualizar `requirements.txt` com novas dependências assíncronas (`httpx`, `pydantic-settings`, `alembic`, `PyPDF2`, `uvloop`, `pyppeteer`) | — | Paralelo com: [T001, T003] | `requirements.txt` | [ ] |
| T003 | Instalar as dependências do `requirements.txt` via `pip install` em um ambiente virtual Python 3.11+ | — | Paralelo com: [T001, T002] | `venv/` | [ ] |

## Phase 1 - FastAPI App, Security Middleware & Schemas

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Status |
|----|-----------|--------------|-------------|--------------|--------|
| T004 | Criar classe `Settings` com `Pydantic BaseSettings` para carregar `.env` | [T002, T003] | Paralelo com: [T005] | `app/config.py` | [ ] |
| T005 | Definir schemas Pydantic (`ResearchRequest`, `ReportResponse`, `AuthErrorResponse`) | [T002] | Paralelo com: [T004] | `app/schemas/request_models.py`, `app/schemas/response_models.py` | [ ] |
| T006 | Implementar middleware FastAPI que valida headers de auth (`Authorization: Bearer`) e schema do payload; aborta com 400/401/422 | [T004, T005] | — | `app/middleware/security.py` | [ ] |
| T007 | Criar `app/main.py` com `FastAPI()` e roteador `/api/research` e `/api/reports/{id}` | [T004, T005] | — | `app/main.py` | [ ] |

## Phase 2 - Async DB Models (SQLAlchemy + PostgreSQL)

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Status |
|----|-----------|--------------|-------------|--------------|--------|
| T008 | Configurar `AsyncEngine` e `AsyncSessionLocal` usando `DATABASE_URL` do `.env` | [T003, T004] | — | `app/db/database.py` | [ ] |
| T009 | Criar modelos SQLAlchemy (`Research`, `ResearchPoint`, `EvidenceRecord`, `AuditTrail`, `Report`) incluindo coluna `version` para *Optimistic Locking* | — | — | `app/models/domain_models.py` | [ ] |
| T010 | Gerar a primeira migration base com Alembic (`alembic init` + script autogerado) | [T003, T009] | — | `alembic/env.py`, `alembic/versions/` | [ ] ] |

## Phase 3 - Async Orchestration Engine

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Status |
|----|-----------|--------------|-------------|--------------|--------|
| T011 | Implementar classe `Orchestrator` com método `dispatch_points()` que lê pontos e cria tasks assíncronas | [T008, T009] | — | `app/engine/orchestrator.py` | [ ] |
| T012 | Implementar mecanismo de *Optimistic Locking* no repositório de evidências (tenta commit, retry em `StaleDataError`) | [T008] | — | `app/repository/evidence_repo.py` | [ ] |
| T013 | Criar lógica de *loop de auditoria*: espera por conclusão dos 4 workers de um ponto, então dispara a auditoria | [T011] | — | `app/engine/audit_scheduler.py` | [ ] |

## Phase 4 - Workers & Search-Read-Clean Subflow

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Status |
|----|-----------|--------------|-------------|--------------|--------|
| T014 | Implementar subfluxo unificado `search_read_clean(query)` usando `httpx` assíncrono (SerpAPI/Jina/Apify como fallback) | [T003, T004] | — | `app/tools/search_pipeline.py` | [ ] |
| T015 | Implementar worker base `BaseWorker` (classe abstrata com `async run()` e `persona_prompt`) | [T014] | — | `app/agents/workers/base_worker.py` | [ ] |
| T016 | `[//]` Implementar os 4 workers concretos (Historiador, Cético, Pragmático, Visionário) herdando de `BaseWorker` | [T015] | **Paralelo entre si:** [T016] Historiador, [T016] Cético, [T016] Pragmático, [T016] Visionário | `app/agents/workers/historian.py`, `skeptic.py`, `pragmatist.py`, `futurist.py` | [ ] | [ ] [ ] [ ] [ ] |
| T017 | Criar pool de workers `WorkerPool` que mapeia pontos → 4 personas e executa tudo em paralelo (`asyncio.gather`) | [T011, T016] | — | `app/engine/worker_pool.py` | [ ] |
| T018 | Implementar worker de *Briefing & Scout* (mockado ou simplificado para esta fase) | [T014] | — | `app/agents/scout.py` | [ ] |

## Phase 5 - Auditor Logic & Retry Loop

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Status |
|----|-----------|--------------|-------------|--------------|--------|
| T019 | Implementar `Auditor.check_point(research_point_id)` (fact-check, mapeamento de contradições, geração de `outline`) | [T008, T013] | — | `app/agents/auditor.py` | [ ] |
| T020 | Implementar lógica do loop de retenção (`max_attempts = 3`) com ativação de *blocker* após 3 falhas | [T019] | — | `app/engine/retry_handler.py` | [ ] |

## Phase 6 - Report Writer & Webhook Callback

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Status |
|----|-----------|--------------|-------------|--------------|--------|
| T021 | Implementar `Redator.compile_report()` (Markdown synthesis sem tools, estritamente do outline aprovado) + envio de callback HTTP POST para `callback_url` | [T019, T020] | — | `app/agents/writer.py`, `app/services/webhook.py` | [ ] |

## Notas de Design

* **T016 (Workers):** As 4 implementações de workers são marcadas com `[//]` (paralelizáveis entre si), pois lidam com arquivos diferentes e não dependem umas das outras.
* **Optimistic Locking:** A coluna `version` em `EvidenceRecord` garante atomicidade sem travas pesadas.
* **Subfluxo de Busca:** Prioriza Jina como fallback gratuito (sem chave) seguido por Apify e SerpAPI.
