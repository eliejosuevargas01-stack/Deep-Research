# Regression Watch — Feature 002 Investigação Paralela por Personas

- **Feature:** `002-investigacao-personas`
- **Data de Fechamento:** 2026-10-14
- **Base de comparação:** `HEAD` `8bfd529`
- **Status:** Todas as 10 falhas herdadas e 8 itens de vigilância foram verificados e aprovados.

## 1. Itens de Vigilância Ativos

| ID | Origem (arquivo, seção) | Regra esperada após mudança | Tipo de verificação | Status |
|---|---|---|---|---|
| W001 | `docs/api/briefing-scout.md`; `app/briefing/router.py` | `POST /briefings/{research_id}/reopen` em briefing aprovado retorna 409 sem mutar estado | pytest: `tests/test_briefing_api.py::BriefingAPI::test_read_edit_approve_reopen_approved_and_versions` | 🟢 APROVADO |
| W002 | `app/services/pipeline/writer.py`; `app/services/research.py` | Estados finais canônicos `DONE` e `FAILED`; `run_research` aceita `SCRAPER` | pytest: `tests/test_backend.py` (testes de pipeline e status) | 🟢 APROVADO |
| W003 | `app/investigation/storage.py`; `app/investigation/service.py` | Retomada despacha apenas pares (ponto, persona) pendentes sem duplicar `research_step_results` | pytest: `tests/investigation/test_investigation_runtime_regressions.py::test_resume_dispatches_only_missing_worker_results` | 🟢 APROVADO |
| W004 | `alembic/versions/0007_investigation_step_results_and_status.py` | Migração bidirecional reversível; colunas de título migradas para `Text` | pytest: `tests/investigation/test_investigation_migration.py::InvestigationMigrationTests::test_0006_to_0007_backfill_and_downgrade` | 🟢 APROVADO |
| W005 | `tests/test_briefing_api.py`, `tests/test_briefing_acceptance.py` | Suíte completa de briefing (20 arquivos, 184 testes) roda com 100% de aprovação | pytest: `tests/test_briefing*` (184 passed, 509 subtests passed) | 🟢 APROVADO |
| W006 | `app/investigation/service.py` (`run_investigation`) | Fan-out concorrente $N \times 4$ personas via `asyncio.gather`; isolamento de falhas | pytest: `tests/investigation/test_investigation_e2e.py` | 🟢 APROVADO |
| W007 | `app/investigation/worker.py` (`_sanitize_error`) | Segredos e chaves de API mascarados em erros (teto 500 chars); sucesso não truncado | pytest: `tests/investigation/test_persona_worker.py` | 🟢 APROVADO |
| W008 | `app/investigation/service.py`; `app/investigation/worker.py` | Despacho estrito de credenciais por modelo/provedor sem vazamento cruzado | pytest: `tests/investigation/test_persona_credential_dispatch.py` | 🟢 APROVADO |

## 2. Resolução das Falhas Herdadas do Baseline 8bfd529

Todas as 10 falhas históricas comprovadas no baseline foram sanadas:

| Grupo | Testes | Causa Raiz Identificada | Ação Corretiva Aplicada |
|---|---|---|---|
| **A (5)** | `test_base_url_ssrf_validation`<br>`test_a03_creation_payload_strict...`<br>`test_a2_scout_distinct_domains...`<br>`test_llm_complete_fallback_to_9router...`<br>`test_full_pipeline_with_controlled...` | 1. SSRF bypass apagado em commit anterior<br>2. ID string vs UUID em consulta SQLAlchemy<br>3. Mocks ausentes de runtime_jina_*<br>4. DNS não resolvido para 9router.internal<br>5. Disparo automático removido por Q1/D-12 | 1. Guard SSRF restaurado em `settings.py`<br>2. `uuid.UUID(rid)` na fixture<br>3. Mocks fornecidos para jina URL e proxy<br>4. Resolução simulada via `socket.getaddrinfo`<br>5. Disparo explícito via `client.portal.call` (T028, T034) |
| **B (4)** | `test_full_pipeline_e2e_integration`<br>`test_scout_worker`<br>`test_persona_workers`<br>`test_writer_agent` | Decorador `@pytest.mark.asyncio` sem o plugin pytest-asyncio instalado | Compatibilizados com AnyIO via fixture local `anyio_backend` e `@pytest.mark.anyio` (T029) |
| **C (1)** | `test_criteria_full_flow` | Resolução de DNS externa para `custom-openai.internal` durante catalogação dinâmica | Descoberta de modelos mockada em fixtures locais sem dependência de rede (T035) |

## 3. Deliberações do Operador Integradas

- **Q1/D-12**: Aprovação do briefing não agenda `run_research` em background; disparo de investigação é exclusivamente via `POST /briefings/{research_id}/investigate` ou explícito no teste legado.
- **Q11**: Títulos do Scout e de passos analíticos utilizam `sa.Text` ilimitado (migração 0007).
- **Q12**: Falhas de orquestração do Scout discriminam HTTP 500, 502 e 503.
- **Q13**: Tema da pesquisa mantém validação estrita entre 3 e 300 caracteres, com erro HTTP 422 descritivo.
