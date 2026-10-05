# Legacy Impact — T010: Orchestrator Refactoring

**Feature**: Modularização backend (REQ-01..07)
**Data**: 2026-10-05
**Política de edição do legado**: `allowLegacyEdits: true` (caminhos liberados: `app/**`, `tests/**`, etc.)

## Arquivos Afetados

| Arquivo | Componente (arquitetura.md) | Tipo | Severidade | Justificativa |
|---------|----------------------------|------|-----------|---------------|
| `app/services/research.py` | Orchestrator (services) | `regra-alterada` | HIGH | 591 → 161 LOC; lógica extraída para `app/services/pipeline/*`; API pública preservada via re-export |
| `app/services/pipeline/__init__.py` | Orchestrator (services) | `componente-novo` | MEDIUM | Package dos estágios extraídos; sem re-exports de `scout` para não sombrear submódulo |
| `app/services/pipeline/constants.py` | Orchestrator (services) | `componente-novo` | LOW | `PERSONAS` compartilhado para quebrar import circular |
| `app/services/pipeline/scout.py` | Scout (services) | `regra-alterada` | HIGH | `scout()`, `_scout_impl()`, `extract_site_domain()`, `SCOUT_GLOBAL_TIMEOUT` movidos verbatim |
| `app/services/pipeline/worker.py` | Workers (services) | `regra-alterada` | HIGH | `run_worker()` (antigo `_worker`), `PERSONA_CONTRACTS`, `_quote_supported`, `_fetch_direct_urls` movidos |
| `app/services/pipeline/audit_stage.py` | Auditor (services) | `regra-alterada` | HIGH | `_audit_point()`, `sanitize_audit_dict` movidos verbatim |
| `app/services/pipeline/point_executor.py` | Orchestrator (services) | `regra-alterada` | HIGH | `_run_point()` + `remaining_attempts` movidos |
| `app/services/pipeline/writer.py` | Writer (services) | `regra-alterada` | HIGH | `_write_report()`, `validate_report_quality` movidos verbatim |
| `app/services/workers/__init__.py` | Workers (services) | `componente-novo` | MEDIUM | Factory `create_workers()` adicionada (T010) |
| `tests/test_backend.py` | Testes | `regra-alterada` | MEDIUM | Monkeypatch targets atualizados: `app.services.research.{search_read,complete}` → `app.services.pipeline.scout.{search_read,complete}` (2 linhas) |

## Diff Conceitual por Componente

**Orchestrator (`research.py`)**: era monolito de 591 LOC com 5 estágios inline. Agora é façade de 161 LOC que re-exporta a API pública (`PERSONAS`, `scout`, `run_worker`, `_audit_point`, `_run_point`, `_write_report`, `run_research`, `sanitize_error`, `point_dependencies`, `ready_point_batches`, `remaining_attempts`, `add_event`, `sanitize_audit_dict`, `_quote_supported`, `PERSONA_CONTRACTS`, `_scout_impl`, `validate_report_quality`) e mantém apenas orquestração (`run_research`) + helpers puros (`point_dependencies`, `ready_point_batches`, `sanitize_error`).

**Scout/Worker/Audit/Writer**: lógica movida verbatim — mesmos prompts, mesmos limites (MAX_WORKER_QUERIES, MAX_AUDIT_ATTEMPTS), mesmas regras A1-02/A2-01/A2-02/MA-01/MA-08. Nenhuma regra de negócio alterada.

**Compatibilidade**: `_worker = run_worker` (alias) preservado; `app.services.research.complete` não existe mais como atributo de módulo — testes que faziam monkeypatch desse símbolo foram atualizados para `app.services.pipeline.scout.complete`.

## Preservadas (regras 🟢 de domain.md intactas)

- R-01: verbatim citation contract (`_quote_supported` inalterado)
- R-02: SSRF guard em `read_source` (inalterado)
- R-03: sanitization de erros (`sanitize_error` inalterado)
- R-04: retry com feedback do auditor (`_run_point` preservado)
- R-05: recovery de `lifespan` (scouting/revising/in_progress — routers inalterados)
- R-06: idempotência de evidências (unique constraint research_point_id+persona+source_url)
- R-07: concorrência com semáforo (`WORK_LIMIT` preservado)

## Modificadas

- Nenhuma regra 🟢 removida ou alterada semanticamente. Apenas relocalização de código.

## Validação

- `python -c "from app.services.research import ..."` — todos os símbolos públicos importam
- `pytest tests/unit/ -x` — 4 passed
- `pytest tests/test_backend.py -k "not full_pipeline and not llm_complete and not settings_test and not search_falls_back"` — 10 passed (inclui test_create_scout, test_point_dependencies, test_ssrf, test_auditor_verdict)
- `wc -l app/services/research.py` = 161 (< 200 critério T010)
