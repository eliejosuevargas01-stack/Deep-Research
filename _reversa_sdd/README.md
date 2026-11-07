# Documentação reversa — Hermes Deep Research (código atual)

Índice da documentação reversa do backend em `src/` como implementado na árvore de trabalho (pós D-01..D-12 + correções das auditorias 2026-11-07). Não descreve intenção da spec: descreve o código lido e executado via `pytest` (78) + frontend (51) + `fastapi.testclient` com `tests/fake_hermes.py` + smoke manual de API key.

## Unidades (7, cada uma com requirements/design/contracts/tasks)

| Unidade | Cobre |
|---|---|
| `ingestao-e-api/` | `src/api.py` (+auth API key, SSE `/eventos|/events`, `auditorias`/`avaliacao_pontos`), `src/contracts.py` (`ResearchRequest`), `src/main.py`, `src/config.py` (só `pipeline`), workspace + `MODELS.json`; inclui `routes.json` (9 rotas) |
| `planejamento/` | `_planejar`, `PlanoLLM`/`PontoPlano` (+`urls_lidas/usadas` D-07), `src/prompts/planner.md`, retentativa, `salvar_plano`, varredura exploratória; compactação não muda plano (D-11) |
| `coleta-personas/` | `_coletar`, `payload_buscador`, `INSTRUCAO_LOTE`, `BuscadorSaida`, blacklist, isolamento por persona, eventos `fonte.lida`/`ponto.coletado` (arrays), `agent_executions`, compactação D-11 |
| `auditoria-e-loop/` | `_auditar` (auditor ausente → 12 false), `payload_auditor` (compactado), `AuditorSaida`, `src/planner.py` (`avaliar` + `avaliacao_pontos` oficial D-08), `salvar_auditoria` + histórico `auditorias[]` (D-04) |
| `redacao-e-consolidacao/` | `_redigir` (validador por ponto), `payload_redator` (compactado), `RedatorSaida`, consolidação resiliente (ponto incompleto vira seção), `avaliacao_pontos` no dossiê/webhook/`run.concluido`, `src/webhook.py` (5 tentativas D-01) |
| `configuracao-e-execucao/` | engine separado (`engine/service.py`, `Dockerfile` `latest` D-12, compose 2 serviços), provider só-env (D-10), modelos por papel forte/leve D-09 (7 papéis, `MODELS.json`), perfil `config.yaml`, plugin `por_papel`, `src/hermes_runner.py`, workspace, `state.db :ro` |
| `telemetria-e-persistencia/` | `src/telemetria.py` (state.db `:ro`, fallback usage→`orquestrador`), `src/db/sqlite_manager.py` (4 tabelas + `research_events`), `src/db/schema.sql` (PG canônico, nunca executado), `src/db/repository.py` (DB integral × prompt compactado) |

Provas em `verification/`: `comandos.md`, `pytest.txt` (**78 passed**), `api-smoke.md` (smoke 200/401/202/422 + `auditorias`/`avaliacao_pontos`), `db-inventory.md`, `runner-e2e.md`. Frontend: 51 passed + build OK (ver `cross-review-result.md`).

Decisões em `migration/DECISIONS.md` (D-01..D-12); perguntas em `questions.md` (nenhuma aberta).

## Limites de verificação

- `hermes` fora do PATH: nenhum teste aciona Hermes real, `delegate_task` real, `state.db` de produção ou depth-10 real. Prova usa `tests/fake_hermes.py` e `state.db` sintético (`tests/test_lacunas.py`).
- PostgreSQL não executado: `src/db/schema.sql` é DDL não exercitado; paridade SQLite×PG é leitura, não prova.
- SSE snapshot é at-least-once (`src/api.py:88-92`): replay pode duplicar; cliente deduplica por id.
- `frontend/src/services/api.ts` legado (12 rotas `/api/v1/*` mortas) ainda compila via `tsc`; fluxo ativo (`main.tsx` → `AppV12`) não o usa — bundle limpo, fonte com dívida técnica (G-08).
