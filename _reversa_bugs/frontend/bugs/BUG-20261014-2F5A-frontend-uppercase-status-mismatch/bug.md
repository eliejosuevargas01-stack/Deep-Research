---
schema_version: 1
id: BUG-20261014-2F5A
display_number: 5
context: frontend
title: "Quebra total da máquina de estados do Frontend com o enum canônico ResearchStatus em UPPERCASE"
status: open
phase: triaging
severity: critical
priority: P0
security_suspected: false
visibility: internal
created: "2026-10-14T18:14:35-03:00"
updated: "2026-10-14T18:14:35-03:00"
area:
  - frontend
  - research-pipeline
module:
  - research-ui
  - research-orchestrator
feature:
  - deep-research-execution
  - report-rendering
origin:
  type: depth-inspection
  external_ref: "_reversa_bugs/modulo-briefing/inspections/depth-inspection-20261014/report.md#f-fe-01"
reported_by: "reversa-depth-inspection"
reported_at: "2026-10-14T18:14:35-03:00"
environment:
  app: deep-research
  branch: main
  commit: "582ed04abd3f03de8d38f8d162d1d945534e6b54"
traceability:
  specs:
    - "app/CRITERIA.md#a1-telas-e-estados"
    - "app/CRITERIA.md#a3-editor-de-briefing"
    - "app/CRITERIA.md#a6-relatorio"
    - "_reversa_forward/002-investigacao-personas/requirements.md#421-entidade-research-pesquisa"
  expected_behavior: |
    O frontend deve reconhecer os status canônicos de Research (`PENDING`, `BRIEFING`, `PENDING_APPROVAL`, `SCRAPER`, `AUDIT`, `WRITE`, `DONE`, `FAILED`) para renderizar o card de revisão do briefing, o grid das 4 personas, o relatório final, o card de erro/retomada e encerrar o polling quando a pesquisa atingir estado terminal.
  observed_behavior: |
    O backend grava e retorna status em UPPERCASE (`BRIEFING`, `PENDING_APPROVAL`, `SCRAPER`, `AUDIT`, `DONE`, `FAILED`), mas `frontend/src/main.tsx` e `frontend/src/research-utils.ts` comparam strings minúsculas legadas (`scouting`, `pending_approval`, `approved`, `in_progress`, `completed`, `failed`). Consequentemente: (1) o card de revisão/aprovação do briefing (`main.tsx:1229`) nunca aparece; (2) `isCompleted` (`main.tsx:1102`) é sempre `false` para `DONE`, nunca carregando o relatório e mantendo o polling de 4s em loop infinito; (3) o botão de retomada (`main.tsx:1137, 1539`) nunca aparece em `FAILED`; (4) `STATUS_RANK` (`research-utils.ts:440`) atribui rank 0 aos novos status.
  affected_code:
    - "frontend/src/main.tsx:684-689"
    - "frontend/src/main.tsx:844-891"
    - "frontend/src/main.tsx:1102-1195"
    - "frontend/src/main.tsx:1213-1369"
    - "frontend/src/main.tsx:1539-1635"
    - "frontend/src/research-utils.ts:252-265"
    - "frontend/src/research-utils.ts:440-469"
    - "app/routers/research.py:166"
  tests_existing:
    - "frontend/tests/frontend.test.mjs"
root_cause:
  summary: "A migração 0007 e a Feature 002 (T002/T023) converteram `Research.status` no backend para UPPERCASE canônico sem atualizar `STATUS_RANK`, `canTransitionStatus`, `statusLabel` e os predicados de estado em `frontend/src/main.tsx`."
  files:
    - "frontend/src/main.tsx:684-689"
    - "frontend/src/main.tsx:844-891"
    - "frontend/src/main.tsx:1102-1195"
    - "frontend/src/main.tsx:1213-1369"
    - "frontend/src/main.tsx:1539-1635"
    - "frontend/src/research-utils.ts:252-265"
    - "frontend/src/research-utils.ts:440-469"
    - "app/routers/research.py:166"
spec_verdict: null
resolution_kind: null
closure:
  policy: local-software
  satisfied: false
change_set: []
regression_tests: []
labels:
  - state-machine
  - status-enum
  - frontend-broken
  - infinite-polling
relations: []
express: false
---

# BUG-20261014-2F5A — Quebra total da máquina de estados do Frontend com o enum canônico ResearchStatus em UPPERCASE

## Resumo

Achado `F-FE-01` promovido a partir da inspeção profunda (`/reversa-depth-inspection`) realizada em 14/10/2026 sobre as features existentes do sistema Deep Research Engine.

## Esperado vs Observado

- **Esperado:** O frontend deve reconhecer os status canônicos de Research (`PENDING`, `BRIEFING`, `PENDING_APPROVAL`, `SCRAPER`, `AUDIT`, `WRITE`, `DONE`, `FAILED`) para renderizar o card de revisão do briefing, o grid das 4 personas, o relatório final, o card de erro/retomada e encerrar o polling quando a pesquisa atingir estado terminal.
- **Observado:** O backend grava e retorna status em UPPERCASE (`BRIEFING`, `PENDING_APPROVAL`, `SCRAPER`, `AUDIT`, `DONE`, `FAILED`), mas `frontend/src/main.tsx` e `frontend/src/research-utils.ts` comparam strings minúsculas legadas (`scouting`, `pending_approval`, `approved`, `in_progress`, `completed`, `failed`). Consequentemente: (1) o card de revisão/aprovação do briefing (`main.tsx:1229`) nunca aparece; (2) `isCompleted` (`main.tsx:1102`) é sempre `false` para `DONE`, nunca carregando o relatório e mantendo o polling de 4s em loop infinito; (3) o botão de retomada (`main.tsx:1137, 1539`) nunca aparece em `FAILED`; (4) `STATUS_RANK` (`research-utils.ts:440`) atribui rank 0 aos novos status.

## Causa Raiz (Confirmada na Inspeção)

A migração 0007 e a Feature 002 (T002/T023) converteram `Research.status` no backend para UPPERCASE canônico sem atualizar `STATUS_RANK`, `canTransitionStatus`, `statusLabel` e os predicados de estado em `frontend/src/main.tsx`.

**Arquivos e linhas afetados:**
- `frontend/src/main.tsx:684-689`
- `frontend/src/main.tsx:844-891`
- `frontend/src/main.tsx:1102-1195`
- `frontend/src/main.tsx:1213-1369`
- `frontend/src/main.tsx:1539-1635`
- `frontend/src/research-utils.ts:252-265`
- `frontend/src/research-utils.ts:440-469`
- `app/routers/research.py:166`

## Passos para Reproduzir

1. Criar uma pesquisa via UI (`POST /api/research`).
2. Quando o Scout termina, `GET /api/research/{id}` retorna `status: "PENDING_APPROVAL"`.
3. Observar em `ResearchPage` (`main.tsx:1229`) que `research.status === 'pending_approval'` avalia para `false`, ocultando o editor de briefing e exibindo 'Pesquisa autônoma em andamento'.

## Escopo do Fix Sugerido (para `/reversa-debugger-fix`)

1. Atualizar `STATUS_RANK`, `canTransitionStatus` e `statusLabel` em `frontend/src/research-utils.ts` para suportar tanto os status canônicos em UPPERCASE quanto os legados.
2. Atualizar todas as checagens de `research.status` e `data.status` em `frontend/src/main.tsx`.
3. Alinhar `POST /api/research` (`app/routers/research.py:166`) para retornar `ResearchStatus.BRIEFING.value`.

## Agent Notes

- **Origem:** Promovido de `F-FE-01` (`_reversa_bugs/modulo-briefing/inspections/depth-inspection-20261014/report.md`).
- **Severidade / Prioridade:** `critical` / `P0`.
- **Política de Fechamento (`closure.policy`):** `local-software` (requer correção validada por teste de regressão automatizado antes de transitar para `resolved`).
