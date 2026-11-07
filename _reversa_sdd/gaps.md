# Lacunas de verificação e divergências

Severidade: `alta` (risco de comportamento errado em produção), `media` (risco de interpretação/entrega), `baixa` (higiene documental).

## Lacunas de verificação (não executado)

- G-01 `alta` — Hermes real ausente: `delegate_task`, fan-out real 40, `state.db` de produção e modelos por papel efetivos no engine nunca observados. Dono: `configuracao-e-execucao`. Evidência: `which hermes` vazio; `tests/test_hermes_runner.py:24` usa fake. (Depth 10 real não executado.)
- G-02 `alta` — Falha do webhook mantém COMPLETED sem teste de integração: `executar` com notificador que levanta nunca executado; só lido (`src/orchestrator.py:166-173`). Dono: `redacao-e-consolidacao`.
- G-03 `media` — DDL PostgreSQL (`src/db/schema.sql`, inclui `research_events`) nunca executado; paridade SQLite×PG é leitura. Dono: `telemetria-e-persistencia`.
- G-04 `media` — Truncamento `reasoning_trace[:20000]` (`src/telemetria.py:17,161`) sem teste de estouro; `state.db` ausente e `cwd IS NULL` sem teste dedicado. Dono: `telemetria-e-persistencia`.
- G-05 `baixa` — Esgotamento de retentativas do planner (`PipelineError`) sem prova direta; só sucesso + 1 correção (`tests/test_pipeline.py`). Dono: `planejamento`.
- G-06 `baixa` — Plugin `por_papel` não importável neste host (só runtime Hermes). Dono: `configuracao-e-execucao`.
- G-07 `media` — SSE snapshot **at-least-once**: replay `depois_de=proximo` pode reduplicar o que o snapshot trouxe (`src/api.py:88-92`); "sem duplicação" estrito exige dedupe no cliente. Dono: `ingestao-e-api`.
- G-08 `media` — Frontend legado `src/App.tsx` + `src/services/api.ts` (12 rotas mortas `/api/v1/*`) ainda compilam via `tsc`; só `main.tsx` os exclui do bundle. Dívida técnica e risco de regressão. Dono: `ingestao-e-api` (frontend).

## Divergências código × PRD/SDD (código é autoridade) — resolvidas em D-09..D-12

- Webhook fora da transação de COMPLETED: `consolidar` marca COMPLETED + commit e só então chama o notificador; falha é só log (D-01). Dono: `redacao-e-consolidacao`.
- Provider só-env: `PUT /config` com `base_url/api_key` não-vazio → 422; `GET` retorna `api_key:""` + `provider_fonte:"env"` (D-10). Dono: `ingestao-e-api`/`configuracao-e-execucao`.
- Prompt auditor/redator compactado (D-11); DB integral. PRD "100% bytes no prompt" → "100% bytes no DB + `compactacao{}`". Dono: `coleta-personas`.
- `hidratar` = 2 SELECTs + Python, não `jsonb_object_agg` da spec; semântica equivalente + compactação documentada. Dono: `telemetria-e-persistencia`.
- `latest` aceito (`engine/Dockerfile:5`); SDD registra. Dono: `configuracao-e-execucao`.

## Removidas (corrigidas — não são mais drift)

- ~~`api_key` em GET/PUT~~ → `GET` retorna `""`, `PUT` não-vazio dá 422 (`src/settings.py:93-98,141-144`).
- ~~webhook 2 tentativas~~ → 5 tentativas (1,2,4,8s) (`src/webhook.py:14-50`).
- ~~frontend fora do escopo~~ → fluxo v1.2 ativo (`main.tsx` só `AppV12`); legado fora do bundle.
- ~~sem SSE/histórico/avaliacao~~ → SSE + `auditorias[]` + `avaliacao_pontos` implementados e testados.
- ~~`config/hermes_config.yaml` espelho~~ → só seção `pipeline` (14 linhas, sem `delegation`).
- ~~segredo no config~~ → `config.yaml` do perfil sem `base_url/api_key`, `provider: env`.
- ~~docstring `planner.py:57-58` "sem chamador"~~ → docstring atual cita consumo via `obter_avaliacao` (D-08).
- ~~`data/deep_research.db` sem `research_events`~~ → `sqlite_manager.py:81-90` cria 4 tabelas + índice (artefato local não versionado como prova).
