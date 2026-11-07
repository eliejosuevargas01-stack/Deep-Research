# Telemetria e persistência — comportamento observado

Fonte: `src/telemetria.py`, `src/db/sqlite_manager.py`, `src/db/schema.sql`, `src/db/repository.py`, `src/hermes_runner.py`, `src/engine.py` (`AgentCall`), `src/orchestrator.py` (`_registrar`).

## Telemetria (`src/telemetria.py`)

- R-TP-01 — Fonte `state.db`: `DR_HERMES_STATE_DB` ou `diretorio_perfil()/state.db`; ausente → `{}` (`:77-83,92-94`). Conexão **read-only** URI `mode=ro` (`:97`), `Row`, sempre `close` (`:167`). Erro SQLite → `{}`/vazios, nunca lança. **CONFIRMADO** (compose monta `:ro` via volume `hermes_home:ro`).
- R-TP-02 — `sessions WHERE started_at >= desde AND (cwd = workspace OR cwd IS NULL)` (`:104-110`); soma input/output/reasoning, tool_calls, latência. **CONFIRMADO** por `tests/test_lacunas.py::test_coletar_reasoning_toollcalls_latency`.
- R-TP-03 — Chave `_pai` p/ título sem id (`:111-115`); regex papel (`:16`); agregação por tarefa. **CONFIRMADO**.
- R-TP-04 — `reasoning`+`reasoning_content` com `\n`, **truncado 20_000** (`:17,161`); `tool_calls` parseado (lista estende, dict anexa, inválido ignora `:64-73`). **CONFIRMADO** (2 testes `test_lacunas.py`; truncamento 20k lido, sem teste de estouro — **LACUNA** parcial).
- R-TP-05 — Sem tabela `messages` (state antigo): vazios, sem erro (`:20-38`). **CONFIRMADO** por `tests/test_lacunas.py::test_coletar_sem_tabela_messages`.
- R-TP-06 — Consumo no runner: planner sem sessão usa `_pai`; lote publica `__orquestrador__` de `_pai` ou `usage.json` agregado; `_registrar_orquestrador` persiste `agent_role="orquestrador"` (`src/orchestrator.py:612-630`; `pop` some do dict). **CONFIRMADO**.

## Persistência (`src/db/repository.py`, `src/db/sqlite_manager.py`, `src/db/schema.sql`)

- R-TP-07 — SQLite local `SCHEMA` inline (`:13-91`): **4 tabelas** (`research_runs`, `research_points`, `agent_executions`, **`research_events`** + `idx_events_lookup` `:81-90`); WAL, `foreign_keys=ON`; migração `model_used` pré-v1.2 (`:102-104`). PG canônico em `src/db/schema.sql:1-85` (4 tabelas, `research_events :77-85`). **CONFIRMADO** (DDL PG nunca executado — **LACUNA**).
- R-TP-08 — Escritas: `criar_run`, `salvar_plano` (UPDATE+DELETE+executemany, commit único), `registrar_execucao` (INSERT + `UPDATE ... + ?` nos totais), `salvar_auditoria` (só última), `salvar_relatorio`, `marcar_status`, `emitir_evento` (INSERT+commit, id crescente — **persist-before-publish**). **CONFIRMADO**.
- R-TP-09 — Leituras: `obter_run/pontos/auditorias/avaliacao/execucoes`; **`hidratar` integral sem truncamento** (2 SELECTs + Python, só personas, `informacao_coletada NOT NULL`, ordenado rodada/rowid; :354-389). **CONFIRMADO** por `tests/test_repositorio.py::test_hidratacao_preserva_todas_as_rodadas_e_personas`.
- R-TP-10 — DB integral × prompt compactado (D-11): `hidratar` devolve 100% bytes; compactação só no payload (`hydrator`), DB nunca reescrito. **CONFIRMADO** (`tests/test_evidencias.py:95-96` entrada não mutada).
- R-TP-11 — Eventos SSE: `listar_eventos(id>base, ASC, limite 500)`, `ultimo_evento_id` (`:209-227`). **CONFIRMADO** (`tests/test_eventos.py:52-60`).
