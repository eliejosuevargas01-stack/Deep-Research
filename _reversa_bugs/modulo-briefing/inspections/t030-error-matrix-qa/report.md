# QA focada pós-auditoria — T030 (Matriz de erros e segurança da exceção)

## Veredito
**PASS_LOCAL**. 21/21 métodos em `tests/test_briefing_llm_binding.py` passaram com exit 0 (1 sync, 20 async; zero skips ou testes enfraquecidos). Execução independente da matriz de classificação em runtime simulado sem rede externa validou 21 casos elegíveis (todos convertidos em `LLMAttemptError` com mensagem fixa `"Geração de briefing indisponível"` e sem vazamento de segredos em `str`, `repr(args)`, `__cause__`, `__suppress_context__` e traceback), 19 casos negativos (todos propagados com a mesma identidade de exceção, sem máscara), 13 validações de status estrito em `_real_status_code` (rejeição de bool, strings e float), e manutenção do comportamento T029 (1 request HTTP 503 e restauração completa de redirecionamentos em clientes globais). Integridade de 99/99 arquivos congelados da linha 71 do `progress.jsonl` confirmada (zero mismatches). Zero defeitos de produto confirmados; zero bugs promovidos (`promoted_to: null`).

## Preflight e mapa aceitação → símbolo → checks
Root `/root/projects/deep-research`, branch `main`; worktree com alterações pré-existentes não commitadas mantidas intactas. Preflight validado: `AGENTS.md`, `.reversa/state.json`, `.reversa/active-requirements.json`, `.reversa/reversa-config.json`. Feature ativa: `_reversa_forward/001-modulo-briefing` em estágio `coding`. Relatório de inspeção prévia `../t030-error-matrix/report.md` aprovou o produto com veredito CONDITIONAL e zero defeitos promovidos.

| Aceitação | Fonte / símbolo | Check próprio |
|---|---|---|
| RF-08 / T030: Matriz concreta de erros elegíveis | `requirements.md:58`, `actions.md:84`; `app/briefing/llm_binding.py:46–86` (`_is_eligible_llm_error`) | 21 casos elegíveis instanciados e executados contra `make_scout_complete`: LiteLLM (`APIConnectionError`, `Timeout`, `InternalServerError`, `RateLimitError`, `ServiceUnavailableError`), `APIError` (429, 500, 502, 503, 504), HTTPX transporte (ConnectError, ConnectTimeout, ReadTimeout, WriteTimeout, PoolTimeout), `HTTPStatusError` (429, 500, 502, 503, 504) e `TimeoutError` nativo viram `LLMAttemptError` com mensagem fixa e `await_count == 1`. |
| RF-08: Exceção segura e sanitização de credenciais | `requirements.md:58`; `app/briefing/service.py:23–28` (`LLMAttemptError`), `app/briefing/llm_binding.py:152–155` | 21 casos elegíveis com sentinela secreta nos argumentos/corpo: asserts dentro de `except` ativo validam `sentinel not in str(caught)`, `sentinel not in repr(caught.args)`, `caught.__cause__ is None`, `caught.__suppress_context__ is True` e `sentinel not in "".join(traceback.format_exception(caught))`. |
| RF-08 / D5: Casos negativos propagam identidade real | `audit/t011-integration-decomposition.md:112–120`, `audit/t029-t031-planning-delta.md:21–30`; `app/briefing/llm_binding.py:72–86` | 19 casos negativos (`AuthenticationError`, `PermissionDeniedError`, status 401/403, `ProviderConfigurationError`, `BadRequestError`, `RuntimeError`/`TypeError` arbitrários e `RuntimeError` com `status_code=503`) propagam com a **mesma identidade** de objeto (`caught is exc`), sem máscara. |
| RF-08: Status estrito rejeita tipos espúrios | `app/briefing/llm_binding.py:34–43` (`_real_status_code`) | 13 verificações de tipo: `True`, `False`, `"503"`, `503.0`, `None`, `"429"` retornam `None`; inteiros numéricos canônicos (429, 500, 502, 503, 504, 401, 403, 418) retornam o int. |
| Manutenção T029: 503 OpenAI count 1 e isolamento | `tests/test_briefing_llm_binding.py:410–472` (`test_no_internal_retries_on_503_openai_sdk`) | Execução do método unitário com flags globais `follow_redirects` semeadas em `True`: exatamente 1 request HTTP 503 disparado, captura de `LLMAttemptError` e restauração exata das flags dos clientes globais. |
| Preservação de suíte e baseline | `tests/test_briefing_llm_binding.py` | 21 métodos (1 sync, 20 async) executados via `unittest -v`: todos passam, exit 0, nenhum teste pulado ou enfraquecido. |
| Integridade dos congelamentos | `_reversa_forward/001-modulo-briefing/progress.jsonl:71` (`pre_dispatch_sha256`) | 99/99 hashes SHA-256 verificados contra o disco; zero discrepâncias. `git diff --check` exit 0. |

## Execução própria e resultados factuais

### 1. Suíte unitária do binding
Comando: `python3 -B -m unittest tests.test_briefing_llm_binding -v` (cwd: `/root/projects/deep-research`)
- Exit code: **0**
- Testes executados: **21** (21 passed, 0 failures, 0 errors, 0 skipped)
- Duração: ~0.42s
- Métodos por tipo (AST): **1 sync** (`test_default_timeout_validation_overflow_and_invalid`), **20 async**.

### 2. Matriz de classificação e segurança de exceção (Probe QA A)
Comando: `python3 -B -c '<probe_a>'` (com bloqueio total de socket antes de imports)
- Casos elegíveis: **21** aprovados. Todos resultaram em `type(caught) is LLMAttemptError`, `caught.args == ("Geração de briefing indisponível",)`, `caught.__cause__ is None`, `caught.__suppress_context__ is True`. A sentinela de teste `QA_TOP_SECRET_SENTINEL_TOKEN_XYZ_8899` não apareceu em `str(caught)`, `repr(caught.args)` nem em `"".join(traceback.format_exception(caught))`.
- Casos não-elegíveis: **19** aprovados. Todos propagaram com a identidade original intacta (`caught is exc`), sem conversão para `LLMAttemptError`.
- Chamadas externas: `await_count == 1` em todas as 40 invocações.
- Status estrito: **13** asserções em `_real_status_code` aprovadas.

### 3. Manutenção T029 e isolamento (Probe QA B)
Comando: `python3 -B -c '<probe_b>'`
- Teste real com MockTransport 503 executado com flags `follow_redirects` dos clientes globais `module_level_aclient` e `module_level_client` forçadas para `True`.
- Resultado: exatamente **1 request HTTP** efetuado; flags globais restauradas para `[True, True]`.

### 4. Transporte SDK real para 401 e 403 (Probe QA C)
Comando: `python3 -B -c '<probe_c>'`
- Derivação dinâmica do teste SDK OpenAI com HTTP 401 e 403:
  * HTTP 401 resultou em `litellm.exceptions.AuthenticationError` propagado diretamente (count 1).
  * HTTP 403 resultou em `litellm.exceptions.APIError` com status 403 propagado diretamente (count 1).
- Ambas as exceções propagaram sem conversão para `LLMAttemptError`, confirmando que credenciais/permissões não são mascaradas em runtime real do SDK OpenAI.

### 5. Integridade do congelamento
- Manifesto `pre_dispatch_sha256` na linha 71 do `progress.jsonl`: **99 arquivos** auditados via SHA-256.
- Mismatches encontrados: **0**.
- `git diff --check`: exit **0**.

## Observação contratual (O-CONTRACT-01)
- Identificador: `O-CONTRACT-01`
- Severidade: **MEDIUM** (confiança alta na análise estática, alcance em provider não demonstrado).
- Detalhe: `litellm.exceptions.Timeout` aceita construtor com `exception_status_code=401` ou `403`. Como `_is_eligible_llm_error` prioriza o tipo `litellm_exceptions.Timeout` antes da verificação de status, uma exceção construída dessa forma é convertida em `LLMAttemptError`. Porém, a inspeção de todos os 8 callsites no código do LiteLLM (`exception_mapping_utils.py`) demonstrou que o SDK apenas instancia `Timeout` com status 504. Em cenários reais com MockTransport para 401 e 403, o SDK instancia `AuthenticationError` e `APIError(403)` respectivamente, ambos propagados sem máscara.
- Ação QA: Registrado como observação técnica, sem promoção a bug (`promoted_to: null`).

## Dependências avaliadas (`importlib.metadata`)
- `litellm`: **1.104.0**
- `httpx`: **0.28.1**
- `pydantic`: **2.13.5**
- `openai`: **2.54.0**
- `python`: **3.14.7**

## Exclusões e limites
- **Rede externa**: Chamadas de rede bloqueadas via guard em `socket.socket.connect` e `socket.socket.connect_ex`.
- **Banco de dados**: Sem execução contra banco SQLite/Postgres real; runtime avaliado com fakes assíncronos e `SimpleNamespace`.
- **T031**: Transações de storage, deduplicação de concorrência e lifecycle de transação do briefing permanecem pendentes e fora deste recorte de QA.
- **Escrita**: Apenas este relatório foi criado. Todos os demais arquivos de código, testes e planejamento do repositório permanecem estritamente inalterados.

## Probes reproduzíveis

### Script completo de validação (executável via `python3 -B -c`)

```python
import os
os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"

import asyncio, ast, hashlib, json, pathlib, socket, textwrap, traceback, types, unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
import importlib.metadata as md

def _block(*args, **kwargs):
    raise OSError("NETWORK_BLOCKED")

socket.socket.connect = _block
socket.socket.connect_ex = _block
socket.create_connection = _block

import httpx, litellm
import litellm.exceptions as E
from app.briefing.llm_binding import make_scout_complete, _real_status_code, _is_eligible_llm_error
from app.briefing.service import LLMAttemptError
from app.services.llm import ProviderConfigurationError
from tests.test_briefing_llm_binding import _patch_rt, BindingTests
import tests.test_briefing_llm_binding as binding_test_module

R = pathlib.Path("/root/projects/deep-research")
S = "QA_TOP_SECRET_SENTINEL_TOKEN_XYZ_8899"
req = httpx.Request("POST", "https://example.invalid")

# 1. 21 Eligible cases
eligible = [
    E.APIConnectionError(S, "openai", "m"),
    E.Timeout(S, "m", "openai"),
    E.InternalServerError(S, "openai", "m"),
    E.RateLimitError(S, "openai", "m"),
    E.ServiceUnavailableError(S, "openai", "m"),
]
eligible += [E.APIError(s, S, "openai", "m") for s in (429, 500, 502, 503, 504)]
eligible += [c(S, request=req) for c in (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout, httpx.WriteTimeout, httpx.PoolTimeout)]
eligible += [httpx.HTTPStatusError(S, request=req, response=httpx.Response(s, request=req)) for s in (429, 500, 502, 503, 504)]
eligible += [TimeoutError(S)]
assert len(eligible) == 21, f"Eligible count mismatch: {len(eligible)}"

# 2. 19 Negative cases
negative = [
    E.AuthenticationError(S, "openai", "m"),
    E.PermissionDeniedError(S, "openai", "m", httpx.Response(403, request=req)),
    E.BadRequestError(S, "m", "openai"),
    ProviderConfigurationError(S),
    RuntimeError("arbitrary quota 429 503 timeout"),
    TypeError("arbitrary quota 429 503 timeout"),
]
unknown_with_503 = RuntimeError("arbitrary quota 429 503 timeout")
unknown_with_503.status_code = 503
negative.append(unknown_with_503)
negative += [E.APIError(s, S, "openai", "m") for s in (418, 401, 403, True, False, "503")]
for s in (418, 401, 403, True, False, "503"):
    resp = httpx.Response(200, request=req)
    resp.status_code = s
    negative.append(httpx.HTTPStatusError(S, request=req, response=resp))
assert len(negative) == 19, f"Negative count mismatch: {len(negative)}"

async def check_call(exc, is_eligible):
    fr, fg = _patch_rt({"gemini": "fake"}, {"scout": "gemini/m"})
    with patch("app.briefing.llm_binding.runtime_settings", fr), \
         patch("app.briefing.llm_binding.get_record", fg), \
         patch("app.briefing.llm_binding._enforce_safe_transport"), \
         patch("app.briefing.llm_binding.litellm.acompletion", AsyncMock(side_effect=exc)) as ac:
        try:
            fn = make_scout_complete(SimpleNamespace())
            await fn("sys", "usr")
        except Exception as caught:
            if is_eligible:
                assert type(caught) is LLMAttemptError, f"Expected LLMAttemptError, got {type(caught)}"
                assert caught.args == ("Geração de briefing indisponível",)
                assert str(caught) == "Geração de briefing indisponível"
                assert caught.__cause__ is None
                assert caught.__suppress_context__ is True
                assert S not in str(caught)
                assert S not in repr(caught.args)
                tb = "".join(traceback.format_exception(caught))
                assert S not in tb
            else:
                assert caught is exc
                assert not isinstance(caught, LLMAttemptError)
        else:
            raise AssertionError("Exception was not raised")
        assert ac.await_count == 1

async def test_matrix():
    for e in eligible:
        await check_call(e, True)
    for n in negative:
        await check_call(n, False)

asyncio.run(test_matrix())
print("MATRIX: 21 eligible, 19 negative PASS (security + unmasked identity + await_count 1)")

# 3. 13 Strict status checks
for val in (True, False, "503", 503.0, None):
    assert _real_status_code(SimpleNamespace(status_code=val)) is None
for val in (429, 500, 502, 503, 504, 401, 403, 418):
    assert _real_status_code(SimpleNamespace(status_code=val)) == val
print("STATUS_STRICT: 13 checks PASS")

# 4. T029 maintenance check
clients = [getattr(litellm, n).client for n in ("module_level_aclient", "module_level_client") if hasattr(litellm, n) and getattr(litellm, n)]
orig_fr = [c.follow_redirects for c in clients]
try:
    for c in clients:
        c.follow_redirects = True
    seeded = [c.follow_redirects for c in clients]
    res = unittest.TestResult()
    BindingTests("test_no_internal_retries_on_503_openai_sdk").run(res)
    assert res.wasSuccessful(), f"T029 failed: {res.errors} {res.failures}"
    assert [c.follow_redirects for c in clients] == seeded
    print("T029: 503 request count 1 + seeded global redirects cleanup PASS")
finally:
    for c, v in zip(clients, orig_fr):
        c.follow_redirects = v

# 5. Real SDK MockTransport auth checks (401 and 403)
test_source = (R / "tests/test_briefing_llm_binding.py").read_text()
tree = ast.parse(test_source)
node = next(n for n in ast.walk(tree) if isinstance(n, ast.AsyncFunctionDef) and n.name == "test_no_internal_retries_on_503_openai_sdk")
body = textwrap.dedent(ast.get_source_segment(test_source, node))
for status, exc_name in ((401, "AuthenticationError"), (403, "APIError")):
    code = body.replace("503,\n", f"{status},\n").replace("self.assertRaises(LLMAttemptError)", f"self.assertRaises(litellm.exceptions.{exc_name})")
    ns = dict(vars(binding_test_module))
    exec(code, ns)
    test_instance = binding_test_module.BindingTests("test_no_internal_retries_on_503_openai_sdk")
    test_instance.test_no_internal_retries_on_503_openai_sdk = types.MethodType(ns[node.name], test_instance)
    res = unittest.TestResult()
    test_instance.run(res)
    assert res.wasSuccessful(), (res.errors, res.failures)
    print(f"REAL_SDK: {status} {exc_name} PASS (unmasked, count 1, cleanup intact)")

# 6. Frozen hashes check
manifest = json.loads((R / "_reversa_forward/001-modulo-briefing/progress.jsonl").read_text().splitlines()[70])["pre_dispatch_sha256"]
mismatches = [p for p, h in manifest.items() if hashlib.sha256((R / p).read_bytes()).hexdigest() != h]
assert len(manifest) == 99, f"Expected 99 manifest entries, got {len(manifest)}"
assert len(mismatches) == 0, f"Mismatches: {mismatches}"
print(f"FROZEN: 99 files verified against progress line 71: 0 mismatches")

# 7. Method counts check
methods = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith("test_")]
sync_methods = [n.name for n in methods if isinstance(n, ast.FunctionDef)]
async_methods = [n.name for n in methods if isinstance(n, ast.AsyncFunctionDef)]
assert len(methods) == 21
assert len(sync_methods) == 1
assert len(async_methods) == 20
print(f"METHODS: {len(methods)} total (1 sync: {sync_methods[0]}, 20 async)")
```
