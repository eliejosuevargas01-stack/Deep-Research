---
schema_version: 1
id: BUG-20261014-3C9B
display_number: 6
context: research-pipeline
title: "Fluxo /api/research estaciona em SCRAPER e InvestigationService estaciona em AUDIT sem consumidor"
status: open
phase: triaging
severity: high
priority: P1
security_suspected: false
visibility: internal
created: "2026-10-14T18:14:35-03:00"
updated: "2026-10-14T18:14:35-03:00"
area: [research-pipeline]
module: [research-orchestrator, investigation-service]
feature: [deep-research-execution, investigacao-personas]
origin: {type: depth-inspection, external_ref: "_reversa_bugs/modulo-briefing/inspections/depth-inspection-20261014/report.md#f-pipe-01"}
reported_by: reversa-depth-inspection
reported_at: "2026-10-14T18:14:35-03:00"
environment: {app: deep-research, branch: main, commit: "582ed04abd3f03de8d38f8d162d1d945534e6b54"}
traceability:
  specs: ["GOAL.md#1-problem-statement--mission", "contracts.md#7-protocol-compliance--api-compatibility-contract"]
  expected_behavior: "Após aprovação/revisão o pipeline deve avançar até DONE."
  observed_behavior: "Aprovação muda para SCRAPER sem agendar investigação; run_investigation termina em AUDIT sem consumidor."
  affected_code: ["app/routers/research.py:84-103", "app/routers/research.py:286-318", "app/investigation/service.py:149-163", "frontend/src/main.tsx:913-956"]
  tests_existing: ["tests/test_backend.py", "tests/investigation/test_investigation_runtime_regressions.py"]
root_cause:
  summary: "Desconexão entre fluxo legado /api/research e fluxo modular /briefings/{id}/investigate."
  files: ["app/routers/research.py", "app/investigation/service.py", "frontend/src/main.tsx"]
spec_verdict: null
resolution_kind: null
closure: {policy: local-software, satisfied: false}
change_set: []
regression_tests: []
labels: [pipeline-stall, orchestration-gap, scraper-status, audit-status]
relations: []
express: false
---
# BUG-20261014-3C9B

## Escopo do Fix Sugerido (para `/reversa-debugger-fix`)
Unificar o disparo da investigação e conectar AUDIT aos estágios seguintes conforme os contratos atuais.
