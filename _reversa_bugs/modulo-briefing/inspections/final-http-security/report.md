# Inspeção final HTTP, segurança e rastreabilidade — T013

## Veredictos

- **LOCAL: PASS com observações e limites.** Suite local: **183 passed, 6 warnings, exit 0**. Nenhum defeito Must confirmado no contrato HTTP vigente de briefing nos caminhos inspecionados.
- **OVERALL: CONDITIONAL / feature não DONE.** Gate T012 com provedor real configurado não executado; MockTransport valida SDK local, não interoperabilidade hospedada. Aprovações finais e QA independente continuam pendentes conforme checkpoint L95.
- **Afirmação universal de segurança: não demonstrada.** Nem todos os 422 têm `detail` string fixa; exceções internas podem preservar causas sensíveis. Isso não equivale a vazamento de provedor no corpo HTTP observado.
- Todos os achados têm `promoted_to: null`. Nenhum bug registrado, código corrigido ou checkbox fechado nesta inspeção.

## Escopo, fontes e mapa

Root `/root/projects/deep-research`, branch `main`; working tree já continha alterações entregues. Única saída documental autorizada: este relatório. Não escritos forward/audit, actions, progress, registry ou views.

Fontes normativas: `requirements.md` RN-01–RN-07, RF-01–RF-10 e NFR segurança/rastreabilidade; `interfaces/briefing-http.md:9–45,104–107` como contrato detalhado vigente. Texto histórico da interface não substitui prescrição vigente. NFR proveniência completa de prompt/busca é Should, não requisito Must de snapshot nesta rodada (`interfaces/briefing-http.md:68`).

Mapa:

| Camada | Arquivos/símbolos | Dados e fronteiras |
|---|---|---|
| HTTP/auth | `app/main.py:46–60,73`; `app/briefing/router.py`; `app/core/security.py:31–92` | Registro das sete rotas, Pydantic, auth real cookie/CSRF/Bearer/API-key |
| Domínio/schema | `app/briefing/domain.py`, `schemas.py` | Tema 3–300, pontos 3–7, estado, version, approved_at; snapshots tuple/frozen |
| Orquestração | `app/briefing/service.py:104–194` | Tx1, prompt, SERP, LLM, CAS Tx2, emergência best-effort |
| Persistência | `storage.py:64–116`; `domain_models.py:131–159`; migration `0006` | `briefings`, `briefing_versions`, unicidade `(briefing_id,version)` |
| Geração externa | `prompt_loader.py`, `serp_client.py`, `llm_binding.py`; helper `app/services/llm.py:141–160` | Disco UTF-8, Jina POST, role scout/LiteLLM, credenciais copiadas, guardrail |
| Testes | 20 arquivos `tests/test_briefing*.py` | SQLite isolado, fakes de fronteira e MockTransport; sem gate hosted-provider |

Não examinados siblings mutáveis `audit/cross-check.md` e `audit/requirements-audit.md`. Nenhum hash desses arquivos calculado. Checkpoint L94 consultado como histórico: 114 entradas, 1 divergência conhecida em actions; não utilizado como baseline final. **L95, 2026-10-11T19:42:54.150664+00:00: 114 hashes conferidos, 0 divergências; subconjunto direto feature/HTTP/testes: 36, 0 divergências.** Contagem maior inclui integridade de manifesto, não auditoria semântica do projeto inteiro. Arquivo de prompt não consta nesse manifesto; leitura de disco foi exercitada, não afirmada congelada por L95.

## Lentes e evidências

### 1. Conformidade

- Sete rotas `/briefings` registradas em app real; criação síncrona retorna draft v2 e 201; leitura approved não inicia pesquisa. API suite 12 métodos verdes, incluída na execução de 183.
- `domain.py:127–162`: completar/editar/aprovar/reabrir incrementam versão, edição exige draft, aprovação copia pontos válidos, reabertura limpa approved_at. API cobre estado incompatível, inexistência, body omitido/null/{}, rejeições sem mutação.
- Schema current/history valida pontos em draft/approved; generating/failed aceita ausência de conteúdo, compatível com estados terminais.
- RF-04: router injeta `load_briefing_prompt`, serviço chama uma vez a cada geração; loader `read_text` a cada invocação. Sem fallback de system prompt na lógica. `_OUTPUT_FORMAT` é instrução de formato no payload user, não fallback system.

### 2. Fluxo de dados e integridade

- `storage.py:21–61` limita pontos persistidos a title/description; não grava raw_llm, prompt integral ou objeto upstream. `test_raw_canary_excluded_from_current_and_history_serialization` injeta canary em campos extras e verifica exclusão.
- Histórico começa em v2, não reserva v1: Tx1 grava somente current. `save_briefing_transition` atualiza current por CAS e insere histórico na mesma transação; `get_briefing_versions` ordena ASC.
- `test_saved_edit_approve_reopen_history_is_immutable` compara **todas as colunas** de linhas anteriores em fresh sessions, incluindo created_at/error/approved_at/status/version/points_json. Edição, aprovação, reabertura e nova edição preservam linhas anteriores.
- QA persistida verifica conteúdo exato/ordem, mesmo ID, recuperação e exaustão com erro fixo; falha nova não altera histórico anterior. SQL insert failure test verifica rollback pelo caller; não se promete recuperação automática da sessão em qualquer erro de infraestrutura.
- Append-only demonstrado pelos caminhos do módulo. Não há trigger/ACL que impeça UPDATE/DELETE por acesso DB externo; FK CASCADE remove histórico se pai for apagado. Nenhuma rota DELETE entregue.

### 3. Contratos e integrações

- Jina: endpoint fixo `https://s.jina.ai/`, POST `{q: tema}`, Authorization Bearer, no-content, redirects false; parser exporta title/url/description, tolera extras e rejeita resultados inutilizáveis. Até quatro tentativas por operação, sucesso encerra loop.
- Binding scout lê e copia runtime keys/models em sessão curta, fecha antes de LiteLLM; kwargs incluem `num_retries=0`, `max_retries=0`. Suite exercita completion real com HTTP fake 503 e conta uma requisição. Não prova todos providers nem provedor real.
- Router `72–87,144–160` usa SEARCH_TIMEOUT_SECONDS finito positivo não-bool; mesma configuração vai SERP, binding e serviço. API testa 45/45.0/12.5 e inválidos; binding cobre overflow extremo, override, zero I/O de configuração inválida e valor >30 permitido.
- Fronteira é timeout por tentativa; não SLA total da geração nem prazo de fila/lock/cleanup. Falha LLM reutiliza resultado SERP, sem nova busca de sucesso.

### 4. Erros e edge cases

| Caminho | Resultado verificado / fonte |
|---|---|
| Pydantic theme/points/UUID/extra | 422 com lista de erros; `main.py:49–60` remove input, mas preserva loc/msg/ctx |
| approve/reopen body inválido | 422 string fixa `Corpo inválido`, router 110–125 |
| Pai ausente | 404 `Briefing não encontrado` |
| Estado/CAS incompatível | 409 string fixa por branch; API verifica CAS preservado |
| Prompt ausente | 500 `Prompt de briefing indisponível`; FAILED persistido |
| SERP/LLM exaustão | 503 `Busca SERP indisponível` / `Geração de briefing indisponível` |
| Configuração/auth upstream tipada | 500 `Erro interno ao gerar briefing`; API injeta SECRET_CANARY em classes/status reais |
| Unknown RuntimeError | identidade preservada; ASGITransport com raise_app_exceptions=False observa 500 `Internal Server Error`, sem canary |
| Cancelamento | repropaga; serviço persistido tenta FAILED de emergência, fresh session observa cenário local testado |

Não exigido apagar exceção interna desconhecida: contrato exige identidade e fronteira HTTP genérica. Serviço repropaga após tentativa de emergência; falha DB/crash pode impedir gravação. Starlette debug=False protege corpo HTTP observado, sem afirmar ausência de traceback nos logs do servidor.

### 5. Cobertura

Comando real `pytest tests/test_briefing*`, cwd root, exit **0**: **183 passed, 6 warnings in 13.78s**. API 12 métodos; acceptance 10 métodos. Warnings: Pydantic ReadOnly e Alembic path_separator. Não contados subtests nem requests como tests independentes.

Probes adicionais em subprocesso `PYTHONDONTWRITEBYTECODE=1 python - <<'PY'`:

1. Transport Jina real + MockTransport que lança ConnectError com canary fictício; quatro requests. `str(SerpSearchError)` seguro, traceback formatado contém causa canary. Loader default com `Path.read_text` fake retorna duas versões em duas chamadas; OSError fake contém canary e causa aparece no traceback. API real, fixture SQLite/auth existentes, extra field nomeado com canary retorna 422 que inclui canary em loc; unknown RuntimeError retorna corpo genérico quando raise_app_exceptions=False. **Exit 0.**
2. Mesmo fixture API: unknown RuntimeError repropaga objeto idêntico (`caught is exc`). Guardrail diretamente exercitado com canaries fictícios injetados em quatro settings e três valores extra-sensitive de provedores; todos rejeitados com mensagens sem canary. **Exit 0.** Esse segundo check prova helper, não transporte/HTTP de cada provider.
3. SHA-256 L95: **114 entradas, 0 divergências, exit 0**; consulta anterior, antes de append parent, informou L95 ausente. Baseline final consultado após append.

Saída observada dos probes:

```text
SERP transport: attempts=4 safe_str=True canary_in_formatted_traceback=True
HTTP validation: status=422 detail_type=list canary_in_extra_field_loc=True
HTTP ASGI raise_app_exceptions=True: raw RuntimeError propagated=True
HTTP production debug=False: status=500 body=Internal Server Error canary_absent=True
Prompt default loader: disk_reads=2 changed_content_observed=True
Prompt read failure: safe_str=True canary_in_formatted_traceback=True
Unknown HTTP ASGI exception identity preserved=True
Guardrail: 4 configured settings canaries rejected with safe_str=True
Guardrail: 3 extra-sensitive provider canaries rejected with safe_str=True
L95 Total checked: 114, mismatches: 0
```

Probes não criaram testes mantidos. Recipe mínima reproduzível dos dois pontos de segurança adicionais:

```bash
PYTHONDONTWRITEBYTECODE=1 python - <<'PY'
import asyncio, importlib.util, traceback
import httpx
spec=importlib.util.spec_from_file_location('fixture','tests/test_briefing_api.py')
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
from app.briefing.serp_client import JinaSerpClient, SerpSearchError
C='AUDIT_FICTITIOUS_SECRET_CANARY_2026'
async def main():
    calls=0
    def broken(req):
        nonlocal calls
        calls+=1
        raise httpx.ConnectError(C,request=req)
    async with httpx.AsyncClient(transport=httpx.MockTransport(broken)) as http:
        try: await JinaSerpClient('fake-audit-key',http_client=http).search('Tema valido auditoria')
        except SerpSearchError as exc:
            assert exc.__traceback__ is not None
            assert C not in str(exc)
            assert C in ''.join(traceback.format_exception(exc))
            assert calls==4
        else: raise AssertionError('expected SERP failure')
    case=m.BriefingAPI('test_create_invalid_rejected_before_generation')
    await case.asyncSetUp()
    try:
        h={'Authorization':'Bearer test-api-secret-0123456789'}
        r=await case.client.post('/briefings',json={'theme':'Tema valido',C:'x'},headers=h)
        assert r.status_code==422 and C in r.text
        error=RuntimeError(C); case.llm.error=error
        try: await case.client.post('/briefings',json={'theme':'Tema valido'},headers=h)
        except RuntimeError as exc: assert exc is error
        else: raise AssertionError('expected unknown failure')
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=m.app,raise_app_exceptions=False),base_url='http://test') as client:
            r=await client.post('/briefings',json={'theme':'Tema valido'},headers=h)
            assert r.status_code==500 and r.text=='Internal Server Error' and C not in r.text
    finally: await case.asyncTearDown()
    print('Security scope probe PASS')
asyncio.run(main())
PY
```

### 6. Concorrência, autorização e segurança

- Auth real nunca overridden: testes usam override DB e I/O apenas. Sem credencial 401; cookie mutation sem CSRF ou CSRF ruim 403; CSRF válido/Bearer/API-key aceitos. `require_admin` roda antes de domínio; auth pode fazer SELECT antes da validação. Router rollback encerra transação auth antes de domínio/externo e não acessa ORM principal expirado depois.
- CAS WHERE id/version evita stale update do caminho testado; test stale winner preserva current e histórico. Unicidade evita duas versões iguais. Não demonstrada concorrência de múltiplos processos PostgreSQL.
- Lock Jina é por instância; router cria instância por request, sem serialização global. Serviço faz tentativas LLM sequenciais por operação. Essa é garantia vigente, não uma chamada ativa no sistema inteiro.
- Guardrail do binding recebe todos runtime keys e settings sensíveis; conteúdo com canary configurado conhecido é bloqueado. Não prova impossibilidade de segredo desconhecido, transformado/codificado ou digitado voluntariamente em theme/points; HTTP de edição não chama guardrail.
- Logs de aplicação/SDK/servidor não capturados. Nenhuma garantia de confidencialidade de logs emitida. Causas internas Jina/loader preservadas e observáveis em traceback são limite específico, não vazamento HTTP demonstrado.

## Achados e disposição

| ID | Lente | Classificação / severidade | Evidência e conclusão | Confiança | promoted_to |
|---|---|---|---|---|---|
| F-SEC-01 | Erros/segurança | Observação LOW | `main.py:49–60`, schemas extra forbid: 422 preserva nome dinâmico de campo extra em loc. Canary fictício enviado como nome voltou. Invalida afirmação “todas mensagens detail fixas”; contrato vigente aceita erros de schema. Não comprova segredo de configuração/upstream exposto. | Alta | null |
| F-SEC-02 | Segurança/observabilidade | Limite MEDIUM | `serp_client.py:74,94–102`, `prompt_loader.py:19–20`: causas com canary aparecem em traceback formatado. HTTP conhecido consome erro e retorna fixo; unknown HTTP observado genérico. Logs não capturados, portanto exposição operacional não confirmada. | Alta quanto a traceback; não aferida quanto a logs | null |
| F-TRACE-01 | Dados/conformidade | Limite Should LOW | Modelos 131–159 e interface 68: sem digest/snapshot do prompt ou busca por briefing. Origem em disco comprovada; reconstrução histórica de prompt/busca não implementada. Não converter Should em falha Must. | Alta | null |
| F-TRACE-02 | Concorrência/integridade | Limite LOW | Append-only comprovado nas transições; ORM/DB não proíbe UPDATE/DELETE externo e FK é CASCADE. Não afirmar trilha imutável contra administrador DB. | Alta | null |
| F-COVER-01 | Contratos/cobertura | Gate pendente HIGH para aceite overall | L95 e escopo executado: nenhum request autorizado a provedor real configurado. SDK+MockTransport local não satisfaz T012 runtime real. | Alta | null |

Totais: **5 observações/limites/gates; 0 defeitos Must confirmados; 0 bugs promovidos.** Severidade de gate indica bloqueio de aceite, não vulnerabilidade confirmada.

Cluster: fronteira de diagnóstico. Strings de erro públicas conhecidas são fixas; objetos internos conservam informações, e validação conserva loc client-supplied. Revisão de logs e política de entrada sensível exigem escopo autorizado separado; não justificar catch-all que destrua identidade de unknown errors.

## Não coberto / handoff

- Não executado T012 com provedor hospedado, Jina real, egress real, timeout remoto ou credenciais reais.
- Não capturados logs; nenhum teste de redaction de logger SDK/Uvicorn. Não inspecionado projeto inteiro.
- SQLite local não prova timezone/microsegundos/concorrência PostgreSQL; tests de história preservam campos no backend exercitado.
- Não executados browser, frontend, lifespan com retomada do pipeline legado ou deploy.
- Preservar actions finais abertos até gates parent. Este PASS local não autoriza DONE, commit, push ou deploy.
