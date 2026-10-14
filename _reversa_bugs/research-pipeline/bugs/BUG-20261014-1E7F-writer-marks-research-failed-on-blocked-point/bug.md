---
schema_version: 1
id: BUG-20261014-1E7F
display_number: 9
context: research-pipeline
title: "_write_report marca a pesquisa inteira como FAILED quando qualquer ponto termina blocked"
status: open
phase: triaging
severity: high
priority: P1
security_suspected: false
visibility: internal
created: "2026-10-14T18:14:35-03:00"
updated: "2026-10-14T18:14:35-03:00"
area: [report, research-pipeline]
module: [writer-stage, research-orchestrator]
feature: [deep-research-execution, report-rendering]
origin: {type: depth-inspection, external_ref: "_reversa_bugs/modulo-briefing/inspections/depth-inspection-20261014/report.md#f-pipe-02"}
reported_by: reversa-depth-inspection
reported_at: "2026-10-14T18:14:35-03:00"
environment: {app: deep-research, branch: main, commit: "582ed04abd3f03de8d38f8d162d1d945534e6b54"}
traceability:
  specs: [".reversa/principles.md#iii-resiliencia-por-degradacao-graciosa-e-limites-rigidos", "app/CRITERIA.md#b33-teto-de-tentativas"]
  expected_behavior: "Relatório persistido com pontos approved/blocked deve concluir DONE."
  observed_behavior: "writer.py define FAILED se nem todos os pontos forem approved."
  affected_code: ["app/services/pipeline/writer.py:69-73", "app/routers/research.py:205-208", "app/routers/research.py:337-351"]
  tests_existing: ["tests/test_backend.py"]
root_cause:
  summary: "Ramo else da migração para ResearchStatus foi mapeado para FAILED em vez de conclusão degradada."
  files: ["app/services/pipeline/writer.py:69-73"]
spec_verdict: null
resolution_kind: null
closure: {policy: local-software, satisfied: false}
change_set: []
regression_tests: []
labels: [regression, audit-blocked, writer-status, graceful-degradation]
relations:
  - {type: related-to, target: BUG-20261005-7H2K, state: confirmed}
express: false
---
# BUG-20261014-1E7F

## Escopo do Fix Sugerido (para `/reversa-debugger-fix`)
Concluir DONE quando todos os pontos estiverem em approved/blocked e o relatório tiver sido persistido.
