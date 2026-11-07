# configuracao-e-execucao — contracts

## `config.yaml` do perfil (`hermes_home/profiles/deep-research/config.yaml:1-21`)

`model.{default: ocg/deepseek-v4.1-flash, provider: env}`, `plugins.enabled=[por_papel]`, `delegation.{backend: por_papel, max_spawn_depth: 2, max_concurrent_children: 40, oneshot_max_children: 0, backends.por_papel.modelos.{7 papéis: forte p/ planner/auditor/redator, lite p/ 4 buscadores}}`. Sem `base_url/api_key`. `CONFIRMADO`.

## `ConfigHermes` / config efetiva (`src/settings.py:80-149`)

PUT: 7 campos opcionais + `modelos_por_papel{7}`; `base_url/api_key` não-vazio → 422. Resposta: `{base_url(env), api_key:"", default_model, provider_fonte:"env", limites, modelos_por_papel{7}}`. `CONFIRMADO`.

## `MODELS.json` (`src/orchestrator.py:106-110`)

`{"modelos_por_papel": {...}}` — snapshot do perfil na criação. `CONFIRMADO`.

## `tarefas.json` + instruções (`src/hermes_runner.py:30-53`)

`[{id, papel, arquivo, ponto_id, rodada}]`; planner ≤5 buscas + `urls_lidas/usadas`; lote N tarefas 1:1 `delegate_task`. `CONFIRMADO`.

## Engine (`engine/service.py`, `engine/Dockerfile`, `docker-compose.yml`)

- Imagem **`nousresearch/hermes-agent:latest`** (D-12). `CONFIRMADO` (`engine/Dockerfile:5`).
- `GET /health` sem auth; `/run|/config` com `X-Engine-Token` (401/500; 403 fora de `/workspaces`); `/run` timeout máx 3600, corta saída em 200k. `CONFIRMADO`.
- `/config` (engine e backend) nunca persiste `base_url/api_key`; `provider="env"`; segredo só em `.env` 600 no volume (entrypoint `:58-71`). `CONFIRMADO`.
- Compose: api (`DR_ENGINE_URL`, `ENGINE_TOKEN`, `DR_API_KEY`, `DR_HERMES_STATE_DB`, `hermes_home:ro`) + engine (`LLM_*` por papel com defaults forte/leve, `expose 8100`). `CONFIRMADO`.

## Divergências vs PRD/SDD

- Nenhuma pendente: provider só-env documentado, `latest` aceito (D-12), espelho morto removido (D-06), 7 papéis pinados (D-09).
