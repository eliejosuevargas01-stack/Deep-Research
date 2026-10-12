# QA independente Sprint 4 — T004/T005, gate local T007

## Veredito: PASS local

0 defeitos observados. 3 métodos unittest novos; suíte briefing passou de 46 para 49 métodos. Subtests não contados como métodos. Produção não alterada. Testes de comportamento existente passaram na primeira execução; esta QA não alega RED novo nem reexecuta evidência histórica RED/GREEN do implementador.

Arquivo novo: `/root/projects/deep-research/tests/test_briefing_lifecycle_qa.py`.
Relatório novo: `/root/projects/deep-research/_reversa_forward/001-modulo-briefing/audit/qa-sprint4.md`.

## Preflight e fontes

Branch `main`, working tree já sujo, inclusive docs excluídas, arquivos modificados e briefing/testes não rastreados. Nenhuma restauração. AGENTS.md e `.reversa/state.json` históricos não provam conclusão. `.reversa/active-requirements.json:3–7` aponta feature 001-modulo-briefing, estágio coding. `.reversa/reversa-config.json:3–11` permite edição de tests; autorização de QA separado em execution-policy.md:11. Âncora greenfield existente: `_reversa_sdd/prd.md` e `_reversa_sdd/sdd/briefing.md`, ambos planejados. Fonte de produto: requirements.md:32–44,51–60; contrato local efetivo: roadmap.md:64–81 e data-delta.md:35–76. Não usadas regras antigas de pesquisa como requisitos.

O-coverage-01 preservada no relatório anterior, sem edição/fechamento daquele documento. Casos complementares agora duráveis: edição/aprovação em 3/4/5/6/7, snapshots completos, cadeia de versões exata, timestamp/error inválidos e fronteiras/cópias em ambas operações. Não copiado probe de 278 assertions. Cobertura existente mantida para matriz de estados, contagens inválidas, campos inválidos e imutabilidade. Nenhuma implementação duplicada, mock, fallback, skip ou expectedFailure nos testes novos.

## Matriz critério → símbolo → execução real

Prefixos: D=`app/briefing/domain.py`; V=`tests/test_briefing_validation.py`; L=`tests/test_briefing_lifecycle.py`; H=`tests/test_briefing_domain.py`; Q=`tests/test_briefing_lifecycle_qa.py`. Todas linhas relativas à raiz `/root/projects/deep-research`.

| Critério | Símbolo produção | Teste existente/novo executado | Resultado |
|---|---|---|---|
| RF-01 tema 3–300, strip, tipos inválidos, UUID4 | D:31–37 validate_theme; D:94–104 new_briefing | V:13–61; Q:21–29 | PASS local |
| RF-03 geração 3–7; RF-05 edição/reordenação; RF-06 aprovação 3–7 | D:127–131 complete_briefing; D:142–155 edit_briefing/approve_briefing | L:53–80; Q:21–60, matriz edição/aprovação 3/4/5/6/7 | PASS local |
| Título/descrição strings não vazias, preservação de espaços | D:40–53 validate_points; D:107–119 cópia | L:82–113; H:27–58; Q:43–53,109–122 | PASS |
| Atomicidade de recusas e mensagens fixas, datetime fornecido | D:134–139 fail_briefing; D:149–155 approve_briefing | Q:62–85, InvalidContent específico e asdict após cada recusa | PASS |
| Sequence não textual, Mapping não-dict/BriefingPoint, cópia sem alias mutável | D:107–119; D:127–146 | L:115–153; Q:87–122, ambas complete/edit, bytearray/iter/set e itens inválidos | PASS |
| IDs estáveis, +1 por alteração; fail versão 2 sem pontos; read sem incremento | D:94–167 operações | L:193–218; Q:21–60, cadeia [1,2,3,4,4,5] e snapshots completos | PASS |
| generating/draft/failed/approved; bloqueio aprovado; failed terminal | D:56–74 helpers; D:122–167 operações | H:61–86; L:155–191 | PASS |
| RF-09 reopen limpa instante, sem pesquisa/teto de edições | D:158–162 reopen_briefing | L:33–51,193–203; H:88–94; Q:41–53 | PASS local |
| Dataclasses frozen, input/snapshot isolados | D:77–91 dataclasses | L:143–153,205–218; Q:54–60,109–122 | PASS |
| Sem infraestrutura/I-O de domínio; UUID4 stdlib, timestamp caller | D:1–167 leitura integral, imports D:3–8 | Testes reais Q/V/L e leitura estática; sem probe adicional necessário | PASS estático/local |

## Comandos e saídas reais

Todos comandos shell com workdir absoluto `/root/projects/deep-research`.

| Comando completo | Saída observada | Exit |
|---|---|---|
| `git status --short; git branch --show-current; sha256sum app/briefing/domain.py` | dirty pré-existente; main; hash abaixo | 0 |
| `python3 -B -m unittest discover -s tests -p 'test_briefing_*.py' -v` antes | Ran 46 tests in 0.086s; OK | 0 |
| `python3 -B -m unittest tests.test_briefing_lifecycle_qa tests.test_briefing_validation tests.test_briefing_lifecycle -v` | Ran 19 tests in 0.011s; OK | 0 |
| `python3 -B -m unittest tests.test_briefing_domain tests.test_briefing_schemas tests.test_briefing_prompt_loader tests.test_briefing_serp_client -v` | Ran 30 tests in 0.080s; OK | 0 |
| `python3 -B -m unittest discover -s tests -p 'test_briefing_*.py' -v` depois | Ran 49 tests in 0.080s; OK | 0 |
| `python3 -B -m unittest tests.test_briefing_lifecycle_qa -v` | Ran 3 tests in 0.003s; OK | 0 |
| `PYTHONPYCACHEPREFIX=/root/.hermes/profiles/orchestrator/cache/scratch/briefing-qa-pycache python3 -m py_compile tests/test_briefing_lifecycle_qa.py app/briefing/domain.py` | sem saída | 0 |
| `git diff --check` | sem saída | 0 |
| `sha256sum app/briefing/domain.py` depois | hash igual antes/depois | 0 |

Hash domínio antes/depois: `f058679d7a1a923c337a4dc067c01cbc3d0f50d0ca126220de286ec89d557b4a`.

Progress validado sem escrita, comando completo, exit 0:

```sh
python3 -B -c 'import json; from pathlib import Path; b=Path("_reversa_forward/001-modulo-briefing/progress.jsonl").read_bytes(); lines=b.splitlines(); objects=[json.loads(line) for line in lines]; assert len(lines)==len(objects)==20; assert all(isinstance(x,dict) for x in objects); assert b.endswith(bytes([10])); print("PASS physical_lines=20 objects=20 trailing_newline=True")'
```

Saída: `PASS physical_lines=20 objects=20 trailing_newline=True`.

Preservação adicional: hash de todos 174 arquivos existentes enumerados via Git antes da escrita comparado em Python com execução depois dos testes; 174/174 iguais, nenhum removido/alterado, único novo naquele momento era Q. Inclui seis testes congelados, actions/progress/state/config e relatórios anteriores. Comando de captura executado duas vezes, exit 0 em ambas:

```sh
python3 -B -c 'import hashlib,json,subprocess; from pathlib import Path; paths=set(subprocess.check_output(["git","ls-files","-co","--exclude-standard"]).decode().splitlines()); print(json.dumps({p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in sorted(paths) if Path(p).is_file()}))'
```

Comparação real no kernel Python: `sum(after.get(p)==h for p,h in before.items())` retornou 174; lista de diferenças vazia. Relatório foi criado após essa comparação. `git diff --check` cobre rastreados; arquivo novo também revisado/compilado/executado, não tratado como coberto por Git sozinho.

## Falhas observadas e limites

Nenhum teste, compilação ou gate shell acima falhou. Falhas de tooling fora do produto: duas chamadas iniciais de skill com nome incorreto retornaram not found; nomes corretos reversa-coding/test-driven-development carregados depois. Probe preliminar no interpretador isolado execute_code retornou ModuleNotFoundError: app, pois não estava no workdir do projeto; não forneceu evidência e não foi usado como aprovação. Duas leituras Python de resposta deduplicada retornaram KeyError: content; leitura direta resolveu. LSP apontou tipos propositalmente inválidos nos testes negativos; execução runtime validou InvalidContent específico, sem afrouxar expectativa. Nenhuma falha de domínio inferida dessas falhas de ferramenta.

Suite inclui fixture I/O de prompt loader e httpx.MockTransport nos testes originais de SERP; nenhum endpoint real chamado. Q usa só stdlib/dados em memória e funções reais de domínio. Sem rede, DB, .env, credenciais, instalação, deploy, commit/push ou frontend.

Não verificados: serviço T010 e ordem integrada de rejeição pré-SERP/LLM; storage/HTTP/router/auth T011; histórico consultável durável, migrações, concorrência/idempotência/transações; segurança/sanitização do futuro caller; SaaS/LLM real; conteúdo semanticamente não conclusivo; pipeline legado. Não impostas timezone obrigatória, sanitização universal de error, validação universal de construtor, objetos hostis ou object.__setattr__.

T004/T005 permanecem `[ ]`: T004 depende spy integrado T010; T005 depende história durável T011. Nenhuma ação/feature fechada, estado/plano/progress alterado ou relatório anterior editado. PASS restrito ao domínio puro T007 e gates locais de QA.
