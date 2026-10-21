# Legacy impact — 005-convergencia-pipeline

Data observada: 2026-10-20T23:11:14+00:00. Escopo: T003/T004 somente; registro parcial antes do runner. Produto/testes/migrations: zero alterações desta rodada. Pai mantém actions/progress/estado; este documento não aprova entrega.

## Âncora e política

Âncora disponível: `_reversa_sdd/prd.md` + `_reversa_sdd/sdd/briefing.md`, complementados por addenda 001–004 e `diretrizes-20261019-workers-jina-briefing.md`. `architecture.md` e `domain.md` ausentes: não inventados. Âncora formal de origem greenfield não torna implementação existente greenfield: há legado real em app/tests/alembic.

`.reversa/reversa-config.json`: `allowLegacyEdits: true`; `allowedPaths`: `["*", "**/*", ".*", ".*/**/*", "app/**", "frontend/**", "tests/**", "alembic/**", "requirements.txt", "QA_MATRIX.md", "PRODUCT.md", "DESIGN.md"]`. Globs amplos não ampliam delegação: somente este arquivo e regression-watch.md graváveis.

Gates lidos: `audit/cross-check.md`, revalidação editorial, 0 CRITICAL/HIGH/MEDIUM e dois LOW mitigado/operacional; `audit/requirements-audit.md`, revalidação 22/22. Requirements auditado SHA-256 `221c62523541417c9fcf78c5c5cc14b55628429dbdca96598d3aaa6058ad1dfe`; hash actions da auditoria refere snapshot editorial anterior aos checkboxes T001/T002, não igualdade exigida ao estado de trabalho. Q-501/Q-502 permanecem premissas de falha segura, não respostas humanas. Aprovações documentais não comprovam comportamento runtime.

## Alterações efetivas consolidadas (Fechamento T030)

| Arquivo afetado | Componente | Tipo | Severidade | Justificativa |
|---|---|---|---|---|
| `app/services/search.py`, `app/investigation/tools.py` | Jina Search Tool | Implementação (RF-501) | MEDIUM | Coleta integral de 10 páginas (`num=10`), parser HTML stdlib (`_JinaHTMLCleaner`) e SSRF guard |
| `app/investigation/schemas.py`, `app/investigation/worker.py` | Workers Personas | Implementação (RF-502, RF-503) | MEDIUM | Orçamento 1–3 queries, primeira busca mandatória, verificação de citação verbatim |
| `alembic/versions/0008_...`, `app/models/domain_models.py` | Migrações e Modelos | DDL / Schema (RF-503) | MEDIUM | Colunas `investigation_round`, `round`, tabela `investigation_merges` |
| `app/investigation/storage.py` | Storage de Investigação | Implementação (RF-504, RF-506) | MEDIUM | Barreira de 4 personas, persistência de merge; falha técnica não incrementa tentativa |
| `app/audit/service.py`, `app/audit/router.py` | Auditoria | Implementação (RF-504, RF-505) | MEDIUM | Remoção do corte 60k, consumo de merge committed, teto de 4 tentativas (`AUDIT_CAVEAT`) |
| `app/services/pipeline/writer.py` | Writer Pipeline | Implementação (RF-506, RF-507) | MEDIUM | Bundle unificado Evidence + Merges, guardrails de aviso de limitação e proposta, proibição de URLs fictícias |
| `app/services/research.py`, `app/investigation/service.py` | Orquestração & Ciclo | Refatoração / Adaptador (RF-508) | HIGH | `run_research` como adaptador modular, lotes topológicos, CAS WRITE com sessão fechada antes de LLM |
| `app/briefing/router.py`, `app/briefing/service.py` | Briefing Síncrono | Preservação / Conformidade (RF-509) | LOW | POST 201 síncrono, PATCH 200 síncrono, investigate 202 exclusivo, sem polling/rotas extras |
| `tests/` (investigation, audit, unit, briefing, integration) | Suítes de Testes | Testes / Garantia | LOW | 172 testes e 162 subtestes cobrindo 100% da matriz de requisitos |

## Mapeamento do legado e impacto projetado — não implementado

| Código existente | Âncora | Delta planejado |
|---|---|---|
| `app/briefing/{domain,service,serp_client,router}.py`, `app/investigation/router.py` | PRD §§4/9, sdd/briefing §§3/6, addenda 001/002 e diretrizes §4 | RF-509 preserva síncrono/decisão única e Scout SERP-only; nenhum delta agora |
| `app/investigation/{tools,worker,schemas}.py` | addendum 002, diretrizes §§1/2 | RF-501..503: dez corpos, query obrigatória/distinta e resultado validado; projeto, não implementação |
| `app/investigation/{storage,service}.py`, `app/models/domain_models.py`, `alembic/versions/` | addenda 002/003, diretrizes §§2/3 | RF-503..505: rodada, barreira/merge e CAS; migração futura |
| `app/audit/{domain,service,router}.py` | addendum 003, diretrizes §3 | RF-504/505: auditoria vinculada ao merge e teto por ponto |
| `app/services/pipeline/writer.py`, `app/services/research.py`, `app/routers/research.py`, `app/services/webhook.py` | addendum 004 e diretrizes §5; requirements 005 RF-506..508 | Writer limitado/misto, Markdown e entrega convergente; legado preservado agora |
| `tests/` correspondentes | sdd/briefing e addenda 002–004; actions inventário caller/signature | Regressões existentes, novos aceites somente nas próximas ações |

Diff conceitual: apenas rastros documentais. Coleta, persistência, auditoria, Writer e HTTP não mudaram. Normas futuras não são fatos implementados. Adendos antigos contêm alegações históricas/superadas; não reutilizados como prova atual de execução ou live.

## Preservadas

- Tema normalizado 3–300 e 3–7 pontos: sdd/briefing §3, `app/briefing/domain.py`, testes puros existentes selecionáveis.
- Aprovação definitiva sem reabertura: addendum 002, `app/briefing/domain.py`; teste existente selecionável.
- Configuração sem leitura de `.env` é restrição deste runner, não mudança no Settings de produto.
- Todo conteúdo dos 124 caminhos no manifesto preflight conferido antes da execução: zero divergências. Nenhuma alegação de preservação funcional global baseada só em hashes.

## Modificadas

Nenhuma regra de produto modificada/removida nesta rodada. Nenhum novo componente greenfield ou revision Alembic criado.

## Grafo Alembic estático

AST somente, sem importar env.py, Settings ou ScriptDirectory: `0001 (parent None), 0002/0001, 0003/0002, 0004/0003, 0005/0004, 0006/0005, 0007/0006`. Head único observado novamente: `0007`, parent `0006`. Nova revisão/parent da futura migration devem ser recalculados em T011; nenhuma ID reservada. Nenhum DB/DDL/migration executado.

## Validação T004

### Resultado real

- GREEN isolado: exit 0; guards dotenv (open e reader), DNS/socket e DB URL antes da factory passaram; imports config/database/tools passaram. DB connections bloqueadas inclusive SQLite; nenhum DDL executado.
- Regressão existente focused: 3 passed, 4 subtests passed em 0.03s, exit 0. Dois nodes de domínio e um contrato Jina via MockTransport. Fixtures/conftest lidos; sem autouse; fixtures DB não requisitadas. Plugin autoload desativado; somente `anyio.pytest_plugin` explícito. pytest-asyncio ausente, não instalado nem necessário.
- RED comportamental separado: exit 1 esperado. `JinaToolAdapter.search` real recebeu nove corpos sintéticos via MockTransport e retornou sucesso com nove URLs e conteúdo confirmado; assert específico abaixo falhou. Lacuna real RF-501/RN-501, premissa Q-501: coleta inferior a dez ainda não falha explicitamente. Não é import/assinatura/ambiente nem negativo dos guards. Não prova todos aceites de coleta integral/parser/contexto.
- Traceback sanitizado: `<stdin>:97` chama asyncio.run; `<stdin>:96`, red: `AssertionError: RF-501/RN-501 Q-501: nine bodies accepted; expected explicit safe failure`. Nenhum corpo/chave real/URL DB herdada impresso.
- Python 3.14.7; pytest 9.1.1; anyio 4.15.1; httpx 0.28.1; SQLAlchemy 2.1.4; pydantic 2.14.1; pydantic-settings 2.15.0; aiosqlite 0.22.1; alembic 1.20.0. Interpretador observado em `/root/.hermes/tools/python-3.14.7+202****0901-linux-x64/bin/python` (caminho redigido automaticamente na saída, comando usa `python` instalado).
- PRE/POST nos dois filhos: 124 caminhos do manifesto sem divergência, agregado SHA-256 do JSON normalizado com sort_keys `36f8006329d0c786607222a3f280d69ab33363f5c66f883ef35b1d02b26e7044`. Isso inclui AGENTS/política/requirements.txt e app/tests/alembic; não equivale a 124 arquivos só de app/tests/alembic. Manifesto histórico somente lido.
- Limites: nenhuma suite completa, PostgreSQL/migration, API paga, provedor live, production_probe, instalação ou T005+; nenhum produto/teste alterado. Guards não removidos pelos testes selecionados. MockTransport prova contrato local, não SSRF de produto. Não fecha feature nem aprova próprio código.
- Ocorrência operacional: primeira submissão ao executor Python tinha erro de sintaxe no wrapper (`print(green_result) torn?`), exit 1, zero comandos executados; corrigido antes dos filhos. Primeira execução GREEN sem `-u` teve saída inicial truncada pelo ambiente; repetida unbuffered, exit 0 com evidência completa. Nenhuma falha ambiental contada como RED.

### Comandos reproduzíveis completos

Executar da raiz `/root/projects/deep-research`. O bloco seguinte roda dois processos filhos Python distintos: GREEN seguido de RED. O exit 1 do RED é esperado; não mudar para pass nem desativar guard. Segredos somente gerados em memória. Runner inline, nenhum arquivo auxiliar.

```bash
cd /root/projects/deep-research
for mode in green red; do
PYTHONDONTWRITEBYTECODE=1 python -B -u - "$mode" <<'PY'
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
manifest = json.loads(Path('/root/.hermes/profiles/orchestrator/cache/scratch/forward-005-coding-preflight/manifest.json').read_text())
def baseline(label):
    bad=[p for p,h in manifest.items() if hashlib.sha256(Path(p).read_bytes()).hexdigest()!=h]
    assert not bad,bad
    print(label,len(manifest),'unchanged',hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest())
baseline('PRE')
print('PYTHON',sys.version.split()[0])
for n in ('pytest','anyio','httpx','SQLAlchemy','pydantic','pydantic-settings','aiosqlite','alembic'):
    print('VERSION',n,md.version(n))
from app.core.config import settings
assert settings.DATABASE_URL == 'sqlite+aiosqlite:///:memory:'
import app.db.database
from app.investigation.tools import JinaToolAdapter,JinaSearchError
print('IMPORTS GREEN: config, database, investigation.tools')
if sys.argv[1] == 'green':
    import pytest
    nodes=['tests/test_briefing_domain.py::BriefingDomainTests::test_theme_normalized_boundaries','tests/test_briefing_domain.py::BriefingDomainTests::test_approved_cannot_reopen','tests/investigation/test_jina_tool.py::test_jina_search_success_direct_contract_and_payload']
    print('NODES',json.dumps(nodes))
    rc=pytest.main(['-q','-p','no:cacheprovider','-p','anyio.pytest_plugin',*nodes])
    baseline('POST')
    raise SystemExit(rc)
assert sys.argv[1] == 'red'
async def red():
    recorded=[]
    payload={'data':[{'title':f'Page {i}','url':f'https://example.com/{i}','content':'synthetic body '+str(i)} for i in range(9)]}
    def handler(request):
        recorded.append(request)
        return httpx.Response(200,json=payload)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler),trust_env=False) as client:
        adapter=JinaToolAdapter(api_key=secrets.token_urlsafe(24),http_client=client)
        try: result=await adapter.search('synthetic RF-501 nine bodies')
        except JinaSearchError: return
        assert len(recorded)==1 and len(result.urls)==9
        assert all('synthetic body '+str(i) in result.content for i in range(9))
        print('RED SETUP GREEN: real adapter returned nine synthetic bodies as success')
        raise AssertionError('RF-501/RN-501 Q-501: nine bodies accepted; expected explicit safe failure')
try: asyncio.run(red())
finally: baseline('POST')

PY
rc=$?
printf '%s exit=%s\n' "$mode" "$rc"
done
```

### Reprodução da inspeção estática e hashes dos inputs/gates

Não importa Alembic/app; nenhuma leitura de `.env`.

```bash
cd /root/projects/deep-research
python -B - <<'PY'
import ast, hashlib, json
from pathlib import Path
base=Path('_reversa_forward/005-convergencia-pipeline')
for name in ['requirements.md','roadmap.md','actions.md','questions.md','investigation.md','data-delta.md','onboarding.md','interfaces/pipeline-http.md','audit/cross-check.md','audit/requirements-audit.md']:
    print(name,hashlib.sha256((base/name).read_bytes()).hexdigest())
graph={}
for p in Path('alembic/versions').glob('*.py'):
    d={}
    for n in ast.parse(p.read_text()).body:
        if isinstance(n,(ast.Assign,ast.AnnAssign)):
            for t in n.targets if isinstance(n,ast.Assign) else [n.target]:
                if isinstance(t,ast.Name) and t.id in ('revision','down_revision'):
                    d[t.id]=ast.literal_eval(n.value)
    graph[d['revision']]=d['down_revision']
assert all(parent is None or parent in graph for parent in graph.values())
for revision in graph:
    seen=set(); current=revision
    while current is not None:
        assert current not in seen
        seen.add(current); current=graph[current]
print('GRAPH',dict(sorted(graph.items())))
print('HEADS',sorted(set(graph)-{v for v in graph.values() if v}))
m=json.loads(Path('/root/.hermes/profiles/orchestrator/cache/scratch/forward-005-coding-preflight/manifest.json').read_text())
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in m.items())
print('BASELINE',len(m),'unchanged')
PY
```

Saída real da inspeção estática acima, exit 0:

```text
requirements.md 221c62523541417c9fcf78c5c5cc14b55628429dbdca96598d3aaa6058ad1dfe
roadmap.md 718769ee2e19ada032092345ed9408a8514a23bf6adf4202b16d0112108db986
actions.md 656444dca07cb140d81769bba433eb06d163e3f002f33366baffe8046c649077
questions.md c6c9171af8cea3642b633467a62ee6b4c235b2776a12c0767de1f380999e96ae
investigation.md f9dc6839d5a67aade9728b083c2cd36eaa16afbaeffeaed4164905f961cdc39f
data-delta.md 06f33dfddfc37a337e182d7e6b3c98a50ed6ed4674a8f6593dc547afeb4863a9
onboarding.md f5042a0e66e723ce81754b22c987fd224a1acacd3952b7ea70206384b6449b48
interfaces/pipeline-http.md 8afd6c66835d78797604b5dee133f01adb390db0c735024df37d15e7361ed904
audit/cross-check.md aae7fae3631ca4b69bfa148d486649f89b0f14c0424401bbb908ddb3bf8d6876
audit/requirements-audit.md 3239478dd2a36c248aec07dedb88f8e4434c7428dad91dc68e4780d7e35591bc
GRAPH {'0001': None, '0002': '0001', '0003': '0002', '0004': '0003', '0005': '0004', '0006': '0005', '0007': '0006'}
HEADS ['0007']
BASELINE 124 unchanged
```
