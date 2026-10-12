# Inspeção diagnóstica T031 — ownership de session_factory e lifecycle

## Veredito: PASS

Auditoria diagnóstica T031 concluída com sucesso. Zero defeitos confirmados, zero observações impeditivas. Assinatura da fábrica `make_scout_complete(session_factory, default_timeout_s=30.0)` em estrita conformidade com D5 vigente; caller-owned `AsyncSession` rejeitada; override de timeout validado precocemente com ZERO chamadas em `session_factory`; sessão própria curta aberta via `async with session_factory() as session:`, escalares imutáveis copiados e sessão fechada estritamente ANTES de `_enforce_safe_transport()` e `litellm.acompletion`; nenhuma chamada a `commit()` ou `rollback()` no chamador; D3 comprovado com SQLite em memória (`sqlite+aiosqlite:///:memory:`), onde criação transitória por flush de `get_record` reverte no close da sessão isolada e deixa 0 linhas de `AppSettings` no banco. Suite de testes do módulo com 24 métodos (1 sync, 23 async) passando 100% via unittest; 140 testes de briefing passando globalmente; integridade dos 101 arquivos congelados preservada (101/101 SHA-256 conferidos contra baseline da linha 74 do `progress.jsonl`).

## Preflight e mapa do recorte

- Root: `/root/projects/deep-research`, branch `main`.
- Preflight: `AGENTS.md`, `.reversa/state.json`, `.reversa/active-requirements.json`, `.reversa/reversa-config.json` e `git status --short` conferidos.
- Feature: `_reversa_forward/001-modulo-briefing` em estágio `coding`. Requisitos aprovados e PRD/spec greenfield existentes são as fontes de produto vigentes.
- Papel: auditor leaf, sem subdelegação, sem alteração de código/testes/documentos de planejamento.
- Recorte exclusivo: F-CONSISTENCY-01 / `actions.md:85` / D3/D5 vigentes em `audit/t011-integration-decomposition.md:99–110` e `audit/t029-t031-planning-delta.md:32–39`.
- Entrega inspecionada: `audit/t031-execution.md`, cobrindo `app/briefing/llm_binding.py` e `tests/test_briefing_llm_binding.py`.
- Arquivos congelados: 101 arquivos auditados com SHA-256 idêntico ao registro de pre-dispatch da linha 74 de `progress.jsonl`.
- Regra de edição estrita: única escrita permitida é este relatório `_reversa_bugs/modulo-briefing/inspections/t031-session-factory/report.md`.

## Contagens por lente

| Lente | Evidência executada | Defeitos confirmados | Observações | Veredito |
|---|---|---:|---:|:---:|
| 1. Conformidade e contratos | Assinatura fábrica/callable, validação default e override, early abort 0 chamadas factory, rejeição caller-owned session, overflow float em ValueError fixo, >30s aceito | 0 | 0 | PASS |
| 2. Concorrência, consistência e ciclo de vida | Ordem de chamada estrita (session close < acompletion), sem commit/rollback, D3 com SQLite em memória provando 0 linhas persistidas após flush transitório | 0 | 0 | PASS |
| 3. Cobertura e preservação | 24 métodos unittest (1 sync, 23 async), preservação de `num_retries=0` e `max_retries=0` (T029), matriz de erro T030, guardrail de output, `_enforce_safe_transport()`, 101 SHA congelados | 0 | 0 | PASS |

Total de defeitos: 0. Total de observações: 0. Promovidos a bugs: 0.

## Verificações e evidências reais

### 1. Suite de testes do módulo binding
Comando: `python3 -B -m unittest tests.test_briefing_llm_binding -v`
Resultado: Exit 0. 24 testes executados em 0.728s, 24 OK.
- 1 método síncrono: `test_default_timeout_validation_overflow_and_invalid`.
- 23 métodos assíncronos cobrindo ciclo de vida, abort precoce, SQLite integrado, retries zero, matriz de erro, guardrail e propagação de exceções.

### 2. Suite global de testes de briefing
Comando: `python3 -B -m unittest discover -s tests -p 'test_briefing_*.py'`
Resultado: Exit 0. 140 testes executados em 3.603s, 140 OK. Zero regressões no módulo de briefing.

### 3. Git diff check
Comando: `git diff --check`
Resultado: Exit 0. Nenhuma divergência de formato, espaço em branco ou conflito.

### 4. Integridade dos 101 arquivos congelados
Executado script Python calculando SHA-256 dos 101 arquivos listados em `pre_dispatch_sha256` na linha 74 de `_reversa_forward/001-modulo-briefing/progress.jsonl`:
Resultado:
- Total de arquivos auditados: 101.
- Mismatches: 0.
- Missing: 0.
- Todos os 101 arquivos mantêm o conteúdo congelado intacto.

### 5. Probe de ciclo de vida e ordem de chamada
Verifica que a sessão aberta é fechada estritamente antes do início do transporte e da chamada `litellm.acompletion`, e que nenhum `commit()` ou `rollback()` é invocado.
Evidência observada:
- Ordem de eventos: `['session_enter', 'session_close', 'session_exit', 'litellm_acompletion']`.
- `session_close` e `session_exit` ocorrem estritamente antes de `litellm_acompletion`.
- `fake_session.commit.called` == False.
- `fake_session.rollback.called` == False.

### 6. Probe D3 — SQLite em memória e reversão de flush transitório
Executado teste com `sqlite+aiosqlite:///:memory:` e `StaticPool`, com metadata real de `Base` (incluindo tabela `app_settings`):
- `get_record(session)` executa `session.add(record)` e `await session.flush()` quando o banco está vazio.
- `make_scout_complete` extrai os modelos e chaves configurados via settings de runtime.
- Ao sair do bloco `async with session_factory() as session:`, a sessão é encerrada sem commit.
- Consulta subsequente com nova sessão: `select(AppSettings)` retorna 0 linhas (`len(rows) == 0`).
- Comprovado: nenhuma linha de configuração é persistida silenciosamente como efeito colateral da primeira leitura.

### 7. Probe de contratos e validação precoce de timeout
- Factory chamada com overrides inválidos (`0`, `-5`, `nan`, `inf`, `True`, `'abc'`, `10**1000` overflow):
  - Todos lançam `ValueError` com mensagem padronizada `Configuração de timeout LLM inválida (timeout_s)`.
  - Contagem de chamadas a `session_factory`: exatamente 0 (early abort sem tocar no banco, transporte ou LLM).
- Passagem de caller-owned session (`AsyncSession` diretamente em vez de factory):
  - Lança `TypeError` ao tentar invocar a sessão como contexto assíncrono.
- Timeout válido > 30s (ex.: `45.5s`):
  - Aceito e repassado integralmente aos kwargs de `litellm.acompletion` (`timeout=45.5`).
  - Preservados simultaneamente: `num_retries=0` e `max_retries=0`.

## Scripts de probes reproduzíveis

### Probe A: Ordem de chamada e ausência de commit/rollback
```python
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from types import SimpleNamespace
from app.briefing.llm_binding import make_scout_complete

async def probe():
    call_order = []
    fake_session = AsyncMock()
    async def fake_close():
        call_order.append('session_close')
    fake_session.close = AsyncMock(side_effect=fake_close)
    
    class CM:
        async def __aenter__(self):
            call_order.append('session_enter')
            return fake_session
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            await fake_session.close()
            call_order.append('session_exit')

    factory = MagicMock(side_effect=CM)
    async def fake_acompletion(**kw):
        call_order.append('litellm_acompletion')
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='ok'))])

    async def fake_runtime(db):
        return {'gemini': 'k'}, {'scout': 'gemini/m'}
    async def fake_record(db):
        return SimpleNamespace(openai_base_url=None)

    with patch('app.briefing.llm_binding.runtime_settings', fake_runtime), \
         patch('app.briefing.llm_binding.get_record', fake_record), \
         patch('app.briefing.llm_binding.litellm.acompletion', fake_acompletion), \
         patch('app.briefing.llm_binding._enforce_safe_transport'):
        fn = make_scout_complete(factory, default_timeout_s=30.0)
        res = await fn('sys', 'usr')
        assert res == 'ok'

    assert call_order == ['session_enter', 'session_close', 'session_exit', 'litellm_acompletion']
    assert not hasattr(fake_session, 'commit') or not fake_session.commit.called
    assert not hasattr(fake_session, 'rollback') or not fake_session.rollback.called

asyncio.run(probe())
```

### Probe B: SQLite em memória e D3
```python
import asyncio
from unittest.mock import AsyncMock, patch
from types import SimpleNamespace
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy import select
from app.models.domain_models import AppSettings, Base
from app.briefing.llm_binding import make_scout_complete

async def probe():
    engine = create_async_engine(
        'sqlite+aiosqlite:///:memory:',
        poolclass=StaticPool,
        connect_args={'check_same_thread': False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    fake_resp = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='briefing text'))])

    with patch('app.services.settings.settings.SCOUT_MODEL', 'gemini/gemini-3.1-flash-lite-preview'), \
         patch('app.services.settings.settings.GEMINI_API_KEY', 'gemini-integrated-key'), \
         patch('app.briefing.llm_binding.litellm.acompletion', new=AsyncMock(return_value=fake_resp)), \
         patch('app.briefing.llm_binding._enforce_safe_transport'):
        fn = make_scout_complete(session_factory, default_timeout_s=30.0)
        res = await fn('sys_prompt', 'user_prompt')
        assert res == 'briefing text'

    async with session_factory() as check_session:
        rows = (await check_session.execute(select(AppSettings))).scalars().all()
        assert len(rows) == 0, f'Esperado 0 linhas, obtido {len(rows)}'

    await engine.dispose()

asyncio.run(probe())
```

## Cobertura e limites da inspeção

- Cobertura: Esta auditoria focou exclusivamente na implementação e testes do binding LiteLLM para T031 (`app/briefing/llm_binding.py` e `tests/test_briefing_llm_binding.py`), conferindo as 3 lentes mandatórias (contratos de fábrica/callable, concorrência e ciclo de vida de sessão com D3, cobertura e preservação de comportamento).
- Limites: Não foram alterados nem estendidos módulos fora do escopo (`app/services/llm.py`, `app/briefing/service.py`, `actions.md`, `progress.jsonl`). Nenhuma rede externa real foi acessada; todos os testes e probes utilizam transportes mock ou SQLite em memória.
- Próximo passo recomendado: O artefato de código e testes está apto para aprovação pelo QA especializado e encerramento de T031 em `actions.md`.
