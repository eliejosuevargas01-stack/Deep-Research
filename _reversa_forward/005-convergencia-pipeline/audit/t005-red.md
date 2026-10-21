# T005 — autoria RED coleta/parser

Execução final: **20 failed, 11 passed**, pytest exit **1**, 0.85s. Arquivo único selecionado: `tests/investigation/test_jina_tool.py` (e `tests/investigation/conftest.py` como fixture). Nenhum node investigation coletado/lido; nenhum DB conectado. Produto sem alteração. Evidência autoral, não aprovação independente; pai mantém actions/progress/estado.

## Contrato exercitado

Imports e chamadas reais a `JinaToolAdapter`, `JinaSearchResult`, `JinaSearchError`, `_parse_body`, `ENDPOINT` e fixtures `make_jina_mock_transport`, `sample_jina_items` de `app.investigation.tools`. Nenhuma assinatura futura inventada. `sample_jina_items` é fixture representativa de 10 itens; `ENDPOINT` verdadeiro (`https://s.jina.ai/`); `JinaSearchError` e `_parse_body` são produtos reais. Requests simulados via `httpx.MockTransport` interceptam na camada de transporte sem rede real. LiteLLM não carregado; DB em memória apenas para smoke.

## Nodes e bloqueio

Prefixo de todos nodes: `tests/investigation/test_jina_tool.py::`.

| Node | RF/RN | Resultado / primeiro bloqueio real |
|---|---|---|
| test_jina_search_success_direct_contract_and_payload | RF-06/RN-05 | FAIL: `sent_payload` sem `"num": 10` — produtor omite campo `num` |
| test_jina_search_with_proxy_configuration | RF-06/RN-05 | FAIL: `sent_payload` sem `"num": 10` |
| test_jina_search_proxy_without_proxy_key_falls_back_to_api_key | RF-06/RN-05 | PASS: fallback api_key no proxy; caractorização |
| test_jina_search_timeout_parameter_and_enforcement | RN-07/RF-06 | PASS: timeout 90s default e customizado aplicados |
| test_jina_search_retries_transient_failure_then_success | RN-07/RF-08 | PASS: 429 + ConnectError + 200 — 3 tentativas, backoff 2.0s/4.0s |
| test_jina_search_retry_after_header_respected | RN-07/RF-08 | PASS: Retry-After: 1 respeitado no delay |
| test_jina_search_exhaustion_raises_jina_search_error_no_secret_leak | RN-07/RF-08 | PASS: JinaSearchError(3), secrets não vazam em str/repr/traceback |
| test_jina_search_recursive_url_extraction_and_deduplication | RF-06/RN-08 | PASS: URL recursiva não promovida a corpo; deduplicação preservada |
| test_jina_search_input_validations | RF-06/RN-05 | PASS: api_key vazia/None/espaços; timeout 0/-10/True/NaN; proxy_url vazia; query vazia/None — todos rejeitados |
| test_jina_search_non_retryable_client_error | RF-08 | PASS: 400 não-429 não executa retries, JinaSearchError(1) |
| test_jina_search_malformed_json_retries_then_succeeds | RF-08 | PASS: JSON inválido → _AttemptFailed → retry → sucesso |
| test_jina_search_timeout_error_exhaustion | RN-07/RF-08 | PASS: 3 ReadTimeout → JinaSearchError(3) |
| test_database_fixtures_smoke_test | RF-501 | PASS: SQLite em memória; Research/DomainModels ORM reais |
| test_conftest_litellm_mock_fixtures | T005 | PASS: mocks LiteLLM tool-call e final response validam JinaSearchArgs e PersonaResultPayload |
| test_jina_ten_complete_bodies_keep_attribution | RF-501 | FAIL: `item["title"]` / `item["url"]` não encontrados no `section` entre corpos — atribuição não associada no formato de atribuição esperado |
| test_jina_html_cleaning_preserves_useful_body | RF-501/RN-08 | FAIL: ruído HTML (`HEADER_NOISE`, `NAV_NOISE`, `SCRIPT_NOISE`, `STYLE_NOISE`, `AD_NOISE`, `FOOTER_NOISE`) e tag `<article>` permanecem em `result.content` |
| test_jina_incomplete_collection_fails_safe | RF-501 | FAIL: 4/4 sub-casos (`nine`, `missing-body`, `inaccessible`, `snippets-only`) não levantam `JinaSearchError` — coleta incompleta não falha safe |
| test_jina_unsafe_source_url_fails_safe | RN-08 | FAIL: 7/7 URLs perigosas não levantam `JinaSearchError` — SSRF não falha safe |
| test_parse_body_does_not_promote_snippets_or_recursive_urls | RF-501/RN-08 | FAIL: `_parse_body` não levanta `JinaSearchError` — snippets e URLs recursivas promovidos indevidamente a corpo |
| test_stdlib_parser_keeps_tail_beyond_input_slice | RN-08 | FAIL: `_safe_html_to_text` corta conteúdo útil (`END_AFTER_200000`) em vez de preservar cauda além de 100k chars |

## Regressões preservadas (11 passed)

Retries (429, ConnectError), Retry-After header, timeout (default 90s + customizado), non-retryable 4xx (400), malformed JSON recovery, timeout exhaustion, recursive URL deduplication, input validations (api_key/timeout/proxy/query), secret leak guard, LiteLLM conftest mocks, SQLite fixture smoke test. Nenhuma regressão introduzida.

## Achados RED detalhados

1. **sent_payload sem `"num": 10`**: Produtor (`JinaToolAdapter.search`) omite campo `num` no JSON enviado ao endpoint. Contrato exige `{"q": query, "num": 10}`. Afeta `test_jina_search_success_direct_contract_and_payload` e `test_jina_search_with_proxy_configuration`.

2. **Atribuição não associada ao corpo**: Em `test_jina_ten_complete_bodies_keep_attribution`, `item["title"]` e `item["url"]` não aparecem no `section` entre posições de corpos adjacentes. Formato de atribuição (título/URL/query associados por atribuição) quebrado.

3. **Ruído HTML não removido**: Em `test_jina_html_cleaning_preserves_useful_body`, todos os ruídos (`header`, `nav`, `script`, `style`, `aside.advertisement`, `footer`) e tags `<article>` permanecem em `result.content`. Limpeza de HTML não implementada ou ineficaz.

4. **Coleta incompleta não falha safe**: Em `test_jina_incomplete_collection_fails_safe`, sub-casos (`nine` — <10 corpos, `missing-body` — campo `content` ausente, `inaccessible` — status 403, `snippets-only` — apenas snippets) não levantam `JinaSearchError`. Falha safe de coleta não implementada.

5. **URLs inseguras/SSRF não falham safe**: Em `test_jina_unsafe_source_url_fails_safe`, 7 URLs proibidas (`file:///etc/passwd`, `ftp://`, `127.0.0.1`, `169.254.169.254` (metadata), `::1`, `10.0.0.1`, `localhost`, credenciais na URL) não rejeitadas pelo parser/adapter. Validação SSRF ausente.

6. **Snippets e URLs recursivas promovidos a corpo**: Em `test_parse_body_does_not_promote_snippets_or_recursive_urls`, `_parse_body` não levanta `JinaSearchError` quando itens têm apenas `snippet` + `metadata.url` (sem `content`). Snippets e URLs recursivas são promovidos indevidamente ao corpo.

7. **Parser stdlib corta cauda útil**: Em `test_stdlib_parser_keeps_tail_beyond_input_slice`, `_safe_html_to_text(raw, max_chars=len(raw))` retorna string onde `END_AFTER_200000` (posição >200000 no input) é cortada. Parser usa slice de 100k chars em vez de preservar cauda útil.

## Observações

- MockTransport intercepta na camada de transporte; não prova resolução DNS, pinning ou proxy real (limitação documentada no próprio teste `test_jina_unsafe_source_url_fails_safe`).
- DB conectado apenas para smoke test SQLite; nenhum DB real.
- LiteLLM mocks validam contrato de schemas (`JinaSearchArgs`, `PersonaResultPayload`) mas não chamadas reais.
- 20 falhas são de produto (não de harness); 11 passes são de caracterização/regresso.

## Comando completo reproduzível

Raiz `/root/projects/deep-research`; comando final realmente executado, exit 1 esperado.

```bash
cd /root/projects/deep-research
python -B - <<'PY'
import os, sys, base64, secrets, pytest
os.environ.update(ENVIRONMENT='test', DATABASE_URL='sqlite+aiosqlite:///:memory:', ADMIN_PASSWORD=secrets.token_urlsafe(32), SESSION_SECRET=secrets.token_urlsafe(48), API_AUTH_SECRET=secrets.token_urlsafe(32), APP_ENCRYPTION_KEY=base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(), PYTEST_DISABLE_PLUGIN_AUTOLOAD='1', PYTHONDONTWRITEBYTECODE='1')
rc = pytest.main(['-q', '--assert=plain', '-p', 'no:cacheprovider', '-p', 'anyio.pytest_plugin', 'tests/investigation/test_jina_tool.py'])
print('TOTAL RC:', rc)
PY
```

Sem install, stack, API externa, DB real, migration, git mutável ou teste live. Restante: revisão independente e GREEN T007/T008; não marcar T005 como aprovado com esta autoria.