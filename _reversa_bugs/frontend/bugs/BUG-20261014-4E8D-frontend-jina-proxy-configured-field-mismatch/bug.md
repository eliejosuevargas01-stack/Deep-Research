---
schema_version: 1
id: BUG-20261014-4E8D
display_number: 15
context: frontend
title: "Divergência de campo jina_proxy_configured (backend) vs jina_proxy_auth_configured (frontend) oculta status da chave do proxy"
status: open
phase: triaging
severity: medium
priority: P2
security_suspected: false
visibility: internal
created: "2026-10-14T18:14:35-03:00"
updated: "2026-10-14T18:14:35-03:00"
area: [frontend, settings]
module: [research-ui, settings-router]
feature: [settings-management]
origin:
  type: depth-inspection
  external_ref: "_reversa_bugs/modulo-briefing/inspections/depth-inspection-20261014/report.md#f-fe-02"
reported_by: reversa-depth-inspection
reported_at: "2026-10-14T18:14:35-03:00"
environment: {app: deep-research, branch: main, commit: "582ed04abd3f03de8d38f8d162d1d945534e6b54"}
traceability:
  specs: ["app/CRITERIA.md#a7-configuracoes", "contracts.md#2-security--credential-handling-contract"]
  expected_behavior: "A UI deve reconhecer quando a chave do proxy Jina está configurada."
  observed_behavior: "Backend retorna jina_proxy_configured; frontend lê jina_proxy_auth_configured e sempre considera a chave ausente."
  affected_code: ["app/services/settings.py:339-341", "frontend/src/types.ts:85", "frontend/src/main.tsx:2349-2360"]
  tests_existing: ["frontend/tests/frontend.test.mjs"]
root_cause:
  summary: "Contrato JSON e tipo TypeScript usam nomes diferentes para o mesmo campo."
  files: ["app/services/settings.py:339-341", "frontend/src/types.ts:85", "frontend/src/main.tsx:2349-2360"]
spec_verdict: null
resolution_kind: null
closure: {policy: local-software, satisfied: false}
change_set: []
regression_tests: []
labels: [settings-ui, schema-mismatch, jina-proxy]
relations:
  - {type: related-to, target: BUG-20261006-57LI, state: confirmed}
express: false
---
# BUG-20261014-4E8D

## Resumo
A página de configurações nunca reconhece a chave Jina proxy já salva por divergência de nomenclatura entre backend e frontend.

## Escopo do Fix Sugerido (para `/reversa-debugger-fix`)
Compatibilizar o campo retornado pelo backend e o consumido pela UI, com regressão cobrindo o estado configurado.
