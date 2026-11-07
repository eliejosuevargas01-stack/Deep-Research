# ingestao-e-api — design

## Fluxo

1. `uvicorn main:app` (`src/main.py:3-5`) → `create_app()` (`src/api.py:45-47`) injeta `Pipeline`.
2. Auth `Depends(_exigir_chave)` em tudo exceto `GET /health` (`src/api.py:49-77`): sem chave configurada = aberto; com chave, `X-API-Key`/Bearer/`?api_key=` + `compare_digest` (`:23-42`). `CONFIRMADO`.
3. `POST /research`: valida `ResearchRequest` → `criar` (INSERT `PROCESSING` + workspace + `MODELS.json`) → `BackgroundTasks(executar)` → 202. `CONFIRMADO` (`src/api.py:66-70`, `src/orchestrator.py:68-111`).
4. `GET /research/{id}`: `_consultar_run` = `obter_run` + `obter_pontos` + `obter_auditorias` (com `planner.avaliar` por item: taxa/aprovado) + `obter_avaliacao` (omitido sem pontos). `CONFIRMADO` (`src/api.py:130-157`).
5. `GET/PUT /config` (+ alias `/api/v1/settings`, `include_in_schema=False`): `ler_config`/`aplicar_config`; com `DR_ENGINE_URL`, engine é dono (`_aplicar_no_engine`). PUT nunca grava segredo. `CONFIRMADO` (`src/settings.py:200-282`).
6. SSE: snapshot una vez (`proximo<=0`) + loop `listar_eventos(id>proximo)` + heartbeat 15s; encerra se cliente desconecta ou run some. Snapshot é **at-least-once** (replay `depois_de=proximo` pode reduplicar; cliente deduplica por id — `src/api.py:88-92`). `CONFIRMADO`.

## Módulos/funções

- `src/api.py:create_app/_chave_api/_exigir_chave/_consultar_run` — rotas + auth + consulta. `CONFIRMADO`.
- `src/contracts.py:ResearchRequest` — validação de borda. `CONFIRMADO`.
- `src/orchestrator.py:Pipeline.criar/caminho_workspace/_preparar_workspace` — id + workspace + `MODELS.json`. `CONFIRMADO`.
- `src/config.py:Config.carregar` — YAML `pipeline` + env. `CONFIRMADO`.

## Estados

`research_runs.status`: `PROCESSING` → `COMPLETED`/`FAILED`. `CONFIRMADO`.

## Decisões/trade-offs

- BackgroundTasks em vez de fila: falha vira `FAILED` silencioso no HTTP (já houve 202). `INFERIDO`.
- Alias `/api/v1/settings` oculto mantém compat sem documentar duas rotas. `INFERIDO`.
- `MODELS.json` congela modelos do perfil por pesquisa. `CONFIRMADO` (`src/orchestrator.py:106-110`).
- Snapshot at-least-once: nunca perde, pode duplicar; dedupe no cliente. `CONFIRMADO` (`src/api.py:88-92`).

## ponytail existentes

Nenhum neste escopo de arquivos.
