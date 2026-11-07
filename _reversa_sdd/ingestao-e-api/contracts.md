# ingestao-e-api — contracts

## POST /research — request `ResearchRequest` (`src/contracts.py:54-70`)

| Campo | Tipo | Obrig. | Default | Regra |
|---|---|---|---|---|
| tema | string | sim | — | strip, min 3, não vazio |
| profundidade | int | sim | — | 1..10 |
| veracidade_alvo | float | sim | — | 0..100 |
| max_rodadas_auditoria | int | não | 4 | 1..10 |
| atualidade | string | não | "ALL" | `^(ALL|\d{1,3}[HDMY])$` |
| callback_url | HttpUrl | sim | — | http/https válida |

`extra="forbid"` — campo desconhecido = 422. `CONFIRMADO`.

## POST /research — response 202 (`src/api.py:66-70`)

`{"research_id": "<16 HEX MAIÚSC>", "status": "PROCESSING"}`. `CONFIRMADO`.

## GET /research/{id} — response 200 (`src/api.py:130-157`)

Run + `pontos[]` + `auditorias[]` (cada item com `perguntas_true/porcentagem_aprovacao/meta_veracidade_alvo/aprovado` via `planner.avaliar`) + `avaliacao_pontos` (omitido quando run sem pontos). 404: `{"detail":"pesquisa não encontrada"}`. `CONFIRMADO` (smoke: `auditorias: 1`, `avaliacao: True`).

## GET/PUT /config (`src/settings.py`, `src/api.py:53-64`)

Resposta: `{base_url (env), api_key: "", default_model, provider_fonte: "env", max_concurrent_children=40, max_spawn_depth=2, oneshot_max_children=0, modelos_por_papel{7}}`. PUT parcial; `base_url/api_key` não-vazio → 422. `CONFIRMADO` (smoke: `provider: env`; `PUT api_key=x` 422).

## SSE `GET /research/{id}/eventos` (+ `/events`) (`src/api.py:76-125`)

`Last-Event-ID` vence, senão `?desde=`; `<=0` → `event: snapshot` (run completo); senão replay `id>base`; heartbeat `: ping`/15s. Auth `?api_key=` p/ EventSource. At-least-once (comentário `:88-92`). `CONFIRMADO` — `tests/test_eventos.py:81-107`, `tests/test_api_key.py:66-87`.

## Auth (`src/api.py:23-42`)

`DR_API_KEY|API_KEY`; sem chave = aberto (dev); `GET /health` sempre aberto; `X-API-Key`/Bearer/`?api_key=`; `hmac.compare_digest`; 401 `API key inválida`. `CONFIRMADO`.

## Tabela tocada: `research_runs` (`src/db/sqlite_manager.py:14-35`)

`research_id PK, tema, profundidade CHECK 1..10, veracidade_alvo CHECK 0..100, ..., status DEFAULT 'PROCESSING', ...`. `CONFIRMADO`.

## Divergências vs PRD/SDD

- `atualidade` regex aceita `0H`/`999Y` — semântica não checada. `CONFIRMADO` (`src/contracts.py:61`).
- Snapshot SSE at-least-once: "sem duplicação" estrito exige dedupe no cliente. `CONFIRMADO` (`src/api.py:88-92`).
