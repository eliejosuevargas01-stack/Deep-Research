---
schema_version: 1
id: BUG-20261014-8F3E
display_number: 21
context: frontend
title: "frontend.test.mjs falha com ERR_UNKNOWN_FILE_EXTENSION em Node 18/20 e não está integrado ao CI"
status: fixed
phase: fixed
severity: low
priority: P3
security_suspected: false
visibility: internal
created: "2026-10-14T18:14:35-03:00"
updated: "2026-10-14T18:14:35-03:00"
area: [frontend, infra]
module: [research-ui]
feature: [deep-research-execution]
origin: {type: depth-inspection, external_ref: "_reversa_bugs/modulo-briefing/inspections/depth-inspection-20261014/report.md#f-tst-01"}
reported_by: reversa-depth-inspection
reported_at: "2026-10-14T18:14:35-03:00"
environment: {app: deep-research, branch: main, commit: "582ed04abd3f03de8d38f8d162d1d945534e6b54"}
traceability:
  specs: ["contracts.md#11-testing--verification-contract", "reversa/05-testes-infra.md"]
  expected_behavior: "Testes frontend devem rodar reprodutivelmente e no CI."
  observed_behavior: "Arquivo .mjs importa .ts diretamente sem loader e CI não executa frontend."
  affected_code: ["frontend/tests/frontend.test.mjs:1-46", "frontend/package.json", ".github/workflows/ci.yml:10-36"]
  tests_existing: ["frontend/tests/frontend.test.mjs"]
root_cause:
  summary: "Loader TypeScript ausente e workflow sem step frontend."
  files: ["frontend/tests/frontend.test.mjs", "frontend/package.json", ".github/workflows/ci.yml"]
spec_verdict: null
resolution_kind: null
closure: {policy: local-software, satisfied: true}
change_set: ["frontend/package.json", ".github/workflows/ci.yml"]
regression_tests: ["frontend/tests/frontend.test.mjs"]
labels: [ci-gap, frontend-tests, node-ts-loader]
relations: []
express: false
---
# BUG-20261014-8F3E

## Escopo do Fix Sugerido (para `/reversa-debugger-fix`)
Configurar execução TypeScript suportada e integrar build/test do frontend ao CI.

# Fix Aplicado (2026-10-14, /reversa-debugger-fix)

- `frontend/package.json`: adicionado `--loader ts-node/esm` ao script `"test"` para que a execução de `node --test` resolva importações de arquivos TypeScript `.ts`.
- `.github/workflows/ci.yml`: adicionados steps de setup do Node.js (`actions/setup-node@v4`), `npm ci`, `npm run build` e `npm test` para a aplicação frontend no pipeline CI.
- Todos os 28 testes em `frontend/tests/frontend.test.mjs` passam com sucesso.
