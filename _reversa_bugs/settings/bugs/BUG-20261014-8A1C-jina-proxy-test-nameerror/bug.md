---
schema_version: 1
id: BUG-20261014-8A1C
display_number: 4
context: settings
title: "test_provider_key lança NameError (payload não definido) ao testar jina_proxy e ignora credenciais não salvas"
status: open
phase: triaging
severity: critical
priority: P0
security_suspected: false
visibility: internal
created: "2026-10-14T18:14:35-03:00"
updated: "2026-10-14T18:14:35-03:00"
area:
  - settings
  - frontend
module:
  - llm-client
  - settings-router
  - research-ui
feature:
  - settings-management
  - llm-gateway-fallback
origin:
  type: depth-inspection
  external_ref: "_reversa_bugs/modulo-briefing/inspections/depth-inspection-20261014/report.md#f-set-01"
reported_by: "reversa-depth-inspection"
reported_at: "2026-10-14T18:14:35-03:00"
environment:
  app: deep-research
  branch: main
  commit: "582ed04abd3f03de8d38f8d162d1d945534e6b54"
traceability:
  specs:
    - "app/CRITERIA.md#f1-teste-de-credenciais"
    - "app/CRITERIA.md#a7-configuracoes"
    - "contracts.md#6-configuration-ownership--dynamic-runtime-contract"
  expected_behavior: |
    POST /api/settings/test com provider='jina_proxy' deve testar a conexão contra a URL do Worker usando o parâmetro base_url e aceitar credenciais/URL informadas na requisição antes mesmo de serem salvas no banco de dados (CRITERIA.md §1.F1).
  observed_behavior: |
    app/services/llm.py:480 executa 'base_url = payload.base_url', mas 'payload' não existe no escopo de test_provider_key(provider, api_key, base_url). Isso levanta NameError: name 'payload' is not defined em 100% das chamadas, capturado na linha 500 e retornado como 'Falha de conexão ao testar provedor: NameError'. Além disso, app/routers/settings.py:51-60 e frontend/src/main.tsx:2373 ignoram os campos digitados no formulário e leem apenas os valores já persistidos no banco.
  affected_code:
    - "app/services/llm.py:479-483"
    - "app/routers/settings.py:51-60"
    - "frontend/src/main.tsx:2367-2381"
  tests_existing:
    - "tests/test_backend.py"
root_cause:
  summary: "Referência à variável inexistente 'payload.base_url' dentro de test_provider_key em app/services/llm.py:480 (cujo parâmetro real é 'base_url'), combinada com leitura exclusiva do banco em app/routers/settings.py:51-60."
  files:
    - "app/services/llm.py:479-483"
    - "app/routers/settings.py:51-60"
    - "frontend/src/main.tsx:2367-2381"
spec_verdict: null
resolution_kind: null
closure:
  policy: local-software
  satisfied: false
change_set: []
regression_tests: []
labels:
  - name-error
  - jina-proxy
  - settings-test
  - criteria-f1
relations:
  - type: related-to
    target: BUG-20261006-57LI
    state: confirmed
    note: "Introduzido na adição de suporte ao proxy Jina."
express: false
---

# BUG-20261014-8A1C — test_provider_key lança NameError (payload não definido) ao testar jina_proxy e ignora credenciais não salvas

## Resumo

Achado `F-SET-01` promovido a partir da inspeção profunda (`/reversa-depth-inspection`) realizada em 14/10/2026 sobre as features existentes do sistema Deep Research Engine.

## Esperado vs Observado

- **Esperado:** POST /api/settings/test com provider='jina_proxy' deve testar a conexão contra a URL do Worker usando o parâmetro base_url e aceitar credenciais/URL informadas na requisição antes mesmo de serem salvas no banco de dados (CRITERIA.md §1.F1).
- **Observado:** app/services/llm.py:480 executa 'base_url = payload.base_url', mas 'payload' não existe no escopo de test_provider_key(provider, api_key, base_url). Isso levanta NameError: name 'payload' is not defined em 100% das chamadas, capturado na linha 500 e retornado como 'Falha de conexão ao testar provedor: NameError'. Além disso, app/routers/settings.py:51-60 e frontend/src/main.tsx:2373 ignoram os campos digitados no formulário e leem apenas os valores já persistidos no banco.

## Causa Raiz (Confirmada na Inspeção)

Referência à variável inexistente 'payload.base_url' dentro de test_provider_key em app/services/llm.py:480 (cujo parâmetro real é 'base_url'), combinada com leitura exclusiva do banco em app/routers/settings.py:51-60.

**Arquivos e linhas afetados:**
- `app/services/llm.py:479-483`
- `app/routers/settings.py:51-60`
- `frontend/src/main.tsx:2367-2381`

## Passos para Reproduzir

1. Acessar `/settings` no frontend ou chamar `POST /api/settings/test` com `{"provider": "jina_proxy", "api_key": "segredo", "base_url": "https://worker.example.com"}`.
2. Caso `jina_proxy_url` esteja salva no banco, `test_provider_key` é chamado e falha na linha 480 com `NameError: name 'payload' is not defined`.
3. Caso `jina_proxy_url` ainda não esteja salva no banco, `settings.py:56` rejeita antes do teste com `jina_proxy_url não configurada`, impedindo o teste pré-salvamento.

## Escopo do Fix Sugerido (para `/reversa-debugger-fix`)

1. Em `app/services/llm.py:480`, remover `base_url = payload.base_url` e validar diretamente o parâmetro `base_url`.
2. Em `app/routers/settings.py:51-60`, usar `payload.base_url.strip()` e `payload.api_key.strip()` quando fornecidos, fazendo fallback para `runtime_jina_proxy(db)` apenas quando omitidos.
3. Em `frontend/src/main.tsx:2371-2374`, enviar `api_key: jinaProxyAuthKey` e `base_url: jinaProxyUrl || null` no payload do botão 'Testar Proxy'.

## Agent Notes

- **Origem:** Promovido de `F-SET-01` (`_reversa_bugs/modulo-briefing/inspections/depth-inspection-20261014/report.md`).
- **Severidade / Prioridade:** `critical` / `P0`.
- **Política de Fechamento (`closure.policy`):** `local-software` (requer correção validada por teste de regressão automatizado antes de transitar para `resolved`).
