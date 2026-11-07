# verification — api-smoke

Smoke via `fastapi.testclient.TestClient` contra `create_app` com `FakeExecutor`, banco/workspace/perfil em tmp. CONFIRMADO.

## Sem chave (modo aberto dev)

- `GET /health` -> 200 `{"status":"ok"}` (`src/api.py:33-34,49-51`).

## Com chave (`DR_API_KEY=k-secreta`, smoke 2026-11-07)

- `GET /health` sem chave -> 200 (sempre aberto, `src/api.py:33-34`); `tests/test_api_key.py:44-46` cobre 200 com chave errada.
- `POST /research` sem chave -> 401 `{"detail":"API key inválida"}`.
- `POST /research` com `X-API-Key` -> 202 `{research_id, PROCESSING}`.
- `GET /research/{id}` -> 200 com `pontos` + `auditorias` (1 item) + `avaliacao_pontos` (presente).
- `PUT /config {"api_key":"x"}` -> 422 (provedor só env, `src/settings.py:93-98`).
- `PUT /config {"api_key":""}` -> 200.
- `GET /config` -> 200 `provider_fonte: "env"`, `api_key: ""`.
- SSE `GET /research/{id}/eventos?api_key=...` -> 200 `event: snapshot` (`tests/test_api_key.py:66-87`).

## Rotas efetivas

`GET /health` (sem auth), `GET/PUT /config` + alias `/api/v1/settings` (com auth), `POST /research`, `GET /research/{id}`, `GET /research/{id}/eventos|/events` (SSE), + docs automáticos.
