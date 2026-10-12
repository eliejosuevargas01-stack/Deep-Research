# Recheck documental T034 — F-EVIDENCE-01/02

## Veredito: PASS (somente documental)

Duas observações anteriores corrigidas na entrega salva. Zero pendências documentais no recorte, zero novos achados, zero defeitos de produto confirmados, zero bugs promovidos. T034 permanece `[ ]` em `actions.md:89`; este PASS autoriza handoff para QA documental, não fechamento da ação nem aprovação da API.

O erro upstream Nvidia registrado em `progress.jsonl:82` não anulou a entrega física: SHA-256 de `audit/t034-execution.md` confere com dispatch e L82/L83: `7a0c841fb7daa8e0ed30e0673a49ca5ab9f17e8a0d93a4dc107e0757862c100c`. Não repetida implementação. Adendo do implementador é reparo factual, não autoaprovação independente.

## Preflight, mapa e readset

Root `/root/projects/deep-research`; branch `main...origin/main`; worktree já suja, incluindo documentos untracked. Preflight: AGENTS dos ancestrais e dos diretórios pertinentes; somente AGENTS da raiz existe. `.reversa/state.json`, `active-requirements.json`, `config.toml`, `reversa-config.json` e `execution-policy.md` lidos. Feature ativa `001-modulo-briefing`, estágio `coding`; state global histórico não substitui estado da feature. Config permite caminhos, mas dispatch restringe escrita a este relatório novo.

Mapa do recorte:

- Aceitação documental: F-EVIDENCE-01/02 em `_reversa_bugs/modulo-briefing/inspections/t034-traceability/report.md:55–86`, preservado sem edição.
- Entrega: `_reversa_forward/001-modulo-briefing/audit/t034-execution.md:1–80`, especialmente :15,51,76–80.
- Contexto mínimo: `legacy-impact.md:166–193`, `regression-watch.md:179–198`, actions linha T034 e T030/T031; checkpoints `progress.jsonl:82–83`. L72/L76 consultadas somente para proveniência de contagens; comandos ali gravados não executados.
- Fontes de veredito: relatórios concretos `t030-error-matrix/report.md:3–7,27`, `t030-error-matrix-qa/report.md:4,52–56`, `t031-session-factory/report.md:3–5`, `t031-session-factory-qa/report.md:4–11,72`, todos sob `_reversa_bugs/modulo-briefing/inspections/`. Execuções T030/T031 lidas para assinatura e proveniência, sem replay.
- Código/testes: `app/briefing/llm_binding.py` e `tests/test_briefing_llm_binding.py` apenas existência e SHA nesta passagem; sem importar produto, sem executar testes. Assinatura e contagens citadas vêm das fontes anteriores, não de nova execução.
- Dados: metadados documentais, manifesto SHA, tabelas Markdown e caminhos locais. Nenhuma DB, cache de produto, fila ou serviço externo acessado.
- Varredura estrutural de tabelas e IDs W lê texto completo de legacy/regression sem auditar semântica histórica fora dos adendos. Bytes de outros arquivos do manifesto usados exclusivamente para SHA, não inspeção de conteúdo.

## Disposições estáveis

| Finding | Lente | Confiança | Severidade anterior | Disposição nesta passagem | promoted_to |
|---|---|---|---|---|---|
| F-EVIDENCE-01 | Evidência / contratos documentais | alta | low | Corrigida, recheck PASS | null |
| F-EVIDENCE-02 | Evidência / alcance de checks | alta | low | Corrigida, recheck PASS | null |

### F-EVIDENCE-01 — promoção versus aprovação

`audit/t034-execution.md:15` agora registra inspeção T030 **CONDITIONAL**, O-CONTRACT-01 **não promovida a bug**, QA **PASS_LOCAL**, com dois paths reais distintos. :78 explicita produto ordinário PASS. Isso concorda com inspeção T030:3–7,27 e QA T030:4,52–56. Inspeção T030 não virou overall PASS_LOCAL; observação não promovida não equivale a aprovação. Inspeção T031 permanece PASS; QA T031 permanece PASS_LOCAL.

Descrição de :78 é semanticamente equivalente ao reparo, não citação literal completa da linha :15. Ausência do parêntese “produto ordinário PASS” na linha :15 não cria novo achado: produto PASS está expresso no adendo e fonte. Não inferida reachability global de Timeout SDK com auth status, nem reaberto O-CONTRACT-01/T030.

### F-EVIDENCE-02 — tracked versus untracked

`audit/t034-execution.md:51` qualifica expressamente **apenas arquivos tracked**. :80 documenta no-index do próprio relatório: exit 3, dois trailing-whitespace intencionais em :3–4, usados como hard breaks Markdown. Resultados reproduzidos nesta auditoria. Não exigida remoção desses hard breaks; não alegada limpeza de whitespace dos untracked.

Linha :42 e tabela de checks lidas em conjunto com qualificação :51 e adendo :80, não como garantia global independente. Aceitação documental dos dois hard breaks não significa que Git reportou zero whitespace. Nenhuma falha runtime demonstrada.

Contagens: 2 observações anteriores rechecadas, 2 corrigidas, 0 abertas; novos achados 0; defeitos confirmados 0; bugs promovidos 0. Severidades originais: low 2; medium/high/critical 0. Confiança: alta 2, média/baixa 0. Cluster anterior limitado à precisão dos metadados de evidência, sem cluster de software confirmado.

## Lentes aplicadas e limites específicos

| Lente | Evidência neste recheck | Resultado / limite |
|---|---|---|
| Conformidade documental | Critérios F-EVIDENCE-01/02, texto :15/51/78/80 e fontes de veredito | PASS no recorte |
| Fluxo de dados documental | Transcrição de vereditos, proveniência L72/L76, manifesto L83 | PASS; nenhuma transformação de dados de produto exercitada |
| Contratos e integrações documentais | Separação inspection/product/QA/promotion e binding-ready versus API-ready | PASS; contratos HTTP/provider não reabertos |
| Erros e edge cases documentais | Tracked exit 0 versus untracked exit 3; overload com entrega salva | PASS; erro upstream não usado como evidência de produto |
| Cobertura da evidência | Tabelas, paths, links explícitos zero, controle negativo estrutural | PASS; nenhum teste de produto executado |
| Concorrência e consistência documental | SHA congelado, manifesto L83 com exclusões nomeadas e T034 aberta | PASS no snapshot; nenhuma concorrência runtime medida |

Lentes condicionais de segurança runtime, desempenho, migrations/config de produto e observabilidade runtime não ativadas. Nenhum diagnóstico global novo, registro de bugs, geração de views ou atualização de skills autorizado.

## Ledger de proveniência preservada

- T030 inspeção: CONDITIONAL; produto ordinário PASS; 21 métodos e 98 hashes segundo próprio relatório. QA T030: PASS_LOCAL; 21 métodos e 99 hashes. Não transferidos totais de fases posteriores.
- 137 testes briefing da fase T030 têm origem em `progress.jsonl:72`, campo `evidence.parent_replay`; não atribuídos como execução própria da QA T030.
- T031 inspeção: PASS; 24 métodos, 140 briefing e 101 hashes segundo próprio relatório. QA T031: PASS_LOCAL; 24 métodos, 140 briefing em :72 e 102 hashes. `progress.jsonl:76` campo `evidence.parent_replay` também registra 24/24 e 140. Tudo evidência histórica citada, não execução desta auditoria.
- Adendos conservam factory session_factory, settings encerrados antes LLM, early abort, zero finalização caller-owned e flush first-use revertido conforme fontes T031. Binding pronto não prova router API pronto; T025/T026/T012/T013 não fechadas por este relatório.

## Checks próprios e stdout

Todos comandos executados no root, sem runner, import de produto ou rede. Comandos de Git somente leitura. Preflight `pwd`, `git status --short --branch`, `git diff --stat`, `git diff --name-status`, `git ls-files --others --exclude-standard`: execução do lote exit 0; root correto e alterações pré-existentes inventariadas, sem restaurar nada.

### Estrutura e referências — Python stdlib, exit 0

Contagem de pipes por linha física versus primeira linha de cada bloco de tabela:

```text
TABLE legacy-impact.md 9 tables 46 rows errors [] SCOPED_LINKS 0
TABLE regression-watch.md 14 tables 58 rows errors [] SCOPED_LINKS 0
TABLE audit/t034-execution.md 1 table 12 rows errors [] SCOPED_LINKS 0
WATCH 30 distintos W001–W030
DELIMITER_NEGATIVE_CONTROL PASS; malformed row rejected
```

Controle negativo em memória acrescentou pipe à terceira linha de tabela sintética; checker retornou `[3]`, enquanto tabela válida retornou `[]`. Sem escrita de fixture. Contagem W sobre prefixo anterior ao adendo T030/T031, IDs completos preservados; hashes legacy/regression iguais a L83 sustentam preservação desta passagem, não reconstrução de baseline anterior à implementação T034.

**0 links Markdown explícitos** nos adendos/execução. Backticks são paths/símbolos/comandos, não hyperlinks explícitos. Scoped path check encontrou **34 ocorrências concretas**: legacy 6, regression 3, execution 25; todas existem. Resolver usa root/feature, e abreviação `llm_binding.py` usa path plenamente qualificado em execution:11. Paths roadmap/interfaces/delta citados nos próximos passos tiveram somente existência verificada; nenhuma revisão de contratos fora do recorte. Não alegada resolução de anchors Markdown nem cobertura factual do histórico completo.

### Git — comandos e saídas literais

`git diff --check`: **exit 0**, stdout vazio, stderr vazio. Escopo: tracked apenas.

`git diff --no-index --check /dev/null _reversa_forward/001-modulo-briefing/audit/t034-execution.md`: **exit 3**, stderr vazio:

```text
_reversa_forward/001-modulo-briefing/audit/t034-execution.md:3: trailing whitespace.
+**Data:** 2026-10-11  
_reversa_forward/001-modulo-briefing/audit/t034-execution.md:4: trailing whitespace.
+**Feature:** _reversa_forward/001-modulo-briefing  
```

Os dois espaços finais nas linhas com `+` representam bytes observados; hard breaks intencionais aceitos documentalmente. Nenhuma declaração de “untracked sem whitespace”.

### SHA — manifesto L83, Python stdlib, exit 0

`progress.jsonl:83` campo `pre_dispatch_sha256`: **108 entradas**, **105 conferidas**, **3 excluídas**, **0 mismatches/missing**. Ignoradas somente:

1. `tests/test_briefing_schemas.py`
2. `_reversa_forward/001-modulo-briefing/audit/t035-execution.md`
3. `_reversa_forward/001-modulo-briefing/audit/t025-t026-planning-delta.md`

Exclusões são repairs siblings ativos; seus bytes não foram lidos. Demais 105 entradas: existência, formato 64 hex e SHA-256 dos bytes comparados. Arquivos fora do readset semântico, inclusive roadmap/interfaces, apenas hash para prova de congelamento, não conteúdo interpretado. Portanto não declarar 108/108 verificados nem revisar sibling a partir dos hashes.

```text
MANIFEST 108 checked 105 excluded 3 mismatch []
SHA audit/t034-execution.md 7a0c841fb7daa8e0ed30e0673a49ca5ab9f17e8a0d93a4dc107e0757862c100c
SHA inspection anterior 680ccb105f22cdf2ebd099fc5fd7ab00ccd7be0d6acf199d400c41af129b4ee3
SHA progress.jsonl 2339b99d4ffe323189ee6df38511e36bb8da1b7a1f561c70f2972f160a242cb9
```

Último hash é snapshot observado de progress, não entrada do próprio manifesto nem licença para alterá-lo.

### Receita reproduzível dos checks centrais

Executar como `python3 -B` com stdin abaixo no root. Não executar comandos históricos de QA contidos nas fontes.

```python
from pathlib import Path
import hashlib, json, re, subprocess
b = Path('_reversa_forward/001-modulo-briefing')
row = json.loads((b / 'progress.jsonl').read_text().splitlines()[82])
m = row['pre_dispatch_sha256']
exclude = {'tests/test_briefing_schemas.py', str(b / 'audit/t035-execution.md'),
           str(b / 'audit/t025-t026-planning-delta.md')}
assert len(m) == 108 and len(exclude & m.keys()) == 3
bad = []
for name, expected in m.items():
    if name in exclude:
        continue
    p = Path(name)
    if not re.fullmatch('[0-9a-f]{64}', expected) or not p.is_file():
        bad.append(name)
    elif hashlib.sha256(p.read_bytes()).hexdigest() != expected:
        bad.append(name)
print('MANIFEST', len(m), 'checked', len(m)-3, 'mismatch', bad)
assert not bad
for name, start in [('legacy-impact.md', 166), ('regression-watch.md', 179),
                    ('audit/t034-execution.md', 1)]:
    lines = (b / name).read_text().splitlines()
    width = None
    tables = rows = 0
    for line in lines:
        if line.startswith('|'):
            if width is None:
                tables += 1
                width = line.count('|')
            rows += 1
            assert line.count('|') == width
        else:
            width = None
    scoped = '\n'.join(lines[start-1:])
    print('TABLE', name, tables, rows, 'SCOPED_LINKS',
          len(re.findall(r'\[[^\]]*\]\([^)]*\)', scoped)))
watch = sorted(set(re.findall(r'\bW\d{3}\b',
    (b / 'regression-watch.md').read_text().split('## Adendo T030/T031')[0])))
assert watch == [f'W{i:03}' for i in range(1, 31)]
print('WATCH', len(watch))
for command in [['git', 'diff', '--check'],
                ['git', 'diff', '--no-index', '--check', '/dev/null',
                 str(b / 'audit/t034-execution.md')]]:
    result = subprocess.run(command, text=True, capture_output=True)
    print('COMMAND', command, 'EXIT', result.returncode,
          'STDOUT', repr(result.stdout), 'STDERR', repr(result.stderr))
```

Receita vinculada ao checkpoint **L83**, não à última linha móvel. Alterações futuras legítimas podem invalidar snapshot sem demonstrar defeito de produto.

## Verificação do artefato novo

Receita Python extraída do bloco salvo e executada sem alteração: **exit 0**; stdout reproduziu manifesto 108/105, zero mismatches, tabelas 9/46, 14/58, 1/12, links explícitos zero, 30 watches, tracked exit 0 e execution no-index exit 3. Relatório novo: 2 tabelas, 12 linhas físicas de tabela, delimitadores consistentes.

`git diff --no-index --check /dev/null _reversa_bugs/modulo-briefing/inspections/t034-traceability-recheck/report.md`: **exit 3**, stderr vazio, trailing whitespace somente :92 e :94. São os dois espaços preservados na transcrição literal de stdout do documento auditado, não nova afirmação de limpeza; aceitos como fidelidade da evidência. Hashes do relatório anterior e execution reconferidos após escrita, ambos iguais aos registrados acima.

## Ownership e handoff

Única escrita: `_reversa_bugs/modulo-briefing/inspections/t034-traceability-recheck/report.md`. Inspection anterior imutável. Nenhuma alteração de actions, progress, specs, código, testes, state, skills, registry ou views; nenhum test runner/runtime, `.env`, DB, rede, install, commit/push/deploy, todo ou subdelegação.

Próximo gate: QA documental independente deste reparo aprovado, com mesmo recorte e sem testes de produto. Parent decide fechamento T034 somente após QA aplicável. PASS desta passagem não remove gates siblings nem aprova T025/T026 ou integração real.
