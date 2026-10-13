# Actions: Investigação Paralela por Personas (Workers)

> Identificador: `002-investigacao-personas`  
> Data: `2026-10-12` (revisão pós-auditoria)  
> Roadmap: `_reversa_forward/002-investigacao-personas/roadmap.md`  
> Escopo: Backend exclusivo (adaptação do frontend web deliberada para feature/sprint posterior)

## Resumo

| Métrica | Valor |
|---------|-------|
| Total de ações | 21 |
| Paralelizáveis (`[//]`) | 8 |
| Maior cadeia de dependência | 9 (T001 -> T002 -> T008 -> T010 -> T011 -> T012 -> T013 -> T018 -> T020) |

---

## Fase 1, Preparação

<!-- Setup, scaffolding, migrações iniciais, configuração e schemas -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T001 | Criar migração Alembic `0007_investigation_step_results_and_status.py`: tabela `research_step_results`, atualização de `Research.status`, novos status em `research_points` (removendo `SEARCH_SUCCESS`) e backfill de briefings legados órfãos | - | - | `alembic/versions/0007_investigation_step_results_and_status.py` | 🟢 | `[ ]` |
| T002 | Atualizar modelos de domínio SQLAlchemy: mapear entidade `ResearchStepResult`, atualizar enum `ResearchStatus` para o conjunto unificado (`PENDING`, `BRIEFING`, `PENDING_APPROVAL`, `SCRAPER`, `AUDIT`, `WRITE`, `DONE`, `FAILED`) e status em `ResearchPoint` | T001 | - | `app/models/domain_models.py` | 🟢 | `[ ]` |
| T003 | Criar schemas Pydantic da investigação: request/response de `/investigate`, schemas da tool Jina e modelo de resultado da persona (`result`, `used_urls`) | - | `[//]` | `app/investigation/schemas.py` | 🟢 | `[ ]` |
| T004 | Estruturar prompts e mapeamento de personas: carregar prompts de `app/prompts/personas.json`, incluir instrução de JSON final com citação factual e definir resolução de modelo por persona (`app_settings.models.<persona>`) com fallback para o modelo do `scout` | - | `[//]` | `app/investigation/prompts.py` | 🟢 | `[ ]` |

---

## Fase 2, Testes

<!-- Testes unitários e fixtures que balizam a implementação das ferramentas e workers -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T005 | Criar fixtures de teste e mocks isolados para Jina Search (POST direto e proxy) e LiteLLM function calling | T003 | `[//]` | `tests/investigation/conftest.py` | 🟢 | `[ ]` |
| T006 | Criar testes unitários para o adaptador de busca Jina: validar POST `https://s.jina.ai/` e proxy, payload `{"q": query}`, headers `Accept`/`X-Engine`, timeout de 90s, retries com `Retry-After`/backoff 2s/4s e extração integral de URLs retornadas | T005 | `[//]` | `tests/investigation/test_jina_tool.py` | 🟢 | `[ ]` |
| T007 | Criar testes unitários para o loop da persona: validar parada antecipada voluntária, teto estrito de 3 queries, retries de API, até 3 correções de JSON e timeout global de 600s | T004, T005 | - | `tests/investigation/test_persona_worker.py` | 🟢 | `[ ]` |

---

## Fase 3, Núcleo

<!-- Lógica central da ferramenta Jina, execução do worker e orquestração de fan-out -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T008 | Implementar `JinaToolAdapter`: transporte HTTP POST (`s.jina.ai` e proxy configurado), header `X-Engine: direct`, timeout 90s, retries técnicos com backoff/`Retry-After` e captura de todas as URLs lidas em `read_urls` | T002, T003 | - | `app/investigation/tools.py` | 🟢 | `[ ]` |
| T009 | Implementar binding do LiteLLM para investigação: chamada assíncrona (`litellm.acompletion`) com histórico em memória RAM exclusivamente, sem semáforo | T003 | `[//]` | `app/investigation/llm_binding.py` | 🟢 | `[ ]` |
| T010 | Implementar `PersonaWorker`: receber `(research_id, step_id, step_title, persona)`, resolver modelo com fallback no scout, loop de tool calling Jina (teto 3 buscas), parada voluntária, até 3 correções de JSON, timeout de 600s e geração de `result` + `used_urls` | T004, T008, T009 | - | `app/investigation/worker.py` | 🟢 | `[ ]` |
| T011 | Implementar persistência de resultados e atualização de passos: inserção atômica append-only em `research_step_results`, incremento de `attempt_count` em falha com erro sanitizado (máx 500 chars) e transição de status do passo | T002, T010 | - | `app/investigation/storage.py` | 🟢 | `[ ]` |
| T012 | Implementar `InvestigationService`: fan-out concorrente via `asyncio.gather` irrestrito (N pontos x 4 personas), resiliência parcial e transição final de `research.status` para `AUDIT` (ou `FAILED` se 100% dos passos falharem) | T010, T011 | - | `app/investigation/service.py` | 🟢 | `[ ]` |

---

## Fase 4, Integração

<!-- Endpoints HTTP, ganchos de ciclo de vida e alinhamento cirúrgico com a Feature 001 e legado -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T013 | Implementar `InvestigationRouter`: endpoint `POST /briefings/{research_id}/investigate` exigindo `require_admin`, validando status `SCRAPER` e pontos em `SCRAPER_PENDING`, transitando pontos para `SCRAPER_IN_PROGRESS`, retornando HTTP 202 assíncrono e validando HTTP 409 em re-disparo | T012 | - | `app/investigation/router.py` | 🟢 | `[ ]` |
| T014 | Atualizar schemas e storage de Briefing da Feature 001: emitir `research_id` no lugar de `id` em `BriefingResponse`, criar linha em `Research` antes de `Briefing` em `create_generating_briefing` e persistir pontos em `research_points` na aprovação | T002 | `[//]` | `app/briefing/storage.py` | 🟢 | `[ ]` |
| T015 | Atualizar `BriefingRouter` e `BriefingDomain`: padronizar paths com `{research_id}`, bloquear transição de reabertura após aprovação retornando HTTP 409 em `POST /briefings/{research_id}/reopen` | T014 | - | `app/briefing/router.py` | 🟢 | `[ ]` |
| T016 | Implementar novo `PATCH /briefings/{research_id}` por feedback: schema `{"note": str}` (3..4000), Scout executando tool calling Jina com tema + rascunho anterior + feedback, salvando nova versão em `briefing_versions` e marcando `FAILED` em caso de erro | T014, T015 | - | `app/briefing/service.py` | 🟢 | `[ ]` |
| T017 | Atualizar `app/routers/research.py` e pipeline legado para os novos valores de `ResearchStatus` unificado (`BRIEFING`, `PENDING_APPROVAL`, `SCRAPER`, etc.), sem tocar no lifespan | T002 | `[//]` | `app/routers/research.py` | 🟢 | `[ ]` |
| T018 | Registrar `InvestigationRouter` em `app/main.py` e adicionar hook de inicialização do FastAPI para detecção e retomada automática de workers incompletos em pesquisas com passos em `SCRAPER_IN_PROGRESS` | T013, T017 | - | `app/main.py` | 🟢 | `[ ]` |

---

## Fase 5, Polimento

<!-- Adaptação da suíte de testes legada, testes de integração E2E e validação final -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T019 | Atualizar a suíte de 184 testes de Briefing (20 arquivos em `tests/test_briefing*.py`) e testes legados afetados pelo enum (`tests/test_backend.py`, `tests/test_e2e_criteria.py`) para o novo contrato (`research_id`, 409 no reopen, novo PATCH por feedback e enum unificado), mantendo 100% verdes | T015, T016, T017 | - | `tests/test_briefing_lifecycle.py` | 🟢 | `[ ]` |
| T020 | Criar teste de integração E2E da Feature 002: fluxo completo desde briefing aprovado até disparo assíncrono de 20 workers, mock Jina/LLM, persistência em `research_step_results` com status `AUDIT_PENDING` e transição da pesquisa para `AUDIT` | T013, T018 | - | `tests/investigation/test_investigation_e2e.py` | 🟢 | `[ ]` |
| T021 | Atualizar documentação de API (`docs/api/briefing-scout.md` e novo `docs/api/investigation-personas.md`) refletindo o campo `research_id`, novo PATCH por feedback e o endpoint `/investigate` | T019, T020 | `[//]` | `docs/api/investigation-personas.md` | 🟢 | `[ ]` |

---

## Notas de execução

- Nenhuma alteração amplia escopo para a Feature 003 (Auditoria) ou Feature 004 (Redação/Relatório final).
- Frontend web permanece intocado nesta feature; adequação de telas legadas fica para a sprint do frontend.
- Todos os testes unitários utilizam banco SQLite em memória via `NullPool` sem depender de rede externa.

---

## Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-10-12 | Versão inicial gerada por `/reversa-to-do` | reversa |
| 2026-10-12 | Revisão pós-auditoria: correção da cadeia crítica para 9 passos, inclusão de schemas/storage de briefing, isolamento de arquivos alvos e detalhamento dos 184 testes | reversa |
