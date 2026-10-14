---
schema_version: 1
id: BUG-20261014-5D8A
display_number: 7
context: modulo-briefing
title: "POST /briefings não atualiza Research.status para PENDING_APPROVAL ou FAILED"
status: open
phase: triaging
severity: high
priority: P1
security_suspected: false
visibility: internal
created: "2026-10-14T18:14:35-03:00"
updated: "2026-10-14T18:14:35-03:00"
area: [scout, research-pipeline]
module: [briefing-storage, briefing-service, research-orchestrator]
feature: [modulo-briefing, investigacao-personas]
origin: {type: depth-inspection, external_ref: "_reversa_bugs/modulo-briefing/inspections/depth-inspection-20261014/report.md#f-brf-01"}
reported_by: reversa-depth-inspection
reported_at: "2026-10-14T18:14:35-03:00"
environment: {app: deep-research, branch: main, commit: "582ed04abd3f03de8d38f8d162d1d945534e6b54"}
traceability:
  specs: ["_reversa_forward/002-investigacao-personas/requirements.md#43-maquina-de-estados-consolidada"]
  expected_behavior: "DRAFT=>PENDING_APPROVAL, FAILED=>FAILED, APPROVED=>SCRAPER também no Research."
  observed_behavior: "save_briefing_transition só sincroniza Research no APPROVED; DRAFT/FAILED ficam BRIEFING e startup dispara scout legado."
  affected_code: ["app/briefing/storage.py:71-78", "app/briefing/storage.py:99-148", "app/briefing/service.py:252-323", "app/main.py:28-40"]
  tests_existing: ["tests/test_briefing_storage.py", "tests/test_briefing_persisted_orchestration.py"]
root_cause:
  summary: "Transições DRAFT e FAILED não atualizam Research.status."
  files: ["app/briefing/storage.py", "app/briefing/service.py", "app/main.py"]
spec_verdict: null
resolution_kind: null
closure: {policy: local-software, satisfied: false}
change_set: []
regression_tests: []
labels: [state-desync, startup-recovery, tx2-persistence, briefing-storage]
relations: []
express: false
---
# BUG-20261014-5D8A

## Escopo do Fix Sugerido (para `/reversa-debugger-fix`)
Sincronizar `Research.status` em DRAFT/FAILED/APPROVED e cobrir reinício sem scout legado indevido.
