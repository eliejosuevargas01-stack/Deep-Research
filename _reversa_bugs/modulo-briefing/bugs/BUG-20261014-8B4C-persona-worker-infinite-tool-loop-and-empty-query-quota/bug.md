---
schema_version: 1
id: BUG-20261014-8B4C
display_number: 12
context: modulo-briefing
title: "PersonaWorker mantém tools ativo após teto de 3 buscas e gasta cota em query vazia"
status: closed
phase: closed
severity: medium
priority: P2
security_suspected: false
visibility: internal
created: "2026-10-14T18:14:35-03:00"
updated: "2026-10-14T18:14:35-03:00"
area: [research-pipeline]
module: [investigation-worker]
feature: [investigacao-personas]
origin: {type: depth-inspection, external_ref: "_reversa_bugs/modulo-briefing/inspections/depth-inspection-20261014/report.md#f-inv-01"}
reported_by: reversa-depth-inspection
reported_at: "2026-10-14T18:14:35-03:00"
environment: {app: deep-research, branch: main, commit: "582ed04abd3f03de8d38f8d162d1d945534e6b54"}
traceability:
  specs: ["docs/api/investigation-personas.md#4-comportamento--efeitos-colaterais"]
  expected_behavior: "Após 3 buscas, tools devem ser desativadas; query vazia não consome cota; tool inválida recebe erro."
  observed_behavior: "tools seguem ativos até timeout global; contador incrementa antes de validar query; tool desconhecida é ignorada."
  affected_code: ["app/investigation/worker.py:242-296"]
  tests_existing: ["tests/investigation/test_persona_worker.py"]
root_cause:
  summary: "tools são enviados incondicionalmente e search_count incrementa antes da validação."
  files: ["app/investigation/worker.py:242-296"]
spec_verdict: null
resolution_kind: code-fix
closure: {policy: local-software, satisfied: true}
change_set: ["app/investigation/worker.py"]
regression_tests: ["tests/investigation/test_persona_worker.py"]
labels: [tool-calling, infinite-loop, quota-accounting, persona-worker]
relations: []
express: false
---
# BUG-20261014-8B4C

## Escopo do Fix Sugerido (para `/reversa-debugger-fix`)
Desativar tools ao atingir teto/correção, validar query antes de incrementar e responder a tool inválida.
