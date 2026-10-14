---
schema_version: 1
id: BUG-20261014-9A6F
display_number: 17
context: research-pipeline
title: "resume pula tentativa interrompida e conflita com attempt_count por persona"
status: open
phase: triaging
severity: medium
priority: P2
security_suspected: false
visibility: internal
created: "2026-10-14T18:14:35-03:00"
updated: "2026-10-14T18:14:35-03:00"
area: [research-pipeline]
module: [research-orchestrator, investigation-storage]
feature: [deep-research-execution, investigacao-personas]
origin: {type: depth-inspection, external_ref: "_reversa_bugs/modulo-briefing/inspections/depth-inspection-20261014/report.md#f-pipe-03"}
reported_by: reversa-depth-inspection
reported_at: "2026-10-14T18:14:35-03:00"
environment: {app: deep-research, branch: main, commit: "582ed04abd3f03de8d38f8d162d1d945534e6b54"}
traceability:
  specs: ["app/CRITERIA.md#e-servico-de-eventos-e-retomada"]
  expected_behavior: "Retomada deve continuar do checkpoint correto sem consumir tentativa interrompida."
  observed_behavior: "attempt_count é incrementado antes da rodada e também reutilizado como contador de falhas de personas."
  affected_code: ["app/routers/research.py:383-425", "app/services/pipeline/point_executor.py:17-32", "app/investigation/storage.py:58-65"]
  tests_existing: ["tests/test_backend.py", "tests/investigation/test_investigation_runtime_regressions.py"]
root_cause:
  summary: "Coluna attempt_count tem semânticas incompatíveis nos dois pipelines e é incrementada cedo demais."
  files: ["app/routers/research.py", "app/services/pipeline/point_executor.py", "app/investigation/storage.py"]
spec_verdict: null
resolution_kind: null
closure: {policy: local-software, satisfied: false}
change_set: []
regression_tests: []
labels: [resume, attempt-count, durable-execution, state-conflict]
relations: []
express: false
---
# BUG-20261014-9A6F

## Escopo do Fix Sugerido (para `/reversa-debugger-fix`)
Rotear retomada modular corretamente e não pular tentativa ainda sem AuditTrail concluído.
