# Impacto da Feature 002: Pipeline Autônomo Seguro

> Identificador: `002-pipeline-autonomo-seguro`
> Data: `2026-10-22`
> Cenário: greenfield

## Resumo das Modificações

1. **Segurança por API Key (`app/core/security.py`, `app/api/v1/router.py`):**
   - Dependência `verify_api_key` adicionada globalmente no `api_router`.
   - Rotas protegidas contra acesso indevido se `API_SECRET_KEY` estiver configurada.
   - Rotas públicas preservadas (`/health`, `/docs`).
2. **Continuidade Assíncrona e Orquestrador (`app/core/pipeline_runner.py`, `app/api/v1/endpoints/plan.py`):**
   - Suporte ao parâmetro `"async_execute": true` no `POST /api/v1/plan`.
   - `PipelineRunner` orquestra busca, auditoria cumulativa, retentativas automáticas e redação sem intervenção externa.
3. **Consulta de Status em Tempo Real (`app/api/v1/endpoints/pipeline.py`):**
   - Rota `GET /api/v1/pipeline/{id_pesquisa}/status` exposta.
4. **Resolução de Webhook de Callback nas Configurações (`app/services/credential_resolver.py`):**
   - Suporte dinâmico a `CALLBACK_WEBHOOK_URL` e `WEBHOOK_HMAC_SECRET`.

## Testes Automatizados

- 78 testes passando com 100% de sucesso (`pytest`).
