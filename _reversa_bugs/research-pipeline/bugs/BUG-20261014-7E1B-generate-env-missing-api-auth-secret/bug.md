---
schema_version: 1
id: BUG-20261014-7E1B
display_number: 20
context: research-pipeline
title: "scripts/generate_env.py não gera API_AUTH_SECRET, deixando Bearer/X-API-Key inabilitado"
status: open
phase: triaging
severity: low
priority: P3
security_suspected: false
visibility: internal
created: "2026-10-14T18:14:35-03:00"
updated: "2026-10-14T18:14:35-03:00"
area: [security, infra]
module: [env-bootstrap, auth-cors]
feature: [deep-research-execution]
origin: {type: depth-inspection, external_ref: "_reversa_bugs/modulo-briefing/inspections/depth-inspection-20261014/report.md#f-sec-04"}
reported_by: reversa-depth-inspection
reported_at: "2026-10-14T18:14:35-03:00"
environment: {app: deep-research, branch: main, commit: "582ed04abd3f03de8d38f8d162d1d945534e6b54"}
traceability:
  specs: ["contracts.md#2-security--credential-handling-contract"]
  expected_behavior: "Bootstrap deve gerar API_AUTH_SECRET forte quando ausente."
  observed_behavior: "generate_env.py não cria a variável e docker-compose recebe valor vazio."
  affected_code: ["scripts/generate_env.py:11-16", "docker-compose.yml:26"]
  tests_existing: []
root_cause:
  summary: "API_AUTH_SECRET não foi incluído no gerador de ambiente."
  files: ["scripts/generate_env.py", "docker-compose.yml"]
spec_verdict: null
resolution_kind: null
closure: {policy: local-software, satisfied: false}
change_set: []
regression_tests: []
labels: [env-bootstrap, authentication, api-auth-secret]
relations: []
express: false
---
# BUG-20261014-7E1B

## Escopo do Fix Sugerido (para `/reversa-debugger-fix`)
Gerar `API_AUTH_SECRET` seguro no bootstrap, preservando valores existentes e cobrindo por teste.
