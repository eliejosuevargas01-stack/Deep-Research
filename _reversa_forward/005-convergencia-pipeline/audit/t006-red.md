# T006 — autoria RED Writer

## Resultado

Execução final: **6 failed, 10 passed, 0 errors, 0 skipped**, pytest exit **1**, 3.68s. Arquivo único selecionado: `tests/unit/test_pipeline_writer_convergence.py`. Nenhum node investigation coletado/lido; nenhum DB conectado. Produto sem alteração. Evidência autoral, não aprovação independente; pai mantém actions/progress/estado.

Preflight: AGENTS, state, active-requirements e política lidos; gates T001–T004 [X]. Âncora prd.md+sdd/briefing; architecture/domain ausentes. allowLegacyEdits=true com tests/**; escopo limitado aos dois arquivos delegados. Inputs T006/T018/T019, RF-506/507, RN-507/508 e Validação T004 consultados. Não reiniciado planejamento.

## Contrato exercitado

Imports e chamadas reais `validate_report_quality(text, point_titles)` e `_write_report(research, points)`. Nenhuma assinatura futura inventada, implementação de guardrail copiada ou monkeypatch de Writer. Research/ResearchPoint/Evidence/Report são ORM reais, IDs explícitos; pontos AUDIT_CAVEAT conclusivos. Sessão `MagicMock(spec=AsyncSession)` implementa somente contexto/scalars/get/add/commit em memória, sem engine de teste/DDL. LLM e add_event simulados nas fronteiras; add_event não serve como prova de entrega. Substantive repete fato sintético citado para ultrapassar mínimo atual e isolar guardrail Markdown.

Proposta imperativa didática em negrito é fixture representativa do diagnóstico normativo, não transcrição recuperada de execução histórica. Nenhuma frase especial recebe isenção no teste ou produto.

## Nodes e primeiro bloqueio

Prefixo de todos nodes: `tests/unit/test_pipeline_writer_convergence.py::`.

| Node | RF/RN | Resultado / primeiro bloqueio real |
|---|---|---|
| test_rf506_quality_accepts_short_honest_sections | RF-506/RN-507 | FAIL: validate_report_quality levanta ValueError `Writer returned incomplete report` (writer.py:21), antes da aceitação curta |
| test_rf506_quality_still_requires_every_point_section | RF-506 | PASS: seção ausente continua rejeitada; caracterização |
| test_rf506_zero_evidence_conclusive_points | RF-506/RN-507 | FAIL: _write_report levanta RuntimeError `Writer cannot produce a report without evidence` (writer.py:39) |
| test_rf506_mixed_preserves_cited_facts_and_uncited_limit | RF-506/RN-507 | FAIL: RuntimeError `Writer published uncited factual content (prose, list, or table)` (writer.py:68), linha `Sem evidências aproveitáveis para este ponto.` |
| test_rf507_bold_nonfactual_proposal_accepted | RF-507/RN-508 | FAIL: mesma exceção writer.py:68, proposta imperativa em negrito |
| test_rf507_uncited_fact_rejected[prose] | RF-507/RN-508 | PASS: fato sem citação rejeitado; caracterização |
| test_rf507_uncited_fact_rejected[bold] | RF-507/RN-508 | PASS: fato em negrito rejeitado; caracterização |
| test_rf507_uncited_fact_rejected[list] | RF-507/RN-508 | PASS: fato em lista rejeitado; caracterização |
| test_rf507_uncited_fact_rejected[table] | RF-507/RN-508 | PASS: tabela sem fonte rejeitada; caracterização (cabeçalho também candidato atual) |
| test_rf507_uncited_fact_rejected[proposal-label] | RF-507/RN-508 | PASS: rótulo não isenta fato; caracterização |
| test_rf507_uncited_fact_rejected[limitation-label] | RF-507/RN-508 | PASS: rótulo não isenta fato; caracterização |
| test_rf507_uncited_fact_rejected[bold-proposal-fact] | RF-507/RN-508 | PASS: rótulo+bold não isentam; caracterização |
| test_rf507_uncited_fact_rejected[bold-limitation-fact] | RF-507/RN-508 | PASS: rótulo+bold não isentam; caracterização |
| test_rf507_uncited_fact_rejected[arbitrary-bare-url] | RF-507/RN-508 | FAIL: `pytest.raises` test.py:127, `DID NOT RAISE RuntimeError`; URL nua e ausência de pontuação final escapam |
| test_rf507_uncited_fact_rejected[status-table-fact] | RF-507/RN-508 | FAIL: `pytest.raises` test.py:127, `DID NOT RAISE RuntimeError`; cabeçalho Status não deve isentar fato |
| test_rn507_unknown_citation_url_rejected | RN-507/RF-507 | PASS: URL Markdown fora das fontes conhecidas rejeitada; caracterização |

Nos três caminhos positivos _write_report bloqueados (zero/misto/proposta), asserts posteriores de payload, Report único, texto íntegro e commit **não alcançados**. Zero Evidence também não alcança assert evidence_records=0/ausência de http. Misto não alcança asserts preservação CITED/limitação. As duas falhas `DID NOT RAISE` completam Writer e asserts internos de payload/Report/commit antes de falhar expectativa negativa. Nenhuma prova Report/DONE pelos entrypoints; T021/T026 continuam responsáveis. Sem alegação de bundle merge T018 executado.

## Isolamento e ocorrências

Runner derivado literalmente dos guards T004. Python -B, bytecode/cache off, autoload off, somente AnyIO instalado explícito; fixture backend asyncio. Ambiente sensível removido sem imprimir valores; secrets sintéticos em memória. BaseSettings força _env_file=None antes app imports. Dotenv open/readers, DNS/socket/default HTTP e DB conexões bloqueados; URL PostgreSQL sintética negativa barrada antes factory. Guards passam antes pytest, inclusive após desabilitar dispatcher load_dotenv incondicional do LiteLLM. Isso não prova segurança global.

Tentativa 1: exit 2, 1 collection error, LiteLLM chama load_dotenv incondicional. Tentativa 2: exit 2, 1 collection error, LiteLLM tenta buscar mapa de custos por HTTP e guard bloqueia. Não contadas como RED. Correção somente runner: dispatcher load_dotenv retorna False sem leitura, readers/open seguem bloqueados; LITELLM_LOCAL_MODEL_COST_MAP=True usa recurso instalado conforme código da dependência. Tentativa 3: 6 failed/10 passed exit 1. Repetição final reforça negativos readers após dispatcher: mesmo resultado 6/10, exit 1. Nenhum guard desativado para rede/reader/DB.

## Integridade

Syntax compile em memória e whitespace sem trailing espaços: PASS. Teste SHA-256 `df95013f2fa9361864ed2fafc23b00cb75b59f91b775f95aa390baa0173117dc`.
Writer SHA-256 antes/depois `9c9513d6702a564f2639c51f0f764efe3aa0994490c2eed1c9f81f9bbe4ad5f9`.
Manifesto readonly preflight: 122 caminhos protegidos comparados PRE/POST, zero diferenças; dois caminhos sibling autorizados excluídos **sem leitura** (`tests/investigation/test_jina_tool.py`, `tests/investigation/conftest.py`). Nenhum snapshot sobrescrito. Hashes não provam semântica global.

## Comando completo reproduzível

Raiz `/root/projects/deep-research`; comando final realmente executado, exit 1 esperado. Nenhum harness salvo.

```bash
cd /root/projects/deep-research
PYTHONDONTWRITEBYTECODE=1 python -B -u - <<'PY'
import os, sys, base64, secrets
from pathlib import Path
import hashlib, json, importlib.metadata as md
for name in tuple(os.environ):
    if any(w in name.upper() for w in ('DATABASE','DB_URL','KEY','TOKEN','SECRET','PASSWORD','MODEL','PROXY','API_BASE')):
        os.environ.pop(name, None)
os.environ.update(ENVIRONMENT='test', DATABASE_URL='sqlite+aiosqlite:///:memory:', ADMIN_PASSWORD=secrets.token_urlsafe(32), SESSION_SECRET=secrets.token_urlsafe(48), API_AUTH_SECRET=secrets.token_urlsafe(32), APP_ENCRYPTION_KEY=base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(), PYTEST_DISABLE_PLUGIN_AUTOLOAD='1', PYTHONDONTWRITEBYTECODE='1')
class GuardError(RuntimeError): pass
def blocked(*a, **k): raise GuardError('access blocked')
def audit(event,args):
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
from pydantic_settings.sources import DotEnvSettingsSource
dotenv.load_dotenv = dotenv.dotenv_values = dotenv.main.load_dotenv = dotenv.main.dotenv_values = blocked
dotenv.main.DotEnv.dict = dotenv.main.DotEnv.parse = blocked
DotEnvSettingsSource._read_env_file = staticmethod(blocked)
import socket, asyncio, httpx
socket.getaddrinfo = socket.gethostbyname = socket.gethostbyaddr = blocked
asyncio.BaseEventLoop.create_connection = blocked
httpx.HTTPTransport.handle_request = blocked
async def blocked_async(*a, **k): raise GuardError('network blocked')
httpx.AsyncHTTPTransport.handle_async_request = blocked_async
import sqlalchemy, sqlalchemy.ext.asyncio as sa_async, sqlalchemy.engine.create as sa_create
from sqlalchemy.engine import make_url, Engine
from sqlalchemy.ext.asyncio import AsyncEngine
calls = []
def check_url(url):
    u = make_url(url)
    if u.drivername not in ('sqlite','sqlite+aiosqlite') or u.database != ':memory:' or u.host or u.query:
        raise GuardError('DB URL blocked')
real_sync, real_async = sqlalchemy.create_engine, sa_async.create_async_engine
def sync_factory(url,*a,**k):
    check_url(url); calls.append('sync'); return real_sync(url,*a,**k)
def async_factory(url,*a,**k):
    check_url(url); calls.append('async'); return real_async(url,*a,**k)
sqlalchemy.create_engine = sa_create.create_engine = sync_factory
sa_async.create_async_engine = async_factory
Engine.connect = Engine.raw_connection = blocked
AsyncEngine.connect = AsyncEngine.begin = blocked
def socket_negative():
    with socket.socket() as s: s.connect(('192.0.2.1',443))
for check in [lambda: open('.env'),lambda: dotenv.dotenv_values('.env'),lambda: socket.getaddrinfo('example.invalid',443),socket_negative,lambda: async_factory('postgresql+asyncpg://invalid.invalid/forbidden')]:
    before = len(calls)
    try: check()
    except GuardError: pass
    else: raise AssertionError('guard failed')
    assert len(calls) == before
print('GUARDS GREEN: dotenv open/reader, DNS/socket, DB URL before factory; no connection')

for check in [lambda: httpx.Client(trust_env=False).get('https://example.invalid'), lambda: Engine.connect(None)]:
    try: check()
    except GuardError: pass
    else: raise AssertionError('transport/DB connection guard failed')
print('EXTRA GUARDS GREEN: default HTTP and DB connection')
from pathlib import Path
import hashlib, json
path=Path('tests/unit/test_pipeline_writer_convergence.py')
compile(path.read_text(),str(path),'exec')
assert all(line == line.rstrip() for line in path.read_text().splitlines())
print('SYNTAX/WHITESPACE GREEN', hashlib.sha256(path.read_bytes()).hexdigest())
manifest=json.loads(Path('/root/.hermes/profiles/orchestrator/cache/scratch/forward-005-coding-preflight/manifest.json').read_text())
exceptions={'tests/investigation/test_jina_tool.py','tests/investigation/conftest.py'}
def baseline(label):
    # Do not read sibling mutable files, even for hashing.
    checked={p:h for p,h in manifest.items() if p not in exceptions}
    bad=[p for p,h in checked.items() if hashlib.sha256(Path(p).read_bytes()).hexdigest()!=h]
    assert not bad,bad
    print(label,len(checked),'protected paths unchanged; sibling exceptions excluded')
    print('WRITER SHA256',hashlib.sha256(Path('app/services/pipeline/writer.py').read_bytes()).hexdigest())
baseline('PRE')
os.environ['LITELLM_LOCAL_MODEL_COST_MAP'] = 'True'
# LiteLLM unconditionally calls load_dotenv on import; disable dispatcher only.
# Real dotenv readers/open remain blocked and negatively verified.
dotenv.load_dotenv = dotenv.main.load_dotenv = lambda *a, **k: False
for check in [lambda: open('.env'), lambda: dotenv.dotenv_values('.env'), lambda: DotEnvSettingsSource._read_env_file(Path('.env'))]:
    try: check()
    except GuardError: pass
    else: raise AssertionError('dotenv reader guard failed after dispatcher disable')
print('DOTENV READERS GREEN after LiteLLM dispatcher disabled')
from app.core.config import settings
assert settings.DATABASE_URL == 'sqlite+aiosqlite:///:memory:'
import pytest
nodes=['tests/unit/test_pipeline_writer_convergence.py']
print('NODES',json.dumps(nodes))
rc=pytest.main(['-q','-p','no:cacheprovider','-p','anyio.pytest_plugin','--tb=short',*nodes])
baseline('POST')
print('PYTEST EXIT',rc)
raise SystemExit(rc)

PY
```

Sem install, stack, API externa, DB real, migration, git mutável ou teste live. Restante: revisão independente e GREEN T018/T019; não marcar T006 como aprovado com esta autoria.
