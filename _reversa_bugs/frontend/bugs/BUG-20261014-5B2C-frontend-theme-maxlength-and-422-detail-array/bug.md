---
schema_version: 1
id: BUG-20261014-5B2C
display_number: 16
context: frontend
title: "HomePage permite tema até 500 chars e api.ts descarta arrays em error.detail"
status: open
phase: triaging
severity: medium
priority: P2
security_suspected: false
visibility: internal
created: "2026-10-14T18:14:35-03:00"
updated: "2026-10-14T18:14:35-03:00"
area: [frontend]
module: [research-ui]
feature: [deep-research-execution, modulo-briefing]
origin: {type: depth-inspection, external_ref: "_reversa_bugs/modulo-briefing/inspections/depth-inspection-20261014/report.md#f-fe-03"}
reported_by: reversa-depth-inspection
reported_at: "2026-10-14T18:14:35-03:00"
environment: {app: deep-research, branch: main, commit: "582ed04abd3f03de8d38f8d162d1d945534e6b54"}
traceability:
  specs: ["_reversa_forward/002-investigacao-personas/requirements.md#5-requisitos-funcionais", "app/CRITERIA.md#a8-tratamento-de-erros"]
  expected_behavior: "Tema deve ter 3..300 caracteres e erros 422 devem exibir as mensagens de detail[].msg."
  observed_behavior: "HomePage aceita 500 caracteres e api.ts reduz detail array a HTTP 422."
  affected_code: ["frontend/src/main.tsx:494-508", "frontend/src/api.ts:41-50", "frontend/src/api.ts:109-112"]
  tests_existing: ["frontend/tests/frontend.test.mjs"]
root_cause:
  summary: "Limite legado 500 e parser de erro assumindo detail string."
  files: ["frontend/src/main.tsx:494-508", "frontend/src/api.ts:41-50", "frontend/src/api.ts:109-112"]
spec_verdict: null
resolution_kind: null
closure: {policy: local-software, satisfied: false}
change_set: []
regression_tests: []
labels: [validation, ux-error-message, theme-length, http-422]
relations: []
express: false
---
# BUG-20261014-5B2C

## Escopo do Fix Sugerido (para `/reversa-debugger-fix`)
Aplicar teto 300 no formulário/payload e extrair mensagens de arrays FastAPI 422, com regressão.
