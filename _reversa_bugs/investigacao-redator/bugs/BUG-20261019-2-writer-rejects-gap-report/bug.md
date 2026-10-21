---
schema_version: 1
id: BUG-20261019-2
display_number: 23
context: investigacao-redator
title: "Writer rejeita incondicionalmente relatório sem evidência/link, mesmo quando é relatório de lacuna válido"
status: closed
phase: verified
severity: medium
priority: P2
security_suspected: false
visibility: internal
created: "2026-10-19T20:10:00-03:00"
updated: "2026-10-21T08:45:00-03:00"
area:
  - writer-stage
  - evidence-gating
module:
  - pipeline-writer
feature:
  - deep-research-execution
  - report-rendering
origin:
  type: inspection
  external_ref: "_reversa_bugs/investigacao-redator/intake/diagnostico-fdd70d5c.md"
reported_by: reversa-diagnostic
reported_at: "2026-10-19T20:10:00-03:00"
environment:
  app: deep-research
  branch: main
  commit: "582ed04abd3f03de8d38f8d162d1d945534e6b54"
traceability:
  specs:
    - "app/CRITERIA.md#b33-teto-de-tentativas"
    - ".reversa/principles.md#iii-resiliencia-por-degradacao-graciosa-e-limitas-rigidos"
  expected_behavior: "Relatório de lacuna (texto sem evidência/link) deve ser renderizado e persistido com sinalização de incompletude, não rejeitado incondicionalmente."
  observed_behavior: "writer.py:38-39 `if not text.strip() or not evidence: raise RuntimeError`; writer.py:41-43 `if cited == 0: raise`; writer.py:45-48 `if not linked_urls or not linked_urls.issubset(known_urls): raise`. Isso impede qualquer relatório sem evidência ou links, contrariando o princípio de que ausência de conteúdo deve gerar lacuna sem inventar fontes."
  affected_code:
    - "app/services/pipeline/writer.py:38-48"
root_cause:
  state: supported
  hypothesis: "Validação exige evidence e links incondicionalmente, sem distinguir gap report"
  causal_path:
    - "writer.py:38: not evidence -> RuntimeError (sem distinguir gap report)"
    - "writer.py:41: cited == 0 -> RuntimeError (gap report sem links é rejeitado)"
    - "writer.py:45: not linked_urls -> RuntimeError (gap report sem links é rejeitado)"
  evidence:
    - ref: "_reversa_bugs/investigacao-redator/intake/diagnostico-fdd70d5c.md:34"
      observation: "writer.py:38-39 rejeita incondicionalmente `not evidence` mesmo se texto é relatório de lacunas válido"
  code_refs:
    - file: "app/services/pipeline/writer.py"
      symbol: "_write_report.evidence_gate"
      commit: "582ed04abd3f03de8d38f8d162d1d945534e6b54"
spec_verdict: null
resolution_kind: null
closure:
  policy: local-software
  satisfied: false
change_set: []
regression_tests: []
labels:
  - gap-report
  - evidence-gating
  - false-rejection
relations:
  - {type: related-to, target: BUG-20261019-1, state: confirmed}
express: false
---
# BUG-20261019-2 — Writer rejeita incondicionalmente relatório de lacuna válido sem evidência/link

## Summary
O Writer (`writer.py:38-48`) exige evidência e pelo menos um link citado incondicionalmente. A regra `not evidence → RuntimeError` (linha 38-39), `cited == 0 → RuntimeError` (linha 41-43) e `not linked_urls or not linked_urls.issubset(known_urls) → RuntimeError` (linha 45-48) rejeitam **qualquer** saída do modelo quando não há evidência ou links, mesmo quando o texto é um relatório de lacuna legítimo (ex.: "Nenhuma evidência foi coletada; os pontos estão bloqueados").

## Expected Behavior
Conforme clareamento do usuário: **falta de conteúdo deve gerar lacuna sem inventar evidência/link**. O Writer deve permitir relatórios que documentam ausência de dados, desde que sinalizem a incompletude. A exigência de citação aplica-se a afirmações factuais, não a relatórios de lacuna.

## Actual Behavior
- `writer.py:38`: `if not text.strip() or not evidence:` → rejeita quando `evidence` é lista vazia, mesmo que `text` seja um relatório de lacuna válido.
- `writer.py:41-43`: `cited == 0` → rejeita quando nenhum `source_url` aparece no texto, mesmo que texto seja apenas um relatório de lacuna sem links para citar.
- `writer.py:45-48`: `not linked_urls or not linked_urls.issubset(known_urls)` → rejeita quando texto não contém links, independentemente de ser conteúdo factual ou relatório de gap.

## Steps to Reproduce
1. Executar `_write_report` sem evidence (ou evidence vazia)
2. Modelo retorna texto de relatório de lacuna (ex.: "## Visão geral\nNenhuma evidência disponível...")
3. `writer.py:38` dispara `RuntimeError("Writer cannot produce a report without evidence")`
4. Alternativa: com evidence, mas modelo gera texto sem links → linha 41 ou 48 dispara `RuntimeError`

## Evidence
- Diagnóstico: `_reversa_bugs/investigacao-redator/intake/diagnostico-fdd70d5c.md` (linhas 34)
- Código fonte: `app/services/pipeline/writer.py:38-48`
- Contexto: não foi gatilho desta execução específica (78 evidências no caso), mas é defeito estrutural paralelo ao BUG-20261019-1.

## Suspected Area
`app/services/pipeline/writer.py:38-48` — bloco de validação de evidência prévia à persistência.

## Acceptance Criteria
1. Texto de relatório de lacuna (sem evidência, sem links) não é rejeitado incondicionalmente.
2. Texto vazio ou stub continua rejeitado por `validate_report_quality`.
3. Afirmações factuais sem citação continuam rejeitadas (protegido pelo guardrail BUG-20261019-1).
4. Links fornecidos sempre pertencem às evidências (validação linhas 45-48 mantida para caso factuais).
5. Ponderar limite mínimo de palavras no caso de lacunas (não alterar contrato extra sem autorização).

## Traceability
(espelho legível do front matter YAML)

## Agent Notes
- Não inventar evidência ou links: lacuna deve ser documentada, não preenchida.
- Quarta reprovação encerra busca; falta de conteúdo deve gerar lacuna.
- Não transformar aprovação auditor em requisito para Writer.
- Verificar RF401/402 requirements feature004 para sinalização de lacuna.
- Relacionado a BUG-20261019-1 (mesmo módulo, heurística distinta).