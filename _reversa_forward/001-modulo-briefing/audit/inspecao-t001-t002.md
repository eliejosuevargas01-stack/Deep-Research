# Inspeção independente — T001/T002

## Resultado e limites

Recorte: `app/briefing/__init__.py`, `domain.py`, `schemas.py`. Diagnóstico somente; nenhum código corrigido, nenhuma instalação, rede, DB ou pytest. Fontes de produto: `requirements.md` RN-01–RN-07/RF-01–RF-10/seção 9; `_reversa_sdd/sdd/briefing.md`; `_reversa_sdd/prd.md`; `interfaces/briefing-http.md`; `data-delta.md`. Código antigo não define regras.

**3 findings comprovados: 3 MEDIUM; 0 CRITICAL/HIGH/LOW.** Mais 1 observação LOW de proveniência, não contada como bug comprovado. Todos `promoted_to: null`; nenhum registro de bug criado. Restrições específicas desta inspeção substituem bootstrap/registro/views do skill: escrita somente neste relatório.

## Mapa da feature e lentes

- Fronteira: `__init__.py:1` apenas docstring; `domain.py:6–16` limites/estados, `:27–49` validadores, `:52–70` edição/transições. Sem I/O/persistência/investigação nesses arquivos.
- Transporte: `schemas.py:23–56` pontos/criação/edição; `:59–68` aprovação/reabertura vazias; `:71–88` respostas.
- Specs: requisitos `:32–44`, `:51–60`, `:134–153`; SDD `:54–63`, `:95–107`, `:145–154`; PRD `:38–47`, `:61–68`; data delta `:14–21`; HTTP `:7–12`, `:16–42`.
- Testes: T004/T005/T006 seguem pendentes em `actions.md:32–34`. Busca `test_*.py` por `briefing` encontrou testes legados e `tests/test_briefing_prompt_loader.py`; nenhum teste entregue de validação/ciclo destes arquivos foi executado. Probes abaixo são evidência isolada, não suíte de aceite.
- Dados/externos: entidades, storage, SERP, LLM, logs, histórico e metadados não implementados neste recorte; nada acessado.
- Lentes sequenciais: conformidade, fluxo de dados, contratos, erros/edge cases, cobertura; concorrência/consistência limitada à ausência de I/O nos arquivos. Segurança limitada a campos e mensagens locais. Não alegar auditoria de segredo ou atomicidade ponta a ponta.

## Findings comprovados

### F-01 — MEDIUM — Resposta permite estado fora do ciclo aprovado

Lentes: contratos/conformidade. Confiança alta. `promoted_to: null`.

- Evidência: `schemas.py:76` usa `status: str`, embora `domain.py:12–16` defina quatro estados; `data-delta.md:15` restringe ciclo a `generating/draft/failed/approved`.
- Probe P1/P2: `BriefingResponse(..., status="banana")` aceita; JSON Schema de status é `{'title': 'Status', 'type': 'string'}`, sem enum. Exit 0.
- Desvio comprovado no contrato Pydantic, não vazamento real de estado em endpoint. Consumidores não recebem domínio de estados no schema e erro de produtor atravessa validação.
- **Tarefa específica:** tipar `BriefingResponse.status` com `BriefingStatus` (ou literal equivalente); testar rejeição de desconhecido e serialização dos quatro valores; alinhar nome final `status`/`state` com contrato aprovado antes de T011.

### F-02 — MEDIUM — Schemas de resposta aceitam conteúdo aprovado fora de 3–7

Lentes: contratos/conformidade/edge cases. Confiança alta. `promoted_to: null`.

- Evidência: `schemas.py:77` não impõe quantidade dependente de estado; `schemas.py:87` não impõe quantidade nem `validate_points` em resposta exclusivamente aprovada. RN-03/RF-06 em `requirements.md:36,56,152–153` exigem conteúdo aprovado válido.
- Probe P2: respostas `ApprovedBriefingResponse` e `BriefingResponse(status="approved")` aceitam 0, 2 e 8 pontos. Exit 0.
- Limitação: prova de contrato permissivo; não prova aprovação/persistência inválida pelo serviço futuro. Lista vazia em `generating`/`failed` pode ser legítima; não aplicar mínimo global indiscriminadamente.
- **Tarefa específica:** impor 3–7 em `ApprovedBriefingResponse.points`; validar pontos de `BriefingResponse` quando estado representar conteúdo válido (`draft`/`approved`), preservando estados sem rascunho; adicionar regressões 0/2/3/7/8. Manter validação na operação de aprovação futura, não substituí-la por schema de resposta.

### F-03 — MEDIUM — Entrega T001 não registra decisão de entidade

Lente: conformidade de entrega/rastreabilidade. Confiança alta quanto ao artefato ausente no recorte. `promoted_to: null`.

- Evidência: `actions.md:24` marca T001 concluída e inclui decidir entidade isolada versus reutilização seletiva de `Research`. `domain.py:1–70` registra somente regras/estados; `__init__.py:1` somente docstring. `data-delta.md:13` ainda diz decidir no design. `roadmap.md:19` oferece alternativas, não decisão.
- Busca textual por decisão de entidade/reutilização seletiva encontrou obrigação em actions e alternativa em roadmap, não decisão efetiva. Não inferir escolha pela ausência de import legado.
- **Tarefa específica:** registrar escolha explícita no artefato de fronteira previsto por T001, com justificativa e separação de execução de pesquisa; alinhar data delta ao resultado. Não criar modelo/storage prematuramente. Se decisão permanecer pendente, não alegar cumprimento integral desta parcela de T001.

## Observação de proveniência — não bug comprovado

### O-01 — LOW — Timestamps de T001/T002 não sustentam horário real

Lente: rastreabilidade. Confiança alta sobre valores; fabricação não confirmada independentemente. `promoted_to: null`.

- `progress.jsonl:1–2` repete `2026-10-10T00:00:00Z` para tarefas distintas. Contexto delegado identifica valor como fabricado pelo worker. Leitura confirma valor, mas repetição/meia-noite isoladamente não prova fabricação.
- Registros citam `py_compile:0`/`selfcheck_inline:0` sem comandos/saídas suficientes para reprodução. Checks locais novos não autenticam horário nem execução original.
- **Tarefa específica de saneamento futuro:** responsável registrar horário real quando conhecido ou marcar timestamp desconhecido/sintético, preservando trilha original; anexar comando e saída verificável aos checks. Este relatório não altera `progress.jsonl`.

## Suspeitas verificadas sem finding

1. **FAILED sem saída:** `domain.py:66` não permite nenhuma transição. As 16 combinações foram verificadas. RF-10 (`requirements.md:60,142–150`) exige retries automáticos durante operação, não recuperação manual depois de falha terminal. SDD `:75–76,100` explicita falha terminal após esgotamento e recuperação manual/regeneração pendente. **Pergunta aberta:** após falha terminal, permitir nova criação ou regeneração do mesmo registro? Não promover bloqueio como bug; retries podem ocorrer ainda em `generating`.
2. **Comentário antes da docstring:** `schemas.py:1–6` não quebra docstring. Comentários não são statements; `schemas.__doc__` retornou `Contratos HTTP do módulo de briefing (Pydantic v2).` Import e parse passaram.
3. **Field + validator before:** `schemas.py:40–45` funciona. `"  ab  "` vira `ValidationError`; `"  abc  "` produz `"abc"`; 300 caracteres com espaços externos aceitos; 301 rejeitados; inteiro/None/vazio rejeitados como `ValidationError`, não exceção crua do schema. `InvalidContent` herda `ValueError` (`domain.py:19`). Compatível com 422 de validação; status HTTP real não testado. `json.dumps(e.errors())` bruto falha porque ctx contém exceção; `e.json()` e `fastapi.encoders.jsonable_encoder` funcionam. Sem handler HTTP no recorte, não afirmar bug de serialização.
4. **Pontos não normalizados:** `schemas.py:31–34` e `domain.py:45–49` rejeitam somente-whitespace mas preservam espaços de strings válidas (`" t "`). Requisito exige não vazio, não strip persistido de títulos/descrições. SDD OQ-05 `:153` deixa validações além da presença abertas. Sem finding; não inventar normalização obrigatória.
5. **Dict ou objeto:** `domain.py:39–48` suporta dict e objeto com atributos; ambos passam quando válidos. Objeto sem atributos rejeitado; lista com título/descrição whitespace rejeitada; tuple rejeitada no domínio. Dict com chave extra permanece intacto — validador de conteúdo não é filtro de serialização. Schemas públicos usam `extra=forbid`. Risco de transportar extras deve ser verificado no serviço/serializer futuro; nenhuma exfiltração comprovada.
6. **Aprovar/reabrir sem corpo:** schemas vazios aceitam `{}` e recusam extras; operações HTTP `briefing-http.md:10–11` usam conteúdo atual, não exigem points no corpo. Correto para esta proposta. Ausência efetiva de body depende da assinatura do router futuro; não confundir modelo vazio com body HTTP opcional.
7. **Estado/edições:** quatro transições permitidas são geração para draft/failed, draft para approved, approved para draft. `assert_can_edit("approved")` recusa; `draft` aceita 100 chamadas consecutivas. Nenhuma restrição por pesquisa, contador ou limite de edições. `transition` não recebe conteúdo: aprovação válida depende de composição com `validate_points` em T007/serviço; não alegar aprovação segura já entregue.
8. **Formato de representação:** HTTP `:22` usa `state`; schema usa `status` e não inclui erro seguro/proveniência/versionamento. HTTP `:14` e SDD `:92,150` ainda tratam formato como proposta/OQ. Não classificar nomes/campos propostos como quebra de contrato aprovado. **Pergunta aberta:** qual representação mínima final, incluindo motivo seguro de `failed`? T002 não comprova congelamento integral da interface.

## Cobertura honesta por requisito

| RF | Evidência T001/T002 | Não comprovado / tarefa posterior |
|---|---|---|
| RF-01 | Normalização/limite/tipos no domínio e criação | Registro identificável, estado inicial persistido, rejeição antes de I/O: T007/T010/T011 |
| RF-05 | Payload 3–7, strings não vazias, ordem de lista preservada, guard draft | Salvar/consultar versão, preservar anterior após rejeição, atomicidade: T007/T011 |
| RF-06 | Transição draft/approved e recusa de edição approved | Validar conteúdo ao aprovar, persistir coerência: T007/T011; F-02 cobre somente permissividade de resposta |
| RF-09 | approved para draft, sem restrição de pesquisa | Reabertura persistida e edição efetiva posterior: T007/T011 |
| RF-03 | Validador puro 3–7, aceita 3/4/5/6/7 | Geração real, foco não conclusivo, alvo habitual 5: T008/T010 |
| RF-02/04/10 | Nenhuma integração executada | SERP/prompt/retry quatro tentativas/reuso: fora deste recorte |
| RF-07/08 | Schemas de consulta; comentários de matriz e mensagens locais fixas | Read-only aprovado, erros seguros reais e nenhuma investigação: T010/T011/T013 |

Matriz 422/409/404/503 aparece em `schemas.py:1–5`; HTTP ainda prevê 500 para configuração (`briefing-http.md:40`). Comentário não implementa handlers/status/retries. Sem achado de segurança comprovado; `extra=forbid` e ausência de campos de credencial não provam ausência de segredos dentro de textos, erros externos ou logs.

## Evidência executável

Workdir de probes: `/root/projects/deep-research`. Python 3.14.7, Pydantic 2.13.5; FastAPI instalado 0.142.2. Sem instalação. P1 exploratório e P2 assertivo terminaram exit **0**. Parse AST dos três arquivos terminou exit **0**, não executou `py_compile` novo. Um import inicial sem `-B` ocorreu; não houve edição intencional de fonte nem probe escrevendo arquivo de teste. Probes seguintes usaram `-B`; caches Python preexistentes foram observados, não foi possível atribuir eventual atualização do import inicial.

### P2 — reprodução mínima assertiva (`python3 -B -c`), exit 0

```sh
python3 -B -c 'from uuid import UUID; from types import SimpleNamespace; from pydantic import ValidationError; from app.briefing import domain as d, schemas as s
p={"title":"t","description":"d"}; uid=UUID(int=1)
def rejected(fn, typ):
    try: fn()
    except typ: return
    raise AssertionError("expected rejection")
for value in ["  ab  ","a"*301,"",123,None]: rejected(lambda v=value:s.BriefingCreateRequest(theme=v),ValidationError)
assert s.BriefingCreateRequest(theme="  abc  ").theme=="abc"
assert len(s.BriefingCreateRequest(theme=" "+"a"*300+" ").theme)==300
for n in range(3,8):
    assert len(s.BriefingEditPointsRequest(points=[p]*n).points)==n
    assert len(d.validate_points([p]*n))==n
for n in [0,2,8]:
    rejected(lambda n=n:s.BriefingEditPointsRequest(points=[p]*n),ValidationError)
    rejected(lambda n=n:d.validate_points([p]*n),d.InvalidContent)
for key in ["title","description"]:
    rejected(lambda key=key:s.BriefingEditPointsRequest(points=[{**p,key:" \t "}]*3),ValidationError)
assert d.validate_points([SimpleNamespace(**p)]*3)
assert s.BriefingPoint(title=" t ",description=" d ").title==" t "
allowed={("generating","draft"),("generating","failed"),("draft","approved"),("approved","draft")}
for a in d.BriefingStatus:
    for b in d.BriefingStatus:
        if (a.value,b.value) in allowed: assert d.transition(a,b)==b
        else: rejected(lambda a=a,b=b:d.transition(a,b),d.InvalidTransition)
for _ in range(100): d.assert_can_edit("draft")
rejected(lambda:d.assert_can_edit("approved"),d.InvalidTransition)
assert s.BriefingApproveRequest().model_dump()=={}
assert s.BriefingReopenRequest().model_dump()=={}
assert s.__doc__=="Contratos HTTP do módulo de briefing (Pydantic v2)."
assert s.BriefingResponse(id=uid,theme="abc",status="banana").status=="banana"
assert s.BriefingResponse.model_json_schema()["properties"]["status"]=={"title":"Status","type":"string"}
for n in [0,2,8]:
    assert len(s.ApprovedBriefingResponse(id=uid,theme="abc",points=[p]*n).points)==n
    assert len(s.BriefingResponse(id=uid,theme="abc",status="approved",points=[p]*n).points)==n
print("PASS: tema strip/limites/tipos; pontos 3..7/vazios; 16 transicoes; 100 edicoes; docstring; corpos vazios. CONFIRMADO: status banana aceito; aprovado aceita 0,2,8 pontos.")'
```

Saída literal:

```text
PASS: tema strip/limites/tipos; pontos 3..7/vazios; 16 transicoes; 100 edicoes; docstring; corpos vazios. CONFIRMADO: status banana aceito; aprovado aceita 0,2,8 pontos.
```

Probe da docstring (`python3 -c "import app.briefing.schemas as s; print('__doc__:', repr(s.__doc__))"`), exit 0: `__doc__: 'Contratos HTTP do módulo de briefing (Pydantic v2).'`.

Probes auxiliares observaram `errors() json FAIL: Object of type InvalidContent is not JSON serializable`, `e.json ok: True` e `fastapi jsonable_encoder` convertendo ctx em `{}`; exit 0. Nenhum HTTP servido. P1 confirmou campos extras rejeitados, campo obrigatório ausente rejeitado, pontos whitespace/tipo inteiro rejeitados, dict/objeto e limites.

## Fora do recorte e restrições

Não inspecionados: `prompt_loader.py`, código legado, adapters/service/router/storage, autenticação, migrations, concorrência real, idempotência, efeitos externos, geração não conclusiva, retry/reuso, segredos em logs/respostas reais, pesquisa/relatórios. Estado git contém mudanças externas preexistentes; nenhuma atribuída a esta inspeção. Não registrar skill novo, bugs, views ou alterar actions/progress/state, pois somente relatório foi autorizado.

Houve comandos de leitura shell antes de seguir correção de ferramentas e comandos auxiliares com utilitários shell; não constituem autorização nem evidência de escrita no produto. Nenhum commit/push. Evidência principal reproduzível é P2 acima, inline, sem arquivo de teste ou rede.
