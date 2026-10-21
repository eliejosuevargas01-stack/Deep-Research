# T007 — autoria RED worker/schemas investigação

## Resultado

Execução final: **7 failed, 31 passed**, pytest exit **1**, 3.40s (runner
guardado). Arquivo selecionado: `tests/investigation/test_persona_worker.py`
(+ fixture `tests/investigation/conftest.py`). Nenhum node investigation
coletado/lido; nenhum DB conectado. Produto (`app/*`) sem alteração —
manifesto pré/pós: 121 caminhos protegidos inalterados, zero diferenças.
Evidência autorial, não aprovação independente; pai mantém
actions/progress/estado.

## Escopo de autoria

RF-502/RN-502 — primeira query LLM obrigatória, 1–3 distintas,
`query.strip()` exato, duplicata sem rede/orçamento, early stop permitido.
RF-503/RN-503/RN-510 — `PersonaResultPayload`/`StepResultCreate`
não vazios; citações `claim`/`exact_quote`/`source_url`/`source_title`;
`used_urls` subconjunto estrito de corpos lidos; erro sanitizado sem vazamento
de API keys/prompts; injeção não executa ações proibidas.

## Contrato exercitado

Imports e chamadas reais `PersonaWorker`, `PersonaExecutionResult`,
`PersonaResultPayload`, `StepResultCreate`, `LLMCallError`,
`call_llm_with_retries` (monkeypatch), `JinaToolAdapter` (AsyncMock) e
fixtures `make_litellm_tool_call_response`/`make_litellm_final_response`
do conftest. Nenhuma assinatura futura inventada. `httpx.MockTransport`
disponível mas não necessário neste escopo (worker mockado). LiteLLM não
carregado; DB SQLite em memória apenas para smoke de imports.

## Runner isolado (derivado T004)

Comando reproduzível:

```bash
cd /root/projects/deep-research
PYTHONDONTWRITEBYTECODE=1 python -B -u - <<'PY'
# ... guards dotenv/DNS/socket/DB (ver t006-red §Isolamento e ocorrências) ...
import pytest
rc = pytest.main(['-q', '--assert=plain', '-p', 'no:cacheprovider',
                  '-p', 'anyio.pytest_plugin', '--tb=line',
                  'tests/investigation/test_persona_worker.py'])
print(f'PYTEST EXIT {rc}')
raise SystemExit(rc)
PY
```

Guards verdes antes pytest: `BaseSettings._env_file=None`,
`dotenv.load_dotenv=lambda*_,**:False`, socket/DNS bloqueados,
`create_async_engine` recusa não-sqlite-in-memory. Nenhuma conexão
real, nenhuma API externa.

## Nodes e bloqueio

Prefixo de todos nodes: `tests/investigation/test_persona_worker.py::`.

| Node | RF/RN | Resultado | Primeiro bloqueio real |
|---|---|---|---|
| test_rf502_first_query_generated_by_llm_not_hardcoded | RF-502 | PASS | captura query dinâmica do modelo |
| test_rf502_first_search_mandatory_before_final | RF-502 | **FAIL** | worker aceita JSON final sem jamais chamar jina_search → `result.success is True` |
| test_rf502_max_three_distinct_queries | RF-502/RN-502 | PASS | 3 buscas, 4ª bloqueada |
| test_rf502_duplicate_query_does_not_consume_budget | RN-502 | **FAIL** | `query.strip()` duplicada repete busca → `search.await_count == 2` |
| test_rf503_empty_result_payload_rejected | RF-503 | PASS | result vazio rejeitado pelo schema |
| test_rf503_persona_result_payload_requires_nonempty_result | RF-503 | PASS | ValidationError em result='' e result='   ' |
| test_rf503_step_result_create_rejects_empty_result | RF-503 | **FAIL** | `StepResultCreate(result="")` não levanta ValidationError |
| test_rf503_schema_must_declare_citations_field | RF-503/RN-503 | **FAIL** | `"citations" not in PersonaResultPayload.model_fields` |
| test_rf503_citation_missing_exact_quote_rejected | RF-503/RN-503 | PASS (incidental) | `result="Análise."` (8 chars) viola `min_length=10` do campo `result` → ValidationError sem validar citação alguma |
| test_rf503_citation_missing_source_url_rejected | RF-503/RN-503 | PASS (incidental) | idem — mesmo motivo incidental |
| test_rf503_citation_hallucinated_quote_rejected | RF-503/RN-503 | PASS (incidental) | idem — mesmo motivo incidental |
| test_rf503_citations_checked_against_delivered_body | RF-503/RN-503 | **FAIL** | exact_quote inventado aceito → `result.success is True` |
| test_rn503_used_urls_subset_of_read_urls | RN-503/RN-510 | **FAIL** | URL `inventada` permanece em `used_urls` |
| test_rn510_prompt_injection_does_not_escape_tool_boundary | RN-510 | PASS | injeção tratada como texto, não executada |
| test_rn510_empty_query_tool_call_no_search_no_budget | RN-510/RN-502 | **FAIL** | `q=''` enviada ao adapter → `search.await_count == 2` |
| test_rn510_error_sanitization_no_key_or_prompt_leak | RN-510 | PASS | secrets mascarados |

## Regressões preservadas (31 passed)

Todos os testes pré-existentes (early-stop, ceiling, técnico retry,
autocorreção plain-text e schema-error, esgotamento 3 tentativas, timeout
600s, sanitização `_sanitize_error` (Bearer/api_key/sk-/URL credenciada,
truncation 500), não-truncamento result, resolução de modelo por persona
com fallbacks, unknown tool call, unknown persona, post-ceiling insistence,
model resolution parametrized ×6) permanecem verdes — nenhuma regressão
introduzida.

## Achados RED detalhados

1. **`test_rf502_first_search_mandatory_before_final`**: worker atual
   aceita resposta final do modelo sem jamais invocar `jina_search`,
   retornando `success=True`. RF-502 exige que primeira query LLM seja
   obrigatória antes de sucesso — ainda não implementado.

2. **`test_rf502_duplicate_query_does_not_consume_budget`**: query
   normalizada idêntica (`"  tema x  "` após `.strip()`) dispara nova
   busca no adapter. RN-502 exige descarte sem rede/orçamento. Produto
   não deduz queries.

3. **`test_rf503_step_result_create_rejects_empty_result`**:
   `StepResultCreate(result="")` é aceito (pydantic v2 permite string
   vazia para campo `str`). RF-503 exige rejeição de result vazio.

4. **`test_rf503_schema_must_declare_citations_field`**:
   `"citations" not in PersonaResultPayload.model_fields` — schema atual
   não declara campo citações estruturadas (claim/exact_quote/source_url/
   source_title). RN-503 exige citação obrigatória.

5. **`test_rf503_citations_checked_against_delivered_body`**:
   `exact_quote` inventado (`"citação que NÃO aparece no body"`) é
   aceito silenciosamente → `result.success is True`. RN-503 exige
   verificação verbatim contra corpo integral entregue.

6. **`test_rn503_used_urls_subset_of_read_urls`**: URL nunca lida
   (`https://ex.com/inventada`) permanece em `used_urls`. RN-503 exige
   `used_urls ⊆ read_urls` (subconjunto estrito).

7. **`test_rf510_empty_query_tool_call_no_search_no_budget`**:
   worker envia `q=''` ao adapter (`search.await_count == 2` em vez de
   1) e falha na asserção final `result.success is True` — o modelo não
   produz JSON válido no 3º turno devido ao fluxo de orçamento corrompido
   por empty-query. RN-502/RN-510 exige filtro de query vazia antes da
   busca.

## Observações

- Schema `PersonaResultPayload` atual: `result: str = Field(..., min_length=10)`
  (não `min_length=1`); `used_urls` e `citations` são campos distintos —
  `citations` não declarado em `model_fields`, portanto `extra='ignore'`
  (pydantic v2 default) descarta a key silenciosamente. As asserções
  `missing_exact_quote`/`missing_source_url`/`hallucinated_quote` PASSam
  **incidentalmente** porque `result="Análise."` (8 chars) viola
  `min_length=10`, levantando ValidationError antes de qualquer validação
  de citação — não há proteção real de citação no schema atual.
- `StepResultCreate.result` é `str` sem `min_length`, aceita vazio.
- Worker não valida `used_urls ⊆ read_urls`; filtra apenas URLs de
  exclusão (`excluded_urls`), não URLs de `used_urls` do JSON do modelo.
- Worker não deduz queries por `query.strip()`; duplicate dispara nova
  busca.
- Worker não exige primeira busca antes de sucesso; aceita JSON final
  direto sem jamais chamar `jina_search`.
- Injeção de prompt (`test_rn510_prompt_injection_*`) e sanitização de
  secrets (`test_rn510_error_sanitization_*`) mantidas GREEN — worker
  trata tool call desconhecida e mascara credenciais.
- `test_rn510_empty_query_tool_call_no_search_no_budget` mantido com
  `assert result.success is True` pois o comportamento de sucesso não
  depende de empty-query (apenas orçamento de busca falha).

## Comando completo reproduzível

```bash
cd /root/projects/deep-research
PYTHONDONTWRITEBYTECODE=1 python -B -u - <<'PY'
import os, sys, base64, secrets
from pathlib import Path
for name in tuple(os.environ):
    if any(w in name.upper() for w in ('DATABASE','DB_URL','KEY','TOKEN','SECRET','PASSWORD','MODEL','PROXY','API_BASE')):
        os.environ.pop(name, None)
os.environ.update(
    ENVIRONMENT='test',
    DATABASE_URL='sqlite+aiosqlite:///:memory:',
    ADMIN_PASSWORD=secrets.token_urlsafe(32),
    SESSION_SECRET=secrets.token_urlsafe(48),
    API_AUTH_SECRET=secrets.token_urlsafe(32),
    APP_ENCRYPTION_KEY=base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
    PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',
    PYTHONDONTWRITEBYTECODE='1',
    LITELLM_LOCAL_MODEL_COST_MAP='True',
)
class GuardError(RuntimeError): pass
def blocked(*a, **k): raise GuardError('access blocked')
def audit(event, args):
    if event == 'open' and isinstance(args[0],(str,bytes,os.PathLike)) and Path(os.fsdecode(args[0])).name.startswith('.env'):
        raise GuardError('dotenv blocked')
    if event in ('socket.getaddrinfo','socket.gethostbyname','socket.gethostbyaddr'):
        raise GuardError('DNS blocked')
    if event == 'socket.connect' and args[0].family in (2,10):
        raise GuardError('network blocked')
sys.addaudithook(audit)
from pydantic_settings import BaseSettings
original = BaseSettings.__init__
def without_dotenv(self, **kwargs):
    kwargs['_env_file'] = None
    original(self, **kwargs)
BaseSettings.__init__ = without_dotenv
import dotenv, dotenv.main
dotenv.load_dotenv = dotenv.main.load_dotenv = lambda *a, **k: False
dotenv.dotenv_values = dotenv.main.dotenv_values = blocked
dotenv.main.DotEnv.dict = dotenv.main.DotEnv.parse = blocked
from pydantic_settings.sources import DotEnvSettingsSource
DotEnvSettingsSource._read_env_file = staticmethod(blocked)
import socket, asyncio, httpx
socket.getaddrinfo = socket.gethostbyname = socket.gethostbyaddr = blocked
asyncio.BaseEventLoop.create_connection = blocked
httpx.HTTPTransport.handle_request = blocked
async def blocked_async(*a, **k): raise GuardError('network blocked')
httpx.AsyncHTTPTransport.handle_async_request = blocked_async
import sqlalchemy, sqlalchemy.ext.asyncio as sa_async, sqlalchemy.engine.create as sa_create
from sqlalchemy.engine import make_url
def check_url(url):
    u = make_url(url)
    if u.drivername not in ('sqlite','sqlite+aiosqlite') or u.database != ':memory:' or u.host or u.query:
        raise GuardError('DB URL blocked')
real_sync, real_async = sqlalchemy.create_engine, sa_async.create_async_engine
sqlalchemy.create_engine = sa_create.create_engine = lambda url,*a,**k: (check_url(url), real_sync(url,*a,**k))[1]
sa_async.create_async_engine = lambda url,*a,**k: (check_url(url), real_async(url,*a,**k))[1]
from app.core.config import settings
assert settings.DATABASE_URL == 'sqlite+aiosqlite:///:memory:'
import pytest
rc = pytest.main(['-q','--assert=plain','-p','no:cacheprovider','-p','anyio.pytest_plugin','--tb=line','tests/investigation/test_persona_worker.py'])
print(f'PYTEST EXIT {rc}')
raise SystemExit(rc)
PY
```

Sem install, stack, API externa, DB real, migration, git mutável ou teste live.
Restante: revisão independente e GREEN T010 (evolução schemas/worker);
não marcar T007 como aprovado com esta autoria.
