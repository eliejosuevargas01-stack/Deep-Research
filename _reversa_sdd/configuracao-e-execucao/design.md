# configuracao-e-execucao — design

## Fluxo settings

`ler_config` (tolerante) → `aplicar_config` (merge + `backend="por_papel"` + atômico; com engine, repassa via `PUT`) → `materializar_perfil` (provider `env`, sem segredo). `CONFIRMADO` (`src/settings.py`).

## Fluxo execução (`src/hermes_runner.py`)

Prepara workspace → prompts + `tarefas.json` → instrução por modo → subprocesso Hermes (`cwd`=workspace) → coleta JSONs + telemetria `state.db` (`:ro`) com fallback `usage.json` → `AgentCall`. Planner = 1 tarefa sem delegação; lote = N delegadas 1:1. `CONFIRMADO`.

## Resolução de modelo (D-09)

Backend: `modelo_do_papel` (`LLM_MODEL_<PAPEL>` > `LLM_MODEL` planner > default forte/leve). Entrypoint: `modelo_do_papel()` shell (vazio nunca herda forte). Plugin resolve por `papel`. Workspace congela em `MODELS.json`. `CONFIRMADO`.

## Trade-offs

- `materializar_perfil` em `executar` com try/except silencioso — deploy segue com placeholders literais. `CONFIRMADO` (`src/orchestrator.py:128-131`).
- Nunca lança no acionamento: fracasso vira erro por tarefa; retry decide. `CONFIRMADO`.
- Tokens: `state.db` autoridade; `usage.json` só fallback do delegador (`orquestrador`). `CONFIRMADO`.

## ponytail existentes

- `src/settings.py:188-189,242-243`: reescrita YAML perde comentários; round-trip ruamel se editado à mão. `CONFIRMADO`.
- `src/db/sqlite_manager.py:4-5`: ponto de troca `Repository` quando PG entrar. `CONFIRMADO`.
