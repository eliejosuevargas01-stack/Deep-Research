---
schema_version: 1
id: BUG-20261014-6F2E
display_number: 10
context: modulo-briefing
title: "Desvios Q14-Q16: approve legado, investigate sem aprovação implícita e revisão sem 2ª SERP"
status: open
phase: triaging
severity: high
priority: P1
security_suspected: false
visibility: internal
created: "2026-10-14T18:14:35-03:00"
updated: "2026-10-14T18:14:35-03:00"
area: [scout, research-pipeline]
module: [briefing-router, briefing-service, investigation-router]
feature: [modulo-briefing, investigacao-personas]
origin: {type: depth-inspection, external_ref: "_reversa_bugs/modulo-briefing/inspections/depth-inspection-20261014/report.md#f-brf-02"}
reported_by: reversa-depth-inspection
reported_at: "2026-10-14T18:14:35-03:00"
environment: {app: deep-research, branch: main, commit: "582ed04abd3f03de8d38f8d162d1d945534e6b54"}
traceability:
  specs: ["_reversa_forward/002-investigacao-personas/actions.md#sprint-c8--ajuste-de-fluxo-aprovacao-implicita-e-revisao-com-2a-serp-jina"]
  expected_behavior: "Investigar draft aprova implicitamente; revisão usa nova SERP e auto-inicia investigação; /approve deixa de existir."
  observed_behavior: "Contrato Sprint C8 ainda não implementado."
  affected_code: ["app/briefing/router.py:232-306", "app/briefing/service.py:153-230", "app/investigation/router.py:27-68"]
  tests_existing: ["tests/test_briefing_api.py", "tests/test_briefing_lifecycle.py", "tests/investigation/test_investigation_e2e.py"]
root_cause:
  summary: "T036-T040 foram planejadas, mas não implementadas."
  files: ["app/briefing/router.py", "app/briefing/service.py", "app/investigation/router.py"]
spec_verdict: null
resolution_kind: null
closure: {policy: local-software, satisfied: false}
change_set: []
regression_tests: []
labels: [sprint-c8, contract-gap, implicit-approval, feedback-revision]
relations:
  - {type: related-to, target: BUG-20261014-4B9F, state: confirmed}
express: false
---
# BUG-20261014-6F2E

## Escopo do Fix Sugerido (para `/reversa-debugger-fix`)
Executar estritamente T036–T040 e validar o contrato Q14–Q16.
