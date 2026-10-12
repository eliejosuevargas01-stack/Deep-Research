# T031 — Execução: ownership de sessão e assinatura da fábrica (F-CONSISTENCY-01)

**Data:** 2026-10-11
**Task:** T031 — Corrigir F-CONSISTENCY-01
**Escopo exclusivo:** `app/briefing/llm_binding.py`, `tests/test_briefing_llm_binding.py`, este relatório
**Contrato canônico:** `audit/t029-t031-planning-delta.md:32–39` (F-CONSISTENCY-01), D3/D5 vigentes em `audit/t011-integration-decomposition.md:99–110`

## Status: DONE (TDD RED→GREEN, 24/24 testes)

## Mudança de produção (`app/briefing/llm_binding.py`)

- Assinatura: `make_scout_complete(session_factory: async_sessionmaker[AsyncSession], default_timeout_s: float = 30.0)`. Caller-owned `AsyncSession` não mais aceita.
- `scout_complete(system, user, timeout_s=None)`: valida override **antes** de abrir sessão (abort precoce, zero boundary calls).
- Sessão própria curta: `async with session_factory() as session:` → `runtime_settings(session)` + `get_record(session)` → copia escalares imutáveis (`keys`, `models`, `openai_base_url`) → fecha sessão **antes** de `_enforce_safe_transport()` e `litellm.acompletion`.
- Usa scalar `openai_base_url` copiado; nunca toca record detached fora do `async with`.
- Nenhum `commit()`/`rollback()` na sessão do chamador (não existe mais sessão do chamador).
- Preservados: `num_retries=0` + `max_retries=0` (T029), matriz T030, guardrail, `_enforce_safe_transport()`, validação T028 (`bool`/NaN/±inf/zero/negativo/`OverflowError` → `ValueError` fixo; `None` usa default; >30s aceito).

## Mudança de testes (`tests/test_briefing_llm_binding.py`)

- Todos os 23 call sites `SimpleNamespace()` → `_make_fake_session_factory()` (context manager fake com `close` rastreável).
- 3 testes novos:
  1. `test_session_lifecycle_closed_before_network_call` — ordem `session_exit` < `litellm_acompletion`; sem `commit`/`rollback`.
  2. `test_session_factory_never_invoked_on_early_timeout_abort` — factory com `call_count == 0` para overrides inválidos.
  3. `test_integrated_sqlite_settings_read_and_no_spurious_persistence` — SQLite `:memory:` + helpers reais; modelo/chave via `SCOUT_MODEL`/`GEMINI_API_KEY`; após chamada, `select(AppSettings)` retorna 0 linhas (flush transitório revertido pelo close).

## Evidência TDD

- **RED:** 24 testes, `FAILED (failures=1, errors=1)`:
  - `ERROR: test_integrated_sqlite_settings_read_and_no_spurious_persistence` — `AttributeError: 'async_sessionmaker' object has no attribute 'get'` (factory passada como sessão).
  - `FAIL: test_session_lifecycle_closed_before_network_call` — `'session_exit' not found in ['litellm_acompletion']` (sessão nunca aberta/fechada).
- **GREEN:** `Ran 24 tests ... OK` (todas as 21 pré-existentes preservadas + 3 novas).
- `py_compile` ambos arquivos: OK.
- `git diff --check`: OK.

## Comportamentos preservados (verificação)

- T028: `test_default_timeout_validation_overflow_and_invalid`, `test_timeout_override_validation_early_abort_zero_boundary_calls`, `test_valid_timeout_above_30_accepted` — passam sem alteração.
- T029: `test_no_internal_retries_on_503_openai_sdk`, `test_kwargs_include_no_retry_controls` — passam sem alteração.
- T030: todos os testes de matriz/segurança/propagação — passam sem alteração.

## Notas

- Nenhum caller de produção usa `make_scout_complete` fora dos testes (busca confirma único def em `llm_binding.py`); nenhuma migração de caller necessária.
- Não alterados: `app/services/llm.py`, `app/briefing/service.py`, `actions.md`, `progress.jsonl`, `roadmap.md`, `cross-check.md`, `legacy-impact.md`, `regression-watch.md`.
- `todo_list` não chamado (proibição da tarefa).
