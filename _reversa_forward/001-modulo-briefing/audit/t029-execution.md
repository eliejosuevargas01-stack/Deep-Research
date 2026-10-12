# T029 — Desativar retries internos SDK (F-CONTRACT-01)

## Objetivo
`make_scout_complete(db)` deve passar `num_retries=0` E `max_retries=0` nos kwargs de `litellm.acompletion`.
Diferença mínima de dois controles; todos os demais comportamentos preservados (assinatura, default_timeout_s, callable timeout_s, guardrail, provider/model/auth).

## Implementação
- `app/briefing/llm_binding.py` (~linha 81-85): adicionados `"num_retries": 0` e `"max_retries": 0` ao dict `kwargs` de `make_scout_complete`, com comentário F-CONTRACT-01 / RF-10.

## TDD (vertical, backend-low, leaf)

### RED — antes do kwargs
Comando:
`python3 -B -m unittest tests.test_briefing_llm_binding.BindingTests.test_no_internal_retries_on_503_openai_sdk tests.test_briefing_llm_binding.BindingTests.test_kwargs_include_no_retry_controls -v`
Resultado: exit 1, `FAILED (failures=2)`:
- `test_no_internal_retries_on_503_openai_sdk`: `AssertionError: 3 != 1 : Expected 1 HTTP request, got 3`
- `test_kwargs_include_no_retry_controls`: `AssertionError: None != 0`

### GREEN — após adicionar os dois kwargs
Mesmo comando: exit 0, `OK` (2 tests).

Nota HISTÓRICO: as seções "TDD" RED/GREEN e "Detalhes do teste RED" (incluindo a alegação de `_enforce_safe_transport` patchado) são auto-relato histórico do worker; traceback original parcial, não autenticado. Evidência factual vigente é a seção "Validação factual atual (auditor report)" abaixo; a contraprova do auditor é probe novo, distinto da história RED.

## Verificações (ordem exigida)
1. Métodos específicos RED/GREEN via unittest — OK (RED failures=2; GREEN OK).
2. Módulo binding completo: `python3 -B -m unittest tests.test_briefing_llm_binding -v` → `Ran 12 tests ... OK` (10 baseline + 2 novos; nenhum método removido ou pulado).
3. Suite briefing discover: `python3 -B -m unittest discover -s tests -p 'test_briefing_*.py'` → `Ran 128 tests ... OK` (126 baseline + 2 novos).
4. py_compile (PYTHONPYCACHEPREFIX=/root/.hermes/profiles/orchestrator/cache/scratch/briefing-verify-pycache) em `app/briefing/llm_binding.py` e `tests/test_briefing_llm_binding.py` → exit 0.
5. `git diff --check` → exit 0, sem whitespace errors.

## Detalhes do teste RED
- Teste `test_no_internal_retries_on_503_openai_sdk` chama a factory/callable PRODUÇÃO `make_scout_complete` + `litellm.acompletion` real (sem substituir acompletion), com `BaseOpenAILLM._get_async_http_client` patchado para `httpx.AsyncClient` com `MockTransport` retornando HTTP 503 (`follow_redirects=False`), `_enforce_safe_transport` patchado, `runtime_settings`/`get_record` patchados via fixture (sem env/keys reais), contexto fecha o client. Conta requests de transporte: RED=3 (SDK retry interno), GREEN=1.
- Teste `test_kwargs_include_no_retry_controls` verifica `num_retries=0` e `max_retries=0` no mock de happy path (AsyncMock), sem enfraquecer asserts existentes.

## Limites
- Cenário OpenAI só prova SDK instalado (litellm 1.104.0 / openai 2.54.0 / httpx 0.28.1) + mock 503; não prova todos os providers.
- Timeout override >30s continua funcionando (`test_valid_timeout_above_30_accepted` OK).
- T030 (matriz de erros) e T031 (factory session ownership) NÃO executados nesta rodada — dependências abertas; API/QA/provedores não aprovados.

## Validação factual atual (auditor report)
- **Teste SDK executa helper REAL `_enforce_safe_transport`**: `test_no_internal_retries_on_503_openai_sdk` invoca `make_scout_complete` + `litellm.acompletion` real (sem substituir acompletion), com `BaseOpenAILLM._get_async_http_client` patchado para `httpx.AsyncClient` + `MockTransport` HTTP 503 (`follow_redirects=False`), `_enforce_safe_transport` **não** patchado (helper real executado), `runtime_settings`/`get_record` patchados via fixture. Assert: `assertRaises(LLMAttemptError)` + count 1 request transporte.
- **Contraprova auditor**: wrapper runtime removendo ambos kwargs `num_retries=0` e `max_retries=0` (delegando ao `acompletion` real sem controles) observou **3 requests** e teste falhou internamente com `AssertionError: 3 != 1` (1 esperado). Processo do probe **exit 0** (assert de contraprova esperada); unittest interno **FAILED (failures=1)**. Não relatar exit 1 do processo.
- **Checks auditor**: 2 focados + 12 módulo binding **exit 0**; discover 128 reportado pelo parent **NÃO executado** pelo auditor.
- **Resultado auditor**: Produto **PASS** no recorte OpenAI 503; Evidência **CONDITIONAL** (isolamento estado alternativo incompleto, proveniência histórica RED limitada); Processo **CONDITIONAL** (relato helper e W020 demandam revisão documental futura). T029 continua aberta; QA sequencial posterior e T030/T031 não aprovados por este relatório.
- **T032** implementará cleanup (O-TEST-01 redirects cleanup); **não afirmar aprovado ou concluído antes de prova**.
- **Limitações**: OpenAI 503 / SDK instalado, não todos providers; rede/DB/QA não executados. Não inventar resultados/source snippets/keys.
- **Linha 25 arquivo físico**: `python3 -B -c` com leitura física linha 25 retornou `execution_line25_backslash_count 0`, exit **0**. Contradiz nota de contexto do parent que alegava barras antes de aspas; baseline SHA do documento coincide. Não registrar inexistente defeito de escape nem corrigir documento. Comando discover já correto — não tentar corrigir.
