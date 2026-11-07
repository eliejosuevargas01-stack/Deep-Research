# Telemetria e persistência — contratos

## `telemetria.coletar(workspace, desde)` → `dict[tarefa_id, entrada]`

`model_used, prompt/completion/reasoning/total_tokens` (total recalculado `:136-140`), `tool_calls` (contagem), `latency_ms`, `reasoning_trace` (`[:20000]`), `tool_calls_lista`, `sessoes[]`. Chave `_pai` sem id. **CONFIRMADO** (`src/telemetria.py:86-167`)

## `AgentCall` (`src/engine.py:20-31`)

`{dados, texto="", erro="", reasoning_trace="", tool_calls=[], prompt/completion/reasoning/total_tokens=0, latency_ms=0, model_used=""}`. `registrar_execucao`: `raw_output = dados ou {texto}`, `total = total ou soma` (`src/db/repository.py:113-115`). **CONFIRMADO**

## Tabelas (SQLite efetivo × PG canônico)

| tabela | SQLite | PG | delta |
|---|---|---|---|
| `research_runs` | TEXT PK, TEXT JSON, INTEGER tokens | VARCHAR(64) PK, JSONB, BIGINT | tipos; CHECKs iguais |
| `research_points` | `point_uuid` TEXT hex + `UNIQUE(research_id,ponto_id)` | UUID + mesma UNIQUE | tipos |
| `agent_executions` | TEXT hex, TEXT JSON | UUID, JSONB | tipos |
| **`research_events`** | `id INTEGER PK AUTOINCREMENT, research_id, tipo, payload '{}', created_at` + `idx_events_lookup` | `id SERIAL PK, research_id, tipo, payload JSONB, created_at` + índice | tipos |
| índice | `idx_executions_lookup` | idem | igual |

**CONFIRMADO** (ambos lidos; `model_used` nos dois). DDL PG nunca executado — **LACUNA**.

## `CAMPOS_JSON_*` e defaults

`CAMPOS_JSON_RUN` (5) / `CAMPOS_JSON_PONTO` (5) (`src/db/repository.py:16-29`); `obter_run`: `urls_*` default `[]`; `obter_execucoes`: 6 campos JSON. **CONFIRMADO**

## Divergências vs PRD/SDD

- Schema PG nunca executado neste host — paridade é leitura, não prova. **LACUNA** (PG real não executado).
- `hidratar` = 2 SELECTs + Python, não `jsonb_object_agg` da spec; semântica equivalente (ordenado, só personas, NOT NULL) + compactação documentada D-11. **CONFIRMADO**.
