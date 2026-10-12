# Execução T025/T026 — router HTTP de briefing

## Resultado

Implementação concluída conforme prescrição vigente em `interfaces/briefing-http.md` e `audit/t025-t026-planning-delta.md`. Router inclui sete operações canônicas, autenticação real `require_admin`, sessão isolada para configuração SERP/LLM e orquestração síncrona real com fakes somente nas fronteiras de I/O dos testes. Nenhum alias `/api/briefings`.

## TDD e verificações executadas

- **RED observado antes da implementação do router:** `python3 -B -m unittest tests.test_briefing_api -v` terminou com 6 erros, `ModuleNotFoundError`/router ausente. Esse foi o estado observado; arquivo de execução não preserva o log integral.
- **GREEN focado:** `python3 -B -m unittest tests.test_briefing_api -v` — exit 0; 11 testes, `OK`.
- **Suíte briefing:** `python3 -B -m unittest discover -s tests -p 'test_briefing*.py'` — exit 0; 172 testes, `OK`.
- **Sintaxe:** `PYTHONPYCACHEPREFIX=$TMPDIR/pyc python3 -m py_compile app/briefing/router.py app/main.py tests/test_briefing_api.py` — exit 0 (`PY_COMPILE_OK`).
- **Whitespace:** `git diff --check` — exit 0 (`DIFF_CHECK_OK`).
- **Import:** `python3 -B -c "import app.main; print('IMPORT_OK')"` — exit 0 (`IMPORT_OK`); import não inicia lifespan.

A descoberta de rotas expõe implementação FastAPI via `_IncludedRouter` (versão instalada adia expansão em `app.routes`); roteamento foi exercitado via `httpx.ASGITransport`, não inferido de listagem superficial de `app.routes`.

## Matriz rota → teste executado

| Rota | Teste(s) | Resultado exercitado |
|---|---|---|
| `POST /briefings` | `test_create_sync_returns_persisted_draft_and_reuses_serp`, `test_create_invalid_rejected_before_generation`, `test_generation_errors_are_safe_and_persisted`, `test_configuration_errors_map_to_generic_500`, `test_unknown_orchestration_error_propagates` | 201, persistência/versionamento, uma chamada SERP/LLM com orchestration real, 422 sem criação/I/O, estados FAILED e mensagens fixas, falhas de configuração/upstream sem segredo, erro inesperado propaga. |
| `GET /briefings/{id}` | `test_auth_real_dependency_cookie_csrf_bearer_and_api_key`, `test_missing_and_unapproved_errors_preserve_and_external_io_zero` | 200, auth por bearer/API key, 404 ausente. |
| `PATCH /briefings/{id}` | `test_auth_real_dependency_cookie_csrf_bearer_and_api_key`, `test_read_edit_approve_reopen_approved_and_versions`, `test_cas_conflict_maps_409_and_preserves_history`, `test_missing_and_unapproved_errors_preserve_and_external_io_zero` | Cookie+CSRF, sucesso e versão incrementada, 422 sem mutação, 409 estado/CAS com snapshot e histórico preservados, 404 ausente. |
| `POST /briefings/{id}/approve` | `test_read_edit_approve_reopen_approved_and_versions`, `test_rejected_bodies_do_not_mutate_state`, `test_missing_and_unapproved_errors_preserve_and_external_io_zero` | Aprovação, `approved_at`, corpos omitido/null/`{}` aceitos; tipos inválidos 422 sem alteração; ausente 404. |
| `POST /briefings/{id}/reopen` | mesmos testes de approve/reopen | Reabertura, `approved_at=null`; corpos inválidos 422 sem alteração; ausente 404. |
| `GET /briefings/approved/{id}` | `test_read_edit_approve_reopen_approved_and_versions`, `test_missing_and_unapproved_errors_preserve_and_external_io_zero` | Payload publicado, 409 não aprovado, 404 ausente, zero chamada SERP/LLM. |
| `GET /briefings/{id}/versions` | `test_read_edit_approve_reopen_approved_and_versions`, `test_missing_and_unapproved_errors_preserve_and_external_io_zero` | ASC, sem `briefing_id`, `created_at`, pai ausente 404, `generating` v1 produz lista vazia. |

Autenticação exercitada com dependência real: 401 sem credencial; 403 sem CSRF e com CSRF inválido; cookie+CSRF, bearer e X-API-Key aceitos. Testes usam SQLite em memória, sem rede externa, credenciais/provider reais ou lifespan legado.

## Arquivos alterados/criados

- `app/briefing/router.py` — novo router com 7 rotas, validação de body, auth/rollback, chamadas de domínio/storage/service e tradução tipada de erros.
- `app/main.py` — import e `app.include_router(briefing_router)`.
- `tests/test_briefing_api.py` — 11 testes unittest/ASGI isolados, autenticação real e orquestração com I/O fake.
- `_reversa_forward/001-modulo-briefing/audit/t025-t026-execution.md` — este registro factual.

## Limites

- `git status` contém outros arquivos briefing preexistentes/não rastreados fora do escopo; não foram editados nesta entrega. Nenhum commit, push, deploy ou migração de DB real.
- Nenhum teste chama runtime real Jina/LiteLLM; não se afirma validação de runtime real dos provedores.
- Este registro não equivale à aprovação de auditoria independente. Gates T012/T013 permanecem abertos conforme instrução de execução.
