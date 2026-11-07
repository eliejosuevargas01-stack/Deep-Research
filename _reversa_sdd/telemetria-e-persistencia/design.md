# Telemetria e persistência — desenho interno

## Fluxo telemetria → `AgentCall` → banco

1. `_rodar` marca `inicio`, aciona Hermes, `_coletar_saidas` (`src/hermes_runner.py`).
2. Lê `usage.json` (tolerante) + `telemetria.coletar(workspace, inicio-1)` (`state.db` `:ro`).
3. Por tarefa: sessão por `tarefa.id` (fallback `_pai` no planner); `model_used` = sessão ou `modelos_por_papel`; sem JSON → erro; `extrair_json` (erro vira `call.erro`).
4. Planner sem tokens + `uso` → `_aplicar_usage`; lote: `__orquestrador__` de `_pai` ou usage.
5. `Pipeline._registrar` (`src/orchestrator.py:632-669`) persiste tudo + emite `tokens.atualizados{papel, ponto_id, tokens_execucao, tokens_por_papel, totais}`. **CONFIRMADO**

## `_resumo_mensagens` (`src/telemetria.py:20-74`)

`PRAGMA` detecta colunas; sem `session_id`/alvos → vazios; ordem `timestamp` ou `rowid`; concatena reasoning, parseia tool_calls. **CONFIRMADO** (2 testes).

## `hidratar` (`src/db/repository.py:354-389`)

2 SELECTs + Python (sem `jsonb_object_agg`): (1) `rodada,agent_role,informacao_coletada WHERE persona AND NOT NULL ORDER BY rodada,rowid` → `por_rodada`; (2) urls em `rowid` → concat + `normalizar_urls`. Persona ausente **some da chave** (usar `.get`). **CONFIRMADO** (`test_hidratacao_preserva_todas_as_rodadas_e_personas`).

## Transações e concorrência

`_executar` = lock + execute + commit; compostos (`salvar_plano`, `consolidar`) com lock + commit único. WAL + FK ON. Uma conexão por instância. **CONFIRMADO** (concorrência real — **LACUNA**).

## `ponytail:` existente

`src/db/sqlite_manager.py:4-5`: ponto de troca `Repository` quando PG entrar. **CONFIRMADO**
