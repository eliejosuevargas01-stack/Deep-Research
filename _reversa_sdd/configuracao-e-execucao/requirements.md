# configuracao-e-execucao — requirements

Comportamento observado: engine separado, provider só-env, modelos por papel, perfil, executor.

## Requisitos

- `R-conf-01` — `diretorio_perfil()` = `$DR_HERMES_PROFILE_DIR` ou `hermes_home/profiles/deep-research`; `caminho_config()` = `<perfil>/config.yaml`. `CONFIRMADO` — `src/settings.py:58-65`.
- `R-conf-02` — `ler_config()` (`src/settings.py:126-149`): `model.default` (+ `LLM_MODEL` fallback, senão forte), `delegation.{max_concurrent_children=40, max_spawn_depth=2, oneshot_max_children=0}`, `modelos` por papel (ausente=`""`); `base_url` de `LLM_BASE_URL|OPENAI_BASE_URL`, **`api_key` sempre `""`**, **`provider_fonte:"env"`**. `CONFIRMADO` (smoke: `provider: env`).
- `R-conf-03` — `aplicar_config` parcial + `delegation.backend="por_papel"` + escrita atômica; com `DR_ENGINE_URL`, engine é dono (`PUT /config` do engine); nunca grava segredo (validator 422 + defesa em profundidade `:209-212`). `CONFIRMADO` — `src/settings.py:200-282`.
- `R-conf-04` — `materializar_perfil()` garante `model.provider: env`, remove `base_url/api_key` do YAML, expande `${VAR}` em `model.default`. `CONFIRMADO` — `src/settings.py:152-197`.
- `R-conf-05` — `ConfigHermes`: tudo opcional, `extra="forbid"`; `ge=1` p/ `max_concurrent_children/max_spawn_depth`, `ge=0` p/ `oneshot`; `ModelosPorPapel` 7 opcionais; `base_url/api_key` não-vazio → 422. `CONFIRMADO` — `src/settings.py:80-98`.
- `R-conf-06` — Modelos por papel D-09: forte `ocg/deepseek-v4.1-flash` (planner/auditor/redator/default), leve `gemini/gemini-3.5-flash-lite` (historiador/cetico/visionario/futurista); `modelo_do_papel` (`:44-55`): `LLM_MODEL_<PAPEL>` > `LLM_MODEL` (planner) > default do papel; perfil `hermes_home/profiles/deep-research/config.yaml:1-21` com os 7 pinados, `provider: env`, sem segredo. `CONFIRMADO` (script: forte p/ 3, lite p/ 4).
- `R-conf-07` — `config/hermes_config.yaml` hoje **só seção `pipeline`** (14 linhas: sem `delegation`, sem segredo, sem espelho). `CONFIRMADO` (D-06 aplicado).
- `R-conf-08` — Engine separado: `engine/service.py` (`GET /health` sem auth → `{status,model}`; demais com `X-Engine-Token`, 401/500/403; `/run` executa `hermes -p deep-research -z ... --usage-file` com cwd=workspace e `timeout`; `/config` nunca persiste segredo, `provider="env"`); `engine/Dockerfile` **`FROM nousresearch/hermes-agent:latest`** (aceite D-12, `:2-5`); `docker-compose.yml` 2 serviços, api monta `hermes_home:ro`, `DR_HERMES_STATE_DB` no compose (`:14`) lido `:ro` pelo backend (`src/telemetria.py:97`). `CONFIRMADO`.
- `R-conf-09` — `HermesRunner.planejar/executar`: `MODELS.json` lido do perfil na criação; `prompts/<id>.md` + `tarefas.json`; `INSTRUCAO_PLANNER` (varredura ≤5 buscas, `urls_lidas/usadas` no JSON, sem delegar) / `INSTRUCAO_LOTE` (N tarefas 1:1 `delegate_task` com `papel`). `CONFIRMADO` — `src/hermes_runner.py:30-53`, `src/orchestrator.py:106-110`.
- `R-conf-10` — Workspace por pesquisa com `MODELS.json` próprio; `cwd`=workspace; `DR_WORKSPACE`. `CONFIRMADO`.
- `R-conf-11` — `hermes` fora do PATH neste host: prova via `tests/fake_hermes.py`. `CONFIRMADO` (`which hermes` vazio — **LACUNA** Hermes real).
- `R-conf-12` — `SOUL.md` materializado de `SOUL.template.md`; regras: só workspace, sem inventar, planner com varredura, orquestrador só delega 1 `delegate_task`/tarefa. `CONFIRMADO`.

## Mapeamento

- RF02 (40 via `max_concurrent_children`), RF09 (config sem segredo). `INFERIDO`.
