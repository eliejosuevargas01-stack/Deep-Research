---
schema_version: 1
id: BUG-20261014-6C7B
display_number: 19
context: settings
title: "update_settings ignora silenciosamente jina_proxy_timeout_seconds fora de 1..120 (aceitando bool) e descarta chaves reais contendo '*'"
status: open
phase: triaging
severity: low
priority: P3
security_suspected: false
visibility: internal
created: "2026-10-14T18:14:35-03:00"
updated: "2026-10-14T18:14:35-03:00"
area:
  - settings
module:
  - settings-router
feature:
  - settings-management
origin:
  type: depth-inspection
  external_ref: "_reversa_bugs/modulo-briefing/inspections/depth-inspection-20261014/report.md#f-set-03"
reported_by: "reversa-depth-inspection"
reported_at: "2026-10-14T18:14:35-03:00"
environment:
  app: deep-research
  branch: main
  commit: "582ed04abd3f03de8d38f8d162d1d945534e6b54"
traceability:
  specs:
    - "contracts.md#2-security--credential-handling-contract"
    - "contracts.md#6-configuration-ownership--dynamic-runtime-contract"
  expected_behavior: |
    `PUT /api/settings` deve validar `jina_proxy_timeout_seconds` no schema (rejeitando `<= 0`, `> 120` ou `bool` com HTTP 422) e permitir salvar chaves/segredos legítimos mesmo que contenham o caractere `*` (ignorando apenas valores que correspondam ao formato de máscara retornado por `mask_secret`).
  observed_behavior: |
    1. Em `app/services/settings.py:420-423`, se `jina_proxy_timeout_seconds` for `0`, `-10` ou `300`, o valor é silenciosamente ignorado retornando HTTP 200 sem atualizar o campo; e se for `True` (`bool`), `isinstance(True, int)` avalia para `True` e grava `1`.
    2. Em `app/services/settings.py:364, 371`, `elif "*" not in value:` descarta silenciosamente qualquer senha/segredo real (como `PROXY_SECRET_KEY`) que contenha um asterisco `*`.
  affected_code:
    - "app/services/settings.py:361-373"
    - "app/services/settings.py:419-424"
    - "app/schemas/__init__.py:84"
  tests_existing:
    - "tests/test_backend.py"
root_cause:
  summary: "Uso de guarda silenciosa `1 <= jina_proxy_timeout_seconds <= 120` sem `else: raise ValueError(...)` e sem exclusão de `bool`, e checagem ingênua `\"*\" not in value` para detecção de máscara."
  files:
    - "app/services/settings.py:361-373"
    - "app/services/settings.py:419-424"
    - "app/schemas/__init__.py:84"
spec_verdict: null
resolution_kind: null
closure:
  policy: local-software
  satisfied: false
change_set: []
regression_tests: []
labels:
  - settings-validation
  - silent-failure
  - boolean-int-coercion
relations: []
express: false
---

# BUG-20261014-6C7B — update_settings ignora silenciosamente jina_proxy_timeout_seconds fora de 1..120 (aceitando bool) e descarta chaves reais contendo '*'

## Resumo

Achado `F-SET-03` promovido a partir da inspeção profunda (`/reversa-depth-inspection`) realizada em 14/10/2026 sobre as features existentes do sistema Deep Research Engine.

## Esperado vs Observado

- **Esperado:** `PUT /api/settings` deve validar `jina_proxy_timeout_seconds` no schema (rejeitando `<= 0`, `> 120` ou `bool` com HTTP 422) e permitir salvar chaves/segredos legítimos mesmo que contenham o caractere `*` (ignorando apenas valores que correspondam ao formato de máscara retornado por `mask_secret`).
- **Observado:** 1. Em `app/services/settings.py:420-423`, se `jina_proxy_timeout_seconds` for `0`, `-10` ou `300`, o valor é silenciosamente ignorado retornando HTTP 200 sem atualizar o campo; e se for `True` (`bool`), `isinstance(True, int)` avalia para `True` e grava `1`.
2. Em `app/services/settings.py:364, 371`, `elif "*" not in value:` descarta silenciosamente qualquer senha/segredo real (como `PROXY_SECRET_KEY`) que contenha um asterisco `*`.

## Causa Raiz (Confirmada na Inspeção)

Uso de guarda silenciosa `1 <= jina_proxy_timeout_seconds <= 120` sem `else: raise ValueError(...)` e sem exclusão de `bool`, e checagem ingênua `"*" not in value` para detecção de máscara.

**Arquivos e linhas afetados:**
- `app/services/settings.py:361-373`
- `app/services/settings.py:419-424`
- `app/schemas/__init__.py:84`

## Passos para Reproduzir

1. Enviar `PUT /api/settings` com `{"jina_proxy_auth_key": "sec*ret12345", "jina_proxy_timeout_seconds": 200}`.
2. A API retorna HTTP 200 OK, mas nem `jina_proxy_auth_key` nem `jina_proxy_timeout_seconds` são persistidos.

## Escopo do Fix Sugerido (para `/reversa-debugger-fix`)

1. Validar `jina_proxy_timeout_seconds` em `SettingsUpdate` (`ge=1, le=120`, rejeitando `bool`).
2. Em `update_settings`, substituir `"*" not in value` por comparação exata com a máscara atual (`value != mask_secret(current_plain)` ou regex de `****`).

## Agent Notes

- **Origem:** Promovido de `F-SET-03` (`_reversa_bugs/modulo-briefing/inspections/depth-inspection-20261014/report.md`).
- **Severidade / Prioridade:** `low` / `P3`.
- **Política de Fechamento (`closure.policy`):** `local-software` (requer correção validada por teste de regressão automatizado antes de transitar para `resolved`).
