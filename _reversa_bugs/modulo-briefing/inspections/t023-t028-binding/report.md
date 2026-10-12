# Inspeção independente T023/T028 — binding LiteLLM

## Resultado
**FINDINGS**: 3 achados confirmados, confiança alta, `promoted_to: null`; 2 observações de evidência/spec. T028 timeout pré-I/O: **PASS**. Nenhum código, teste, ação, configuração, catálogo ou view alterado. Branch `main`; feature `001-modulo-briefing`, estágio `coding`. Worktree já sujo e arquivos-alvo untracked antes da inspeção.

## Mapa e lentes
- Spec: `_reversa_forward/001-modulo-briefing/requirements.md:58,60,143-162` (RF-08 motivo seguro; RF-10 até 4 tentativas por operação; timeout configurável). `audit/t011-integration-decomposition.md:46-55,79-108` (D3 transações curtas; D5 binding scout one-attempt).
- Código exclusivo: `app/briefing/llm_binding.py:30-112`, fábrica/timeout/configuração/invocação/guardrail. Dependências lidas: helpers `_provider`, `_classify_error`, `_enforce_safe_transport`, `apply_output_guardrail` de `app/services/llm.py`; `runtime_settings`, `get_record`, `validate_base_url` de `app/services/settings.py`. De `service.py`, somente definição `LLMAttemptError:23-27` e constante usada: não auditada orquestração persistida.
- Testes: `tests/test_briefing_llm_binding.py`, 10 métodos, mocks de configurações, transport e `acompletion`; teste segredo usa helper real.
- Dados: `AppSettings` via `AsyncSession`, credenciais resolvidas por request; nenhum briefing persistido inspecionado. SQLite memória isolada somente tabela AppSettings.
- Integração instalada: LiteLLM **1.104.0**, caminho obtido de `Path(litellm.__file__).parent`; OpenAI SDK, HTTPX MockTransport, zero rede de provedor.
- Lentes executadas: conformidade, dados, contratos, estados de erro, cobertura, concorrência; segurança/configuração condicionais ativadas. Achados consolidados abaixo; sem duplicação por lente.
- Preflight: AGENTS.md, state.json, active-requirements.json lidos. `reversa-config.json` raiz ausente; configuração real `.reversa/reversa-config.json` lida. Registro local contém inspeções, sem catálogo/bugs para dedupe; nada registrado.

## PASS — timeout/configuração/guardrail
`llm_binding.py:30-54`: valida factory e override antes de runtime_settings/get_record/transport/provider. Inteiros enormes de ambos sinais viram ValueError fixo; bool, zero, negativos, NaN, ambos infinitos e tipos não int/float rejeitados. Mensagens exatas `Configuração de timeout LLM inválida (default_timeout_s)` e `Configuração de timeout LLM inválida (timeout_s)`. Override None seleciona default; finitos positivos 45, 120 e 1e308 aceitos em defaults/overrides, sem teto 30.

Probe Python in-memory com patches runtime_settings/get_record/_enforce_safe_transport/litellm.acompletion/_provider executou 14 inválidos por caminho (`10**1000`, `-10**1000`, True, False, 0, 0.0, -1, nan, inf, -inf, '30', [], {}, 1j); assertions mensagens fixas e `call_count == 0` para cinco fronteiras. Saída: `invalid factory/override 14 each; boundary calls 0`, exit 0.

Modelo/chave scout, default 30, override 7.5: suíte aprovada. Probe adicionais com mocks verificaram openai/gpt-4o-mini e base pública literal https://8.8.8.8/v1, litellm/gpt-4o-mini com chave litellm e settings.LITELLM_API_BASE=https://8.8.4.4/v1. Bases passadas sem DNS. `validate_base_url` real rejeitou loopback 127.0.0.1, metadata 169.254.169.254, credenciais URL e query. Transport real exercitado em probe P1; `_enforce_safe_transport` criou/verificou clientes e manteve redirects False. Não prova firewall/pinning DNS nem todos provedores.

Erros reais LiteLLM AuthenticationError/BadRequestError preservados por identidade; RateLimitError/ServiceUnavailableError/Timeout viraram LLMAttemptError seguro, sem segredo fictício e com `__suppress_context__ == True`. Erros sintéticos 401/429/503/TimeoutError e ProviderConfigurationError também cobertos pela suíte. Auth raw interno é comportamento deliberado; não afirmar vazamento HTTP sem router.

Fixture alterada `tests/test_briefing_llm_binding.py:125` (`«redacted:sk-…»`) ainda exerce guardrail com força: saída contendo literal passa sem extra_sensitive_values, mas falha especificamente `sensitive configured secrets` ao receber literal como credencial. Mesmo controle com `audit-sensitive-fixture-unique`, saída inocente passa. Não falso positivo de regex genérica. Mudança confirmada no transcript:34.

## Achados confirmados

### F-CONTRACT-01 — SDK repete requests dentro de uma acompletion
- Lentes: contratos / cobertura / conformidade. Severidade sugerida: high; confiança alta; sinais operational-risk, limite de tentativas.
- Esperado D5:80,108: chamada sem retry interno; RF-10 limite total na operação.
- Evidência `llm_binding.py:77-88`: kwargs não incluem max_retries/num_retries. LiteLLM instalado `utils.py:1412-1428,2216-2226` resolve retry global (`num_retries=None` nesta instalação), mas isso não desliga SDK. `main.py:5324-5327,5422-5426,5584`; `llms/openai/openai.py:711-713` escolhe `inference_params.pop('max_retries', 2)`; `_get_openai_client:376-424` entrega max_retries ao AsyncOpenAI; chamada async efetiva segue cliente SDK.
- P1 chamou **binding real e litellm.acompletion real**, alterando somente resolução de settings e transporte HTTPX para MockTransport. Resposta 503 uniforme gerou **3 requests** e um LLMAttemptError seguro. Zero rede de provedor; sem mutação instalada. Refuta one-attempt para provider openai alcançável, não extrapola Gemini/Anthropic/proxy. Nenhum número hipotético de requests do serviço foi aprovado.
- `promoted_to: null`.

### F-CONSISTENCY-01 — configuração abre transação mantida durante LLM
- Lentes: concorrência / dados / conformidade. Severidade sugerida: high; confiança alta; sinal operational-risk.
- Esperado D3:48-50: chamada LiteLLM inteiramente fora de transação ativa, conexão liberada.
- Evidência `llm_binding.py:55-56,88`; `settings.py:275-285,289-303`: db.get inicia autobegin; binding não termina essa transação antes de await acompletion. P2 prova sessão inicialmente sem transação, com registro já commitado; `before False`, `during True`, `after True` (exit 0).
- Defeito alcançável na fábrica atual independentemente de router. Não acusa caminho HTTP ainda ausente nem audita service.py. D3 e D5 atualmente conflitantes na resolução de settings por mesma sessão; correção arquitetural requer decisão de spec/integrador, não inserção unilateral de commit pelo auditor.
- `promoted_to: null`.

### F-ERROR-01 — connection failure/HTTP 500 reais não recebem erro seguro
- Lentes: estados de erro / segurança / cobertura. Severidade sugerida: medium; confiança alta.
- Esperado D5:108 encapsular rede/provedor em LLMAttemptError seguro; RF-08:58 motivo seguro.
- Evidência `llm_binding.py:91-100`, `_classify_error` em `llm.py:239-251`: somente 502/503/504, rate limit ou timeout; APIConnectionError e InternalServerError reais LiteLLM com status 500 não classificados transitórios. P3 confirmou ambos propagados por identidade e mensagem contendo **segredo fictício**.
- Confirma não encapsulamento interno e ausência de retry elegível via LLMAttemptError; não afirma segredo real exposto nem vazamento público HTTP. Auth/config raw é distinto e deliberado, não incluído neste achado.
- `promoted_to: null`.

## Observações (não bugs promovidos)
1. **O-EVIDENCE-01**, cobertura/confiança alta: `t028-execution.md:14` alega exit 1, 10 testes, 2 ERRORS e 12 FAILURES. Transcript `/root/.hermes/profiles/orchestrator/cache/delegation/live/deleg_024fca3f/task-1.log:35-40` registra duas execuções terminal ERROR após patch testes; `:49-50,67-68` registra GREEN terminal ok. Porém saídas truncadas em `…(+25456 chars)`/`…(+19144 chars)` não preservam resumo/exits. Não é possível validar contagens RED ou conteúdo causal completo; alegação não contradita nem certificada. Não reconstruída saída ausente. GREEN atual confirmado independentemente.
2. **O-SPEC-01**, conformidade/confiança alta: D5:83 menciona fallback DEFAULT_ROLE_MODELS, mas runtime_settings:301 usa record.models ou settings.<ROLE>_MODEL, não DEFAULT_ROLE_MODELS; binding testa erro quando modelo ausente. D5 também cita HTTP 500 e RF-08 saída pública segura sem router presente. Registrar gap de spec/integração, não decidir comportamento arquitetural nem declarar endpoint aprovado.

## Checks executados
- `python3 -B -m unittest tests.test_briefing_llm_binding -v`: **exit 0**, `Ran 10 tests in 0.022s`, `OK`; todos 10 métodos.
- Compile por `py_compile.compile(f, cfile=Path(os.environ['TMPDIR']) / ('audit-binding-'+Path(f).name+'c'), doraise=True)` para ambos arquivos: **exit 0**, `compile scratch OK`; artefatos somente scratch autorizado.
- `git diff --check`: **exit 0**, nenhuma saída. Arquivos-alvo untracked: check não substitui inspeção/compile desses arquivos.
- P1, P2, P3 abaixo: **exit 0**. Probes via stdin, sem arquivo de código novo, sem DB externo/credencial real.

## Probes completos reproduzíveis
Executar na raiz `/root/projects/deep-research`, `python3 -B - <<'PY'` com cada bloco, fechando `PY`.

### P1 — contar requests internos, sem rede
```python
import asyncio,httpx,litellm
from unittest.mock import patch
from types import SimpleNamespace
from app.briefing.llm_binding import make_scout_complete
from app.services.llm import _enforce_safe_transport
from litellm.llms.openai.common_utils import BaseOpenAILLM
async def main():
 count=0
 def handle(req):
  nonlocal count
  count+=1
  return httpx.Response(503,json={'error':{'message':'fixture unavailable','type':'server_error'}})
 async def rt(db):return {'openai':'audit-fixture-key'},{'scout':'openai/gpt-4o-mini'}
 async def gr(db):return SimpleNamespace(openai_base_url=None)
 litellm.telemetry=False
 _enforce_safe_transport()
 async with httpx.AsyncClient(transport=httpx.MockTransport(handle),follow_redirects=False) as client:
  with patch('app.briefing.llm_binding.runtime_settings',rt),patch('app.briefing.llm_binding.get_record',gr),patch.object(BaseOpenAILLM,'_get_async_http_client',return_value=client):
   try: await make_scout_complete(SimpleNamespace())('sys','user')
   except Exception as e:print('REAL_ACOMPLETION',type(e).__name__,'requests',count,'safe', 'audit-fixture-key' not in str(e))
asyncio.run(main())
```
Saída relevante: `REAL_ACOMPLETION LLMAttemptError requests 3 safe True`. LiteLLM também imprimiu links de feedback/debug, sem segredo.

### P2 — autobegin SQLite memória, settings real
```python
import asyncio
from types import SimpleNamespace
from unittest.mock import patch
from sqlalchemy.ext.asyncio import create_async_engine,async_sessionmaker
from app.models import AppSettings
from app.briefing.llm_binding import make_scout_complete
async def main():
 engine=create_async_engine('sqlite+aiosqlite:///:memory:')
 async with engine.begin() as c:await c.run_sync(lambda c:AppSettings.__table__.create(c))
 Session=async_sessionmaker(engine,expire_on_commit=False)
 async with Session() as db:
  db.add(AppSettings(id=1,encrypted_credentials={},models={'scout':'openai/gpt-4o-mini'}));await db.commit()
  print('before',db.in_transaction())
  async def ac(**kw):
   print('during',db.in_transaction());assert db.in_transaction()
   return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='ok'))])
  from app.services import settings as sm
  fixture=SimpleNamespace(**{name:None for name in sm.ENV_KEYS.values()});fixture.OPENAI_API_KEY='audit-fixture-key'
  with patch.object(sm,'settings',fixture),patch('app.briefing.llm_binding._enforce_safe_transport'),patch('app.briefing.llm_binding.litellm.acompletion',ac):
   assert await make_scout_complete(db)('s','u')=='ok'
  print('after',db.in_transaction())
 await engine.dispose()
asyncio.run(main())
```
Saída: `before False`, `during True`, `after True`.

### P3 — exceptions reais de rede/500, segredo somente fictício
```python
import asyncio,litellm
from types import SimpleNamespace as NS
from unittest.mock import patch,AsyncMock
from app.briefing.llm_binding import make_scout_complete
async def main():
 for cls in [litellm.APIConnectionError,litellm.InternalServerError]:
  exc=cls(message='fixture audit-only-secret',model='gpt-4o-mini',llm_provider='openai')
  with patch('app.briefing.llm_binding.runtime_settings',AsyncMock(return_value=({'openai':'audit-only-secret'},{'scout':'openai/gpt-4o-mini'}))),patch('app.briefing.llm_binding.get_record',AsyncMock(return_value=NS(openai_base_url=None))),patch('app.briefing.llm_binding._enforce_safe_transport'),patch('app.briefing.llm_binding.litellm.acompletion',AsyncMock(side_effect=exc)):
   try:await make_scout_complete(NS())('s','u')
   except Exception as e:print(cls.__name__,'same_exception',e is exc,'fixture_secret_in_error','audit-only-secret' in str(e))
asyncio.run(main())
```
Saída: `APIConnectionError same_exception True fixture_secret_in_error True`; `InternalServerError same_exception True fixture_secret_in_error True`.

## Readset SHA256 / estabilidade
Primeira leitura e comparação final: primeiros oito arquivos abaixo com hashes capturados no output terminal inicial (log completo `/root/.hermes/profiles/orchestrator/cache/terminal-output/out-1791710293-930-2b0.log`), exceto config real descoberta posteriormente. Demais docs tiveram conteúdo lido antes dos probes; hashes numéricos coletados ao fim (sem baseline hash anterior: não inventado). Verificação adicional após escrita report registrada no adendo.

| Arquivo | SHA256 observado |
|---|---|
| AGENTS.md | 9de50e39699ecac57f33b18ae5b0149186ec04bb6571cdb87218fee2607e1844 |
| .reversa/state.json | 27fc325d313341e303a16a4d4c2dbb03838b91f034f250fe3661a2083353b3df |
| .reversa/active-requirements.json | 802efe8929aa5575e24b23947afdf2a4dff013c9d284b3f2ed7420fc246f2d45 |
| .reversa/reversa-config.json | 33c9ab2158530bcba7c242f15d7e2f173f346b7f9a999115231e195bd8f4c8fe |
| app/briefing/llm_binding.py | 600702234d5a8a162e65481443e27f3d922bced628479a922cf913900c17f256 |
| tests/test_briefing_llm_binding.py | 7383510ec3a9e07d09aa7cb3ecce0c512b2a0ea495852988239e59cf558f6bde |
| app/services/llm.py | ef25323e287b7535c92ebf73cedb48439a30b7008eabcfc65328c74a2a77900c |
| app/services/settings.py | d999f3a69c99182f90a78c948b1b06eaff6bbcfb919e17e6f4785eb070c0091c |
| requirements.md (feature) | 4d749e76bf4d07d1d6f2ae33cc933116c43f2c745f07462a298b5012e8c4d8c5 |
| audit/t011-integration-decomposition.md (feature) | fd679e6a53f017fbc160a0f1352b471f40c3efa971b74a4122b1f2d7423e04bf |
| audit/t028-execution.md (feature) | 38004b25c7ac9ffe4fedb5a3e79f8b5dbae0e9aaf897943b980b4ede08e14df3 |

### Adendo SHA256 final
Após persistência, probe recalculou hashes dos 11 arquivos da tabela e comparou com report via `assert h in report`: todos `UNCHANGED`, exit 0. Para sete arquivos existentes do preflight inicial, comparação também cobre início/fim da inspeção. Config real e docs cobrem baseline numérico tardio/final; limite explicitado acima. Suplementares (somente hash final, sem alegação de estabilidade): `app/briefing/service.py` = `afd3cd120bba22309d3aa9d0a6a0499b246499b1570e66894189ed724f27a05c`; transcript `deleg_024fca3f/task-1.log` = `fb06d26a5c9a4bff934b4e57d58fe29d9720b77e9761453884b4f1fc0ee5573b`.

## Limites e cluster
Cluster: fronteira binding/configuração/dependência instalada; mock acompletion único oculta retries SDK e mocks settings ocultam autobegin. Não cobertos: service.py persistido, storage, HTTP/router futuro, rollout, banco externo/Postgres, credenciais reais, providers não OpenAI em transporte efetivo, DNS rebinding e desempenho medido. Retry zero global em todos providers: **desconhecido**, não aprovado por inferência. Não corrigidos achados nem fechadas ações. Contagem consolidada: 3 confirmados alta, 2 observações alta, 0 bugs registrados.
