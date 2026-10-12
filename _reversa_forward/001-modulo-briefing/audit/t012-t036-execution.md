# T012 + T036 — execution report (RED/GREEN, comandos, contagens)

Data: 2026-10-11. Delta pendente sobre HTTP existente preservado.
Parent guarda actions/progress — este arquivo NÃO fecha T012, ações ou feature.

## T036 — timeout configurável (GREEN)

Mudança (`app/briefing/router.py`):
- `_resolve_briefing_timeout()` lê `settings.SEARCH_TIMEOUT_SECONDS` e valida:
  bool/não-numérico/zero/negativo/NaN/inf → `ValueError`, sem fallback silencioso.
- `create_briefing` resolve timeout ANTES de credenciais (`_runtime_jina_key`),
  construção de clientes e I/O; inválido → 500 genérico sem segredo.
- Mesmo valor passado explicitamente a `_build_serp_client(api_key, timeout=...)`,
  `_build_llm_complete(timeout=...)` → `make_scout_complete(..., default_timeout_s=...)`
  e `orchestrate_persisted_briefing(..., llm_timeout_s=...)`.
- Sem campo novo em `app/core/config.py` (reuso de `SEARCH_TIMEOUT_SECONDS`, default 30).

RED: teste novo `test_configured_timeout_flows_to_builders_and_service`
falharia antes do patch (`_build_*` sem parâmetro, sem `llm_timeout_s`,
sem validação). Contrato fixo antigo (`test_request_scoped_clients_*`
com literais 30/30.0) atualizado para forma parametrizada.
GREEN: `tests.test_briefing_api`: 12 testes OK.

## T012 — suite de aceitação Gherkin (GREEN local, gate provedor NÃO executado)

Arquivo novo: `tests/test_briefing_acceptance.py` (unittest stdlib,
`IsolatedAsyncioTestCase`, SQLite `:memory:` + aiosqlite, ASGITransport
com app de `app.main`, sem lifespan legado). 10 testes:

| # | Cenário Gherkin (requirements.md:74-124) | Prova |
|---|---|---|
| 1 | Gerar rascunho | POST 201 draft, prompt de disco, SERP real 1 chamada, 3-7 pontos |
| 2 | Editar rascunho | PATCH nova versão 3-7 pontos |
| 3 | Rejeitar quantidade inválida | PATCH 2/8 pts → 422 + snapshot intacto; draft inválido (2 pts) semeado no SQLite → approve 422 + preservado (approve aceita só omitido/null/{}) |
| 4 | Aprovar briefing | approved + approved_at, PATCH → 409, GET approved 200 |
| 5 | Reabrir briefing | draft + approved_at None + nova edição 200 |
| 6 | Falha na busca | 4 tentativas HTTP, FAILED no mesmo registro, 503 seguro, LLM 0 chamadas |
| 7 | Retentar sem repetir sucesso | SERP 1 chamada, LLM 4 tentativas, mesmo registro failed |
| 8 | Prompt ausente/inválido | LLM 0 chamadas, FAILED + 500 seguro; `load_briefing_prompt` com path inexistente levanta |
| 9 | Gate de transporte do binding (local) | binding/SDK reais + MockTransport 503: num_retries=0/max_retries=0, 1 request |
| 10 | Contrato SerpSearchError | attempts=4, mensagem sem segredo |

RED observado: `test_prompt_ausente_ou_invalido` falhou 201 vs 500 —
patch mirado em `app.briefing.service.load_briefing_prompt` quando o router
injeta `prompt_loader` via `app.briefing.router.load_briefing_prompt`.
GREEN após corrigir alvo.

Distinção obrigatória de cobertura:
- COBERTO (local, sem rede): RF-01–RF-10 via HTTP + SQLite isolado,
  SERP real sobre MockTransport, SDK litellm real sobre MockTransport.
- NÃO EXECUTADO: gate de runtime contra provedor LLM real
  (credencial + rede reais). T012 permanece ABERTO quanto a esse gate.

## Comandos (exit 0 todos)

- `python3 -B -m unittest tests.test_briefing_acceptance -v` → 10 testes OK
- `python3 -B -m unittest tests.test_briefing_api -v` → 12 testes OK
- `python3 -B -m unittest discover -s tests -p 'test_briefing*.py'` → 183 testes OK, zero regressão
- `PYTHONPYCACHEPREFIX=<scratch>/pyc python3 -m py_compile app/briefing/router.py app/core/config.py tests/test_briefing_api.py tests/test_briefing_acceptance.py` → OK (`config.py` intocado, verificado por leitura)
- `git diff --check` → limpo

## Arquivos

- Modificado: `app/briefing/router.py` (timeout validado + propagação explícita)
- Modificado: `tests/test_briefing_api.py` (+1 teste T036, contrato parametrizado)
- Criado: `tests/test_briefing_acceptance.py` (10 testes T012)
- Criado: este relatório. `app/core/config.py` intocado (reuso de campo existente).
