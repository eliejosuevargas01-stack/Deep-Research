# QA focada pós-auditoria — T029/T032/T033

## Veredito
**PASS_LOCAL**. 12/12 métodos binding OK, zero skips; dois runs independentes do teste SDK real com seeds False/False e True/True OK. Cada invocação observou exatamente 1 POST `/v1/chat/completions`, `LLMAttemptError`, cliente HTTPX simulado fechado e restauração dos estados monitorados. Zero findings novos, zero bugs promovidos; `promoted_to: null`. Aceite somente local no recorte OpenAI 503 + isolamento + documentação. Nenhuma ação fechada.

## Preflight e mapa aceitação → símbolo → checks
Root `/root/projects/deep-research`, branch `main`; worktree já sujo antes da QA. Lidos AGENTS.md, `.reversa/state.json`, `.reversa/active-requirements.json`, `.reversa/reversa-config.json`. Feature ativa `_reversa_forward/001-modulo-briefing`, coding. Reauditoria `../t029-sdk-retries-recheck/report.md:3–4` autoriza QA sequencial e registra três LOW sanadas.

| Aceitação | Fonte / símbolo | Check próprio |
|---|---|---|
| RF-10, uma operação externa por tentativa | `requirements.md:60,113–117`; `actions.md:83`; `app/briefing/llm_binding.py:42–106`, controles :84–85, SDK :90, conversão :94–98 | módulo completo + dois runs SDK reais instrumentados, count1 / POST / caminho exato / LLMAttemptError |
| Helper real conservado | binding :72; `app/services/llm.py:19–98`; `tests/test_briefing_llm_binding.py:280–283` | identidade helper/acompletion real; instrumentação delega MockTransport original, sem fake SDK |
| T032 isolamento | `tests/test_briefing_llm_binding.py:226–228,251–278` | TestCase.run(TestResult) com dois seeds, cleanup acionado, descriptors via inspect.getattr_static e flags/atributos restaurados |
| Dois testes mantidos e baseline | testes :223–286 e :288–307 | AST 12 métodos, 11 async + 1 sync; unittest 12 OK, nenhum skip/exclusão |
| T033 evidência atual vs história | `audit/t029-execution.md:22,40–47` | qualificação histórica parcial/não autenticada; helper real; auditor 2 focados/12 binding separado parent discover128; discover físico :27 zero barras |
| T033 W020 vigente | `regression-watch.md:158–163`; `actions.md:80–88` | supersede :129, T024/T027 [X] e QA persistido local referenciado; T030/T031/API abertos; T032 gate aberto não nega implementação |
| Integridade | `progress.jsonl:67` pre_dispatch_sha256 + progress separado | 95/95 SHA antes/depois; 67 linhas progress preservadas; snapshot amplo 18046 arquivos existentes sem mudança; git diff --check antes/depois exit0 |

Specs são greenfield; requirements permanece fonte de produto, PRD/SDD existentes não reinterpretados. Dados exercitados: settings/modelo/chave fictícios em memória e HTTPX MockTransport 503, sem DB. OpenAI/gpt-4o-mini fixture, não requisito produto. Dedupe: observações O-TEST-01/O-DOC-01/O-DOC-02 já sanadas; F-ERROR-01/T030 e F-CONSISTENCY-01/T031 conhecidos e excluídos.

## Execução própria
Comandos completos, cwd `/root/projects/deep-research`:

```sh
PYTHONPATH=/root/.hermes/profiles/orchestrator/cache/scratch/briefing-qa-guard:$PWD python3 -B -m unittest tests.test_briefing_llm_binding -v
PYTHONPATH=$PWD python3 -B /root/.hermes/profiles/orchestrator/cache/scratch/briefing-qa-probe.py
git diff --check
```

- Módulo: exit **0**, `Ran 12 tests in 0.386s`, `OK`. Todos os 12 métodos executados; nenhum removido, pulado ou excluído.
- Probe final: exit **0**. `baseline_before 95`, `fixture_ascii_before True`; seed false: tests1/failures0/errors0/requests1; seed true: tests1/failures0/errors0/requests1. Ambos `POST /v1/chat/completions`, clientclosed=true, descriptors_restored=true, attributes_restored=true, redirects_restored=true, sdk_real=true, helper_real=true. `docs_semantics True`, `discover_physical_backslashes 0`, `fixture_ascii_after True`, `baseline_after 95`.
- Contagens separadas: 12 métodos baseline; 2 execuções adicionais do mesmo método SDK, **não dois métodos novos**; total 2 requests no probe. Sem fallback de completion observável no cenário (somente requests registrados do MockTransport; não generaliza mecanismos SDK).
- Progress SHA-256 `81ae60746bfea2717b19213dd2cb35d767fdffe8a486d20887e24b4d631c69e8`, 67 linhas, inalterado.
- Versões via importlib.metadata: litellm **1.104.0**, openai **2.54.0**, httpx **0.28.1**, pydantic **2.13.5**, sqlalchemy **2.1.3**.
- Git diff --check pré/pós exit **0**; cobre diff rastreado, não valida todo untracked.

Guard de socket.connect/connect_ex aplicado **antes dos imports SDK/app** na execução baseline por sitecustomize e no probe final por patch restaurável. Import LiteLLM tentou fetch model-cost, bloqueado com OSError; fallback local observado. Esse fallback de metadados é distinto de fallback de completion. Não implica falha produto. Warnings Pydantic ReadOnly e asyncio slow-task não causaram falha. Não se afirma ausência de todo I/O nem segurança global: guard cobre conexões desses sockets, não todos os possíveis mecanismos.

### Tentativas auxiliares e limites de proveniência
- Leitura inicial tentou `001-modulo-briefing/t029-execution.md`, inexistente; corrigido para `audit/t029-execution.md`, sem escrita.
- Parse do progress via saída read_file truncada falhou JSONDecodeError; probe definitivo lê arquivo físico e valida 95 hashes.
- Primeira versão scratch do probe selecionou por engano literal `secret` do teste de guardrail para check ASCII, assert falhou antes dos runs SDK. Corrigido somente scratch para literal da fixture OpenAI em Dict. Não alterado token/projeto; baseline95 já coincidiu. Shell com `; git diff --check` retornou exit0 apesar de assert do probe; **não** contado como probe PASS. Reexecução direta final exit0 acima é evidência vigente.
- Tentativa opcional de contraprova em kernel execute_code não chegou ao teste: ModuleNotFoundError de tests.test_briefing_llm_binding, exit1, ambiente diferente. Não é contraprova executada nem falha produto. Import litellm nessa tentativa não estava sob guard; **não afirmar ausência de I/O anterior nessa tentativa auxiliar**. Nenhum request/payload/headers/chave de provider usado ou exibido nos checks reportados. Contraprova auditor de 3 requests/FAILED1/exit0 em execution :42 permanece evidência atribuída ao auditor, não execução desta QA. Não autentica história RED/GREEN.

## Lentes e findings
Conformidade/contratos: PASS local SDK503 count1. Fluxo de dados: fixture/mapeamento erro no recorte PASS; persistência excluída. Erros: LLMAttemptError para cenário503 PASS; 500/conexão fora do recorte. Cobertura: 12 métodos e assertions SDK preservados. Consistência: dois seeds e descriptors/flags/attrs monitorados restaurados; não extrapola todos os globais/background SDK. Documental/rastreabilidade: histórico devidamente qualificado e gate aberto preservado. Findings novos **0** em todas as lentes, confiança alta no recorte, `promoted_to: null`; nenhum cluster novo. Sem promover bugs ou atualizar views.

## Scripts completos autorizados para reprodução
Criar somente em scratch. Guard usado com comando baseline acima:

```python
import socket

def _qa_no_network(*args, **kwargs):
    raise OSError('QA network blocked')

socket.socket.connect = _qa_no_network
socket.socket.connect_ex = _qa_no_network
```

Probe executado (instrumenta teste mantido; delega transporte original e SDK real):

```python
import socket
from unittest.mock import patch

def blocked(*args, **kwargs):
    raise OSError('QA network blocked')

# Guard precedes SDK/application imports. OSError permits SDK local-cost fallback.
with patch.object(socket.socket, 'connect', blocked), patch.object(socket.socket, 'connect_ex', blocked):
    import ast
    import hashlib
    import inspect
    import json
    import unittest
    from pathlib import Path
    from importlib.metadata import version
    import httpx
    import litellm
    from litellm.llms.custom_httpx.http_handler import AsyncHTTPHandler, HTTPHandler
    from litellm.llms.openai.common_utils import BaseOpenAILLM
    import app.services.llm as service
    import app.briefing.llm_binding as binding
    from tests.test_briefing_llm_binding import BindingTests

    root = Path('/root/projects/deep-research')
    progress = root / '_reversa_forward/001-modulo-briefing/progress.jsonl'
    last = json.loads(progress.read_text().splitlines()[-1])
    baseline = last['pre_dispatch_sha256']
    def integrity():
        matches = sum(hashlib.sha256((root / p).read_bytes()).hexdigest() == h for p, h in baseline.items())
        assert matches == len(baseline) == 95
        return matches
    print('baseline_before', integrity())
    progress_before = hashlib.sha256(progress.read_bytes()).hexdigest()
    source = (root / 'tests/test_briefing_llm_binding.py').read_text()
    tree = ast.parse(source)
    methods = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith('test_')]
    assert len(methods) == 12
    assert sum(isinstance(n, ast.AsyncFunctionDef) for n in methods) == 11
    def fixture_ascii():
        t = ast.parse((root / 'tests/test_briefing_llm_binding.py').read_text())
        values = [v.value for n in ast.walk(t) if isinstance(n, ast.Dict) for k, v in zip(n.keys, n.values) if isinstance(k, ast.Constant) and k.value == 'openai' and isinstance(v, ast.Constant)]
        assert values and all(v.isascii() for v in values)
        return True
    print('fixture_ascii_before', fixture_ascii())
    print('versions', json.dumps({p: version(p) for p in ('litellm', 'openai', 'httpx', 'pydantic', 'sqlalchemy')}))
    descriptors = [(AsyncHTTPHandler, 'create_client'), (HTTPHandler, 'create_client'), (BaseOpenAILLM, '_get_async_http_client'), (BaseOpenAILLM, '_get_sync_http_client')]
    attrs = [(service, '_SAFE_TRANSPORT_ACTIVE'), (service, '_SAFE_TRANSPORT_ERROR')] + [(litellm, n) for n in ('telemetry', 'suppress_debug_info', 'turn_off_message_logging', 'callbacks', 'success_callback', 'failure_callback', '_async_success_callback', '_async_failure_callback')]
    def snapshot():
        return ([inspect.getattr_static(o, n) for o, n in descriptors], [(hasattr(o, n), getattr(o, n, None)) for o, n in attrs])
    original = snapshot()
    globals_clients = [litellm.module_level_aclient.client, litellm.module_level_client.client]
    original_redirects = [c.follow_redirects for c in globals_clients]
    real_request = httpx.MockTransport.handle_async_request
    real_exit = httpx.AsyncClient.__aexit__
    real_completion = litellm.acompletion
    real_helper = binding._enforce_safe_transport
    results = []
    try:
        for seed in (False, True):
            for c in globals_clients:
                c.follow_redirects = seed
            before = snapshot()
            requests = []
            closed_clients = []
            async def record_request(transport, request):
                requests.append((request.method, request.url.path))
                return await real_request(transport, request)
            async def record_exit(client, *args):
                answer = await real_exit(client, *args)
                if isinstance(client._transport, httpx.MockTransport):
                    closed_clients.append(client.is_closed)
                return answer
            result = unittest.TestResult()
            with patch.object(httpx.MockTransport, 'handle_async_request', record_request), patch.object(httpx.AsyncClient, '__aexit__', record_exit):
                assert litellm.acompletion is real_completion
                assert binding._enforce_safe_transport is real_helper
                BindingTests('test_no_internal_retries_on_503_openai_sdk').run(result)
            assert result.wasSuccessful(), (len(result.failures), len(result.errors))
            assert result.testsRun == 1 and not result.skipped
            assert requests == [('POST', '/v1/chat/completions')], requests
            assert closed_clients == [True], closed_clients
            after = snapshot()
            assert all(a is b for a, b in zip(before[0], after[0]))
            assert before[1] == after[1]
            assert [c.follow_redirects for c in globals_clients] == [seed, seed]
            row = dict(seed=seed, tests=result.testsRun, failures=len(result.failures), errors=len(result.errors), requests=len(requests), method=requests[0][0], path=requests[0][1], clientclosed=closed_clients[0], descriptors_restored=True, attributes_restored=True, redirects_restored=True, sdk_real=True, helper_real=True, no_fallback_observed=True)
            results.append(row)
            print('probe', json.dumps(row, sort_keys=True))
    finally:
        for (o, n), v in zip(descriptors, original[0]):
            setattr(o, n, v)
        for (o, n), (exists, v) in zip(attrs, original[1]):
            if exists:
                setattr(o, n, v)
            elif hasattr(o, n):
                delattr(o, n)
        for c, v in zip(globals_clients, original_redirects):
            c.follow_redirects = v
    assert snapshot() == original
    assert [c.follow_redirects for c in globals_clients] == original_redirects
    execution = (root / '_reversa_forward/001-modulo-briefing/audit/t029-execution.md').read_text().splitlines()
    watch = (root / '_reversa_forward/001-modulo-briefing/regression-watch.md').read_text().splitlines()
    actions = (root / '_reversa_forward/001-modulo-briefing/actions.md').read_text().splitlines()
    assert 'auto-relato histórico' in execution[21] and 'não autenticado' in execution[21]
    assert 'helper REAL' in execution[40] and 'NÃO executado' in execution[42]
    assert execution[26].count('\\') == 0
    assert 'supersedido/qualificado' in watch[157]
    assert 'T024/T027 implementadas' in watch[159] and 'QA persistido local' in watch[159]
    assert 'T030' in watch[160] and 'T031' in watch[160] and 'API' in watch[160]
    assert 'ação corretiva aberta' in watch[161]
    assert '[X]' in actions[79] and '[X]' in actions[80]
    assert all('[ ]' in actions[i - 1] for i in (83, 84, 85, 86, 87, 88))
    assert (root / '_reversa_forward/001-modulo-briefing/audit/qa-sprint7-persisted.md').is_file()
    print('docs_semantics', True, 'discover_physical_backslashes', execution[26].count('\\'))
    print('fixture_ascii_after', fixture_ascii())
    print('baseline_after', integrity())
    assert hashlib.sha256(progress.read_bytes()).hexdigest() == progress_before
    print('progress_preserved', progress_before, 'lines', len(progress.read_text().splitlines()))
    print('counts', json.dumps({'baseline_methods': len(methods), 'async': 11, 'sync': 1, 'isolated_runs': len(results), 'requests_total': sum(r['requests'] for r in results)}))
```

## Exclusões e próximo gate
Não executados nesta QA: discover128/global, compile global, DB/API, sessão/ownership T031, matriz 500/conexão T030, rede/live/provedores reais, todos providers, segurança integral de traceback/background SDK, migração, instalação, .env/secrets, commit/push/deploy. Parent discover128 e compile0 anteriores são apenas evidência atribuída, não execução própria.

Única escrita de projeto: este novo report. app/**, tests/**, .reversa, forward docs/actions/progress, relatórios anteriores, bugs e views congelados. Hashes95 e progress separados preservados; snapshot amplo18046 existente sem mudança antes de escrever relatório. Próximo gate: parent avaliar **PASS_LOCAL**, fechar T029/T032/T033 quando apropriado; T030/T031/API continuam abertos. Nenhum aceite global.
