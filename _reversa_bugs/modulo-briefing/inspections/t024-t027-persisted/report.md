# Inspeção independente T024/T027 — orquestração persistida

## Resultado
**PASS funcional no recorte; FINDINGS de cobertura, não defeitos confirmados de produto.** 35 testes existentes OK; 31 cenários independentes OK; compilação exit 0; `git diff --check` exit 0. Nenhum bug registrado, ação fechada ou código alterado. `promoted_to: null` para todos os achados.

## Preflight, mapa e lentes
Root `/root/projects/deep-research`, branch `main`. `AGENTS.md` consultado; mapa antigo não substitui requisitos da feature. `.reversa/state.json` usa pt-BR e descreve ciclo anterior; `.reversa/active-requirements.json` resolve `001-modulo-briefing`, estágio `coding`. `reversa-config.json` na raiz ausente; configuração real `.reversa/reversa-config.json` consultada. Working tree já suja/untracked; sem pressupor alterações como autoria desta auditoria.

- Spec efetiva: `requirements.md:51,53,58,60` RF-01/RF-03/RF-08/RF-10; decisões `audit/t011-integration-decomposition.md:6-15,43-55` D1/D3 e contrato de histórico auxiliar.
- Código alvo: `app/briefing/service.py:104-194`, `orchestrate_persisted_briefing`.
- Dependências somente leitura: `domain.py:94-139` identidade, validação, versão; `storage.py:64-116` Tx1, consulta, CAS e histórico. Sem auditoria geral de storage/domínio.
- Testes alvo: cinco métodos `tests/test_briefing_persisted_orchestration.py:30-179`. `tests/test_briefing_generation.py` executado/lido como baseline puro; aprovação de testes puros não implica cobertura persistida.
- Dados: SQLite `:memory:` isolado, tabelas `briefings` e `briefing_versions`; prompt/SERP/LLM injetados. Nenhuma DB operacional ou rede utilizada pelos probes.
- Lentes sequenciais, sem delegação: conformidade; fluxo de dados; contratos; estados de erro; cobertura; concorrência/consistência. Segurança ativada para mensagens persistidas. Desempenho/configuração/observabilidade sistêmicos fora do recorte.
- Catálogo/views/QA paralelo não lidos nem escritos; dedupe global de bugs não executado por restrição. Único destino gravado: este relatório.

## Evidência funcional por lente
| Lente | Observação executada e referência |
|---|---|
| Conformidade | RF-01: tema inválido rejeitado antes de abrir sessão/chamar externos; tema válido normalizado e persistido. RF-03: todos 3–7 pontos aceitos com comparação exata de título/descrição, não só contagem. `service.py:120-126,165-173`; `domain.py:31-53,107-131`. |
| Fluxo de dados | Durante SERP: exatamente um registro `generating`, v1, vazio, sem erro/histórico. Após conclusão: mesmo UUID, v2, snapshot corrente igual ao retornado; histórico único v2 com `briefing_id`, status, pontos e erro exatos. `service.py:121,138,167,177-180`; `storage.py:79-116`. |
| Contratos | Prompt literal e JSON user contendo tema normalizado/SERP exatos; bytes de user reutilizados em retry. SERP invocado uma vez após prompt válido, nenhuma repetição por falha LLM. Falha SERP não chama LLM. `service.py:130-156`. |
| Erros | JSON parseável inválido (1/8 pontos, vazio, falta de campo, objeto, escalares) consome tentativa; recuperação LLM2/SERP1; exaustão LLM4/SERP1, sem parcial/histórico inválido. `service.py:165-173`. LLMAttemptError retenta até4. Deadline real retenta4; TimeoutError do callable preserva mesma exceção, LLM1, emergência segura. Desconhecidas RuntimeError/InvalidContent e erro prompt propagam; snapshot/histórico recebem apenas mensagem genérica. `service.py:157-194`. |
| Concorrência | Sessão Tx1 saiu do context manager e não tem transação ativa durante cada fake SERP/LLM; sessão Tx2 nova. Vencedor concorrente grava draft v2/7 pontos enquanto LLM está em andamento; Tx2 perdedora e emergência CAS falham sem sobrescrever vencedor nem acrescentar versão. `service.py:124-126,175-194`; `storage.py:93-115`. |
| Cancelamento | Probe sincronizado por `asyncio.Event`: cancelar somente após entrada LLM; CancelledError propaga, LLM1/SERP1, mesmo registro failed v2 e histórico exato com erro genérico. Sem sleep cego no probe. |

A observação “fora de transação” vale para sessão da orquestração e callables fake. **Não prova I/O global sem transação:** binding real, runtime settings e DB própria durante callable real fora do recorte. Comentário `service.py:129` tem escopo mais amplo que evidência desta inspeção; não inferido defeito sem trace real.

## FINDINGS — cobertura lacunar
Todos confiança alta, `promoted_to: null`; severidade abaixo refere risco de regressão, não incidente observado.

### F-test-01 — comparações de conteúdo incompletas (medium)
Lentes cobertura/fluxo; `tests/test_briefing_persisted_orchestration.py:45-58,99-113`: sucesso e recovery verificam estado/versão/contagem, não conteúdo exato retornado/persistido/histórico. Mutação de títulos, descrições ou ordem com mesma contagem poderia passar. Teste recovery não prova explicitamente identidade initial/final v1/v2. **Produto não apresentou desvio:** probes independentes fizeram igualdade exata em todos 3–7 pontos e recovery. Cluster: asserções de persistência insuficientes.

### F-test-02 — histórico de exaustão não consultado (medium)
Lentes cobertura/consistência; `tests/test_briefing_persisted_orchestration.py:73-80,136-146`: exaustões consultam corrente, não histórico; caso malformed também não afirma contagem de chamadas e usa apenas2 tentativas. T027 invalidez afirma LLM2/SERP1, mas não cap4/histórico. **Produto não apresentou desvio:** probes exaustão4 compararam corrente e histórico exatos, sem dados parciais.

### F-test-03 — cancelamento temporal e caminhos persistidos ausentes (low)
Lentes cobertura/erros/concorrência; `tests/test_briefing_persisted_orchestration.py:152-165` usa sleeps10/0.05, não confirmação de entrada no LLM; não afirma histórico de emergência. Cinco métodos não cobrem diretamente Tx1 encerrada, CAS vencedor, deadline vs TimeoutError callable, falhas prompt/SERP ou exceções desconhecidas. Baseline puro não cobre persistência. **Produto não apresentou desvio:** Events/SQL real isolado cobriram esses critérios aqui. Probes não incorporados à suíte congelada.

## Hipóteses versus observações
- Hipótese: InvalidContent ainda escaparia sem consumo. Refutada no código atual e probes; `complete_briefing` agora fica no try `service.py:165-170`.
- Hipótese: emergência sobrescreveria vencedor. Refutada no interleaving testado; ambas escritas usam CAS v1, vencedor permanece v2 com histórico único.
- Hipótese: falha callable TimeoutError seria confundida com deadline. Refutada; `deadline.expired()` diferencia, mesma exceção original propagada.
- Observação de segurança limitada: snapshots/erros persistidos não expõem canário SECRET. Exceções desconhecidas são deliberadamente propagadas e podem conservar mensagem interna; segurança de resposta HTTP não avaliada.
- Emergência best effort não garante fechamento em crash, DB indisponível ou cancelamento repetido durante cleanup. D3 prevê tentativa, não recuperação garantida. Esses cenários não executados; não classificados como defeito.

## Proveniência RED preservada
`_reversa_forward/001-modulo-briefing/audit/t027-execution.md:174-181` já corrige resumo “already-implemented”. Confirmação direta do transcript `/root/.hermes/profiles/orchestrator/cache/delegation/live/deleg_024fca3f/task-0.log:25-36,76-78`: escrita testes09:06:32; RED exit1 às09:06:42; patch09:07:16; execução ainda falha09:07:24; patch09:07:39; GREEN09:07:44; resumo posterior contraditório. Inspeção não reinventou RED nem corrigiu artefatos históricos. Diff com índices reconstruídos não prova commit. Histórico de ownership já registrado pelo parent, fora do recorte de correção.

## Comandos e resultados reais
Working directory para tudo: `/root/projects/deep-research`.
1. `python3 -B -m unittest tests.test_briefing_persisted_orchestration tests.test_briefing_generation -v` — exit0, **Ran35 tests in0.590s, OK** (5 persistidos +30 puros).
2. `PYTHONPYCACHEPREFIX=/root/.hermes/profiles/orchestrator/cache/scratch/t024-t027-compile python3 -m py_compile app/briefing/service.py tests/test_briefing_persisted_orchestration.py` — exit0, confirmado separadamente `compile_exit=0`.
3. `git diff --check` — exit0, confirmado separadamente `diff_exit=0`. Não valida arquivos untracked por si só.
4. Probe abaixo passado completo para `python3 -B -c <código>` — exit0,31 PASS. Reprodução: copiar bloco Python e executar via `python3 -B -c "$(...)"` ou stdin `python3 -B -` sem arquivo novo no repositório.

### Probe completo reproduzível
```python
import asyncio, json
from contextlib import asynccontextmanager
from types import SimpleNamespace
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.models.domain_models import Base, BriefingRecord
from app.briefing.domain import complete_briefing, InvalidContent
from app.briefing.storage import get_briefing, get_briefing_versions, save_briefing_transition, points_to_json, BriefingVersionConflictError
from app.briefing.service import orchestrate_persisted_briefing, LLMAttemptError
from app.briefing.prompt_loader import PromptUnavailable
from app.briefing.serp_client import SerpSearchError

SERP=[{"title":"R", "url":"https://example.org", "description":"S"}]
def points(n): return [{"title":f"Título {i}","description":f"Descrição {i}"} for i in range(n)]
async def case(label, outputs=None, count=3, prompt_error=None, search_error=None, expected_error=None, deadline=False, cancel=False, race=False, invalid_theme=False):
    engine=create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn: await conn.run_sync(Base.metadata.create_all)
    maker=async_sessionmaker(engine, expire_on_commit=False)
    active=[]; closed=[]; initial=[]; calls=[]; searches=[]; entered=asyncio.Event(); blocked=asyncio.Event()
    @asynccontextmanager
    async def factory():
        async with maker() as s:
            active.append(s)
            try: yield s
            finally:
                active.remove(s)
        closed.append(s)
    async def inspect_initial():
        assert not active and len(closed)==1 and not closed[0].in_transaction()
        async with maker() as s:
            rows=list((await s.execute(select(BriefingRecord))).scalars())
            assert len(rows)==1
            b=await get_briefing(s, rows[0].id)
            assert b.status=='generating' and b.version==1 and b.points==() and b.error is None
            assert await get_briefing_versions(s,b.id)==[]
            initial.append(b)
    def prompt():
        assert not active and len(closed)==1
        if prompt_error: raise prompt_error
        return ' exact prompt '
    async def search(theme):
        await inspect_initial(); searches.append(theme)
        if search_error: raise search_error
        return SERP
    async def llm(system,user):
        assert not active and len(closed)==1 and not closed[0].in_transaction()
        assert system==' exact prompt '
        payload=json.loads(user)
        assert payload['tema']=='tema válido' and payload['resultados_serp']==SERP
        calls.append(user)
        if race:
            winner=complete_briefing(initial[0],points(7))
            async with maker() as s: await save_briefing_transition(s,initial[0],winner)
        if cancel:
            entered.set(); await blocked.wait()
        if deadline: await blocked.wait()
        value=outputs[min(len(calls)-1,len(outputs)-1)] if outputs else json.dumps(points(count),ensure_ascii=False)
        if isinstance(value,BaseException): raise value
        return value
    kwargs=dict(serp_client=SimpleNamespace(search=search),llm_complete=llm,prompt_loader=prompt,llm_timeout_s=0.002 if deadline else 30)
    result=None; raised=None
    try:
        if cancel:
            task=asyncio.create_task(orchestrate_persisted_briefing(factory,'  tema válido  ',**kwargs))
            await asyncio.wait_for(entered.wait(),2); task.cancel()
            try: await task
            except asyncio.CancelledError as e: raised=e
        else:
            try: result=await orchestrate_persisted_briefing(factory,' ' if invalid_theme else '  tema válido  ',**kwargs)
            except BaseException as e: raised=e
        if invalid_theme:
            assert isinstance(raised,InvalidContent) and not closed and not searches and not calls
            async with maker() as s: assert list((await s.execute(select(BriefingRecord))).scalars())==[]
        else:
            async with maker() as s:
                rows=list((await s.execute(select(BriefingRecord))).scalars()); assert len(rows)==1
                stored=await get_briefing(s,rows[0].id); history=await get_briefing_versions(s,stored.id)
            assert stored.version==2 and stored.theme=='tema válido' and len(history)==1
            h=history[0]
            assert h.version==2 and h.briefing_id==stored.id and h.status==stored.status
            assert h.points_json==points_to_json(stored.points) and h.error==stored.error
            if initial: assert stored.id==initial[0].id
            if race:
                assert isinstance(raised,BriefingVersionConflictError)
                assert stored.status=='draft' and points_to_json(stored.points)==points(7)
            elif cancel or (expected_error and isinstance(expected_error,BaseException)):
                assert isinstance(raised,asyncio.CancelledError) if cancel else raised is expected_error
                assert stored.status=='failed' and stored.points==() and stored.error=='Processamento abortado ou cancelado'
                assert 'SECRET' not in repr(stored) and 'SECRET' not in str(h.error)
            elif expected_error:
                assert raised is None and result==stored and stored.status=='failed' and stored.points==() and stored.error==expected_error
            else:
                assert raised is None and result==stored and stored.status=='draft'
                assert points_to_json(stored.points)==points(count) and h.points_json==points(count)
            expected_calls=0 if prompt_error or search_error else 1 if cancel or race or isinstance(expected_error,BaseException) else 4 if deadline or expected_error else len(outputs) if outputs else 1
            assert len(calls)==expected_calls,(label,len(calls),expected_calls)
            assert len(searches)==(0 if prompt_error else 1)
            assert len(set(calls))<=1
        print('PASS',label,'SERP',len(searches),'LLM',len(calls))
    finally: await engine.dispose()
async def main():
    for n in range(3,8): await case(f'valid-{n}',count=n)
    invalid=[json.dumps(points(1)),json.dumps(points(8)),json.dumps([{'title':'','description':'D'}]*3),json.dumps([{'title':'T','description':''}]*3),json.dumps([{'title':'T'}]*3),'{}','[1,2,3]']
    for i,bad in enumerate(invalid):
        await case(f'recovery-{i}',outputs=[bad,json.dumps(points(3))])
        await case(f'exhaustion-{i}',outputs=[bad],expected_error='Geração de briefing indisponível')
    await case('known-retry',outputs=[LLMAttemptError(),LLMAttemptError(),LLMAttemptError(),json.dumps(points(3))])
    await case('known-exhaust',outputs=[LLMAttemptError()],expected_error='Geração de briefing indisponível')
    await case('prompt-failed',prompt_error=PromptUnavailable('SECRET'),expected_error='Prompt de briefing indisponível')
    await case('SERP-failed',search_error=SerpSearchError(4),expected_error='Busca SERP indisponível')
    for e in (TimeoutError('SECRET'),RuntimeError('SECRET'),InvalidContent('SECRET')):
        await case(type(e).__name__,outputs=[e],expected_error=e)
    e=RuntimeError('SECRET'); await case('unknown-prompt',prompt_error=e,expected_error=e)
    await case('deadline',deadline=True,expected_error='Geração de briefing indisponível')
    await case('cancellation-event',cancel=True)
    await case('CAS-winner',race=True)
    await case('invalid-theme',invalid_theme=True)
asyncio.run(main())
```

### Saída integral do probe
```text
PASS valid-3 SERP 1 LLM 1
PASS valid-4 SERP 1 LLM 1
PASS valid-5 SERP 1 LLM 1
PASS valid-6 SERP 1 LLM 1
PASS valid-7 SERP 1 LLM 1
PASS recovery-0 SERP 1 LLM 2
PASS exhaustion-0 SERP 1 LLM 4
PASS recovery-1 SERP 1 LLM 2
PASS exhaustion-1 SERP 1 LLM 4
PASS recovery-2 SERP 1 LLM 2
PASS exhaustion-2 SERP 1 LLM 4
PASS recovery-3 SERP 1 LLM 2
PASS exhaustion-3 SERP 1 LLM 4
PASS recovery-4 SERP 1 LLM 2
PASS exhaustion-4 SERP 1 LLM 4
PASS recovery-5 SERP 1 LLM 2
PASS exhaustion-5 SERP 1 LLM 4
PASS recovery-6 SERP 1 LLM 2
PASS exhaustion-6 SERP 1 LLM 4
PASS known-retry SERP 1 LLM 4
PASS known-exhaust SERP 1 LLM 4
PASS prompt-failed SERP 0 LLM 0
PASS SERP-failed SERP 1 LLM 0
PASS TimeoutError SERP 1 LLM 1
PASS RuntimeError SERP 1 LLM 1
PASS InvalidContent SERP 1 LLM 1
PASS unknown-prompt SERP 0 LLM 0
PASS deadline SERP 1 LLM 4
PASS cancellation-event SERP 1 LLM 1
PASS CAS-winner SERP 1 LLM 1
PASS invalid-theme SERP 0 LLM 0```

## Hashes readset antes/depois
SHA-256 abaixo coletado antes das execuções/probes e novamente depois; **todos iguais**. Cada linha fornece valor BEFORE = AFTER, não hash inferido de Git. Leitura dos arquivos precedeu primeiro snapshot; garantia cobre janela dos checks/probes, não momentos anteriores. Documentos auxiliares de proveniência/transcript foram lidos depois, não incluídos nesta garantia de estabilidade.
```text
9de50e39699ecac57f33b18ae5b0149186ec04bb6571cdb87218fee2607e1844 AGENTS.md
27fc325d313341e303a16a4d4c2dbb03838b91f034f250fe3661a2083353b3df .reversa/state.json
802efe8929aa5575e24b23947afdf2a4dff013c9d284b3f2ed7420fc246f2d45 .reversa/active-requirements.json
33c9ab2158530bcba7c242f15d7e2f173f346b7f9a999115231e195bd8f4c8fe .reversa/reversa-config.json
4d749e76bf4d07d1d6f2ae33cc933116c43f2c745f07462a298b5012e8c4d8c5 _reversa_forward/001-modulo-briefing/requirements.md
fd679e6a53f017fbc160a0f1352b471f40c3efa971b74a4122b1f2d7423e04bf _reversa_forward/001-modulo-briefing/audit/t011-integration-decomposition.md
afd3cd120bba22309d3aa9d0a6a0499b246499b1570e66894189ed724f27a05c app/briefing/service.py
48f9411ababa036e00f013e8db03dc86d5ca765bde74c99cc37235802a3e1ab0 app/briefing/storage.py
f058679d7a1a923c337a4dc067c01cbc3d0f50d0ca126220de286ec89d557b4a app/briefing/domain.py
9113560b896614369468052a2935354c3190fd984fcfc70715e98e6acc8dc1c3 tests/test_briefing_persisted_orchestration.py
df730a92c5e432cd3ec79e0472e6ab8472652f56f0ba93c8d4ddc2d01b86b789 tests/test_briefing_generation.py
```
Reprodução dos hashes:
```python
from pathlib import Path
import hashlib
paths = ['AGENTS.md', '.reversa/state.json', '.reversa/active-requirements.json', '.reversa/reversa-config.json', '_reversa_forward/001-modulo-briefing/requirements.md', '_reversa_forward/001-modulo-briefing/audit/t011-integration-decomposition.md', 'app/briefing/service.py', 'app/briefing/storage.py', 'app/briefing/domain.py', 'tests/test_briefing_persisted_orchestration.py', 'tests/test_briefing_generation.py']
for path in paths:
    print(hashlib.sha256(Path(path).read_bytes()).hexdigest(), path)
```

## Limitações e entrega
Sem DB real, rede, HTTP, LiteLLM real, migração aplicada, auditoria geral de storage ou leitura de QA paralelo. Retry interno SERP não medido aqui: fake lança `SerpSearchError(4)`; cap de transporte pertence ao cliente. Probe CAS usa interleaving controlado com SQLite, não stress PostgreSQL/multiprocessos. Falha Tx1, falha de commit/infraestrutura e cancelamento repetido no cleanup não induzidos. Garantia de prompt “não conclusivo” depende de conteúdo/prompt, não inferida de título/descrição estrutural.

Somente este relatório criado. Nenhum catálogo/view/bug/skill alterado, nenhuma ação fechada. Checks criaram cache de compilação no scratch indicado; teste baseline usa tempfile em TMPDIR/scratch. Sem entrega de correção.
