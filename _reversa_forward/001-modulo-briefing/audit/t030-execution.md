# Execução T030 — F-ERROR-01

Status: implementação e testes concluídos; sem autoaprovação de auditoria.

## Alterações

- `app/briefing/llm_binding.py`: classificação por classes concretas `litellm.exceptions`/HTTPX e `TimeoutError`, com status numérico estrito para `APIError` e `HTTPStatusError`. Exceção elegível converte com `raise LLMAttemptError() from None`; classes, status não reconhecidos, autenticação, configuração e erros desconhecidos propagam identidade. Sem texto/regex, sem `_classify_error` legado.
- `tests/test_briefing_llm_binding.py`: adicionados casos elegíveis, negativos, identidade e segurança. Fixture `_err` anterior fabricava `Exception` arbitrária com nome/status sintéticos; removida e substituída por classes reais LiteLLM/HTTPX nos testes preexistentes, preservando comportamentos e asserts essenciais.
- `make_scout_complete(db: AsyncSession, default_timeout_s=30.0)`, `_enforce_safe_transport()`, `num_retries=0` e `max_retries=0` preservados. Nenhuma mudança em `app/services/llm.py` ou T031.

## TDD e verificação

- Baseline: `python3 -B -m unittest tests.test_briefing_llm_binding -v` — 12 testes passaram.
- RED: `test_api_connection_error_becomes_safe_attempt_error` falhou com erro esperado: `litellm.exceptions.APIConnectionError` escapou cru, com status 500 e classificação legada não-retryable.
- GREEN: o mesmo teste passou após classificador concreto e máscara fixa.
- Expansão: suite completa executada — 21 testes passaram (`Ran 21 tests ... OK`). Inclui `InternalServerError`, `Timeout`, classes de transporte HTTPX, status 429/500/502/503/504, status de auth, `BadRequestError`, RuntimeError/TypeError com textos enganosos, identidade, ausência de sentinela na exceção/traceback formatado e chamada única.
- Dependências detectadas via `importlib.metadata`: LiteLLM 1.104.0 e HTTPX 0.28.1. `litellm.exceptions.Timeout` é símbolo exportado real; não usado `APITimeoutError`.
- Timeout do callable desconhecido e deadline de serviço já cobertos sem alterações: `tests/test_briefing_generation.py::test_callable_timeout_error_without_deadline_propagates` e `tests/test_briefing_generation.py::test_llm_timeout_retries_until_draft`; código de serviço mantém `asyncio.timeout` e só reitera se `deadline.expired()`.
- `PYTHONPYCACHEPREFIX=/root/.hermes/profiles/orchestrator/cache/scratch/briefing-verify-pycache python3 -B -m py_compile app/briefing/llm_binding.py tests/test_briefing_llm_binding.py` — passou.
- `git diff --check` — sem saída. Arquivos ainda não rastreados; checagem adicional `git diff --no-index --check /dev/null <arquivo>` não reportou whitespace (exit 1 é diferença esperada contra `/dev/null`).
- SHA-256 ao fim da edição: binding `038bdb57f9f45ce099083b5b9a27e0a91e413ad6722fbebdbf3f61677931cd73`; testes `737a2217124d32c836c8d848e53f7ddb1413d73bb424284e1a2002c1070b9c9e`.

## Limites

A prova exercita binding com transporte/LLM mockados mais teste de transporte OpenAI existente; não afirma cobertura multi-provider. Exceções não reconhecidas continuam sendo propagadas intencionalmente. Nenhuma alteração a `actions.md`, progresso, T031, ou arquivos de impacto/regressão.
