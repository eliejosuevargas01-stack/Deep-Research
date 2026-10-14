# Legacy Impact — Feature 002: Investigação Paralela por Personas

- **Feature:** `002-investigacao-personas`
- **Data de Fechamento:** 2026-10-14
- **Política de Edição do Legado:** `allowLegacyEdits: true`, `allowedPaths: ["*"]`
- **Status Geral:** Concluído e verificado

## 1. Mapeamento de Arquivos Afetados

| Arquivo afetado | Componente | Tipo | Severidade | Justificativa |
|---|---|---|---|---|
| `app/models/domain_models.py` | Modelo de Dados | `regra-alterada` | HIGH | `ResearchStatus` alinhado (SCRAPER, BRIEFING, PENDING_APPROVAL, DONE, FAILED); entidade `ResearchStepResult` criada; colunas `title` e `step_title` em `sa.Text` |
| `alembic/versions/0007_investigation_step_results_and_status.py` | Migrações | `componente-novo` | HIGH | Tabela `research_step_results`, índices, migração reversível de títulos para Text |
| `app/routers/research.py` | Routers Legados | `regra-alterada` | HIGH | Q1/D-12: removido `schedule(run_research)` de `approve` e `run_revision`; transições de status alinhadas ao Enum |
| `app/services/research.py` | Serviços de Pesquisa | `regra-alterada` | HIGH | `run_research` adaptado para status `SCRAPER`; manipulação de `ResearchStatus` canônico |
| `app/services/pipeline/writer.py` | Pipeline Legado | `regra-alterada` | MEDIUM | Estados `DONE`/`FAILED` canônicos; integridade de citações |
| `app/services/webhook.py` | Webhooks | `regra-alterada` | MEDIUM | Normalização de status em dispatch e callbacks |
| `app/services/settings.py` | Configurações & Segurança | `regra-alterada` | HIGH | Guard SSRF restaurado para rejeição de hosts internos (`.internal`, `.local`, `.lan`) sem DNS ou fora de `TRUSTED_ROUTER_HOSTS` |
| `app/briefing/schemas.py` | Schemas de Briefing | `regra-alterada` | MEDIUM | Q11/Q13: tema restrito a 3–300 chars; `BriefingResponse` e `ApprovedBriefingResponse` usam exclusivamente `research_id: UUID` (sem alias `id`) |
| `app/briefing/router.py` | Router de Briefing | `regra-alterada` | HIGH | Reopen retorna 409 em briefing aprovado; `PATCH /briefings/{research_id}` com `note` via Scout |
| `app/briefing/service.py` | Serviço de Briefing | `regra-alterada` | HIGH | CAS atômico e incremento de versão; bloqueio estrito de reopen em aprovado (409) |
| `app/investigation/` | Investigação por Personas | `componente-novo` | HIGH | Módulos `router.py`, `service.py`, `storage.py`, `worker.py`, `prompts.py`: fan-out paralelo irrestrito de 4 personas por ponto, persistência atômica e sanitização de erro em 500 chars |
| `tests/test_backend.py` | Suíte de Testes | `regra-alterada` | MEDIUM | Correção de 5 regressões de fronteira (T028, T034) e alinhamento de lifespan à Q1/D-12 (T035) |
| `tests/test_e2e_criteria.py` | Suíte de Testes | `regra-alterada` | MEDIUM | Isolamento de mock de DNS e catálogo de modelos dinâmico sem rede externa (T035) |
| `tests/integration/test_full_pipeline.py` | Testes de Integração | `regra-alterada` | MEDIUM | Compatibilização AnyIO com `@pytest.mark.anyio` e disparo explícito de pipeline (T029) |
| `tests/unit/workers/test_workers_and_auditor.py` | Testes Unitários | `regra-alterada` | MEDIUM | Compatibilização AnyIO com fixture local `anyio_backend` (T029) |

## 2. Riscos e Resoluções

| Risco Anterior | Resolução Comprovada | Evidência |
|---|---|---|
| Aprovação legada com agendamento automático concorrente | Removido `schedule()` em `app/routers/research.py:101,311` (Sprint C2 - T017) | `test_investigation_runtime_regressions.py` e testes de lifespan verdes |
| Falhas herdadas do baseline (Grupos A, B, C) | Todas as 10 falhas corrigidas e comprovadas em T028, T029, T034 e T035 | `pytest` com 59 passed em backend/e2e e 5 passed em integration/unit |
| Vazamento de prompts ou CoT | Isolamento em RAM e asserções comprovando ausência de canários em banco | `test_persona_credential_dispatch.py` e `test_persona_worker.py` (T033) |
| Truncamento de resposta válida por sanitizador | Sanitizador restrito a exceções de erro (<=500 chars); sucesso analítico preservado | `test_worker_success_result_not_truncated` (T033) |
| Concorrência de escrita de step_results | Tabela `research_step_results` opera em modo append-only com índice único e retry | 231 passed em `tests/investigation` e `tests/test_briefing*` |
