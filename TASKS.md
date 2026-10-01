# Deep Research Engine - TASKS.md (Live Backlook)

## Status do Projeto
- 🚧 **Em Planejamento** — Documentos de plano gerados (goal.md, plan.md, tasks.md, contracts.md)
- 🔴 **Nenhuma task de implementação iniciada** — Aguardando aprovação do plano

## 📊 Resumo do Plano (21 Ações)

| Fase | Ações | Paralelizáveis | Status |
|------|-------|----------------|--------|
| Phase 0 - Scaffold | 3 | 3 | ⬜ Pendentes |
| Phase 1 - FastAPI & Auth | 4 | 2 | ⬜ Pendentes |
| Phase 2 - DB Models | 3 | 0 | ⬜ Pendentes |
| Phase 3 - Orchestration Engine | 3 | 0 | ⬜ Pendentes |
| Phase 4 - Workers & Subflow | 5 | 4 | ⬜ Pendentes |
| Phase 5 - Auditor Logic | 2 | 0 | ⬜ Pendentes |
| Phase 6 - Redator & Webhooks | 1 | 0 | ⬜ Pendentes |

## 🔗 Diagrama de Dependência

```
P0 ──► P1 ──► P2 ──► P3 ──► P4 ──► P5 ──► P6
 (Scaffold) (API) (DB) (Engine) (Workers) (Audit) (Writer)
```

## 📋 Tarefas por Prioridade

* 🔴 Critical: T003 (Instalar dependências), T006 (Middleware de Auth), T014 (Subflow de Busca)
* 🟡 Importante: T009 (Models DB), T001 (Estrutura de pastas), T019 (Auditor)
* 🟢 Melhoria: T016 (Workers), T004 (Settings)

> Nenhuma task será executada sem seu visto positivo.

---

# Deep Research Engine - Live Task Backlog

- ⬜ **T001**: Criar estrutura de pastas base (`app/api/`, `app/engine/`, `app/tools/`, `app/models/`)
  * **Contexto:** Nenhum arquivo pré-existente no projeto — é o scaffold da aplicação.
  * **Critério:** Pastas vazias criadas.

- ⬜ **T002**: Atualizar `requirements.txt` com `httpx`, `pydantic-settings`, `alembic`, etc.
  * **Critério:** `requirements.txt` reflete as 5 seções do README original.
  - Paralelo com: [T001, T003]

- ⬜ **T003**: Instalar as dependências do `requirements.txt` via `pip install` em venv Python 3.11+.
  * **Critério:** `venv/` com todos os pacotes importáveis.

- ⬜ **T004**: Criar classe `Settings` com `pydantic-settings` para carregar `.env`.
  * **Critério:** `Settings().DATABASE_URL` e `.API_AUTH_SECRET` resolvem sem erro.

- ⬜ **T005**: Definir schemas Pydantic (`ResearchRequest`, `ReportResponse`).
  * **Critério:** `pydantic` valida corretamente um JSON de exemplo.

- ⬜ **T006**: Implementar middleware FastAPI que valida headers de auth e schema do payload; aborta com 400/401/422.
  * **Critério:** Request sem Bearer token retorna `401 Unauthorized`.

- ⬜ **T007**: Criar `app/main.py` com FastAPI e roteador `/api/research` e `/api/reports/{id}`.
  * **Critério:** `uvicorn app.main:app` inicia sem erros e o root `/` responde `200 OK`.

- ⬜ **T008**: Configurar `AsyncEngine` e `AsyncSessionLocal` usando `DATABASE_URL` do `.env`.
  * **Critério:** `AsyncSession` consegue fazer `SELECT 1` ao DB.

- ⬜ **T009**: Criar modelos SQLAlchemy (`Research`, `ResearchPoint`, `EvidenceRecord`, `AuditTrail`, `Report`) com *Optimistic Locking*.
  * **Critério:** Todos os 5 modelos criam tabelas via migration.

- ⬜ **T010**: Gerar a primeira migration base com Alembic.
  * **Critério:** `alembic upgrade head` roda sem erros.

- ⬜ **T011**: Implementar classe `Orchestrator` com método `dispatch_points()`.
  * **Critério:** `orchestrator.dispatch_points(research_id=uuid)` cria tasks assíncronas.

- ⬜ **T012**: Implementar mecanismo de *Optimistic Locking* no repositório de evidências.
  * **Critério:** Conflito de escrita sob `version` causa retry, não overwrite.

- ⬜ **T013**: Criar lógica de *loop de auditoria*.
  * **Critério:** `Scheduler` dispara `Auditor.check_point` apenas quando 4 workers concluem.

- ⬜ **T014**: Implementar subfluxo unificado `search_read_clean(query)` usando `httpx` (SerpAPI/Jina/Apify fallback).
  * **Critério:** Consulta de teste retorna texto limpo de 5-10 páginas.

- ⬜ **T015**: Implementar worker base `BaseWorker`.
  * **Critério:** Classe abstrata com `async run()` e propriedade `persona_prompt`.

- ⬜ **[//]** **T016a**: Implementar worker `Historiador Contextual`.
  * **Critério:** Worker responde à sua "Pergunta Interna" e persiste evidências.
  - Paralelo com: [T016b, T016c, T016d]

- ⬜ **[//]** **T016b**: Implementar worker `Cético Analítico`.

- ⬜ **[//]** **T016c**: Implementar worker `Pragmático Aplicado`.

- ⬜ **[//]** **T016d**: Implementar worker `Visionário Futurista`.

- ⬜ **T017**: Criar pool de workers `WorkerPool` que executa tudo em paralelo.
  * **Critério:** `pool.run_all_points(points)` usa `asyncio.gather` e captura exceções.

- ⬜ **T018**: Implementar worker de *Briefing & Scout* (mockado).
  * **Critério:** Gera rascunho de 5 pontos e persiste em `Research.briefing_draft`.

- ⬜ **T019**: Implementar `Auditor.check_point()` (fact-check, contradições, outline).
  * **Critério:** Auditor retorna JSON `{approved: bool, outline: [], rationale: str}`.

- ⬜ **T020**: Implementar lógica do loop de retenção (`max_attempts = 3`) com *blocker*.
  * **Critério:** Após 3 falhas, o status do ponto muda para `BLOCKED` e avança para o redator com notas.

- ⬜ **T021**: Implementar `Redator.compile_report()` + envio de callback HTTP POST.
  * **Critério:** Relatório é salvo no DB e POST é feito para `callback_url` registrada.
