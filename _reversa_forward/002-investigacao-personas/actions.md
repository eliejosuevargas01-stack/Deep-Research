# Actions: Investigação Paralela por Personas (Workers)

> Identificador: `002-investigacao-personas`
> Data: `2026-10-13` (revisão reconciliada pós-esclarecimentos Q1–Q10)
> Roadmap: `_reversa_forward/002-investigacao-personas/roadmap.md`
> Escopo: Backend exclusivo (adaptação do frontend web deliberada para feature/sprint posterior)

## Resumo

| Métrica | Valor |
|---------|-------|
| Total de ações | 35 |
| Paralelizáveis (`[//]`) | 4 |
| Maior cadeia de dependência | 12 ações (11 arestas): T001, T002, T014, T015, T016, T023, T028, T035, T019, T021, T025, T030 |

---

## Fase 1, Preparação

<!-- Setup, scaffolding, migrações iniciais, configuração e schemas -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T001 | Criar migração Alembic `0007_investigation_step_results_and_status.py`: tabela `research_step_results`, atualização de `Research.status`, novos status em `research_points` (removendo `SEARCH_SUCCESS`) e backfill de briefings legados órfãos | - | - | `alembic/versions/0007_investigation_step_results_and_status.py` | 🟢 | `[X]` |
| T002 | Atualizar modelos de domínio SQLAlchemy: mapear entidade `ResearchStepResult`, atualizar enum `ResearchStatus` para o conjunto unificado (`PENDING`, `BRIEFING`, `PENDING_APPROVAL`, `SCRAPER`, `AUDIT`, `WRITE`, `DONE`, `FAILED`) e status em `ResearchPoint` | T001 | - | `app/models/domain_models.py` | 🟢 | `[X]` |
| T003 | Criar schemas Pydantic da investigação: request/response de `/investigate`, schemas da tool Jina e modelo de resultado da persona (`result`, `used_urls`) | - | `[//]` | `app/investigation/schemas.py` | 🟢 | `[X]` |
| T004 | Estruturar prompts e mapeamento de personas: carregar prompts de `app/prompts/personas.json`, incluir instrução de JSON final com citação factual e definir resolução de modelo por persona (`app_settings.models.<persona>`) com fallback para o modelo do `scout` | - | `[//]` | `app/investigation/prompts.py` | 🟢 | `[X]` |

---

## Fase 2, Testes

<!-- Testes unitários e fixtures que balizam a implementação das ferramentas e workers -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T005 | Criar fixtures de teste e mocks isolados para Jina Search (POST direto e proxy) e LiteLLM function calling | T003 | - | `tests/investigation/conftest.py` | 🟢 | `[X]` |
| T006 | Criar testes unitários para o adaptador de busca Jina: validar POST `https://s.jina.ai/` e proxy, payload `{"q": query}`, headers `Accept`/`X-Engine`, timeout de 90s, retries com `Retry-After`/backoff 2s/4s e extração integral de URLs retornadas | T005 | - | `tests/investigation/test_jina_tool.py` | 🟢 | `[X]` |
| T007 | Criar testes unitários para o loop da persona: validar parada antecipada voluntária, teto estrito de 3 queries, retries de API, até 3 correções de JSON e timeout global de 600s | T004, T005 | - | `tests/investigation/test_persona_worker.py` | 🟢 | `[X]` |

---

## Fase 3, Núcleo

<!-- Lógica central da ferramenta Jina, execução do worker e orquestração de fan-out -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T008 | Implementar `JinaToolAdapter`: transporte HTTP POST (`s.jina.ai` e proxy configurado), header `X-Engine: direct`, timeout 90s, retries técnicos com backoff/`Retry-After` e captura de todas as URLs retornadas pela Jina em `read_urls` | T002, T003 | - | `app/investigation/tools.py` | 🟢 | `[X]` |
| T009 | Implementar binding do LiteLLM para investigação: chamada assíncrona (`litellm.acompletion`) com histórico em memória RAM exclusivamente, sem semáforo | T003 | - | `app/investigation/llm_binding.py` | 🟢 | `[X]` |
| T010 | Implementar `PersonaWorker`: receber `(research_id, step_id, step_title, persona)`, resolver modelo com fallback no scout, loop de tool calling Jina (teto 3 buscas), parada voluntária, até 3 correções de JSON, timeout de 600s e geração de `result` + `used_urls` | T004, T008, T009 | - | `app/investigation/worker.py` | 🟢 | `[X]` |
| T011 | Implementar persistência de resultados e atualização de passos: inserção atômica append-only em `research_step_results`, incremento de `attempt_count` em falha com erro sanitizado (máx 500 chars) e transição de status do passo | T002, T010 | - | `app/investigation/storage.py` | 🟢 | `[X]` |
| T012 | Implementar `InvestigationService`: fan-out concorrente via `asyncio.gather` irrestrito (N pontos x 4 personas), resiliência parcial e transição final de `research.status` para `AUDIT` (ou `FAILED` se 100% dos passos falharem) | T010, T011 | - | `app/investigation/service.py` | 🟢 | `[ ]` |

---

## Fase 4, Integração

<!-- Endpoints HTTP, ganchos de ciclo de vida e alinhamento cirúrgico com a Feature 001 e legado -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T013 | Implementar `InvestigationRouter`: endpoint `POST /briefings/{research_id}/investigate` exigindo `require_admin`, validando status `SCRAPER` e pontos em `SCRAPER_PENDING`, transitando pontos para `SCRAPER_IN_PROGRESS`, retornando HTTP 202 assíncrono e validando HTTP 409 em re-disparo; cobrir pesquisa inexistente 404, admin ausente/inválido 401/403 e zero pontos 409 (D-19) | T012 | - | `app/investigation/router.py` | 🟢 | `[X]` |
| T014 | Atualizar schemas e storage de Briefing da Feature 001: emitir `research_id` no lugar de `id` em `BriefingResponse`, criar linha em `Research` antes de `Briefing` em `create_generating_briefing` e persistir pontos em `research_points` na aprovação | T002 | `[//]` | `app/briefing/schemas.py`, `app/briefing/storage.py` | 🟢 | `[X]` |
| T015 | Atualizar `BriefingRouter` e `BriefingDomain`: padronizar paths com `{research_id}`, bloquear transição de reabertura após aprovação retornando HTTP 409 em `POST /briefings/{research_id}/reopen` | T014 | - | `app/briefing/router.py`, `app/briefing/domain.py` | 🟢 | `[X]` |
| T016 | Implementar novo `PATCH /briefings/{research_id}` por feedback: schema `{"note": str}` (3..4000), Scout executando tool calling Jina com tema + rascunho anterior + feedback, salvando nova versão em `briefing_versions` e marcando `FAILED` em caso de erro | T014, T015 | - | `app/briefing/service.py`, `app/briefing/router.py`, `app/briefing/schemas.py` | 🟢 | `[X]` |
| T017 | Remover agendamento automático `schedule(run_research)` na aprovação e revisão legadas; manter pesquisa `SCRAPER` e pontos `SCRAPER_PENDING` aguardando `/investigate`, conforme Q1/D-12 | T002 | `[//]` | `app/routers/research.py`, `tests/investigation/test_investigation_runtime_regressions.py` | 🟢 | `[ ]` |
| T018 | Registrar `InvestigationRouter` em `app/main.py` e adicionar hook de inicialização do FastAPI para detecção e retomada automática de workers incompletos em pesquisas com passos em `SCRAPER_IN_PROGRESS` | T013, T017 | - | `app/main.py` | 🟢 | `[X]` |

---

## Fase 5, Polimento

<!-- Adaptação da suíte de testes legada, testes de integração E2E e validação final -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T019 | Consolidar novo contrato e 100% de aprovação da suíte completa de briefing (20 arquivos físicos, 184 testes é baseline histórico da 001) mais testes backend/E2E afetados; inventário abaixo. Não reduzir testes, dispensar falhas Q2 ou confundir suíte parcial de 8 arquivos com suíte total. | T014, T015, T016, T017, T023, T027, T028, T029, T034, T035 | - | `tests/test_briefing_lifecycle.py` (alvo principal), 20 arquivos de briefing enumerados abaixo, `tests/test_backend.py`, `tests/test_e2e_criteria.py` | 🟢 | `[ ]` |
| T020 | Criar teste de integração E2E da Feature 002: fluxo completo desde briefing aprovado até disparo assíncrono de 20 workers, mock Jina/LLM, persistência em `research_step_results` com status `AUDIT_PENDING` e transição da pesquisa para `AUDIT` | T013, T018 | - | `tests/investigation/test_investigation_e2e.py` | 🟢 | `[X]` |
| T021 | Atualizar documentação de API (`docs/api/briefing-scout.md` e novo `docs/api/investigation-personas.md`) refletindo o campo `research_id`, novo PATCH por feedback e o endpoint `/investigate` | T019, T020 | - | `docs/api/briefing-scout.md`, `docs/api/investigation-personas.md` | 🟢 | `[X]` |

---

## Correções verificadas pós-entrega

Auditorias de planejamento anteriores existem; nova revisão documental aguarda audit/quality independentes. Auditoria de implementação e QA final ainda não aprovados. Checkboxes reabertos representam critérios sem evidência completa; trabalho entregue permanece preservado. Detalhes e snapshot em `progress.jsonl`.

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T022 | Corrigir integração de T009/T012/T013/T018: resolver chave/base URL por modelo, limitar tentativas externas, retomar somente pares sem resultado, reservar disparo atomicamente e preservar espera humana no startup; testes mantidos do caminho real | T002, T003, T008, T010, T011 | - | `app/investigation/service.py`, `app/investigation/router.py`, `app/main.py`, `tests/investigation/test_investigation_runtime_regressions.py` | 🟢 | `[ ]` |
| T023 | Alinhar valores canônicos de `ResearchStatus` nos caminhos legados de pesquisa, writer e callback, preservando contratos não substituídos. Q2 é gate obrigatório nas ações T028/T029/T034/T035, sem dispensa por baseline. | T002, T015, T016 | - | `app/services/research.py`, `app/services/pipeline/writer.py`, `app/services/webhook.py` | 🟢 | `[ ]` |
| T024 | Corrigir T001: migrar SEARCH_SUCCESS para AUDIT_PENDING e tornar backfill Boolean portável; validar 0006 para 0007 com dados existentes em banco isolado, sem modificar bases existentes | T002 | - | `alembic/versions/0007_investigation_step_results_and_status.py`, `tests/investigation/test_investigation_migration.py` | 🟢 | `[X]` |
| T025 | Reconciliar documentação de API com contrato final aprovado e correções de coding: sem prefixos/domínios inventados, reopen 409, identificador research_id, PATCH note e append-only sem unicidade artificial. Rastros de coding ficam em T030. | T021, T027, T031, T032, T033 | - | `docs/api/briefing-scout.md`, `docs/api/investigation-personas.md` | 🟢 | `[ ]` |
| T026 | Corrigir resolução de credenciais multi-provedor por persona em `app/investigation/service.py`: resolver api_base e api_key individualmente por persona com base no modelo configurado em `settings.models.<persona>` (fallback scout), repassando para PersonaWorker executar cada persona com sua credencial correspondente | T022 | - | `app/investigation/service.py`, `app/investigation/worker.py`, `tests/investigation/test_investigation_runtime_regressions.py`, `tests/investigation/test_persona_credential_dispatch.py` | 🟢 | `[X]` |

| T027 | Adequar schemas e contratos de Briefing a Q11–Q13: validar tema 3–300 com HTTP 422 e erro explícito (Q13); remover teto de 500 dos títulos gerados pelo Scout em schemas e migrar colunas de título (`research_points.title`, `research_step_results.step_title`) para `sa.Text` (Q11, D-13); e discriminar HTTP 500/502/503 na falha do Scout no PATCH (Q12, D-20). | T014, T016 | - | `app/briefing/schemas.py`, `app/briefing/domain.py`, `alembic/versions/0007_investigation_step_results_and_status.py`, `tests/test_briefing_schemas.py` | 🟢 | `[X]` |
| T028 | Corrigir três regressões de fronteira HTTP/DNS: base_url_ssrf_validation, a03_creation_payload_strict_and_backend_callback e a2_scout_distinct_domains_and_timeout, após reprodução isolada contra baseline; preservar guard SSRF e usar rede simulada nas fixtures (Q2/D-14). | T023 | - | `tests/test_backend.py`, `app/tools/outbound.py`, `app/services/settings.py` | 🟢 | `[ ]` |
| T029 | Adequar execução dos quatro testes async de integração/workers ao runner async já instalado (AnyIO), preservando assertions e contratos. Reproduzir node IDs no inventário; não adicionar plugin se marcador/fixture existente resolver (Q2/D-14). | T017, T023 | - | `tests/integration/test_full_pipeline.py`, `tests/unit/workers/test_workers_and_auditor.py` | 🟢 | `[ ]` |
| T030 | Completar legacy-impact.md e regression-watch.md conforme âncora greenfield real; registrar somente símbolos/testes/causas comprovados e corrigir atribuições históricas sem inventar aprovação (T025 original). | T025 | - | `_reversa_forward/002-investigacao-personas/legacy-impact.md`, `_reversa_forward/002-investigacao-personas/regression-watch.md` | 🟢 | `[ ]` |
| T031 | Provar exaustão inicial + 3 correções JSON no caminho worker até persistência: FAILED, result literal Invalid JSON response after 3 corrections, used_urls=[] e incremento único do contador; corrigir apenas desvio demonstrado (Q7/D-15). | T010, T011, T012 | - | `app/investigation/worker.py`, `app/investigation/storage.py`, `tests/investigation/test_persona_worker.py` | 🟢 | `[ ]` |
| T032 | Provar attempt_count inicial 0, incremento atômico +1 por falha definitiva e retomada sem repetir persona persistida/incremento; consolidar estado do ponto no término das suas personas, conforme máquina de estados, corrigindo somente desvios (Q8/D-16/D-11). | T011, T022, T026 | - | `app/investigation/storage.py`, `app/investigation/service.py`, `tests/investigation/test_investigation_runtime_regressions.py` | 🟢 | `[ ]` |
| T033 | Provar isolamento RAM dos prompts/CoT e ausência de canários sintéticos em banco/log/API no fluxo real; result contém análise final ou erro sanitizado até500, sem truncar análise de sucesso. Corrigir sanitização somente se desvio for demonstrado (Q9/D-17). | T004, T009, T012 | - | `app/investigation/prompts.py`, `app/investigation/worker.py`, `tests/investigation/test_persona_credential_dispatch.py` | 🟢 | `[ ]` |
| T034 | Corrigir dois casos legados de LLM/pipeline controlado: full_pipeline_with_controlled_sources_and_models e llm_complete_fallback_to_9router_on_primary_rate_limit; preservar fallback e isolamento de mocks (Q2/D-14). | T023 | - | `tests/test_backend.py`, `app/services/llm.py` | 🟢 | `[ ]` |
| T035 | Corrigir test_criteria_full_flow sensível à ordem/DNS, mantendo verificações de contrato e restaurando configurações/overrides; demonstrar execução isolada e integrada sem DNS externo nas fixtures (Q2/D-14). | T028, T029, T034 | - | `tests/test_e2e_criteria.py`, `tests/test_backend.py` | 🟢 | `[ ]` |

---

## Notas de execução

- Nenhuma alteração amplia escopo para a Feature 003 (Auditoria) ou Feature 004 (Redação/Relatório final).
- Frontend web permanece intocado nesta feature; adequação de telas legadas fica para a sprint do frontend.
- Alvo de verificação: testes isolados sem rede externa. Nem todos os testes existentes possuem esse isolamento comprovado; falhas Q2 continuam bloqueantes. Não executar DDL contra bancos com dados existentes.

---

## Inventário e gates de T019/Q2

184 testes é evidência histórica da 001, não contagem atual executada. T019 cobre os 20 arquivos físicos seguintes, além de `tests/test_backend.py` e `tests/test_e2e_criteria.py`:

- `tests/test_briefing_acceptance.py`
- `tests/test_briefing_api.py`
- `tests/test_briefing_domain.py`
- `tests/test_briefing_generation.py`
- `tests/test_briefing_generation_boundaries_qa.py`
- `tests/test_briefing_generation_concurrency_qa.py`
- `tests/test_briefing_generation_flow_qa.py`
- `tests/test_briefing_lifecycle.py`
- `tests/test_briefing_lifecycle_qa.py`
- `tests/test_briefing_llm_binding.py`
- `tests/test_briefing_migration.py`
- `tests/test_briefing_persisted_orchestration.py`
- `tests/test_briefing_persisted_orchestration_qa.py`
- `tests/test_briefing_prompt_loader.py`
- `tests/test_briefing_schemas.py`
- `tests/test_briefing_serp_client.py`
- `tests/test_briefing_storage.py`
- `tests/test_briefing_storage_converters.py`
- `tests/test_briefing_storage_qa.py`
- `tests/test_briefing_validation.py`

Falhas conhecidas a reproduzir antes da correção: cinco node IDs de `tests/test_backend.py` distribuídos em T028/T034; `tests/integration/test_full_pipeline.py::test_full_pipeline_e2e_integration` e `tests/unit/workers/test_workers_and_auditor.py::{test_scout_worker,test_persona_workers,test_writer_agent}` em T029; `tests/test_e2e_criteria.py::test_criteria_full_flow` em T035. Notação de chaves nessa lista agrupa nomes, não é comando pytest.

Comandos de aceite previstos, NÃO executados nesta rodada: `python3 -B -m pytest tests/investigation -q -p no:cacheprovider`; suíte completa `python3 -B -m pytest tests -q -p no:cacheprovider`, apenas com DB descartável confirmado e fixtures sem credenciais/rede reais. Capturar contagens, warnings, skips e exit codes. Parar antes de testes destrutivos caso isolamento não esteja comprovado.

## Rastreabilidade do plano vigente

| Fonte | Decisões | Ações |
|---|---|---|
| RF-01/RF-02 | D-01 | T014 |
| RF-03 | D-10/D-19 | T013, T022 |
| RF-04 | D-02/D-04 | T012 |
| RF-05 | D-05/D-07 | T009, T010 |
| RF-06/RF-07 | D-06 | T006, T008 |
| RF-08 | D-08/D-09/D-15 | T007, T008, T009, T010, T022, T031 |
| RF-09 | D-03/D-16/D-17 | T011, T031, T032, T033 |
| RF-10 | D-04 | T012, T020 |
| RF-11 | D-01/D-03 | T001, T002, T024 |
| RF-12 | D-01/D-12/D-13/D-20 | T014, T015, T016, T017, T027 |
| RF-13 | D-11 | T018, T022, T032 |
| Q1/Q2 | D-12/D-14 | T017, T019, T023, T028, T029, T034, T035 |
| Q11/Q13 | D-13 | T027 |
| Q12 | D-20 | T016, T019, T027 |
| Q7/Q8/Q9 | D-15/D-16/D-17 | T031, T032, T033 |
| RN-10 | D-18 | T004, T026 |

Os 23 cenários Gherkin são atendidos pelas decisões/ações acima: disparo/conflito/404/admin/zero pontos (T013/T022); criação prévia/tema (T014/T027); aprovação/títulos longos (T014/T027); parada/teto/retry/URLs/proxy (T006–T010); falha individual/global e sucesso parcial (T011/T012/T020/T031/T032); migração/backfill (T001/T024); reopen (T015); PATCH/sua falha discriminada 500/502/503 (T016/T027); retomada (T018/T022/T032); JSON esgotado (T031). Os cenários não provam execução por si só.

## Sprints futuras de coding

| Sprint | Recorte | IDs |
|---|---|---|
| C1 | Contrato briefing, tema 3–300 e títulos sa.Text | T014, T027 |
| C2 | Disparo exclusivo legado e estados | T017, T023 |
| C3 | Orquestração e conclusão/resume | T012, T022, T032 |
| C4 | Falha JSON e privacidade | T031, T033 |
| C5 | Regressões de fronteira/LLM | T028, T034 |
| C6 | Runner async e isolamento E2E | T029, T035 |
| C7 | Consolidação e documentação | T019, T025, T030 |

`[//]` significa independência por fase, não execução simultânea entre fases dependentes. Mesmo sem marcador, arquivos que aparecem em duas sprints têm proprietário sequencial. Não executar auditoria/QA sobre diff enquanto alguém o altera. Preservar T001–T026 e seus históricos; T014 reaberta porque alias público `id` ainda existe no código, não por execução de testes nesta rodada. T027–T035 iniciam abertos. Sem fechamento em massa.

## Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-10-12 | Versão inicial gerada por `/reversa-to-do` | reversa |
| 2026-10-12 | Revisão pós-auditoria: correção da cadeia crítica para 9 passos, inclusão de schemas/storage de briefing, isolamento de arquivos alvos e detalhamento dos 184 testes | reversa |

| 2026-10-13 | Reconciliados Q1–Q10, inventário20, escopo e gates; T027–T035 novos; T014 reaberta por alias id; preservado restante do trabalho entregue | Orchestrator — fallback documental autorizado |
