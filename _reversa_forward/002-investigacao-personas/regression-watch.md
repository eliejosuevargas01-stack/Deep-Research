# Regression Watch — Feature 002 Investigação Paralela por Personas

- Feature: `002-investigacao-personas`
- Data: 2026-10-13
- Base de comparação: `HEAD` `8bfd529`
- Regra: cada item abaixo tem verificação automatizada. Nenhum caminho foi inferido: todos foram conferidos com `grep` no repositório em 2026-10-13.

## Itens de Vigilância

| ID | Origem (arquivo, seção) | Regra esperada após mudança | Tipo de verificação | Sinal de violação |
|----|-------------------------|-----------------------------|---------------------|-------------------|
| W001 | `docs/api/briefing-scout.md` (reopen); `app/briefing/router.py` (`reopen_briefing_route`) | `POST /briefings/{research_id}/reopen` em briefing aprovado retorna 409 sem mutar estado nem versão | pytest: `tests/test_briefing_api.py::BriefingAPI::test_read_edit_approve_reopen_approved_and_versions`; `tests/test_briefing_domain.py::test_approved_cannot_reopen` | Reopen retorna 200 ou altera `status`/versão de briefing aprovado |
| W002 | `app/services/pipeline/writer.py`; `app/services/research.py` (`run_research`) | Estados finais canônicos `DONE` e `FAILED`; `run_research` aceita `SCRAPER` (além de `approved`, `in_progress`, `interrupted`); testes legados de pontos seguem com `approved` e `in_progress` | pytest: `tests/test_backend.py` (testes de pipeline e sanitização) | Pesquisa termina em `completed`/`blocked` ou `run_research` rejeita pesquisa em `SCRAPER` |
| W003 | `app/investigation/storage.py` (`get_pending_workers_for_research`); `app/investigation/service.py` (`run_investigation`) | Retomada despacha só pares (ponto, persona) sem linha em `research_step_results` | pytest: `tests/investigation/test_investigation_runtime_regressions.py::test_resume_dispatches_only_missing_worker_results` | Retomada reexecuta par já concluído ou duplica linha em `research_step_results` |
| W004 | `alembic/versions/0007_investigation_step_results_and_status.py` | Migração mapeia `SEARCH_SUCCESS` para `AUDIT_PENDING`; backfill booleano portável com `sa.true()`; upgrade e downgrade reversíveis | pytest: `tests/investigation/test_investigation_migration.py::test_0006_to_0007_backfill_and_downgrade` | Upgrade falha em SQLite ou Postgres, ou downgrade perde o mapeamento de status |
| W005 | `tests/test_briefing_api.py`, `tests/test_briefing_acceptance.py` (`setUp`/`addCleanup`) | `API_AUTH_SECRET` isolado e restaurado; suítes `tests/investigation` e `tests/test_briefing_*.py` passam em qualquer ordem | pytest: ambas as suítes nas duas ordens de execução | Falhas 401 que dependem da ordem de execução |
| W006 | `app/investigation/service.py` (`run_investigation`) | N pontos × 4 personas despachados com `asyncio.gather`; falha de um worker não derruba os demais | pytest: `tests/investigation/test_investigation_e2e.py::test_investigation_e2e_full_flow`, `::test_investigation_e2e_partial_resilience`, `::test_investigation_e2e_total_failure` | Exceção de um worker cancela os demais ou linhas de resultado faltam |
| W007 | `app/investigation/worker.py` (`_sanitize_error`) | Chaves de API e tokens Bearer mascarados em qualquer erro gravado ou retornado | pytest: `tests/investigation/test_persona_worker.py::test_worker_error_sanitization_masks_bearer_and_api_secrets`, `::test_sanitize_error_comprehensive` | Segredo sintético aparece em `error` ou `result` persistido |
| W008 | `app/investigation/service.py` (`_resolve_persona_credentials`); `app/investigation/worker.py` (`PersonaWorker._run`) | Chave e `base_url` resolvidas por persona via `settings.models.<persona>`, com fallback para `scout`; chave de um provedor nunca é enviada a outro | pytest: `tests/investigation/test_investigation_runtime_regressions.py::test_persona_credentials_follow_each_models_provider`. Verificação do caminho completo `InvestigationService → PersonaWorker → LLM` **pendente** (T026, `deleg_f3a87778` em andamento) | Persona `anthropic` recebe chave `openai`, ou vice-versa |

## Histórico de re-extrações

(vazio)

## Arquivadas

(vazio)

## Falhas herdadas do baseline `HEAD` `8bfd529`

Não introduzidas pela Feature 002. Comprovadas em cópia do baseline. Log da execução completa: `/root/.hermes/profiles/orchestrator/cache/scratch/feature002-full-suite-verification.log` (277 passed, 10 failed, 1 skipped).

| Grupo | Testes | Causa |
|-------|--------|-------|
| A (5) | `tests/test_backend.py::test_full_pipeline_with_controlled_sources_and_models`, `::test_llm_complete_fallback_to_9router_on_primary_rate_limit`, `::test_base_url_ssrf_validation`, `::test_a03_creation_payload_strict_and_backend_callback`, `::test_a2_scout_distinct_domains_and_timeout` | Não classificada individualmente; ver log acima |
| B (4) | `tests/integration/test_full_pipeline.py::test_full_pipeline_e2e_integration`; `tests/unit/workers/test_workers_and_auditor.py::test_scout_worker`, `::test_persona_workers`, `::test_writer_agent` | Plugin `pytest-asyncio` ausente no ambiente: `async def functions are not natively supported` |
| C (1) | `tests/test_e2e_criteria.py::test_criteria_full_flow` | Passa isolado; falha na suíte combinada ao resolver DNS de `custom-openai.internal` |

## Decisões pendentes do usuário

1. **Aprovação legada:** `app/routers/research.py` ainda chama `schedule(research_id)` após gravar `SCRAPER`, concorrendo com `POST /briefings/{research_id}/investigate`. Sem decisão registrada; código não alterado.
2. **Falhas herdadas:** tratar ou dispensar os grupos A, B e C. Sem decisão registrada; nenhuma falha foi dispensada.
