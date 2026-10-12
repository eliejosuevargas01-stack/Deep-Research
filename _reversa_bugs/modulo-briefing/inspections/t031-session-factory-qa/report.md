# QA focada pós-auditoria — T031 (Ownership de session_factory e ciclo de vida)

## Veredito
**PASS_LOCAL**. Todos os 24 métodos em `tests/test_briefing_llm_binding.py` passaram com exit 0 (1 sync, 23 async; zero skips ou testes enfraquecidos). Validação rigorosa e independente de ciclo de vida e concorrência comprovou que:
1. A sessão aberta via `session_factory()` é encerrada estritamente antes da chamada de rede (`litellm.acompletion`), garantindo fechamento e devolução imediata da conexão ao pool antes de qualquer latência externa de LLM.
2. Nenhuma invocação de `commit()` ou `rollback()` ocorre no binding LiteLLM do briefing.
3. Overrides inválidos de timeout (`0`, `-1`, `nan`, `inf`, `-inf`, `bool`, `string`, overflow numérico) acionam early abort com contagem de chamadas a `session_factory` exatamente igual a 0.
4. Passagem de caller-owned session (`AsyncSession` direta em vez de fábrica) é rejeitada com `TypeError`.
5. Teste integrado com SQLite em memória (`sqlite+aiosqlite:///:memory:`) e `StaticPool` comprovou a garantia D3: `get_record` obtém settings e o encerramento da sessão isolada sem commit reverte o flush transitório, mantendo o banco com 0 linhas na tabela `app_settings`.
6. Garantias anteriores preservadas: `test_no_internal_retries_on_503_openai_sdk` (T029) passa com 1 request e flags globais preservadas; matriz de erros T030 e guardrail de output permanecem 100% íntegros.
7. Integridade: `git diff --check` exit 0; 102/102 arquivos congelados da linha 75 do `progress.jsonl` conferidos via SHA-256 (zero discrepâncias). Zero defeitos de produto confirmados; zero bugs promovidos (`promoted_to: null`).

## Preflight e mapa do recorte
- Root: `/root/projects/deep-research`, branch `main`.
- Preflight validado: `AGENTS.md`, `.reversa/state.json`, `.reversa/active-requirements.json`, `.reversa/reversa-config.json` e `git status --short`.
- Feature ativa: `_reversa_forward/001-modulo-briefing` em estágio `coding`. Requisitos aprovados e PRD/spec greenfield são as fontes de produto vigentes.
- Papel: auditor leaf / qa-specialist, sem subdelegação, sem alteração de código, testes ou documentos de planejamento.
- Recorte exclusivo: F-CONSISTENCY-01 / `actions.md:85` / D3 e D5 vigentes em `audit/t011-integration-decomposition.md:99–110` e `audit/t029-t031-planning-delta.md:32–39`.
- Entrega inspecionada: `audit/t031-execution.md` e relatório da inspeção prévia `_reversa_bugs/modulo-briefing/inspections/t031-session-factory/report.md` (veredito PASS).
- Regra de edição estrita: única escrita de projeto permitida é este relatório `_reversa_bugs/modulo-briefing/inspections/t031-session-factory-qa/report.md`.

## Mapa aceitação → símbolo → checks

| Aceitação | Fonte / símbolo | Check próprio |
|---|---|---|
| D5 / T031: Ownership de sessão e factory injetável | `audit/t011-integration-decomposition.md:99–110`, `audit/t029-t031-planning-delta.md:32–39`; `app/briefing/llm_binding.py:100–121` (`make_scout_complete`) | `make_scout_complete` recebe `session_factory: async_sessionmaker[AsyncSession]`. Caller-owned `AsyncSession` direta falha com `TypeError`. Sessão de curta duração aberta com `async with session_factory() as session:`, escalares imutáveis copiados e contexto fechado antes do transporte. |
| RF-08 / D5: Ordem estrita de chamada e ausência de commit/rollback | `requirements.md:58`, `actions.md:85`; `app/briefing/llm_binding.py:113–120, 148` | Probe de eventos instrumentado: sequência observada `['session_enter', 'runtime_settings', 'get_record', 'session_close', 'session_exit', 'litellm_acompletion']`. `session_close` e `session_exit` ocorrem estritamente antes de `litellm_acompletion`. `session.commit` e `session.rollback` possuem contagem de chamadas exatamente igual a 0. |
| RF-10 / D5: Early abort de timeout com 0 chamadas à factory | `audit/t029-t031-planning-delta.md:32–39`; `app/briefing/llm_binding.py:89–98, 107–112` (`_checked_timeout`) | Validação estrita de `timeout_s` override ocorre antes do bloco `async with session_factory()`. Valores inválidos (`0`, `-1`, `nan`, `inf`, `-inf`, `True`, `False`, `'abc'`, `10**1000`) levantam `ValueError` e `session_factory.call_count == 0`. |
| D3 / T031: Reversão de flush transitório em SQLite integrado | `audit/t011-integration-decomposition.md:105–110`; `app/briefing/llm_binding.py:113–120`; `tests/test_briefing_llm_binding.py:107–146` | Banco `sqlite+aiosqlite:///:memory:` com `StaticPool` e DDL de `Base.metadata`. Invocação de `make_scout_complete`: `get_record` efetua flush transitório de `AppSettings` para ler campos. Encerramento da sessão isolada sem commit reverte inserção: consulta posterior em nova sessão retorna exatamente 0 linhas em `app_settings`. |
| Manutenção T029: 1 request HTTP 503 e flags globais | `tests/test_briefing_llm_binding.py:476–544` (`test_no_internal_retries_on_503_openai_sdk`) | Execução do método unitário contra MockTransport 503 com flags de clientes globais forçadas: exatamente 1 request disparado, captura de `LLMAttemptError` e flags globais restauradas. |
| Manutenção T030: Matriz de erros e guardrail de output | `app/briefing/llm_binding.py:46–86` (`_is_eligible_llm_error`), `tests/test_briefing_llm_binding.py` | 12 testes dedicados à matriz de erros T030 e sanitização de output passando com 100% de sucesso. |
| Integridade dos congelamentos | `_reversa_forward/001-modulo-briefing/progress.jsonl:75` (`pre_dispatch_sha256`) | 102/102 hashes SHA-256 verificados contra o disco; zero discrepâncias. `git diff --check` exit 0. |

## Execução própria e resultados factuais

### 1. Suíte unitária do binding
Comando: `python3 -B -m unittest tests.test_briefing_llm_binding -v` (cwd: `/root/projects/deep-research`)
- Exit code: **0**
- Testes executados: **24** (24 passed, 0 failures, 0 errors, 0 skipped)
- Duração: ~0.76s
- Métodos por tipo (AST):
  * **1 sync**: `test_default_timeout_validation_overflow_and_invalid`
  * **23 async**: cobrindo ciclo de vida, ausência de commit/rollback, abort precoce, SQLite integrado, retries zero, matriz de erro T030 e guardrail.

### 2. Validação rigorosa de ciclo de vida e concorrência (Probe QA 1 & 2)
- **Ordem de chamada**:
  * Eventos observados: `['session_enter', 'runtime_settings', 'get_record', 'session_close', 'session_exit', 'litellm_acompletion']`
  * `session_close` e `session_exit` ocorrem estritamente antes do início do transporte e de `litellm.acompletion`.
- **Proibição de commit e rollback**:
  * `fake_session.commit.call_count == 0`
  * `fake_session.rollback.call_count == 0`
- **Early abort com zero chamadas à factory**:
  * Testados 9 valores inválidos de `timeout_s` override (`0`, `-1`, `float('nan')`, `float('inf')`, `-float('inf')`, `True`, `False`, `'abc'`, `10**1000` overflow).
  * Todos levantaram `ValueError` com mensagem padronizada `"Configuração de timeout LLM inválida (timeout_s)"`.
  * Contagem de chamadas a `session_factory` em todas as iterações: **exatamente 0**.
- **Rejeição de caller-owned session**:
  * Passagem de instância de `AsyncSession` diretamente em vez de `async_sessionmaker`:
  * Lança `TypeError: 'AsyncSession' object is not callable`, impedindo que o chamador acople o ciclo de vida da sua sessão externa.

### 3. Teste integrado com SQLite em memória e D3 (Probe QA 3)
- Engine: `sqlite+aiosqlite:///:memory:` com `StaticPool` e `connect_args={'check_same_thread': False}`.
- DDL completo criado via `Base.metadata.create_all`.
- Invocação real de `make_scout_complete(session_factory)` com settings de runtime.
- Leitura de settings: `get_record` adiciona `AppSettings` com defaults e roda `flush()`.
- Saída do contexto assíncrono fecha a sessão sem commit.
- Verificação subsequente: `select(AppSettings)` executado em nova sessão retorna **0 linhas** (`len(rows) == 0`).
- Garantia D3 comprovada: nenhuma persistência espúria ocorre no banco de dados.

### 4. Preservação de garantias anteriores
- **T029**: `test_no_internal_retries_on_503_openai_sdk` executado com sucesso; exactamente 1 requisição HTTP disparada sob erro 503; `num_retries=0` e `max_retries=0` repassados a `litellm.acompletion`.
- **T030**: Todos os 12 testes da matriz de erros de classificação e sanitização passam com 100% de conformidade.
- **Suíte global de briefing**: `python3 -B -m unittest discover -s tests -p 'test_briefing_*.py'` executa 140 testes em 3.54s com exit 0 (zero regressões).

### 5. Verificações de integridade
- `git diff --check`: exit **0** (nenhum trailing whitespace, conflito ou erro de formato).
- Manifesto `pre_dispatch_sha256` na linha 75 do `progress.jsonl`: **102 arquivos** auditados via SHA-256.
- Mismatches encontrados: **0**.
- Arquivos ausentes: **0**.

## Dependências avaliadas (`importlib.metadata`)
- `litellm`: **1.104.0**
- `sqlalchemy`: **2.1.3**
- `aiosqlite`: **0.22.1**
- `httpx`: **0.28.1**
- `pydantic`: **2.13.5**
- `alembic`: **1.20.0**
- `fastapi`: **0.142.2**
- `python`: **3.14.7**

## Exclusões explícitas
- **Rede externa**: Nenhuma conexão externa real executada; chamadas de LLM e transporte operadas via mocks controlados.
- **Banco Postgres externo**: Teste integrado executado com `sqlite+aiosqlite:///:memory:` e `StaticPool` para validação de lifecycle e flush sem necessidade de serviço externo.
- **T025**: A orquestração persistida permanece bloqueada aguardando encerramento sequencial de T031.
- **Escrita de código**: Nenhum arquivo além deste relatório foi criado ou modificado no repositório. Código, testes e configurações permanecem 100% congelados.

## Probes reproduzíveis em blocos fenced python

### Probe QA 1: Ciclo de vida estrito, ordem e ausência de commit/rollback
```python
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from types import SimpleNamespace
from app.briefing.llm_binding import make_scout_complete

async def probe_lifecycle():
    call_order = []
    fake_session = AsyncMock()
    async def fake_close():
        call_order.append("session_close")
    fake_session.close = AsyncMock(side_effect=fake_close)
    fake_session.commit = AsyncMock(side_effect=lambda: call_order.append("commit"))
    fake_session.rollback = AsyncMock(side_effect=lambda: call_order.append("rollback"))

    class CM:
        async def __aenter__(self):
            call_order.append("session_enter")
            return fake_session
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            await fake_session.close()
            call_order.append("session_exit")

    factory = MagicMock(side_effect=CM)
    async def fake_acompletion(**kw):
        call_order.append("litellm_acompletion")
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))])

    async def fake_runtime(db):
        call_order.append("runtime_settings")
        return {"gemini": "k"}, {"scout": "gemini/m"}
    async def fake_record(db):
        call_order.append("get_record")
        return SimpleNamespace(openai_base_url=None)

    with patch("app.briefing.llm_binding.runtime_settings", fake_runtime), \
         patch("app.briefing.llm_binding.get_record", fake_record), \
         patch("app.briefing.llm_binding.litellm.acompletion", fake_acompletion), \
         patch("app.briefing.llm_binding._enforce_safe_transport"):
        fn = make_scout_complete(factory, default_timeout_s=30.0)
        res = await fn("sys", "usr")
        assert res == "ok"

    assert call_order == ["session_enter", "runtime_settings", "get_record", "session_close", "session_exit", "litellm_acompletion"]
    assert call_order.index("session_close") < call_order.index("litellm_acompletion")
    assert call_order.index("session_exit") < call_order.index("litellm_acompletion")
    assert fake_session.commit.call_count == 0
    assert fake_session.rollback.call_count == 0

asyncio.run(probe_lifecycle())
```

### Probe QA 2: Early abort com zero chamadas à factory
```python
import asyncio
from unittest.mock import MagicMock
from app.briefing.llm_binding import make_scout_complete

async def probe_early_abort():
    invalids = [0, -1, float("nan"), float("inf"), -float("inf"), True, False, "abc", 10**1000]
    for inv in invalids:
        factory = MagicMock()
        fn = make_scout_complete(factory, default_timeout_s=30.0)
        try:
            await fn("sys", "usr", timeout_s=inv)
            raise AssertionError(f"Deveria ter falhado para {inv}")
        except ValueError as e:
            assert "Configuração de timeout LLM inválida (timeout_s)" in str(e)
            assert factory.call_count == 0, f"Factory chamada {factory.call_count} vezes para {inv}"

asyncio.run(probe_early_abort())
```

### Probe QA 3: SQLite em memória integrado com StaticPool e D3
```python
import asyncio
from unittest.mock import AsyncMock, patch
from types import SimpleNamespace
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy import select
from app.models.domain_models import AppSettings, Base
from app.briefing.llm_binding import make_scout_complete

async def probe_sqlite():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    fake_resp = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="briefing text"))])

    with patch("app.services.settings.settings.SCOUT_MODEL", "gemini/gemini-3.1-flash-lite-preview"), \
         patch("app.services.settings.settings.GEMINI_API_KEY", "gemini-integrated-key"), \
         patch("app.briefing.llm_binding.litellm.acompletion", new=AsyncMock(return_value=fake_resp)), \
         patch("app.briefing.llm_binding._enforce_safe_transport"):
        fn = make_scout_complete(session_factory, default_timeout_s=30.0)
        res = await fn("sys_prompt", "user_prompt")
        assert res == "briefing text"

    async with session_factory() as check_session:
        rows = (await check_session.execute(select(AppSettings))).scalars().all()
        assert len(rows) == 0, f"Esperado 0 linhas, obtido {len(rows)}"

    await engine.dispose()

asyncio.run(probe_sqlite())
```

### Probe QA 4: Integridade dos 102 arquivos congelados
```python
import hashlib, json, pathlib

R = pathlib.Path("/root/projects/deep-research")
line75 = (R / "_reversa_forward/001-modulo-briefing/progress.jsonl").read_text().splitlines()[74]
manifest = json.loads(line75)["pre_dispatch_sha256"]
assert len(manifest) == 102

mismatches = []
missing = []
for p, h in manifest.items():
    fp = R / p
    if not fp.exists():
        missing.append(p)
    elif hashlib.sha256(fp.read_bytes()).hexdigest() != h:
        mismatches.append(p)

assert len(missing) == 0, f"Faltando: {missing}"
assert len(mismatches) == 0, f"Discrepâncias: {mismatches}"
print(f"102/102 arquivos congelados verificados com sucesso.")
```
