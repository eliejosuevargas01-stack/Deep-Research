---
schema_version: 1
id: BUG-20261006-57LI
display_number: 2
context: settings
title: "Impossível configurar URL/chave do Cloudflare Worker proxy Jina (frontend Settings e backend não expõem jina_base_url)"
status: fixed
phase: fixed
severity: medium
priority: P2
security_suspected: false
visibility: public
area:
  - settings
  - frontend
module:
  - settings-router
  - research-ui
  - search-pipeline
feature: llm-gateway-fallback
origin:
  type: manual-report
  external_ref: "app/CRITERIA.md#modo-jina-proxy"
reported_by: "user (produção)"
reported_at: "2026-10-06T00:55:00-03:00"
environment:
  app: deep-research (research.dominuslabs.online)
  backend_image: "j0kvxhooxnusvlyoascewxvw_backend:9c8ded032efbf378ea0917bced296751b82af47c"
traceability:
  specs:
    - "app/CRITERIA.md#modo-jina-proxy"
    - "app/CRITERIA.md#A7-configuracoes"
  expected_behavior: |
    Página de Configurações deve permitir cadastrar URL base do Cloudflare
    Worker/relay Jina + segredo de autenticação do Worker. O pipeline de busca
    (search_pipeline.py, search.py) deve usar essa URL em vez de hardcoded
    https://r.jina.ai/. Pool de keys/rotação pertence ao Worker, não ao Deep Research.
  affected_code:
    - "app/services/settings.py:22-30" # PROVIDER_BASE_URLS declara jina_base_url mas update_settings não persiste
    - "app/services/settings.py:296-305" # public_settings não expõe jina_base_url
    - "app/services/settings.py:311-351" # update_settings não aceita jina_base_url
    - "app/tools/search_pipeline.py:71,204" # r.jina.ai hardcoded
    - "app/services/search.py:71,204" # r.jina.ai hardcoded
    - "app/schemas/__init__.py:75-113" # SettingsUpdate sem jina_base_url
    - "app/models/domain_models.py:124" # AppSettings só tem openai_base_url
    - "frontend/src/main.tsx:2225" # campo jina só pede API key, sem URL
    - "alembic/versions/0003_settings_callback_and_base_url.py" # migration só criou openai_base_url
  tests_existing: []
labels:
  - spec-gap-code
  - settings
  - jina-proxy
  - cloudflare-worker
  - ssrf-surface
relations:
  - type: related-to
    target: BUG-20261005-7H2K
    state: proposed
    note: "Ambos envolvem resiliência de infra externa (LLM gateway / Jina) sem superfície de configuração adequada."
express: false
---

# Resumo
Usuário não consegue, em lugar nenhum do frontend, configurar a URL nem a chave API do seu Cloudflare Worker/proxy para o Jina. A página de Configurações só expõe campo de API key por provedor (para `jina`, apenas a key), sem campo de URL base. Investigação revelou que o gap não é só frontend: o backend declara `jina_base_url` em `PROVIDER_BASE_URLS` mas nunca persiste, expõe ou consome esse valor.

# Esperado vs Observado
- **Esperado** (CRITERIA.md#modo-jina-proxy): usuário configura URL base do Worker + segredo; pipeline usa essa URL no lugar de `https://r.jina.ai/`; pool de keys/rotação/failover fica no Worker.
- **Observado**:
  1. Frontend Settings: campo `jina` só pede API key (`main.tsx:2225`).
  2. Backend `SettingsUpdate` schema não tem `jina_base_url` (`app/schemas/__init__.py:75`).
  3. `update_settings()` não aceita nem persiste `jina_base_url` (`app/services/settings.py:311`).
  4. `AppSettings` não tem coluna `jina_base_url` (só `openai_base_url`, migration 0003) — `PROVIDER_BASE_URLS["jina"]` aponta para campo inexistente.
  5. `search_pipeline.py:71,204` e `search.py:71,204` montam URLs `https://r.jina.ai/...` hardcoded, nunca consultam settings.

# Passos para reproduzir
1. Logar no frontend → Settings.
2. Observar que não há campo para URL do Cloudflare Worker Jina.
3. Tentar via API `PUT /settings` com `jina_base_url` no payload → rejeitado (campo desconhecido/ignorado).
4. Rodar research → `search_pipeline.py` chama `https://r.jina.ai/` direto.

# Frequência
Determinístico. Sempre presente; funcionalidade simplesmente não existe.

# Evidências
- `evidence/screenshot-settings.png` — tela Settings atual (card "Chave OpenAI" apenas).
- Análise de código: itens 1 a 5 acima, todos verificados nesta sessão via leitura direta dos arquivos.

# Escopo do fix sugerido (para o /reversa-debugger-fix)
1. Migration 0004: coluna `jina_base_url` em `app_settings` (String 2048, nullable).
2. `SettingsUpdate` + `update_settings()` + `public_settings()`: campo `jina_base_url` com `validate_base_url` (SSRF guard já existente).
3. `search_pipeline.py` + `search.py`: ler `jina_base_url` do runtime settings; fallback `https://r.jina.ai/` quando vazio. Enviar `Authorization: Bearer <jina_key>` quando key configurada (Worker valida seu próprio segredo).
4. Frontend `main.tsx`: campo URL + API key para Jina (padrão do campo `openai_base_url` já existente).

# Agent Notes
- `spec-gap` invertido: spec CRITERIA.md#modo-jina-proxy EXISTE e é clara; o código nunca implementou. Labels: spec-gap-code.
- Superfície SSRF nova: `jina_base_url` é URL configurável pelo admin → deve passar pelo mesmo `validate_base_url` que `openai_base_url` usa (já coberto pelo plano do fix).
- Severidade `medium`: sem isso, usuário não pode usar seu proxy Worker e fica preso ao `r.jina.ai` público (rate-limit/sem key própria).
- Relação `related-to` com BUG-20261005-7H2K: proposta, não confirmada.


# Fix Aplicado (2026-10-06, /reversa-debugger-fix)

- `alembic/versions/0004_jina_base_url.py` — nova migration
- `app/models/domain_models.py` — `AppSettings.jina_base_url`
- `app/schemas/__init__.py` — `SettingsUpdate.jina_base_url` + `validate_base_urls` (SSRF guard)
- `app/services/settings.py` — `public_settings` + `update_settings` + `runtime_jina_base_url`
- `app/routers/settings.py` — PUT /api/settings propagates `jina_base_url`
- `app/services/search.py` — `DEFAULT_JINA_BASE_URL`; `search`, `_duckduckgo_search`, `read_source`, `search_read` aceitam `jina_base_url`; `read_source` envia `Authorization: Bearer` quando key configurada
- `app/services/pipeline/scout.py` + `app/services/pipeline/worker.py` + `app/services/workers/base.py` — propagam `jina_base_url` de settings
- `frontend/src/types.ts` — `Settings.jina_base_url`
- `frontend/src/research-utils.ts` — `buildSettingsPayload.jina_base_url`
- `frontend/src/main.tsx` — campo "Proxy Jina via Cloudflare Worker" no settings, igual padrão `openai_base_url`

`app/tools/search_pipeline.py` permanece sem modificação: não é importado por ninguém (dead code) — separado como P3 "remover app/tools/search_pipeline.py" para futura limpeza.
