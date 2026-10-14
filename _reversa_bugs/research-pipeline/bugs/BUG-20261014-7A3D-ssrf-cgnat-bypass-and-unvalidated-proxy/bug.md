---
schema_version: 1
id: BUG-20261014-7A3D
display_number: 11
context: research-pipeline
title: "Bypass de SSRF em CGNAT/Alibaba metadata, proxy_url sem validação e NameError em settings"
status: open
phase: triaging
severity: high
priority: P1
security_suspected: true
visibility: internal
created: "2026-10-14T18:14:35-03:00"
updated: "2026-10-14T18:14:35-03:00"
area: [security, research-pipeline, settings]
module: [outbound-ssrf, investigation-tools, settings-router]
feature: [ssrf-protection, investigacao-personas]
origin: {type: depth-inspection, external_ref: "_reversa_bugs/modulo-briefing/inspections/depth-inspection-20261014/report.md#f-sec-01"}
reported_by: reversa-depth-inspection
reported_at: "2026-10-14T18:14:35-03:00"
environment: {app: deep-research, branch: main, commit: "582ed04abd3f03de8d38f8d162d1d945534e6b54"}
traceability:
  specs: ["contracts.md#3-ssrf-prevention-contract-connection-level-pinning--redirect-safety", "GOAL.md#4-definition-of-done-testable-acceptance-criteria"]
  expected_behavior: "Saídas devem bloquear IPs não-globais, validar proxy_url e não conter referências não importadas."
  observed_behavior: "100.64.0.0/10 pode passar; JinaToolAdapter não valida proxy_url; settings.py usa logging sem import."
  affected_code: ["app/tools/outbound.py:31-51", "app/investigation/tools.py:121-125", "app/services/settings.py:62-71"]
  tests_existing: ["tests/test_backend.py", "tests/investigation/test_jina_tool.py"]
root_cause:
  summary: "Validação SSRF parcial, proxy não validado e import logging ausente."
  files: ["app/tools/outbound.py", "app/investigation/tools.py", "app/services/settings.py"]
spec_verdict: null
resolution_kind: null
closure: {policy: local-software, satisfied: false}
change_set: []
regression_tests: []
labels: [ssrf, security, cgnat, cloud-metadata, name-error]
relations: []
express: false
---
# BUG-20261014-7A3D

## Escopo do Fix Sugerido (para `/reversa-debugger-fix`)
Bloquear `not ip.is_global` após normalizar ipv4_mapped, validar proxy_url e corrigir import/trecho morto de logging.
