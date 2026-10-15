---
schema_version: 1
id: BUG-20261014-9D4E
display_number: 8
context: settings
title: "GET /api/settings/models aborta com HTTP 500 se qualquer provedor configurado falhar na listagem de catálogo"
status: closed
phase: closed
severity: high
priority: P1
security_suspected: false
visibility: internal
created: "2026-10-14T18:14:35-03:00"
updated: "2026-10-14T18:14:35-03:00"
area:
  - settings
  - frontend
module:
  - settings-router
  - llm-client
feature:
  - settings-management
  - llm-gateway-fallback
origin:
  type: depth-inspection
  external_ref: "_reversa_bugs/modulo-briefing/inspections/depth-inspection-20261014/report.md#f-set-02"
reported_by: "reversa-depth-inspection"
reported_at: "2026-10-14T18:14:35-03:00"
environment:
  app: deep-research
  branch: main
  commit: "582ed04abd3f03de8d38f8d162d1d945534e6b54"
traceability:
  specs:
    - "app/CRITERIA.md#f2-descoberta-de-modelos"
    - "app/CRITERIA.md#a7-configuracoes"
    - ".reversa/principles.md#iii-resiliencia-por-degradacao-graciosa-e-limites-rigidos"
  expected_behavior: |
    Ao carregar os catálogos de todos os provedores configurados (`GET /api/settings/models` sem filtro `provider`), a falha de um provedor individual (ex.: chave do `.env` expirada, HTTP 401/429 ou timeout) não deve derrubar a listagem dos demais provedores saudáveis.
  observed_behavior: |
    `get_provider_models` (`app/routers/settings.py:91-97`) chama `await list_provider_models(p, api_key, base_url)` em loop sem `try/except`. Como `list_provider_models` (`app/services/llm.py:578`) lança `RuntimeError` em qualquer erro HTTP ou de rede, uma única chave inválida/indisponível faz `GET /api/settings/models` responder HTTP 500 Internal Server Error, deixando todos os selects de modelos vazios na página de Configurações.
  affected_code:
    - "app/routers/settings.py:80-99"
    - "app/services/llm.py:504-578"
  tests_existing:
    - "tests/test_backend.py"
root_cause:
  summary: "Ausência de tratamento de exceção por provedor (`try/except Exception`) no loop `for p in target_providers:` em `app/routers/settings.py:91-97`."
  files:
    - "app/routers/settings.py:80-99"
    - "app/services/llm.py:504-578"
spec_verdict: compliant
resolution_kind: code-fix
closure:
  policy: local-software
  satisfied: true
change_set:
  - "app/routers/settings.py"
regression_tests:
  - "tests/test_bug_9d4e_settings_models.py"
labels:
  - graceful-degradation
  - model-discovery
  - http-500
  - settings
relations: []
express: false
---

# BUG-20261014-9D4E — GET /api/settings/models aborta com HTTP 500 se qualquer provedor configurado falhar na listagem de catálogo

## Resumo

Achado `F-SET-02` promovido a partir da inspeção profunda (`/reversa-depth-inspection`) realizada em 14/10/2026 sobre as features existentes do sistema Deep Research Engine.

## Esperado vs Observado

- **Esperado:** Ao carregar os catálogos de todos os provedores configurados (`GET /api/settings/models` sem filtro `provider`), a falha de um provedor individual (ex.: chave do `.env` expirada, HTTP 401/429 ou timeout) não deve derrubar a listagem dos demais provedores saudáveis.
- **Observado:** `get_provider_models` (`app/routers/settings.py:91-97`) chama `await list_provider_models(p, api_key, base_url)` em loop sem `try/except`. Como `list_provider_models` (`app/services/llm.py:578`) lança `RuntimeError` em qualquer erro HTTP ou de rede, uma única chave inválida/indisponível faz `GET /api/settings/models` responder HTTP 500 Internal Server Error, deixando todos os selects de modelos vazios na página de Configurações.

## Causa Raiz (Confirmada na Inspeção)

Ausência de tratamento de exceção por provedor (`try/except Exception`) no loop `for p in target_providers:` em `app/routers/settings.py:91-97`.

**Arquivos e linhas afetados:**
- `app/routers/settings.py:80-99`
- `app/services/llm.py:504-578`

## Passos para Reproduzir

1. Configurar uma chave `OPENAI_API_KEY` válida e uma chave `GEMINI_API_KEY` inválida (ou sem cota).
2. Chamar `GET /api/settings/models` (ou abrir `/settings` no navegador).
3. A requisição falha com HTTP 500 quando itera sobre `gemini`, descartando os modelos já obtidos de `openai`.

## Escopo do Fix Sugerido (para `/reversa-debugger-fix`)

Em `app/routers/settings.py:91-97`, envolver `await list_provider_models(p, api_key, base_url)` em `try/except Exception:` quando `provider is None`, degradando para `catalog[p] = []`. Na consulta de provedor específico (`provider is not None`), erros não são capturados e preservam exceções acionáveis.

## Agent Notes

- **Origem:** Promovido de `F-SET-02` (`_reversa_bugs/modulo-briefing/inspections/depth-inspection-20261014/report.md`).
- **Severidade / Prioridade:** `high` / `P1`.
- **Política de Fechamento (`closure.policy`):** `local-software` (requer correção validada por teste de regressão automatizado antes de transitar para `resolved`).
