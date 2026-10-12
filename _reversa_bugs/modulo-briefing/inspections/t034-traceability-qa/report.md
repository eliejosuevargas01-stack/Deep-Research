# QA documental T034 — rastreabilidade pós-recheck

## Veredito: PASS_LOCAL_DOCUMENTAL

Entrega documental T034 conforme no recorte: zero falhas QA, zero novos achados, zero defeitos de produto, zero bugs promovidos. F-EVIDENCE-01/02 corrigidas conforme recheck. T034 permanece `[ ]` em `actions.md:89`; parent decide fechamento. Este PASS não aprova T035, HTTP, runtime/provider real nem release.

## Preflight e recorte

- Root `/root/projects/deep-research`, branch `main`; worktree já suja e documentos da feature untracked. Nada restaurado.
- AGENTS: somente root `AGENTS.md` existe; ancestrais `/AGENTS.md`, `/root/AGENTS.md`, `/root/projects/AGENTS.md` e diretórios pertinentes `.reversa`, forward, bugs, inspections, SDD ausentes.
- Estado: `.reversa/state.json` histórico `forward-complete`; `.reversa/active-requirements.json` define feature `_reversa_forward/001-modulo-briefing`, estágio `coding`. `config.toml`, `reversa-config.json` e `execution-policy.md` da feature lidos. Âncoras greenfield `_reversa_sdd/prd.md` e `_reversa_sdd/sdd/briefing.md` existem.
- Readset: recheck `_reversa_bugs/modulo-briefing/inspections/t034-traceability-recheck/report.md`; inspection anterior `_reversa_bugs/modulo-briefing/inspections/t034-traceability/report.md`; `legacy-impact.md:166–193`; `regression-watch.md:179–198`; `audit/t034-execution.md:1–80`; `actions.md:80–92`; `progress.jsonl` L72, L76, L83, L85, L86; relatórios T030/T031 citados.
- Não lido: report mutável T035 `_reversa_bugs/modulo-briefing/inspections/t035-d4-schemas/report.md`, código/diff T035. Bytes de arquivos do manifesto usados só para SHA.

## Mapa aceitação → evidência → resultado

| Aceitação | Evidência própria | Resultado |
|---|---|---|
| Factory, close antes LLM, early abort, flush revertido | `legacy-impact.md:174–179`, `regression-watch.md:185–190`; fonte QA T031 `t031-session-factory-qa/report.md:4–11` | PASS; evidência anterior citada, não execução desta QA |
| Binding 24 e suites por fase | `progress.jsonl:72` e `:76`, `evidence.parent_replay` | PASS; 137 fase T030, 140 fase T031; 161 L86 não atribuído a T034 |
| T030/T031 vereditos separados | `t034-execution.md:15–16`; inspection T030:3–7,27; QA T030:4,52–56; inspection T031:3–5; QA T031:4 | PASS; T030 CONDITIONAL, produto ordinário PASS, O-CONTRACT-01 null; QA PASS_LOCAL |
| F-EVIDENCE-01/02 | `t034-execution.md:15,51,76–80`; recheck PASS | PASS; tracked exit 0 qualificado; no-index exit 3 aceito por dois hard breaks |
| Estado das ações | `actions.md` resolvido por ID | PASS; T030/T031 `[X]`, T034/T025 `[ ]` |
| T025 e API | adendos legacy/regression | PASS; desbloqueada, não entregue; binding pronto não prova API pronta |
| W001–W030 | prefixo `regression-watch.md` antes do adendo | PASS; 30 IDs distintos; histórico preservado |
| Paths, links, tabelas e JSONL | checker scratch próprio | PASS; 34 paths existem, 0 links, delimitadores consistentes, JSONL estrito |

## Comandos e saídas literais

Todos executados no root, sem runner de produto, import de produto, DB, rede, `.env`, install ou commit.

### Receita original do recheck

Embed Python de recheck :122–169 igual a `/root/.hermes/profiles/orchestrator/cache/scratch/t035-parent-replays/t034_recipe_original.py`: comparação exata `ORIGINAL_EMBED_MATCH True`; SHA `5d11f299abf4d73fa56e5343c75cc7475a8a48831dfc0fdfff30fe0a6ac5fbf2`.

Comando: `python3 -B /root/.hermes/profiles/orchestrator/cache/scratch/t035-parent-replays/t034_recipe_original.py`. **Exit 1**.

```text
MANIFEST 108 checked 105 mismatch ['_reversa_forward/001-modulo-briefing/audit/cross-check.md']
AssertionError
```

Classificação: baseline stale após reauditoria legítima A007–A010 registrada em `progress.jsonl:85`; não defeito T034. Receita original não foi silenciosamente corrigida.

### Receita rebaseada do parent

Comando: `python3 -B /root/.hermes/profiles/orchestrator/cache/scratch/t035-parent-replays/t034_recipe_rebased.py`. **Exit 0**. Prova distinta: acrescenta exclusão explícita de `cross-check.md`, total 4 exclusões.

```text
MANIFEST 108 checked 104 mismatch []
TABLE legacy-impact.md 9 46 SCOPED_LINKS 0
TABLE regression-watch.md 14 58 SCOPED_LINKS 0
TABLE audit/t034-execution.md 1 12 SCOPED_LINKS 0
WATCH 30
COMMAND ['git', 'diff', '--check'] EXIT 0 STDOUT '' STDERR ''
COMMAND ['git', 'diff', '--no-index', '--check', '/dev/null', '_reversa_forward/001-modulo-briefing/audit/t034-execution.md'] EXIT 3 STDOUT '_reversa_forward/001-modulo-briefing/audit/t034-execution.md:3: trailing whitespace.\n+**Data:** 2026-10-11  \n_reversa_forward/001-modulo-briefing/audit/t034-execution.md:4: trailing whitespace.\n+**Feature:** _reversa_forward/001-modulo-briefing  \n' STDERR ''
```

Exit 3 no-index é esperado: dois hard breaks Markdown :3–4 aceitos documentalmente; não prova untracked limpo.

### Checker QA independente

Arquivo scratch `/root/.hermes/profiles/orchestrator/cache/scratch/t034-documental-qa/check.py`, SHA `2578575531980ab1dac5116d73902e8072d9aef10c9ed14b7654d914980e32fa`. Comando: `python3 -B /root/.hermes/profiles/orchestrator/cache/scratch/t034-documental-qa/check.py`. **Exit 0**.

```text
JSONL strict_rows 86 final_newline True
L86 MANIFEST 108 checked 108 excluded 0 mismatch []
SHA _reversa_bugs/modulo-briefing/inspections/t034-traceability/report.md 680ccb105f22cdf2ebd099fc5fd7ab00ccd7be0d6acf199d400c41af129b4ee3
SHA _reversa_bugs/modulo-briefing/inspections/t034-traceability-recheck/report.md dbb2fe6c3d173cb2b1c4f88e51b242eac96245d5eb04ccb3c4d58e8c2db09ff7
TABLE legacy-impact.md 9 46 SCOPED_LINKS 0 PATH_OCCURRENCES 6
IDS legacy-impact.md ['D3', 'F-CONSISTENCY-01', 'F-ERROR-01', 'T012', 'T013', 'T025', 'T026', 'T028', 'T029', 'T030', 'T031']
TABLE regression-watch.md 14 58 SCOPED_LINKS 0 PATH_OCCURRENCES 3
IDS regression-watch.md ['D3', 'F-CONSISTENCY-01', 'F-ERROR-01', 'T012', 'T013', 'T025', 'T026', 'T028', 'T029', 'T030', 'T031']
TABLE audit/t034-execution.md 1 12 SCOPED_LINKS 0 PATH_OCCURRENCES 25
IDS audit/t034-execution.md ['D3', 'D5', 'F-CONSISTENCY-01', 'F-ERROR-01', 'F-EVIDENCE-01', 'F-EVIDENCE-02', 'O-CONTRACT-01', 'T012', 'T013', 'T025', 'T026', 'T030', 'T031', 'T034']
PATHS total 34 unique 18
WATCH 30 W001-W030
ACTION T030 LINE 85 STATE [X]
ACTION T031 LINE 86 STATE [X]
ACTION T034 LINE 89 STATE [ ]
ACTION T025 LINE 91 STATE [ ]
PROVENANCE 72 evidence.parent_replay all QA replay probes exit0; 21/21 binding tests OK, 137 briefing tests OK
PROVENANCE 76 evidence.parent_replay all 4 QA replay probes exit0; 24/24 binding tests OK, 140 briefing tests OK
NEGATIVE invalidpipe DETECTED AssertionError(('table pipes', [3]))
NEGATIVE rootmissingpath DETECTED AssertionError(('missing path', '_reversa_forward/001-modulo-briefing/nonexistent-t034-qa.md'))
NEGATIVE syntheticunrecognizedid DETECTED AssertionError(('unknown ID', ['T999']))
NEGATIVE_EXIT invalidpipe 1 AssertionError: ('table pipes', [3])
NEGATIVE_EXIT rootmissingpath 1 AssertionError: ('missing path', '_reversa_forward/001-modulo-briefing/nonexistent-t034-qa.md')
NEGATIVE_EXIT syntheticunrecognizedid 1 AssertionError: ('unknown ID', ['T999'])
QA_DOCUMENTAL_CHECKS PASS
```

Checker vincula L86 por índice, `ts` `2026-10-11T16:15:55.811258+00:00` e status `s8_t035_inspection_dispatched`, não por última linha. Manifesto L86 congela 108 paths atuais; L83 difere somente em `cross-check.md`, `t035-execution.md`, `t025-t026-planning-delta.md` e `tests/test_briefing_schemas.py`. JSONL estrito rejeita chave duplicada e exige newline final.

Força do checker: três fixtures sintéticas em memória e três subprocessos sem arquivo de fixture retornaram exit 1. Nenhum path inexistente, linha inválida ou ID sintético escrito no repositório. Checker valida invariantes nomeadas, não semântica global de todo histórico.

### Verificação do próprio relatório

Checker reexecutado após escrita: exit 0, `L86 MANIFEST 108 checked 108 excluded 0 mismatch []`, hashes inspection anterior e recheck inalterados. Tabela deste relatório: 1 tabela, 10 linhas físicas, delimitadores consistentes. `git diff --no-index --check /dev/null` neste relatório: **exit 1** (diff presente, sem aviso de whitespace; sem stdout). Hash do relatório não incluído aqui para evitar autorreferência.

## Contagens

- Checks QA: 8 aceitação PASS, 0 FAIL.
- Recheck: 2 observações rechecadas, 2 corrigidas, 0 abertas.
- Novos achados 0; defeitos confirmados 0; bugs promovidos 0.
- Manifestos: L83 rebaseado 104/108 checked; L86 próprio 108/108 checked, 0 mismatches.
- Tabelas: legacy 9/46, regression 14/58, execution 1/12.
- Paths: 34 ocorrências, 18 únicos, todos existem; links Markdown explícitos 0.

## Limites e ownership

Única escrita de projeto: `_reversa_bugs/modulo-briefing/inspections/t034-traceability-qa/report.md`. Scratch fora do repo contém somente checker e stdout/stderr/exit. Nenhuma alteração de código, testes, sources, actions, progress, docs, state, skills, registry ou views. Sem runner/teste de produto, DB, rede, `.env`, import de main/SDK, install, deploy, commit, push, todo ou subdelegação.

Evidências de factory, binding, suites, T030/T031 e QA proofs são históricas citadas. PASS_LOCAL_DOCUMENTAL não aprova T035, contratos HTTP, runtime, provider real nem release; T034 não fechada por este relatório.
