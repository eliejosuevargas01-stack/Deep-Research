# Actions — Deep Research Engine Backend Modularization

> Gerado pelo ciclo Reversa Forward  
> Data: 2026-10-05  
> Formato: IDs sequenciais T001, T002... com checkboxes executáveis

---

## T001 — Preparação: Migrar SearchPipeline para app/services/search.py (REQ-01)
- [x] Criar `app/services/search.py` copiando lógica de `app/tools/search_pipeline.py`
- [x] Atualizar imports em `app/services/research.py` e `app/services/llm.py`
- [x] Manter alias em `app/tools/search_pipeline.py` (deprecated warning) por compatibilidade
- [x] Rodar `pytest tests/ -x` — deve passar sem alterações
- **Critério**: `grep -r "from app.tools.search_pipeline" app/ --include="*.py"` retorna vazio

---

## T002 — Estrutura Base: app/services/workers/ + interfaces (REQ-01)
- [x] Criar diretório `app/services/workers/` com `__init__.py`
- [x] Criar `app/services/workers/base.py` com:
  - `BaseWorker(ABC)` — construtor injeta `db, settings, llm, search, model_name, prompt_path`
  - `WorkerResult` dataclass (`point_id, persona, evidences, metrics, errors`)
  - Métodos protegidos: `_search_and_extract`, `_store_evidence`, `_log_structured`
- [x] Criar `app/services/audit_agent.py` com `AuditorAgent` e `AuditVerdict` enum
- [x] Adicionar exports em `app/services/__init__.py`
- **Critério**: `python -c "from app.services.workers.base import BaseWorker, WorkerResult; from app.services.audit_agent import AuditorAgent, AuditVerdict"`

---

## T003 — ScoutWorker: app/services/workers/scout.py (REQ-01)
- [x] Implementar `ScoutWorker(BaseWorker)` com `execute(point, context)`
- [x] Prompt template em `app/prompts/scout.md` (extrair do research.py atual)
- [x] Busca preliminar 3-5 sites distintos → gera 5 pontos com dependências
- [x] Retorna `WorkerResult` com evidências e métricas
- [x] Teste unitário: `tests/unit/workers/test_scout_worker.py` (mock LLM + Search)
- **Critério**: `pytest tests/unit/workers/test_scout_worker.py -v` passa

---

## T004 — HistorianWorker: app/services/workers/historian.py (REQ-01, REQ-03)
- [x] Implementar `HistorianWorker(BaseWorker)` — persona contextual/factual
- [x] Prompt em `app/prompts/historian.md`
- [x] Executa até 3 queries, extrai citações verbatim
- [x] Teste unitário: `tests/unit/workers/test_historian_worker.py`
- **Critério**: teste unitário passa + cobertura > 80% no módulo

---

## T005 — SkepticWorker: app/services/workers/skeptic.py (REQ-01, REQ-03)
- [x] Implementar `SkepticWorker(BaseWorker)` — persona crítico/contraditório
- [x] Prompt em `app/prompts/skeptic.md`
- [x] Teste unitário: `tests/unit/workers/test_skeptic_worker.py`
- **Critério**: teste unitário passa + cobertura > 80%

---

## T006 — PragmatistWorker: app/services/workers/pragmatist.py (REQ-01, REQ-03)
- [x] Implementar `PragmatistWorker(BaseWorker)` — persona aplicável/prático
- [x] Prompt em `app/prompts/pragmatist.md`
- [x] Teste unitário: `tests/unit/workers/test_pragmatist_worker.py`
- **Critério**: teste unitário passa + cobertura > 80%

---

## T007 — FuturistWorker: app/services/workers/futurist.py (REQ-01, REQ-03)
- [x] Implementar `FuturistWorker(BaseWorker)` — persona visionário/tendências
- [x] Prompt em `app/prompts/futurist.md`
- [x] Teste unitário: `tests/unit/workers/test_futurist_worker.py`
- **Critério**: teste unitário passa + cobertura > 80%

---

## T008 — WriterAgent: app/services/workers/writer.py (REQ-01, REQ-03)
- [x] Implementar `WriterAgent(BaseWorker)` — síntese final Markdown
- [x] Prompt em `app/prompts/writer.md`
- [x] Recebe todas evidências + audit_findings → produz relatório com citações canônicas
- [x] Teste unitário: `tests/unit/workers/test_writer_agent.py`
- **Critério**: teste unitário passa + cobertura > 80%

---

## T009 — AuditorAgent: app/services/audit_agent.py (REQ-01)
- [x] Implementar `AuditorAgent` (não herda BaseWorker — não faz busca)
- [x] Método `audit(point, evidences, context) -> AuditVerdict`
- [x] Usa `deterministic_citation_audit` de `app/services/audit.py`
- [x] Lógica de retry (até 3) + `BLOCKED` com ressalvas
- [x] Teste unitário: `tests/unit/test_audit_agent.py`
- **Critério**: teste unitário passa + cobertura > 80%

---

## T010 — Refatorar Orquestrador: app/services/research.py (REQ-02, REQ-04)
- [x] Remover lógica inline de Scout/Workers/Auditor/Writer
- [x] Importar e instanciar workers via factory (injeta dependências)
- [x] Manter API pública: `schedule, schedule_scout, schedule_revision, run_point, run_scout`
- [x] Preservar `lifespan` recovery (scouting, revising, in_progress)
- [x] Meta: research.py < 200 LOC após refactoring
- **Critério**: `wc -l app/services/research.py` < 200 (161 LOC)

---

## T011 — Testes de Integração E2E (REQ-04)
- [x] Criar `tests/integration/test_full_pipeline.py`
- [x] Cenário: POST /api/research → SSE stream → briefing approve → workers → audit → report → webhook
- [x] Mock externo: LLM + Search + Webhook
- [x] Assert: status final = completed, report existe, events SSE emitidos
- **Critério**: `pytest tests/integration/test_full_pipeline.py -v` passa (1 passed em 6.56s)

---

## T012 — CI/CD GitHub Actions + Cobertura (REQ-05, REQ-06)
- [x] Criar `.github/workflows/ci.yml`
- [x] Jobs: lint (ruff), type-check (mypy --strict), unit tests, integration tests, coverage
- [x] Fail se cobertura < 80% (`--cov-fail-under=80`)
- [x] Build docker image multi-stage
- **Critério**: Push para branch roda CI e fica verde

---

## T013 — Smoke Test Local + Documentação (REQ-07)
- [x] `docker compose up -d` sobe Postgres + Backend + Frontend
- [x] Verificar Swagger em http://localhost:8000/docs
- [x] Verificar health em http://localhost:8000/health
- [x] Testar fluxo manual: criar pesquisa → aprovar briefing → aguardar relatório
- [x] Atualizar `README.md` se necessário
- **Critério**: Teste manual completo sem erros no log (backend 200 OK /health, frontend 200 OK)

---

## Checklist de Validação Final (Definition of Done)

| ID | Verificação | Comando |
|:---|:---|:---|
| ✅ | Workers + agents extraídos | `ls app/services/workers/ app/services/audit_agent.py` |
| ✅ | Orquestrador fino (< 200 LOC) | `wc -l app/services/research.py` |
| ✅ | Testes unitários | `pytest tests/unit/ -x --tb=short` |
| ✅ | Teste E2E | `pytest tests/integration/test_full_pipeline.py -x` |
| ✅ | Cobertura >= 80% | `pytest --cov=app --cov-fail-under=80` |
| ✅ | CI/CD verde | GitHub Actions run success |
| ✅ | Docker compose up | `docker-compose up -d && curl -f localhost:8000/health` |
| ✅ | Zero breaking API | `pytest tests/ -k "api" -x` |

---

## Ordem de Execução Recomendada

```
T001 → T002 → (T003|T004|T005|T006|T007|T008|T009 em paralelo) → T010 → T011 → T012 → T013
```

Workers 3-9 podem ser desenvolvidos em paralelo (independentes). T010 depende de todos workers prontos. T011 depende de T010. T012/T013 são finais.

---

## Notas para Implementação

1. **Injeção de dependência**: Use factory function `create_workers(settings, llm, search)` em `app/services/workers/__init__.py`
2. **Settings por persona**: `model_name` vem de `settings.models[persona]` injetado no construtor
3. **Prompts**: Carregados via `Path(__file__).parent.parent / "prompts" / f"{persona}.md"`
4. **Logging**: Use `structlog` ou `logging` com `extra={"research_id": ..., "point_id": ..., "persona": ...}`
5. **Async**: Todos workers são `async def execute(...)` — usar `asyncio.gather` com semáforo no orquestrador