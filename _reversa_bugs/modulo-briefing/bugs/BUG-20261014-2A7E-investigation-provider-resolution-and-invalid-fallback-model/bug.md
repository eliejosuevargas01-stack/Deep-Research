---
schema_version: 1
id: BUG-20261014-2A7E
display_number: 14
context: modulo-briefing
title: "InvestigationService resolve provider de forma divergente e usa fallback openai/implement inválido"
status: open
phase: triaging
severity: medium
priority: P2
security_suspected: false
visibility: internal
created: "2026-10-14T18:14:35-03:00"
updated: "2026-10-14T18:14:35-03:00"
area: [research-pipeline, settings]
module: [investigation-service, llm-client]
feature: [investigacao-personas, llm-gateway-fallback]
origin: {type: depth-inspection, external_ref: "_reversa_bugs/modulo-briefing/inspections/depth-inspection-20261014/report.md#f-inv-02"}
reported_by: reversa-depth-inspection
reported_at: "2026-10-14T18:14:35-03:00"
environment: {app: deep-research, branch: main, commit: "582ed04abd3f03de8d38f8d162d1d945534e6b54"}
traceability:
  specs: ["contracts.md#6-configuration-ownership--dynamic-runtime-contract"]
  expected_behavior: "Resolução de provider deve ser idêntica à de llm._provider e fallback deve ser modelo válido."
  observed_behavior: "Helper local mapeia modelos sem barra/prefixos errado e fallback é openai/implement."
  affected_code: ["app/investigation/service.py:20-21", "app/investigation/prompts.py:79-97"]
  tests_existing: ["tests/investigation/test_persona_credential_dispatch.py"]
root_cause:
  summary: "Provider foi reimplementado de forma simplificada e placeholder inválido permaneceu no fallback."
  files: ["app/investigation/service.py", "app/investigation/prompts.py"]
spec_verdict: null
resolution_kind: null
closure: {policy: local-software, satisfied: false}
change_set: []
regression_tests: []
labels: [provider-resolution, model-fallback, credentials]
relations: []
express: false
---
# BUG-20261014-2A7E

## Escopo do Fix Sugerido (para `/reversa-debugger-fix`)
Reutilizar o resolver canônico de provider e substituir `openai/implement` pelo default válido do projeto.
