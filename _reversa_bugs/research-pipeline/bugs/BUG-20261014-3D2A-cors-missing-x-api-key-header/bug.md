---
schema_version: 1
id: BUG-20261014-3D2A
display_number: 18
context: research-pipeline
title: "Header X-API-Key suportado por require_admin está ausente de allow_headers no CORSMiddleware"
status: fixed
phase: fix-applied
severity: medium
priority: P2
security_suspected: false
visibility: internal
created: "2026-10-14T18:14:35-03:00"
updated: "2026-10-14T18:30:00-03:00"
area: [security, research-pipeline]
module: [auth-cors]
feature: [deep-research-execution, modulo-briefing]
origin: {type: depth-inspection, external_ref: "_reversa_bugs/modulo-briefing/inspections/depth-inspection-20261014/report.md#f-sec-03"}
reported_by: reversa-depth-inspection
reported_at: "2026-10-14T18:14:35-03:00"
environment: {app: deep-research, branch: main, commit: "582ed04abd3f03de8d38f8d162d1d945534e6b54"}
traceability:
  specs: ["GOAL.md#3-operator-experience--security-workflow-ux-walkthrough", "docs/api/briefing-scout.md#2-autenticacao--headers"]
  expected_behavior: "CORS deve permitir X-API-Key em origens autorizadas."
  observed_behavior: "allow_headers omite X-API-Key e o preflight falha."
  affected_code: ["app/main.py:83-89", "app/core/security.py:38-61"]
  tests_existing: ["tests/test_backend.py"]
root_cause:
  summary: "Lista CORS não foi atualizada quando X-API-Key foi adicionado à autenticação."
  files: ["app/main.py:83-89"]
spec_verdict: null
resolution_kind: code_fix
closure: {policy: local-software, satisfied: true}
change_set: ["app/main.py"]
regression_tests: ["tests/test_bug_3d2a_cors_x_api_key.py"]
labels: [cors, x-api-key, authentication]
relations: []
express: false
---
# BUG-20261014-3D2A

## Escopo do Fix Sugerido (para `/reversa-debugger-fix`)
Adicionar `X-API-Key` a `allow_headers` e provar preflight por regressão automatizada.

# Fix Aplicado

- Adicionado `"X-API-Key"` à lista `allow_headers` do `CORSMiddleware` em `app/main.py`.
- Adicionado teste de regressão dedicado `tests/test_bug_3d2a_cors_x_api_key.py` comprovando que preflight CORS com `Access-Control-Request-Headers: X-API-Key` é aceito para origens autorizadas e rejeitado/não liberado para origens não autorizadas.
