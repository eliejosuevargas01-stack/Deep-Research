# Inspeção independente T007 — domínio puro

## Veredito: PASS (somente recorte local)

- Confirmados: **0**. Observações: **1**, cobertura persistente dos testes. Bugs promovidos/registrados: **0**. `promoted_to: null` em todos os registros deste relatório.
- Produção auditada: `app/briefing/domain.py:1–167`, SHA256 `f058679d7a1a923c337a4dc067c01cbc3d0f50d0ca126220de286ec89d557b4a`, conferido antes/depois.
- Auditoria leitora; nenhuma correção. Único artefato novo: este relatório. Nenhuma edição em actions, progress, state, taxonomy, intake ou views.
- Branch `main`. Working tree já sujo, com documentação antiga excluída, arquivos modificados e módulo/testes novos não rastreados; não restaurados. `git log -3 --oneline -- app/briefing/domain.py` não retornou histórico para o arquivo novo. Ausência de histórico não comprova preservação byte a byte dos helpers pré-T007; compatibilidade dos helpers foi verificada por leitura e testes atuais.
- `.reversa/active-requirements.json:3–7` aponta feature correta, estágio `coding`. `.reversa/state.json:10` e AGENTS são histórico obsoleto, não prova de conclusão. Configuração encontrada em `.reversa/reversa-config.json:1–18`; tentativa inicial no caminho raiz inexistente foi resolvida sem alterar configuração.
- `actions.md:43–44,51,65–66`: T007 `[X]`; T004/T005 `[ ]`; 9/16 ações marcadas concluídas. Esta inspeção não fecha gates T010/T011 nem produto inteiro.

## 1. Mapa spec → código → testes → dados

Fonte de produto: `_reversa_forward/001-modulo-briefing/requirements.md`, RN-01/03/05/06/07, RF-01/03/05/06/07/08/09. Âncoras lidas: `_reversa_sdd/prd.md` e `_reversa_sdd/sdd/briefing.md`; são planejadas, não evidência de implementação. Contrato técnico efetivo: `roadmap.md:64–81` e `data-delta.md:35–76`, adendo T004/T005/T007. Também lidos actions, legacy-impact, regression-watch, execution-policy, AGENTS, state, active-requirements, config e registro de bugs.

README do registro: closure policy `local-software`. Taxonomy antiga não contém briefing. Busca textual `briefing|Briefing` em `_reversa_bugs` não encontrou bug anterior deste contexto antes deste relatório; sem registro/promover/alterar taxonomy.

### Código e fronteiras

- Helpers existentes: `validate_theme:31–37`, `validate_points:40–53`, `assert_can_edit:56–58`, `transition:61–74`.
- Entidades: `BriefingPoint:77–80`, `Briefing:83–91`, ambas congeladas.
- Ponte de entrada: `_copy_valid_points:107–119`. Aceita Sequence não textual; extrai Mapping por chave; copia BriefingPoint; valida lista nova; produz tupla de novos pontos congelados.
- Operações públicas: `new_briefing:94–104`, `complete_briefing:127–131`, `fail_briefing:134–139`, `edit_briefing:142–146`, `approve_briefing:149–155`, `reopen_briefing:158–162`, `read_approved:165–167`.
- Callers locais atuais: `schemas.py:13–21,43–46,54–57,80–84` usa enum/constantes/helpers; `serp_client.py:9` importa validate_theme. Nenhum caller de produção em `app/briefing` utiliza ainda operações T007; service/router/storage não entregues neste recorte. Prompt loader não importa domínio; pacote `__init__.py` sem efeitos.
- Testes lidos: seis `tests/test_briefing_*.py`. Domínio antigo 10, schemas 6, prompt loader 4, SERP 10, validation 4, lifecycle 12: **46 métodos**. Subtests não somados como testes distintos.
- Dados: tema normalizado, UUID4 estável, status enum, tuple de pontos, versão inteira, datetime de aprovação fornecido pelo caller, erro seguro fornecido pelo caller. Histórico local consiste nos valores que caller retém. Sem tabela/cache/fila/DB/HTTP/rede no domínio. Nenhum segredo operacional acessado.

### Matriz de critérios

Prefixos de testes: V = `tests/test_briefing_validation.py`, L = `tests/test_briefing_lifecycle.py`, D = `tests/test_briefing_domain.py`. P = probe real reproduzível abaixo.

| Critério/spec | Símbolo/linhas | Teste/probe real | Resultado |
|---|---|---|---|
| RN-01/RF-01, strip e 3–300 | validate_theme 31–37; new_briefing 94–104 | V:13–61; D:12–25; P UUID4/versão/tema | PASS |
| RN-03, geração 3–7 | complete 127–131; copy 107–119 | L:53–71; P 3/4/5/6/7 e rejeição 0/1/2/8 | PASS |
| RN-05/RF-05, editar/reordenar 3–7 | edit 142–146 | L:33–51,73–80,131–133,193–203; P edição 3–7 e ordem invertida | PASS local |
| Título/descrição strings não vazias, sem trim obrigatório | validate_points 40–53; copy 107–119 | L:82–113; D:27–58; P campos ausentes/inválidos nas três operações e strings com espaços | PASS |
| RN-06/RF-06, revalidar aprovação | approve 149–155 | L:82–99,179–191; P contagem/campos inválidos e datetime inválido | PASS |
| RF-09, reabrir só aprovado, limpa instante | reopen 158–162 | L:33–51,179–191; P versões e approved_at | PASS |
| RF-07 local, read só aprovado, sem aumento de versão | read 165–167 | L:205–218; P identidade distinta/equivalência/congelamento | PASS local |
| generating complete/fail; failed terminal | require_status 122–124; transition 61–74; fail 134–139 | L:155–177; D:61–86; P matriz 4 estados × 6 operações | PASS |
| Snapshot recusado preservado, ID estável, +1 por alteração | replace 130–167 | L:63–99,193–218; P repr completo antes/depois e cadeia [1,2,3,4,4,5] | PASS |
| Sequence/Mapping defensivos; sem alias mutável | copy 107–119; dataclasses 77–91 | L:115–153; P list/tuple/MappingProxyType/UserDict/BriefingPoint, bytearray/iterador/set/não-sequence, novo ponto e input mutado | PASS |
| Fail com string não vazia, sem pontos | fail 134–139 | L:155–161; P mensagem válida preservada/inválida rejeitada | PASS |
| Sem efeitos externos/imports de infraestrutura | domain 1–167 | Leitura integral; imports somente stdlib; P sem mocks/operação externa | PASS estático local |

## 2. Lentes sequenciais

### 2.1 Conformidade com spec

Confirmados: 0. Evidência alta: contrato adendo `data-delta.md:41–50` corresponde às operações `domain.py:94–167`; focused16 e probe passam. Faixa 3–7 aceita inclusive 4/6; 5 não vira teto ou quantidade fixa. Não foi imposta regra de timezone, sanitização arbitrária do erro ou condição de pesquisa para reopen. `promoted_to: null`.

### 2.2 Fluxo de dados

Confirmados: 0. Evidência alta: tema strip uma vez; ponte copia dict/Mapping para lista validada, tuple nova e pontos novos; ordem/strings preservadas; caller fornece timestamp. Input mutado posteriormente não contamina snapshot. Não há transformação/persistência SERP/LLM dentro do domínio. `promoted_to: null`.

### 2.3 Contratos helpers/API de domínio

Confirmados: 0. Evidência alta: helper validate_points continua recebendo lista; ponte aceita Sequence e converte Mapping não-dict, mantendo contrato do helper. Schema usa pontos Pydantic via helper por atributos, não há caminho atual que passe pontos Pydantic diretamente às operações novas (estas aceitam BriefingPoint de domínio/Mapping). Adaptação futura de serviço não auditada. Helpers antigos passam baseline; nenhuma necessidade demonstrada de ampliar construtores Python internos. `promoted_to: null`.

### 2.4 Erros e edge cases

Confirmados: 0. Evidência alta: estados incompatíveis produzem InvalidTransition; conteúdo/count/timestamp/error inválidos produzem InvalidContent. Probe checa snapshots completos após rejeição, mensagens de validação sem canary de entrada. Aprovação revalida fixtures adulteradas com dataclasses.replace, conforme contrato. Construtor/replace que permite fixture inválida, por si só, não demonstra bug de produção. `promoted_to: null`.

### 2.5 Cobertura real

- finding_id: O-coverage-01
- lens: cobertura de testes
- summary: Casos complementares importantes não estão todos persistidos nos 16 métodos novos; audit probe cobre-os nesta execução.
- classification: observation (não defeito confirmado)
- confidence: alta
- suspected_severity: low
- evidence: `tests/test_briefing_lifecycle.py:53–61,82–99,115–153,193–218`; comandos focused16/suite46/P com exit 0.
- expected: Cobertura continuada pode provar edição/aprovação válidas em todas contagens 3–7, versões exatas em fail/approve/reopen, datetime/error inválidos e preservação integral do snapshot rejeitado.
- real: Geração cobre 3–7; ciclo exercita subconjunto de contagens, versão no repeat-edit/complete/fail e leitura sem incremento. Métodos persistidos não explicitam toda combinação acima. Probe complementar executado passa 278 checks e cobre esses casos sem mocks ou reimplementação.
- signals: [regression-risk]
- promoted_to: null

Sem porcentagem de cobertura instrumentada ou mutation testing. Ausência desses instrumentos não foi convertida em finding funcional.

### 2.6 Consistência/imutabilidade

Confirmados: 0. Evidência alta: funções produzem novos valores, rejeição não altera entrada, IDs constantes, version+1 em cada alteração aceita, read sem incremento. Read compartilha tuple/pontos congelados: compartilhamento imutável seguro nos snapshots produzidos pelas operações, não alias mutável. Não é transação/controle de concorrência durável; isso pertence a T011. `promoted_to: null`.

### Condicional: segurança local

Confirmados: 0. Mensagens de validação não interpolam conteúdo de entrada; fail recebe motivo seguro do caller (data-delta:44), sem promessa de sanitizador universal. Domain não lê credenciais, rede, DB, arquivos ou relógio; UUID4 usa stdlib. Não validada autorização/segurança HTTP, logs, sanitização do futuro caller ou dados persistidos. Nenhuma lente de desempenho/DB/migrations foi ativada. `promoted_to: null`.

## 3. Provas executadas e comandos completos

Todos comandos de shell executados com workdir absoluto `/root/projects/deep-research`. Resultados independentes: não usados auto-reports do implementador/parent como prova.

| Comando | Saída real | Exit |
|---|---|---|
| `python3 -B -m unittest tests.test_briefing_validation tests.test_briefing_lifecycle -v` | Ran 16 tests in 0.005s; OK | 0 |
| `python3 -B -m unittest tests.test_briefing_domain tests.test_briefing_schemas tests.test_briefing_prompt_loader tests.test_briefing_serp_client -v` | Ran 30 tests in 0.144s; OK | 0 |
| `python3 -B -m unittest discover -s tests -p 'test_briefing_*.py' -v` | Ran 46 tests in 0.112s; OK | 0 |
| `PYTHONPYCACHEPREFIX=/root/.hermes/profiles/orchestrator/cache/scratch/briefing-audit-pycache python3 -m py_compile app/briefing/domain.py` | sem saída | 0 |
| `git diff --check` | sem saída (executado duas vezes) | 0 |
| `sha256sum app/briefing/domain.py` | hash informado no início, igual antes/depois | 0 |
| `git status --short; git branch --show-current; git log -3 --oneline -- app/briefing/domain.py` | working tree pré-existente sujo; main; log vazio para arquivo novo | 0 |

`git diff --check` verifica diff rastreado, não substitui revisão dos arquivos novos não rastreados. Compilação escreveu cache exclusivamente no scratch permitido. Suite exigida inclui prompt tests com TemporaryDirectory/write_text no scratch do runtime e SERP tests com httpx.MockTransport e esperas curtas; nenhum serviço real chamado. Isso é I/O de fixture dos testes de compatibilidade, não efeito de domínio. Probe complementar abaixo usa apenas stdlib e dados em memória.

### Probe de domínio real

Comando executado (string integral, sem pseudocódigo), exit 0. Saída: `PASS 278 assertion checks; domain real; no mocks; all data in memory`. Checks são assertions, **não 278 testes unittest**.

```sh
python3 -B -c 'from collections import UserDict
from collections.abc import Sequence
from dataclasses import replace, FrozenInstanceError
from datetime import datetime, timezone
from types import MappingProxyType, SimpleNamespace
from app.briefing import domain as d
checks=0
def check(value):
    global checks
    assert value
    checks+=1
def pts(n):
    return [{"title": f" title {i} ", "description": f" desc {i} "} for i in range(n)]
def rejected(op, snapshot, arg, exc):
    before=repr(snapshot)
    try:
        op(snapshot, *arg)
    except exc as err:
        check(repr(snapshot)==before)
        check("ENTRY-CANARY" not in str(err))
    else:
        raise AssertionError("accepted invalid input")
t=datetime(2026,10,11,tzinfo=timezone.utc)
g=d.new_briefing("  tema  ")
check(g.id.version==4 and g.theme=="tema" and g.version==1)
for n in range(3,8):
    raw=pts(n)
    draft=d.complete_briefing(g,raw)
    edit=d.edit_briefing(draft,tuple(reversed(raw)))
    approved=d.approve_briefing(edit,t)
    read=d.read_approved(approved)
    reopen=d.reopen_briefing(approved)
    check([s.version for s in (g,draft,edit,approved,read,reopen)]==[1,2,3,4,4,5])
    check(all(s.id==g.id for s in (draft,edit,approved,read,reopen)))
    check([p.title for p in edit.points]==[p["title"] for p in reversed(raw)])
    check(approved.points==edit.points and approved.approved_at is t and reopen.approved_at is None)
    check(read==approved and read is not approved)
    raw[0]["title"]="changed"; raw.clear()
    check(draft.points[0].title==" title 0 ")
    for obj, field, value in ((read,"version",99),(read.points[0],"description","changed")):
        try: setattr(obj,field,value)
        except FrozenInstanceError: check(True)
        else: raise AssertionError("mutable snapshot")
draft=d.complete_briefing(g,pts(3))
approved=d.approve_briefing(draft,t)
failed=d.fail_briefing(g," safe error ")
check(failed.id==g.id and failed.version==2 and failed.error==" safe error " and failed.points==())
ops=[(d.complete_briefing,(pts(3),),d.BriefingStatus.GENERATING),
     (d.fail_briefing,("safe",),d.BriefingStatus.GENERATING),
     (d.edit_briefing,(pts(3),),d.BriefingStatus.DRAFT),
     (d.approve_briefing,(t,),d.BriefingStatus.DRAFT),
     (d.reopen_briefing,(),d.BriefingStatus.APPROVED),
     (d.read_approved,(),d.BriefingStatus.APPROVED)]
for snapshot in (g,draft,approved,failed):
    for op,arg,status in ops:
        if snapshot.status!=status: rejected(op,snapshot,arg,d.InvalidTransition)
for n in (0,1,2,8):
    rejected(d.complete_briefing,g,(pts(n),),d.InvalidContent)
    rejected(d.edit_briefing,draft,(pts(n),),d.InvalidContent)
    rejected(d.approve_briefing,replace(draft,points=tuple(pts(n))),(t,),d.InvalidContent)
for field in ("title","description"):
    for value in ("", " \t\n", None, 0, True, [], {}):
        raw=pts(3); raw[1][field]=value
        rejected(d.complete_briefing,g,(raw,),d.InvalidContent)
        rejected(d.edit_briefing,draft,(raw,),d.InvalidContent)
        rejected(d.approve_briefing,replace(draft,points=tuple(raw)),(t,),d.InvalidContent)
    raw=pts(3); del raw[1][field]
    rejected(d.complete_briefing,g,(raw,),d.InvalidContent)
    rejected(d.edit_briefing,draft,(raw,),d.InvalidContent)
    rejected(d.approve_briefing,replace(draft,points=tuple(raw)),(t,),d.InvalidContent)
for value in ("ENTRY-CANARY",b"ENTRY-CANARY",bytearray(b"ENTRY-CANARY"),None,0,{},set(),iter(pts(3))):
    rejected(d.complete_briefing,g,(value,),d.InvalidContent)
    rejected(d.edit_briefing,draft,(value,),d.InvalidContent)
for value in (None,0,"ENTRY-CANARY",SimpleNamespace(title="ok",description="ok")):
    rejected(d.complete_briefing,g,([value]*3,),d.InvalidContent)
    rejected(d.edit_briefing,draft,([value]*3,),d.InvalidContent)
raw=pts(3)
mixed=[d.BriefingPoint(**raw[0]),UserDict(raw[1]),MappingProxyType(raw[2])]
for op,snapshot in ((d.complete_briefing,g),(d.edit_briefing,draft)):
    out=op(snapshot,mixed)
    check([p.title for p in out.points]==[p["title"] for p in raw])
    check(out.points[0] is not mixed[0])
for value in (None,0,True,"ENTRY-CANARY",{},[]):
    rejected(d.approve_briefing,draft,(value,),d.InvalidContent)
for value in (None,0,True,"", " \t\n",{},[]):
    rejected(d.fail_briefing,g,(value,),d.InvalidContent)
check(d.approve_briefing(draft,datetime(2026,10,11)).approved_at==datetime(2026,10,11))
check(g.version==1 and draft.version==2 and approved.version==3 and failed.version==2)
print(f"PASS {checks} assertion checks; domain real; no mocks; all data in memory")
'
```

### Estrutura JSONL

Comando executado, exit 0. Saída: `PASS physical_lines=19 objects=19 trailing_newline=True`. Cada linha física passou json.loads; todos objetos dict; newline final existe. Nenhuma escrita em progress. Histórico 18 + registro do parent = 19; isso não aprova código por declaração.

```sh
python3 -B -c 'import json
from pathlib import Path
p=Path("_reversa_forward/001-modulo-briefing/progress.jsonl")
b=p.read_bytes(); lines=b.splitlines(); objects=[json.loads(line) for line in lines]
assert len(lines)==len(objects)==19
assert all(isinstance(x,dict) for x in objects)
assert b.endswith(b"\n")
print(f"PASS physical_lines={len(lines)} objects={len(objects)} trailing_newline={b.endswith(bytes([10]))}")
'
```

Também houve leitura/parse inicial de 19 linhas em ferramenta Python; parse válido. Leitura batch teve stdout truncado e foi recuperada por páginas/faixas relevantes; tentativa de re-read deduplicada causou KeyError no wrapper, não no domínio. Wrapper corrigido com leitura direta/faixas. Nenhum comando de teste/probe falhou.

## 4. Consolidação, clusters e limites

Nenhum cluster de defeitos confirmado. Única observação pertence à cobertura persistente, não ao comportamento atualmente demonstrado. Nenhuma suspeita promovida. Nenhuma ação corretiva criada, nenhum bug registrado, nenhuma view gerada.

Não verificado: feature inteira; serviço T010; spy integrado de rejeição pré-SERP/LLM; DB/storage/router/migration T011; versão salva consultável/histórico durável; concorrência/idempotência/transações; HTTP/auth/autorização; segurança de erros do futuro caller; SaaS Jina real; rede paga; investigação Jina anterior; pipeline legado; frontend; instalação/deploy; garantia semântica de pontos não conclusivos via LLM. Também não foram testados objetos Python hostis que deliberadamente subvertem métodos Sequence/Mapping, object.__setattr__ ou construtores internos sem contrato de boundary; não há caller de produção demonstrado que os aceite.

PASS significa conformidade e compatibilidade do **domínio puro T007 entregue** nas entradas aprovadas e edge cases testados. Não significa aceite total de produto, persistência ou fechamento de T004/T005. Todos `promoted_to: null`.
