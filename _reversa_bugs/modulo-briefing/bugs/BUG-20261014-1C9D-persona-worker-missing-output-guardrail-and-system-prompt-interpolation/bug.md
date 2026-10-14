---
schema_version: 1
id: BUG-20261014-1C9D
display_number: 13
context: modulo-briefing
title: "PersonaWorker persiste result sem output guardrail e interpola entrada no system prompt"
status: open
phase: triaging
severity: medium
priority: P2
security_suspected: true
visibility: internal
created: "2026-10-14T18:14:35-03:00"
updated: "2026-10-14T18:14:35-03:00"
area: [security, research-pipeline]
module: [investigation-worker, investigation-service]
feature: [investigacao-personas]
origin: {type: depth-inspection, external_ref: "_reversa_bugs/modulo-briefing/inspections/depth-inspection-20261014/report.md#f-sec-02"}
reported_by: reversa-depth-inspection
reported_at: "2026-10-14T18:14:35-03:00"
environment: {app: deep-research, branch: main, commit: "582ed04abd3f03de8d38f8d162d1d945534e6b54"}
traceability:
  specs: [".reversa/principles.md#ii-defesa-de-privacidade-e-isolamento-de-prompts", "app/CRITERIA.md#a1-guardrails"]
  expected_behavior: "Resultado deve passar por output guardrail e entradas não confiáveis não devem ser interpoladas no system."
  observed_behavior: "parsed.result retorna direto e theme/title entram no system prompt."
  affected_code: ["app/investigation/worker.py:299-306", "app/investigation/prompts.py:41-76"]
  tests_existing: ["tests/investigation/test_persona_credential_dispatch.py"]
root_cause:
  summary: "Worker chama LiteLLM diretamente sem output guardrail e prompt concatena entrada não confiável."
  files: ["app/investigation/worker.py", "app/investigation/prompts.py"]
spec_verdict: null
resolution_kind: null
closure: {policy: local-software, satisfied: false}
change_set: []
regression_tests: []
labels: [guardrail, prompt-injection, privacy-boundary, principle-ii]
relations: []
express: false
---
# BUG-20261014-1C9D

## Escopo do Fix Sugerido (para `/reversa-debugger-fix`)
Aplicar output guardrail ao resultado e mover theme/title para mensagem user delimitada como entrada não confiável.
