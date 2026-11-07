# ingestao-e-api — requirements

Comportamento observado da superfície HTTP + criação de run/workspace.

## Requisitos

- `R-ingestao-01` — `POST /research` aceita `ResearchRequest` JSON e responde `202 {"research_id","status":"PROCESSING"}`. `CONFIRMADO` — `src/api.py:66-70`; teste `tests/test_api.py`.
- `R-ingestao-02` — Execução roda em `BackgroundTasks` após o 202 (`pipeline.executar`). `CONFIRMADO` — `src/api.py:69`; TestClient executa background de forma síncrona.
- `R-ingestao-03` — `GET /research/{research_id}` retorna run + `pontos` + `auditorias[]` + `avaliacao_pontos` (omitido sem pontos); id inexistente `404 "pesquisa não encontrada"`. `CONFIRMADO` — `src/api.py:72-74,130-157`; smoke manual: `auditorias: 1`, `avaliacao: True`.
- `R-ingestao-04` — Payload inválido retorna `422` via Pydantic (`extra="forbid"`, limites). `CONFIRMADO` — `src/contracts.py:54-70`; `profundidade le=10` (`:58`); teste `tests/test_api.py::test_api_rejeita_payload_invalido`.
- `R-ingestao-05` — `GET /health` retorna `{"status":"ok"}`, **sempre aberto mesmo com chave** (retorna antes de validar). `CONFIRMADO` — `src/api.py:33-34,49-51`; `tests/test_api_key.py:44-46` (200 com chave errada).
- `R-ingestao-06` — `GET /config` e alias oculto `GET /api/v1/settings` retornam mesma config com `api_key:""` + `provider_fonte:"env"`. `CONFIRMADO` — `src/api.py:53-56`, `src/settings.py:141-144`; smoke: `provider: env`.
- `R-ingestao-07` — `PUT /config` parcial (omitido = preservado); `base_url`/`api_key` não-vazio → `422 "provedor vem do ambiente"`; nunca persiste segredo. `CONFIRMADO` — `src/api.py:58-64`, `src/settings.py:93-98,200-212`; smoke: `PUT api_key=x` 422, `PUT api_key=""` 200.
- `R-ingestao-08` — `ResearchRequest`: `tema` min 3, `profundidade` 1..10, `veracidade_alvo` 0..100, `max_rodadas_auditoria` default 4 (1..10), `atualidade` `^(ALL|\d{1,3}[HDMY])$`, `callback_url` HttpUrl, extras proibidos. `CONFIRMADO` — `src/contracts.py:54-70`.
- `R-ingestao-09` — `criar` gera id `secrets.token_hex(8).upper()`, INSERT `PROCESSING`, prepara workspace. `CONFIRMADO` — `src/orchestrator.py:68-73`.
- `R-ingestao-10` — Workspace `<workspaces_dir>/<research_id>`, `mkdir`, `chmod 777` p/ engine, grava `MODELS.json` com `modelos_por_papel`. `CONFIRMADO` — `src/orchestrator.py:88-111`.
- `R-ingestao-11` — Auth: `X-API-Key` + Bearer + `?api_key=` (SSE); `hmac.compare_digest`; sem chave = aberto (dev); com chave, sem credencial = `401 "API key inválida"`. `CONFIRMADO` — `src/api.py:23-42`; `tests/test_api_key.py:32-87`; smoke: sem chave `POST` 401, com chave `POST` 202.
- `R-ingestao-12` — SSE `GET /research/{id}/eventos` (+ alias `/events`): `Last-Event-ID` vence, senão `?desde=`; `proximo<=0` → snapshot (`event: snapshot` com run completo); replay `id>base`; heartbeat `: ping` a cada 15s ociosas; run inexistente → 404; cai se run some. `CONFIRMADO` — `src/api.py:76-125`; `tests/test_eventos.py:81-107`; `tests/test_api_key.py:66-87` (SSE via `?api_key=`).
- `R-ingestao-13` — Entrypoint ASGI `main:app = create_app()`. `CONFIRMADO` — `src/main.py:1-5`.
- `R-ingestao-14` — Config de execução (`db_path`, `workspaces_dir`, `hermes_bin`, timeouts, `engine_url/token`) de `config/hermes_config.yaml` (só seção `pipeline`, 14 linhas, sem `delegation`, sem segredo) + env. `CONFIRMADO` — `src/config.py:15-63`, `config/hermes_config.yaml:1-14`.

## Mapeamento PRD/SDD

- RF01/RF09, SDD §2/§5.2. `INFERIDO` (nomes vindos de docstrings).

## Erros

| Situação | Código | Corpo |
|---|---|---|
| Payload fora do contrato | 422 | detalhe Pydantic |
| Sem/inválida API key (quando configurada) | 401 | `{"detail":"API key inválida"}` |
| research_id inexistente | 404 | `{"detail":"pesquisa não encontrada"}` |
| `base_url/api_key` não-vazio no PUT | 422 | `provedor vem do ambiente` |
| Falha interna no pipeline (background) | — | run `FAILED`, exceção relançada |
