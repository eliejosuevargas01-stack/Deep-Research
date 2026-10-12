# Inspeção diagnóstica T030 — matriz de erros

## Veredito: CONDITIONAL

Matriz ordinária e segurança **PASS**: 21 casos elegíveis, 19 negativos, 13 verificações de status estrito; suite 21/21 OK (1 método sync, 20 async), SDK OpenAI 503 mantém exatamente 1 request e isolamento com flags globais semeadas True. Congelamento 98/98 SHA-256 preservado, incluindo `app/services/llm.py`.

Condição: esclarecer precedência de status 401/403 em `litellm.exceptions.Timeout` nativo. Construtor SDK aceita `exception_status_code=401/403` e response correspondente; binding converte ambos apesar de D5:117 exigir propagação. Sem mutação de atributos. Porém caminho real de provider que produza essa combinação não foi demonstrado: todos oito callsites SDK instalados que passam `exception_status_code` ao Timeout restringem status a 504. Transporte OpenAI real mockado com 401/403 propagou erros, sem conversão. Portanto observação contratual, não defeito runtime confirmado nem bug promovido. Não fechar T030 automaticamente.

## Preflight e mapa do recorte

- Root `/root/projects/deep-research`, branch `main`; árvore já suja e feature untracked. Nada restaurado.
- AGENTS.md e `.reversa/{state.json,active-requirements.json,reversa-config.json}` lidos; feature `001-modulo-briefing` em coding. Requisitos aprovados, PRD/spec greenfield existentes são fontes de produto, não reabertos.
- Produto: `requirements.md:58` RF-08 exige motivo seguro sem segredos; `actions.md:84` T030/F-ERROR-01 permanece `[ ]`.
- Contrato efetivo: `audit/t029-t031-planning-delta.md:21–30`, `audit/t011-integration-decomposition.md:112–120`; `audit/cross-check.md:7–11,24,33–35` PASS documental, não aprovação runtime.
- Entrega: `audit/t030-execution.md:5–25`, SHA de binding/testes coincidem com congelamento parent linha 70.
- Código: `app/briefing/llm_binding.py:31–86,148–155`; testes: `tests/test_briefing_llm_binding.py` 21 métodos. Dados externos: exceções LiteLLM 1.104.0/httpx 0.28.1, transporte OpenAI HTTPX MockTransport; settings e callable substituídos por fakes, sem DB real.
- Legado: `_classify_error` e `complete` não editados; SHA inteiro `app/services/llm.py` permanece `ef25323e287b7535c92ebf73cedb48439a30b7008eabcfc65328c74a2a77900c`. “Diff zero” aqui significa contra baseline congelado, não contra HEAD, que já tinha alterações anteriores.

## Contagens por lente

| Lente | Evidência executada | Defeitos confirmados | Observações |
|---|---|---:|---:|
| Conformidade/contratos | 21 elegíveis + 19 negativos; 13 status; SDK 401/403, count1 | 0 | 1 MEDIUM, confiança alta na divergência construtor/contrato, alcance provider não provado |
| Segurança da exceção | 21 elegíveis, asserts dentro de except ativo: mensagem/args/cause/suppression/str/repr(args)/traceback | 0 | 0 |
| Cobertura/preservação | 21 métodos OK, 1 sync/20 async; SDK 503 count1 e isolamento True; 98 SHA preservados | 0 | 0 |

O-CONTRACT-01 (MEDIUM; `promoted_to: null`): `_is_eligible_llm_error` retorna True por classe em binding:48–58 antes de status/auth; `Timeout(...exception_status_code=401/403,response=...)` convertido em 2 chamadas reais ao binding com exceções SDK construídas por API pública. Contrato D5:117 diz 401/403 propagam. Não reportar como defeito alcançável em provider sem prova adicional. SDK OpenAI MockTransport 401 gerou AuthenticationError; 403 gerou APIError(status403) para payload server_error mantido do fixture. Ambos propagaram, count1. Primeira probe esperava PermissionDeniedError em 403 e falhou por expectativa incorreta; correção para classe observada passou. Erro de probe, não produto.

Sem cluster confirmado. Sem registro de bugs, views, correções ou fechamento de ações.

## Verificações e saídas reais

1. `python3 -B -m unittest tests.test_briefing_llm_binding -v`: exit 0, `Ran 21 tests in 0.433s`, `OK`, nenhum skip. Aviso Pydantic ReadOnly e aviso asyncio tarefa lenta não afetaram resultado.
2. `git diff --check`: exit 0, sem saída; não valida funcionalidade nem conteúdo untracked.
3. Probe A abaixo, executada como `python3 -B -c '<conteúdo completo>'` no root: exit 0. `MATRIX 21 eligible 19 negative; identity/security/count1 PASS`; `STATUS_STRICT 13 PASS`; `SDK_503 request_count1 + seeded global isolation PASS`; `FROZEN 98 mismatch []`; `METHODS 21 sync 1 async 20`.
4. Probe B abaixo, mesma forma/root: exit 0 após corrigir expectativa de 403. `REAL_SDK 401 AuthenticationError PASS count1`; `REAL_SDK 403 APIError PASS count1`.
5. Inspeção read-only via inspect.getsource de construtores SDK: APIConnectionError fixa500; InternalServerError fixa500 e recria response500; ServiceUnavailableError fixa503 e recria response503; Timeout preserva `exception_status_code` e response opcional. MRO AuthenticationError/PermissionDeniedError/BadRequestError não inclui classes elegíveis LiteLLM.
6. Inspeção read-only dos oito callsites instalados `exception_status_code=` em `litellm_core_utils/exception_mapping_utils.py:504,636,850,1031,1139,2117,2211,2328`: sete condições `status_code == 504`, um `case 504`. Não encontrado callsite desses que origine Timeout401/403.

Probes bloqueiam socket com OSError antes de importar SDK; metadata tentou fetch, foi bloqueada e usou backup local. Nenhuma rede real/provider/live DB. Segurança verificada enquanto except ativo, preservando traceback. Todos negativos exigem mesma identidade; desconhecido RuntimeError com atributo status503 permanece negativo. Status APIError/HTTPStatusError cobrem 418/401/403/bool/string além dos cinco reconhecidos. `_real_status_code` só retorna int não-bool; aceita fallback response numérico conforme implementação.

## Cobertura e limites

21 métodos executados incluem 9 novos T030 e 12 existentes identificados pela entrega e leitura estática. Sem skips ou asserts essenciais removidos visíveis: teste transient mantém count1 e classe segura; auth mantém identidade; config propaga; SDK mantém count1 e cleanup real. Fixtures antigas sintéticas substituídas por classes reais conforme relatório da entrega. Snapshot anterior de testes não foi fornecido como arquivo comparável: não se afirma comparação byte-a-byte de 12 métodos históricos. Baseline parent atual e os 98 arquivos permanecem intactos.

RED histórico confirmado por relato de entrega/parent; ordenação registrada, saída histórica truncada não autentica traceback completo. GREEN atual foi executado independentemente; não inventado RED novo. Setup TypeError histórico parent não é defeito produto. Divergência documental LOW `legacy-impact.md:146` (reinspection95 vs fonte94, QA95 correta) informada pelo parent, fora três fontes técnicas estritas; não promovida nem corrigida nesta inspeção.

Fora escopo: projeto inteiro, serviço/deadline externos ao binding, T031 ownership/transações, API/QA futura, cobertura multi-provider, `.env`/keys/DB/live network/global discovery. QA deve ocorrer depois da entrega. Única escrita: este relatório; código/testes/actions/progress/views congelados.

## Probe A — conteúdo completo reproduzível

Executar no root: `python3 -B -c '<script abaixo>'` (aspas de shell adequadas; alternativamente colar conteúdo em executor Python). Script não grava arquivos.

```python
import asyncio, ast, hashlib, json, pathlib, socket, traceback, unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
socket.socket.connect = lambda *a, **k: (_ for _ in ()).throw(OSError("NETWORK_BLOCKED"))
socket.socket.connect_ex = socket.socket.connect
socket.create_connection = socket.socket.connect
import httpx, litellm
import litellm.exceptions as E
from app.briefing.llm_binding import make_scout_complete, _real_status_code
from app.briefing.service import LLMAttemptError
from app.services.llm import ProviderConfigurationError
from tests.test_briefing_llm_binding import _patch_rt, BindingTests
R = pathlib.Path("/root/projects/deep-research")
S = "INSPECTION_SECRET_TOKEN_12345"
req = httpx.Request("POST", "https://example.invalid")
eligible = [E.APIConnectionError(S,"openai","m"),E.Timeout(S,"m","openai"),E.InternalServerError(S,"openai","m"),E.RateLimitError(S,"openai","m"),E.ServiceUnavailableError(S,"openai","m")]
eligible += [E.APIError(s,S,"openai","m") for s in (429,500,502,503,504)]
eligible += [c(S,request=req) for c in (httpx.ConnectError,httpx.ConnectTimeout,httpx.ReadTimeout,httpx.WriteTimeout,httpx.PoolTimeout)]
eligible += [httpx.HTTPStatusError(S,request=req,response=httpx.Response(s,request=req)) for s in (429,500,502,503,504)]
eligible += [TimeoutError(S)]
negative = [E.AuthenticationError(S,"openai","m"),E.PermissionDeniedError(S,"openai","m",httpx.Response(403,request=req)),E.BadRequestError(S,"m","openai"),ProviderConfigurationError(S),RuntimeError("timeout quota 429 503"),TypeError("timeout quota 429 503")]
unknown = RuntimeError("timeout quota 429 503"); unknown.status_code=503; negative.append(unknown)
negative += [E.APIError(s,S,"openai","m") for s in (418,401,403,True,False,"503")]
for s in (418,401,403,True,False,"503"):
 response=httpx.Response(200,request=req); response.status_code=s
 negative.append(httpx.HTTPStatusError(S,request=req,response=response))
async def check(exc, expected):
 fr,fg=_patch_rt({"gemini":"fake"},{"scout":"gemini/m"})
 with patch("app.briefing.llm_binding.runtime_settings",fr),patch("app.briefing.llm_binding.get_record",fg),patch("app.briefing.llm_binding._enforce_safe_transport"),patch("app.briefing.llm_binding.litellm.acompletion",AsyncMock(side_effect=exc)) as ac:
  try: await make_scout_complete(SimpleNamespace())("s","u")
  except Exception as caught:
   if expected:
    assert type(caught) is LLMAttemptError
    assert caught.args == ("Geração de briefing indisponível",)
    assert str(caught)=="Geração de briefing indisponível"
    assert caught.__cause__ is None and caught.__suppress_context__ is True
    for rendered in (str(caught),repr(caught.args),"".join(traceback.format_exception(caught))): assert S not in rendered
   else: assert caught is exc and not isinstance(caught,LLMAttemptError)
  else: raise AssertionError("no exception")
  assert ac.await_count==1
async def main():
 for e in eligible: await check(e,True)
 for e in negative: await check(e,False)
 print("MATRIX",len(eligible),"eligible",len(negative),"negative; identity/security/count1 PASS")
 # Constructor-native boundary, no mutated exception attributes.
 for status in (401,403):
  exc=E.Timeout(S,"m","openai",exception_status_code=status,response=httpx.Response(status,request=req))
  print("NATIVE_TIMEOUT_AUTH",status,"real_status",_real_status_code(exc))
  await check(exc,True)
 print("NATIVE_TIMEOUT_AUTH converted: 2; constructor-supported conflict D5:117; provider reachability unproven")
asyncio.run(main())
for val in (True,False,"503",503.0,None): assert _real_status_code(SimpleNamespace(status_code=val)) is None
for val in (429,500,502,503,504,401,403,418): assert _real_status_code(SimpleNamespace(status_code=val))==val
print("STATUS_STRICT 13 PASS")
# Run actual SDK 503 test with global redirect flags deliberately True.
clients=[getattr(litellm,n).client for n in ("module_level_aclient","module_level_client")]
orig=[c.follow_redirects for c in clients]
try:
 for c in clients: c.follow_redirects=True
 snapshot=[c.follow_redirects for c in clients]
 result=unittest.TestResult(); BindingTests("test_no_internal_retries_on_503_openai_sdk").run(result)
 assert result.wasSuccessful(), (result.errors,result.failures)
 assert [c.follow_redirects for c in clients]==snapshot
 print("SDK_503 request_count1 + seeded global isolation PASS")
finally:
 for c,v in zip(clients,orig): c.follow_redirects=v
manifest=json.loads((R/"_reversa_forward/001-modulo-briefing/progress.jsonl").read_text().splitlines()[69])["pre_dispatch_sha256"]
diff=[p for p,h in manifest.items() if hashlib.sha256((R/p).read_bytes()).hexdigest()!=h]
print("FROZEN",len(manifest),"mismatch",diff); assert len(manifest)==98 and not diff
node=ast.parse((R/"tests/test_briefing_llm_binding.py").read_text()); methods=[n for n in ast.walk(node) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name.startswith("test_")]
print("METHODS",len(methods),"sync",sum(isinstance(n,ast.FunctionDef) for n in methods),"async",sum(isinstance(n,ast.AsyncFunctionDef) for n in methods)); assert len(methods)==21

```

## Probe B — conteúdo completo reproduzível

Mesmo root e comando `python3 -B -c`, sem gravação. Deriva fixture SDK atual em memória, modifica apenas resposta HTTP e classe esperada, preservando cleanup/count1.

```python
import ast, pathlib, socket, textwrap, types, unittest
socket.socket.connect=lambda *a,**k: (_ for _ in ()).throw(OSError("NETWORK_BLOCKED"))
socket.socket.connect_ex=socket.socket.connect
socket.create_connection=socket.socket.connect
import litellm
import tests.test_briefing_llm_binding as M
p=pathlib.Path("/root/projects/deep-research/tests/test_briefing_llm_binding.py")
source=p.read_text(); tree=ast.parse(source)
node=next(n for n in ast.walk(tree) if isinstance(n,ast.AsyncFunctionDef) and n.name=="test_no_internal_retries_on_503_openai_sdk")
body=textwrap.dedent(ast.get_source_segment(source,node))
for status,name in ((401,"AuthenticationError"),(403,"APIError")):
 code=body.replace("503,\n",f"{status},\n").replace("self.assertRaises(LLMAttemptError)",f"self.assertRaises(litellm.exceptions.{name})")
 assert code!=body and f"{status},\n" in code
 ns=dict(vars(M)); exec(code,ns)
 test=M.BindingTests("test_no_internal_retries_on_503_openai_sdk")
 test.test_no_internal_retries_on_503_openai_sdk=types.MethodType(ns[node.name],test)
 result=unittest.TestResult(); test.run(result)
 assert result.wasSuccessful(),(result.errors,result.failures)
 print("REAL_SDK",status,name,"PASS count1; existing scoped cleanup preserved")

```
