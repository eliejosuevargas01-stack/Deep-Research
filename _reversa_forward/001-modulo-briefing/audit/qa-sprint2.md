# QA independente — sprint 2, T009/T016

## Veredito

**PASS restrito ao adapter SERP Jina isolado (T009/T016) e validação local de configuração. Feature NÃO está concluída.** Zero defeitos confirmados neste recorte. Nenhum código de produção, teste existente, action, progress ou auditoria anterior alterado.

Aplicadas lentes de `reversa-depth-inspection`: conformidade, fluxo de dados, contratos, erros, cobertura, concorrência; segurança/configuração como lentes adicionais. Restrição desta missão substitui bootstrap, registro de bugs e views por relatório único; `_reversa_bugs/` ignorado. `delegated-code-delivery` aplicado como gate de evidência, sem aceitar relato anterior como execução própria.

## Pré-checagem e mapa

- Raiz/workdir: `/root/projects/deep-research`; branch `main...origin/main`; HEAD `c741ce77dedfb88d11a8f0916482c721251f112d`.
- Lidos `.reversa/state.json`, `.reversa/active-requirements.json`, `AGENTS.md`, `.reversa/reversa-config.json`, política de execução. Tentativa inicial de `active-requirements.json` na raiz retornou arquivo ausente; caminho correto `.reversa/active-requirements.json` lido antes dos testes. Feature ativa em `coding`; estado global antigo `forward-complete` não prova conclusão.
- Git preflight: `git status --short --branch; git diff --stat; git diff --name-status; git ls-files --others --exclude-standard`, exit 0. Árvore previamente suja, com alterações e deleções alheias; preservada. Adapter/testes são untracked, lidos integralmente. Nenhum commit/push.
- Produto: `requirements.md:32–35,51–60,67–70,155–162`: RF-02, RF-08, RF-10, RN-02; validação de tema de RN-01 como pré-I/O. Âncoras greenfield `_reversa_sdd/prd.md` e `_reversa_sdd/sdd/briefing.md` lidas, sem extração de regras antigas. Auditoria anterior `audit/inspecao-t009-t016.md` apenas referência; evidências abaixo reexecutadas independentemente.

| Camada | Arquivos/símbolos | Contrato/dados |
|---|---|---|
| Adapter | `app/briefing/serp_client.py:11–144`: `ENDPOINT`, `MAX_ATTEMPTS`, `JinaSerpClient.__init__`, `search`, `_single_attempt`, `_parse`, `_valid_url`, `SerpSearchError`, `_AttemptFailed` | POST fixo; JSON `q`; resposta sintética `data[]`; chave somente em memória/header; whitelist; retry e lock local |
| Dependência congelada | `app/briefing/domain.py:27–33`, `validate_theme` | Strip; 3–300 caracteres; ValueError antes de transporte |
| Testes duráveis | `tests/test_briefing_serp_client.py:20–210`, `JinaSerpClientTests` | Dez testes importam adapter de produção e usam MockTransport; nenhum acesso real |
| Regressão local complementar | `tests/test_briefing_domain.py`, `test_briefing_prompt_loader.py`, `test_briefing_schemas.py` | Vinte testes adicionais já existentes; execução somente, sem alterações |
| Dados fora do recorte | Nenhum | Sem tabela, cache de briefing, fila, DB, router, LLM ou frontend exercidos |

## Comandos e saída real

Todos comandos abaixo executados no workdir absoluto acima; Python com `-B`.

| ID | Comando | Exit code | Resultado real |
|---|---|---|---|
| C1 | `python -B -m unittest discover -s tests -p test_briefing_serp_client.py -v` | 0, runner `OK` | `Ran 10 tests in 0.089s`; dez `ok`, nenhum failure/skip |
| C2 | `python -B -m unittest discover -s tests -p "test_briefing_*.py" -v` | 0, runner `OK` | `Ran 30 tests in 0.088s`; trinta `ok`, nenhum failure/skip |
| C3 | `python -B -c '<código completo abaixo>'` | 0 | P1–P8 PASS; saída literal abaixo |
| C4 | `PYTHONPYCACHEPREFIX=/root/.hermes/profiles/orchestrator/cache/scratch/qa-sprint2-pycache python -B -m py_compile app/briefing/serp_client.py tests/test_briefing_serp_client.py && git diff --check` | 0 | Sem saída; compilação e diff-check concluídos |

C1/C2 executados na mesma chamada shell separados por `;`, exit global 0; ambos runners exibiram `OK` independentemente. C4 encadeado com `&&`: exit 0 confirma ambos. Diff-check não verifica arquivos untracked; não substitui leitura/execução do adapter. Nenhuma CI remota alegada.

### Inventário reconciliado dos dez testes duráveis

Todos métodos de `JinaSerpClientTests` abaixo apareceram `ok` em C1 e C2:

1. `test_success_posts_only_to_jina_and_exports_required_fields`
2. `test_retries_sequentially_at_most_four_total_then_succeeds`
3. `test_exhaustion_raises_safe_error_with_real_attempt_count`
4. `test_invalid_json_shape_fields_and_empty_data_fail_safely`
5. `test_invalid_theme_key_and_timeout_fail_before_io`
6. `test_api_key_validation_rejects_non_printable_ascii_control_whitespace_and_non_ascii`
7. `test_timeout_ends_attempt_then_retries_without_long_wait`
8. `test_two_operations_on_same_client_never_overlap`
9. `test_cancellation_propagates_and_releases_lock`
10. `test_redirect_is_not_followed_and_does_not_leak_authorization`

## Matriz critérios de QA

Referências `adapter:L` designam `app/briefing/serp_client.py`; testes numerados remetem ao inventário acima. Probes P1–P8 invocam produção por `search`, não reimplementam parser/cliente.

| Critério | Símbolo de produção | Teste/probe | Comando / exit | Resultado real |
|---|---|---|---|---|
| POST, URL fixa, payload q normalizado, Bearer, Accept/Content-Type JSON, no-content, timeout configurável | `_single_attempt`, `ENDPOINT`, adapter:82–93 | Teste 1; P2 | C1/C3 / 0 | Headers/payload exatos, duas fronteiras válidas; uma chamada por sucesso |
| Sem Reader, fetch de resultado ou redirect, inclusive caller follow_redirects=True | `_single_attempt`, adapter:92; `search` | Teste 10; P4 http_302 | C1/C3 / 0 | Todas URLs observadas `https://s.jina.ai/`; redirect nunca seguido |
| Whitelist title/url/description string não vazia com strip; extras content/usage/publishedTime/tokens descartados | `_parse`, adapter:124–144 | Teste 1; P2/P3 | C1/C3 / 0 | Resultado exatamente EXPECTED; 21 itens inválidos descartados, um conservado |
| URL exige esquema http/https e hostname; lista final vazia retentável | `_valid_url`, `_parse`, `_single_attempt` | Teste 4; P3/P4 all_invalid | C1/C3 / 0 | URLs sem hostname, sem esquema ou esquema impróprio removidas; quatro chamadas no esgotamento |
| Máximo quatro tentativas totais sequenciais em HTTP não-2xx, transporte/timeout, JSON inválido/shape inválido/lista vazia | `search`, `_single_attempt`, `MAX_ATTEMPTS`, adapter:65–105 | Testes 2/3/4/7; P4 | C1/C3 / 0 | Dez classes de falha, cada uma com sucesso nas tentativas 1/2/3/4 e esgotamento em 4: 50 cenários |
| Sucesso interrompe imediatamente, sem chamada extra | `search`, adapter:68 | Testes 1/2; P4 | C1/C3 / 0 | Contagem observada exatamente success_at, de 1 a 4 |
| attempts real e mensagem fixa; str/repr sem chave, corpo, canary ou URL query | `SerpSearchError`, `search`, adapter:18–23,74 | Teste 3; P4 | C1/C3 / 0 | attempts=4; str e repr exatos; canaries excluídos em dez esgotamentos |
| Erros de programação propagam sem retry externo | `_single_attempt`, `search`, adapter:71,116–118 | P5 | C3 / 0 | TypeError e RuntimeError: mesma instância propagada; uma chamada cada |
| Tema 3–300 validado antes de transporte | `search`; `validate_theme` | Teste 5; P1/P2 | C1/C3 / 0 | Seis inválidos sem I/O; fronteiras 3/300 aceitas com strip |
| Token ASCII 33–126, sem espaços/controles, ValueError fixo antes de transporte | `__init__`, adapter:46–50 | Testes 5/6; P1/P2 | C1/C3 / 0 | 39 chaves inválidas rejeitadas; todos 94 caracteres permitidos aceitos juntos |
| Timeout finito positivo e não bool; rejeição antes de transporte | `__init__`, adapter:51–56 | Teste 5; P1 | C1/C3 / 0 | Nove inválidos rejeitados com mensagem fixa; agregado pré-I/O zero chamadas |
| Timeout wall-clock cancela tentativa e retenta | `_single_attempt`, adapter:81,94–95 | Teste 7 | C1 / 0 | Primeira tentativa bloqueada por sleep 0.2; timeout 0.02; segunda sucede, total duas |
| Lock por instância serializa operações concorrentes | `__init__`, `search`, adapter:58,61 | Testes 2/8; P6 | C1/C3 / 0 | Oito operações concorrentes: oito chamadas, max_active=1 |
| CancelledError propaga, lock libera, próxima operação funciona | `search`, `_single_attempt`, adapter:61,69–70,114–115 | Teste 9; P7 | C1/C3 / 0 | Cancelamento observado; operação seguinte sucede; total duas chamadas |
| Cliente injetado permanece aberto em sucesso/falha/cancelamento/programação | `_single_attempt`, adapter:77–78,119–121 | Teste 1; P2/P4/P5/P7 | C1/C3 / 0 | is_closed=False antes de saída do contexto caller |
| Cliente interno fechado após tentativa/operação | `_single_attempt`, adapter:77–78,119–121 | P8 | C3 / 0 | Um cliente criado no sucesso e quatro no esgotamento; todos fechados |

## Probes complementares reproduzíveis

Fixtures **sintéticas**, não fixture oficial nem observação do SaaS. Chaves/canaries fictícios. Nenhum segredo ou `.env` lido. C3 foi executado inline com `python -B -c`, com o código integral abaixo. Para reproduzir sem shell quoting complexo, extrair bloco Python e executar via stdin `python -B` no workdir indicado; patch preserva `RealClient` antes de substituir factory, evitando atingir a factory da própria probe. Nenhum arquivo de probe foi criado no repositório.

```python
import asyncio
import json
import httpx
from unittest.mock import patch
from app.briefing.serp_client import JinaSerpClient, SerpSearchError

RealClient = httpx.AsyncClient
KEY = "SYNTHETIC-KEY-CANARY"
SENSITIVE = "SYNTHETIC-BODY-QUERY-CANARY"
GOOD = {"title": " title ", "url": " https://example.org/path ", "description": " snippet ",
        "content": SENSITIVE, "usage": {"tokens": 99}, "publishedTime": SENSITIVE, "tokens": 99}
EXPECTED = [{"title": "title", "url": "https://example.org/path", "description": "snippet"}]

def response():
    return httpx.Response(200, json={"data": [GOOD]})

async def main():
    seen = []
    def handler(r):
        seen.append(r)
        return response()
    async with RealClient(transport=httpx.MockTransport(handler), follow_redirects=True) as http:
        invalid_keys = [None, 123, ""] + ["key" + chr(i) for i in range(33)] + ["key" + chr(i) for i in (127, 160, 233)]
        for key in invalid_keys:
            try:
                JinaSerpClient(key, http_client=http)
            except ValueError as e:
                assert str(e) == "Chave de API inválida"
            else:
                raise AssertionError("invalid key accepted")
        bad_timeouts = [True, False, None, "30", 0, -1, float("nan"), float("inf"), float("-inf")]
        for timeout in bad_timeouts:
            try:
                JinaSerpClient(KEY, timeout=timeout, http_client=http)
            except ValueError as e:
                assert str(e) == "Timeout inválido"
            else:
                raise AssertionError("invalid timeout accepted")
        for theme in [None, 123, "", "  ", "ab", "x" * 301]:
            try:
                await JinaSerpClient(KEY, http_client=http).search(theme)
            except ValueError:
                pass
            else:
                raise AssertionError("invalid theme accepted")
        assert len(seen) == 0
        print("P1 invalid keys=39 timeouts=9 themes=6 transport_calls=0 PASS")
        for theme in [" abc ", "x" * 300]:
            assert await JinaSerpClient("".join(map(chr, range(33, 127))), timeout=0.5, http_client=http).search(theme) == EXPECTED
            r = seen[-1]
            assert r.method == "POST" and str(r.url) == "https://s.jina.ai/"
            assert json.loads(r.content) == {"q": theme.strip()}
            assert r.headers["authorization"] == "Bearer " + "".join(map(chr, range(33, 127)))
            assert r.headers["accept"] == r.headers["content-type"] == "application/json"
            assert r.headers["x-respond-with"] == "no-content"
            assert all(v == 0.5 for v in r.extensions["timeout"].values())
        assert len(seen) == 2 and not http.is_closed
        print("P2 HTTP whitelist bounds=3,300 printable_ascii=94 calls=2 caller_open PASS")

    invalid = [None, {}, 123]
    for field in ("title", "url", "description"):
        for value in (None, 1, "", "  "):
            invalid.append({**GOOD, field: value})
    for url in ("javascript:alert(1)", "ftp://example.org", "//example.org", "https:///path", "https://", "http://[bad"):
        invalid.append({**GOOD, "url": url})
    async with RealClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"data": invalid + [GOOD]}))) as http:
        assert await JinaSerpClient(KEY, http_client=http).search("abc") == EXPECTED
    print("P3 mixed parser invalid_items=21 kept=1 strip extras_discarded PASS")

    failures = [("http_302", lambda r: httpx.Response(302, headers={"location": "https://attacker.invalid/"})),
                ("http_503", lambda r: httpx.Response(503, text=SENSITIVE)),
                ("json_invalid", lambda r: httpx.Response(200, text=SENSITIVE)),
                ("shape_array", lambda r: httpx.Response(200, json=[])),
                ("shape_missing", lambda r: httpx.Response(200, json={})),
                ("shape_data_object", lambda r: httpx.Response(200, json={"data": {}})),
                ("empty", lambda r: httpx.Response(200, json={"data": []})),
                ("all_invalid", lambda r: httpx.Response(200, json={"data": invalid}))]
    def connection(r):
        raise httpx.ConnectError(SENSITIVE + " https://example.org/?q=" + SENSITIVE, request=r)
    def timeout(r):
        raise httpx.ReadTimeout(SENSITIVE, request=r)
    failures += [("connect", connection), ("read_timeout", timeout)]
    for label, failure in failures:
        for success_at in (1, 2, 3, 4, None):
            calls = []
            def attempt(r):
                calls.append(r)
                return response() if len(calls) == success_at else failure(r)
            async with RealClient(transport=httpx.MockTransport(attempt), follow_redirects=True) as http:
                try:
                    result = await JinaSerpClient(KEY, http_client=http).search(SENSITIVE)
                except SerpSearchError as e:
                    assert success_at is None and e.attempts == len(calls) == 4
                    assert str(e) == "Busca SERP indisponível após 4 tentativas"
                    assert repr(e) == "SerpSearchError('Busca SERP indisponível após 4 tentativas')"
                    for secret in (KEY, SENSITIVE, "https://example.org/?q="):
                        assert secret not in str(e) + repr(e)
                else:
                    assert success_at is not None and result == EXPECTED
                assert len(calls) == (success_at or 4)
                assert all(str(r.url) == "https://s.jina.ai/" for r in calls)
                assert not http.is_closed
        print("P4", label, "success_at=1,2,3,4 exhaustion=4 fixed_str_repr PASS")

    for kind in (TypeError, RuntimeError):
        calls = []
        error = kind("synthetic programming error")
        def programming(r):
            calls.append(r)
            raise error
        async with RealClient(transport=httpx.MockTransport(programming)) as http:
            try:
                await JinaSerpClient(KEY, http_client=http).search("abc")
            except kind as e:
                assert e is error
            else:
                raise AssertionError("programming error swallowed")
            assert len(calls) == 1 and not http.is_closed
    print("P5 TypeError RuntimeError identity_preserved calls=1 each PASS")

    active = maximum = calls = 0
    async def concurrent(r):
        nonlocal active, maximum, calls
        active += 1
        maximum = max(maximum, active)
        calls += 1
        try:
            await asyncio.sleep(0)
            return response()
        finally:
            active -= 1
    async with RealClient(transport=httpx.MockTransport(concurrent)) as http:
        client = JinaSerpClient(KEY, http_client=http)
        assert await asyncio.gather(*(client.search("abc") for _ in range(8))) == [EXPECTED] * 8
    assert maximum == 1 and calls == 8
    print("P6 same_instance operations=8 max_active=1 PASS")

    started = asyncio.Event()
    calls = 0
    async def cancel(r):
        nonlocal calls
        calls += 1
        if calls == 1:
            started.set()
            await asyncio.Event().wait()
        return response()
    async with RealClient(transport=httpx.MockTransport(cancel)) as http:
        client = JinaSerpClient(KEY, http_client=http)
        task = asyncio.create_task(client.search("abc"))
        await asyncio.wait_for(started.wait(), 1)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        else:
            raise AssertionError("cancellation swallowed")
        assert await asyncio.wait_for(client.search("abc"), 1) == EXPECTED
        assert calls == 2 and not http.is_closed
    print("P7 cancellation propagates lock_released calls=2 PASS")

    for fail in (False, True):
        owned = []
        def factory():
            client = RealClient(transport=httpx.MockTransport(lambda r: httpx.Response(503) if fail else response()))
            owned.append(client)
            return client
        with patch("app.briefing.serp_client.httpx.AsyncClient", side_effect=factory):
            try:
                assert await JinaSerpClient(KEY).search("abc") == EXPECTED
            except SerpSearchError:
                assert fail
        assert len(owned) == (4 if fail else 1) and all(c.is_closed for c in owned)
    print("P8 owned_clients success=1 failure=4 all_closed PASS")

asyncio.run(main())
```

Saída literal C3:

```text
P1 invalid keys=39 timeouts=9 themes=6 transport_calls=0 PASS
P2 HTTP whitelist bounds=3,300 printable_ascii=94 calls=2 caller_open PASS
P3 mixed parser invalid_items=21 kept=1 strip extras_discarded PASS
P4 http_302 success_at=1,2,3,4 exhaustion=4 fixed_str_repr PASS
P4 http_503 success_at=1,2,3,4 exhaustion=4 fixed_str_repr PASS
P4 json_invalid success_at=1,2,3,4 exhaustion=4 fixed_str_repr PASS
P4 shape_array success_at=1,2,3,4 exhaustion=4 fixed_str_repr PASS
P4 shape_missing success_at=1,2,3,4 exhaustion=4 fixed_str_repr PASS
P4 shape_data_object success_at=1,2,3,4 exhaustion=4 fixed_str_repr PASS
P4 empty success_at=1,2,3,4 exhaustion=4 fixed_str_repr PASS
P4 all_invalid success_at=1,2,3,4 exhaustion=4 fixed_str_repr PASS
P4 connect success_at=1,2,3,4 exhaustion=4 fixed_str_repr PASS
P4 read_timeout success_at=1,2,3,4 exhaustion=4 fixed_str_repr PASS
P5 TypeError RuntimeError identity_preserved calls=1 each PASS
P6 same_instance operations=8 max_active=1 PASS
P7 cancellation propagates lock_released calls=2 PASS
P8 owned_clients success=1 failure=4 all_closed PASS
```

## Achados por lente e recomendações

- Conformidade, fluxo de dados, contratos, erros e concorrência: zero defeitos confirmados nas execuções acima. Sem cluster causal de defeitos.
- Cobertura — observação LOW, confiança alta, `promoted_to: null`: testes duráveis passam; ownership interno, TypeError/RuntimeError e matriz ampliada de shapes/configuração foram cobertos por probes reproduzíveis, não acrescentados à suíte durável. Converter subset em testes duráveis somente em tarefa futura autorizada; não alterar dez testes congelados neste QA.
- Segurança — observação LOW, confiança alta, `promoted_to: null`: str/repr públicos seguros; `raise SerpSearchError(...) from last_failure` preserva cadeia interna. Esta probe não sanitiza nem valida traceback/log/HTTP sink. Routers e logs futuros devem serializar somente mensagem/attempts permitidos, nunca exception chain, headers, request, response body ou tema. Adicionar testes de canary nesses sinks antes de integrar.
- Próximas fases: validar orquestração real, reuso de SERP após falha LLM, compartilhamento da instância/lock, erros HTTP seguros e persistência na implementação autorizada correspondente. PASS local não fecha esses critérios.

## Limites explícitos

- Sem rede real/Jina SaaS: não comprovados auth real, formato hospedado, SLA, motor exclusivo ou comportamento interno do provedor. `X-Respond-With: no-content` e ausência de fetch adicional comprovados somente no contrato local emitido pelo adapter.
- Lock asyncio por instância apenas; ausência de lock cross-process, coordenação multiworker ou garantia global entre instâncias. Não testada integração que compartilha instância.
- LLM/service/router HTTP/DB/cache de briefing/frontend/deploy NÃO testados nem implementados. Nenhuma migração, commit ou push.
- Timeout local cobre POST; não prazo global incluindo fila do lock/criação/fechamento do cliente. Probes usam MockTransport, não transporte HTTP real.
- Suíte local briefing: 30 testes; não suíte inteira/legado, CI remota ou aceite end-to-end. Código antigo e bugs legados não usados como verdade de produto.
- Relatório único gravável: `_reversa_forward/001-modulo-briefing/audit/qa-sprint2.md`. Pycache explícito em scratch, fora do repo. Estado/progress/actions permanecem congelados.
