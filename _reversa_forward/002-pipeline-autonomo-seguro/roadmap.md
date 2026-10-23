# Roadmap: Pipeline Autônomo Seguro

> Identificador: `002-pipeline-autonomo-seguro`
> Data: `2026-10-22`
> Requisitos: `_reversa_forward/002-pipeline-autonomo-seguro/requirements.md`

## 1. Decisões Técnicas

- **DT-01 (Segurança por API Key via FastAPI Dependency):** Implementar dependência assíncrona `verify_api_key` em `app/core/security.py`. Lê o header `X-API-Key` ou `Authorization: Bearer`. Resolve `API_SECRET_KEY` via `resolve_key(db, "API_SECRET_KEY")`. Se configurada, compara via `secrets.compare_digest`. Aplica como dependência global nas rotas `/api/v1/*` (exceto `/health`).
- **DT-02 (Modelo e Migração da Tabela Pesquisa):** Adicionar colunas `status_pipeline TEXT NOT NULL DEFAULT 'planejado'` e `erro_pipeline TEXT` na tabela `pesquisa` em `app/db/models.py`.
- **DT-03 (Serviço de Orquestração Contínua - PipelineRunner):** Implementar `PipelineRunner` em `app/core/pipeline_runner.py`. Encapsula o ciclo completo:
  - Loop de Busca (`Searcher`) + Auditoria (`Auditor`).
  - Controle de retries até aprovação ou teto de 4 tentativas / 3 reprovações.
  - Invocação do Redator (`Writer`) com evidências integrais.
  - Atualização do `status_pipeline` e persistência do dossiê.
- **DT-04 (Endpoint Assíncrono com BackgroundTasks):** Adicionar suporte a `async_execute: bool = False` e `callback_url: Optional[str] = None` em `PlanRequest`. Se `async_execute=True`, dispara `background_tasks.add_task(runner.run, id_pesquisa, callback_url)` e devolve `HTTP 202 Accepted`.
- **DT-05 (Configurações Dinâmicas de Webhook):** Incluir chaves permitidas `CALLBACK_WEBHOOK_URL` e `WEBHOOK_HMAC_SECRET` no repositório de credenciais e schemas de administração.

## 2. Fases de Execução

1. **Fase 1: Segurança e Autenticação por API Key**
   - Criação de `app/core/security.py` e testes unitários.
   - Integração no router `/api/v1/router.py`.
2. **Fase 2: Modelo de Dados e Configurações**
   - Migração das colunas `status_pipeline` e `erro_pipeline` em `pesquisa`.
   - Suporte a credenciais de webhook nas configurações.
3. **Fase 3: Orquestrador Contínuo (PipelineRunner)**
   - Implementação de `PipelineRunner` em `app/core/pipeline_runner.py`.
   - Testes unitários do runner com mocks.
4. **Fase 4: Endpoints e BackgroundTasks**
   - Atualização de `app/schemas/plan.py` com `async_execute` e `callback_url`.
   - Atualização de `app/api/v1/endpoints/plan.py` com `BackgroundTasks`.
   - Endpoint de status `GET /api/v1/pipeline/{id_pesquisa}/status`.
5. **Fase 5: Testes de Integração e Validação no Container**
   - Suíte de testes unitários e de integração passando 100%.
   - Sincronização e teste real no container Docker.
