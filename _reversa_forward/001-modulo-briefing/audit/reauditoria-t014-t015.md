# Reauditoria independente — T014/T015

## Gate e recorte

**PASS somente para saneamento F-01/F-02/F-03 e O-01 de T001/T002.** Três findings MEDIUM anteriores resolvidos no recorte; zero findings novos confirmados. O-01 saneada documentalmente, com uma limitação histórica LOW remanescente: horário/execução original não autenticados. Nenhum bug registrado (`promoted_to: null`). Não encerra feature, não aprova implementação própria, não comprova API/persistência nem substitui QA final.

Skill `reversa-depth-inspection` carregado antes da leitura. Restrição explícita substitui bootstrap, registro e views: única escrita de projeto autorizada é este relatório. Sem correção, todo_list, instalação, rede, DB, frontend, commit/push/deploy. Caches de compilação exclusivamente no scratch autorizado.

Contexto: `.reversa/state.json:3–6` define pt-BR e `_reversa_sdd`; `.reversa/active-requirements.json:3–12` identifica feature 001 em coding. Estado global antigo e AGENTS.md são contexto, não fonte de produto. Âncora greenfield: `_reversa_sdd/prd.md:99–107`, `_reversa_sdd/sdd/briefing.md:169–170`; fonte funcional prevalente: `requirements.md:14,32–44,51–60,152–153`. Execução contínua: `execution-policy.md:5,11–18`.

Workdir de todos os comandos: `/root/projects/deep-research`. Git `main`, HEAD `c741ce77dedfb88d11a8f0916482c721251f112d`. `git status --short` exit 0 mostrou árvore já suja, com modificações/deleções externas e arquivos novos não rastreados. Não atribuir tais alterações à reauditoria. `git diff --check` não valida conteúdo de arquivos não rastreados; import, unittest e py_compile verificaram os arquivos reais deste recorte.

## Mapa e lentes

- Código: `app/briefing/__init__.py:1`, `domain.py:6–16,36–49`, `schemas.py:24–35,72–95`.
- Testes: `tests/test_briefing_schemas.py:6–7` importa domínio/schemas reais; `:22–72` cobre status, enum, serialização, limites, vazios e extras.
- Artefatos lidos: requirements, actions, data-delta, roadmap, interfaces/briefing-http, legacy-impact, regression-watch, progress.jsonl e inspeção inicial.
- Dados: decisão documental de entidade isolada; nenhuma tabela/storage/migration executada ou inspecionada.
- Lentes sequenciais: conformidade, fluxo de dados, contratos, edge cases, cobertura e rastreabilidade. Concorrência/consistência limitada à validação local sem I/O; sem gate transacional. Segurança limitada a extras/tipos locais, sem prova de ausência de segredos em textos/logs.

## Veredito por item

### F-01 — RESOLVIDO — MEDIUM anterior, confiança alta

`app/briefing/schemas.py:77` usa `BriefingStatus`, definido em `domain.py:12–16`. `banana` rejeitado por ValidationError. Enum JSON Schema contém exatamente `generating`, `draft`, `failed`, `approved`; model_dump(mode="json") serializa quatro estados como strings. Evidência executada: testes `test_briefing_schemas.py:22–24,49–63`, seis testes exit 0 e probe adicional exit 0. Campo canônico `status` alinhado em `interfaces/briefing-http.md:18–26`; não existe mais `state` no exemplo. Rotas e metadados permanecem propostas (`:14,18,20`), não API real congelada.

### F-02 — RESOLVIDO — MEDIUM anterior, confiança alta

`schemas.py:80–84` aplica model_validator after e `validate_points` apenas a draft/approved. Domínio `domain.py:8–9,36–49` exige 3–7 e título/descrição não vazios. `ApprovedBriefingResponse.points` usa Field com constantes min/max (`schemas.py:94`).

Testes reais verificaram, para três respostas com conteúdo, rejeição de 0/2/8 e aceitação de 3/4/5/6/7: 24 casos de quantidade, sendo 9 rejeições e 15 aceitações. generating/failed aceitam vazio, sem mínimo global indevido. Testes de enum/serialização abrangem quatro estados. Probe complementar confirmou 72 rejeições de vazios/whitespace/tipos/ausentes/extras e preservação de whitespace em três respostas válidas. Não exigir exatamente 5 nem trim persistido de títulos. Aprovação atômica e HTTP 422 reais continuam não comprovados: schema não implementa operação nem handler.

### F-03 — RESOLVIDO DOCUMENTALMENTE — MEDIUM anterior, confiança alta

`data-delta.md:9–14` registra decisão explícita: entidade briefing ISOLADA, sem Research/ResearchPoint/ResearchStatus, reutilização futura somente infraestrutura DB/auth. `roadmap.md:19` espelha decisão; `actions.md:25,34` vincula T001/T015. `data-delta.md:14,20` distingue decisão de implementação futura. Ausência de import legado no código não foi usada sozinha para inferir escolha. Citações sobre comportamento legado na justificativa não foram revalidadas fora do read-set nem tratadas como regra de produto.

`legacy-impact.md:13–20` inclui __init__/domain/schemas/testes como componentes novos greenfield e diff conceitual. `regression-watch.md:21–23` possui W003–W005. Nenhuma exigência de modelo/storage antecipado.

### O-01 — SANEADA, COM LIMITE HISTÓRICO — LOW, não bug comprovado

`progress.jsonl:1–4` mantém registros iniciais presentes na entrada desta reauditoria; `:5–6` acrescenta corrected T001/T002, `original_event_time: unknown`, justificativa e checks reproduzíveis. `:7–8` registra done T014/T015 com timestamp explicitamente da verificação do parent, não horário original. Identificadores misturam `task` antigo e `action` novo; probe resolve ambos sem perder IDs. Todos oito registros parseiam; 19 referências de arquivos existem; actions tem 15 IDs únicos e seis [X]: T001/T002/T003/T008/T014/T015.

Não há snapshot anterior independente ou histórico Git desses arquivos não rastreados para autenticar preservação byte a byte dos primeiros quatro registros através de toda a execução. Estado atual preserva registros recebidos, sem reescrita por esta auditoria. Meia-noite repetida não prova fabricação. Timestamp de worker antes de patch e execução local atual também não autenticam execução original. RED/saídas antigas descritos em progress não foram reproduzidos contra versão anterior; evidência GREEN abaixo é nova e independente.

**Observação remanescente: 1 LOW, confiança alta sobre limitação, promoted_to: null.** Tarefa futura específica do responsável por proveniência: anexar fonte contemporânea verificável se existir; sem ela, manter horário original desconhecido e não converter novos checks em prova histórica. Não bloqueia saneamento delimitado.

## Evidência executável atual

Python 3.14.7; Pydantic 2.13.5. Todos comandos abaixo executados no workdir indicado, sem instalação. Comandos individuais da suíte/compile/diff foram novamente executados via subprocess com retorno explicitamente capturado: todos exit 0.

```sh
python3 -B -m unittest discover -s tests -p test_briefing_schemas.py -v
python3 -B -m unittest discover -s tests -p 'test_briefing_*.py' -v
PYTHONPYCACHEPREFIX=/root/.hermes/profiles/orchestrator/cache/scratch/reaudit-briefing-pycache python3 -B -m py_compile app/briefing/__init__.py app/briefing/domain.py app/briefing/schemas.py tests/test_briefing_schemas.py
git diff --check
git status --short
git branch --show-current
git rev-parse HEAD
```

Resultados: schemas `Ran 6 tests`, `OK`, exit 0; conjunto briefing `Ran 10 tests`, `OK`, exit 0; py_compile quatro arquivos exit 0, sem saída; diff --check exit 0, sem saída; status/branch/rev-parse exit 0. Conjunto de dez inclui quatro testes de loader apenas como smoke solicitado, não nova auditoria T008, nem reabertura de seu relatório separado. Primeira rodada de comandos separados por ponto e vírgula não bastava para capturar cada exit; segunda execução registrou cada retorno 0 explicitamente.

Probe complementar reproduzível completo, exit 0:

```sh
python3 -B -c '
import json,re,pathlib
from uuid import UUID
from pydantic import ValidationError
from app.briefing import schemas as s
p={"title":" t ","description":" d "}; count=0
makers=[lambda pts,**kw:s.BriefingResponse(id=UUID(int=1),theme="tema",status="draft",points=pts,**kw),lambda pts,**kw:s.BriefingResponse(id=UUID(int=1),theme="tema",status="approved",points=pts,**kw),lambda pts,**kw:s.ApprovedBriefingResponse(id=UUID(int=1),theme="tema",points=pts,**kw)]
def reject(fn):
 global count
 try: fn()
 except ValidationError: count+=1; return
 raise AssertionError("expected rejection")
for make in makers:
 for key in ("title","description"):
  for value in (""," \t ",None,0,True,[],{}): reject(lambda:make([{**p,key:value}]*3))
  reject(lambda:make([{k:v for k,v in p.items() if k!=key}]*3))
 reject(lambda:make([{**p,"extra":"x"}]*3))
 reject(lambda:make([p]*3,extra="x"))
 for pts in (None,0,"points",{},[None]*3,[0]*3): reject(lambda:make(pts))
 assert make([p]*3).points[0].title==" t "
assert count==72
root=pathlib.Path("/root/projects/deep-research"); f=root/"_reversa_forward/001-modulo-briefing"
rows=[json.loads(x) for x in (f/"progress.jsonl").read_text().splitlines()]
assert [(r.get("task",r.get("action")),r["status"]) for r in rows]==[("T001","done"),("T002","done"),("T003","done"),("T008","done"),("T001","corrected"),("T002","corrected"),("T014","done"),("T015","done")]
assert all(r["original_event_time"]=="unknown" for r in rows[4:6])
assert all(r["ts"]=="2026-10-10T00:00:00Z" for r in rows[:2])
paths=[p for r in rows for p in r["files"]]; assert len(paths)==19 and all((root/p).is_file() for p in paths)
ids=re.findall(r"^\| (?:\[//\] )?(T\d{3}) \|.*\| (\[X\]|\[ \]) \|$",(f/"actions.md").read_text(),re.M)
assert len(ids)==15 and len({i for i,_ in ids})==15
assert {i for i,st in ids if st=="[X]"}=={"T001","T002","T003","T008","T014","T015"}
print("PASS: 72 rejeicoes; 3 preservacoes whitespace; 8 registros JSONL; 19 referencias existentes; 15 IDs unicos; 6 [X]")
'
```

Saída literal:

```text
PASS: 72 rejeicoes; 3 preservacoes whitespace; 8 registros JSONL; 19 referencias existentes; 15 IDs unicos; 6 [X]
```

Probe adicional de status/contagens/serialização também terminou exit 0, `ALL PYDANTIC CONTRACT PROBES PASSED`; não necessário à reprodução, pois mesmos checks estão nos seis testes reais acima. Uma primeira versão do probe complementar imprimiu texto fixo incorreto de 20 referências seguido de contagem calculada 19; erro no rótulo do probe, não no produto. Comando acima corrigiu rótulo, afirmou 19 e foi realmente reexecutado. Não usar saída inicial como contagem válida.

## Fora do gate e dúvidas mantidas

Não inspecionados: prompt_loader/prompt, SERP, service/router, storage/auth/migrations, legado, concorrência real, retry/reuso, logs/segredos, HTTP servido, geração sem conclusões, persistência/preservação transacional e execução de pesquisa. Nenhuma afirmação de status HTTP real deriva de ValidationError ou comentários em schemas.py.

Pergunta aberta preservada: recuperação manual/regeneração após failed terminal, conforme SDD `briefing.md:100` e inspeção anterior `inspecao-t001-t002.md:58`. Não exigir transição failed adicional sem decisão. Representação final de erro seguro/metadados e rotas ainda exige gate de T011; `interfaces/briefing-http.md:14,18` explicita proposta. T007/T011 deverão validar conteúdo na operação de aprovação e persistência; schema de resposta não substitui isso.

Cluster anterior de contratos permissivos eliminado no recorte. Nenhum novo finding confirmado, nenhuma tarefa corretiva de código proposta. Contagem final: **3/3 findings anteriores resolvidos; 0 findings novos/abertos; 1 observação LOW histórica; gate PASS restrito a T014/T015.**
