# Actions: Pipeline Autônomo Seguro

> Identificador: `002-pipeline-autonomo-seguro`
> Data: `2026-10-22`
> Roadmap: `_reversa_forward/002-pipeline-autonomo-seguro/roadmap.md`

## Resumo

| Métrica | Valor |
|---------|-------|
| Total de ações | 10 |
| Concluídas | 10 |
| Em aberto | 0 |
| Paralelizáveis (`[//]`) | 5 |

## Ações Atômicas

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T001 | Implementar middleware/dependency de segurança `verify_api_key` em `app/core/security.py` com checagem via `X-API-Key` / Bearer token, suporte a timing-safe `secrets.compare_digest` e resolução dinâmica via banco ou ENV. | - | `[//]` | `app/core/security.py` | 🟢 | `[X]` |
| T002 | Adicionar testes unitários em `tests/unit/test_security.py` cobrindo requisições sem API key, com chave correta e com chave incorreta (HTTP 401). | T001 | `[//]` | `tests/unit/test_security.py` | 🟢 | `[X]` |
| T003 | Atualizar modelo relacional `Pesquisa` em `app/db/models.py` e `app/db/research_repository.py` adicionando `status_pipeline` e `erro_pipeline`, aplicando migração segura na base SQLite permanente. | - | - | `app/db/models.py` | 🟢 | `[X]` |
| T004 | Garantir suporte formal das credenciais `CALLBACK_WEBHOOK_URL` e `WEBHOOK_HMAC_SECRET` em `app/services/credential_resolver.py` e `app/api/v1/endpoints/admin.py`. | T003 | `[//]` | `app/services/credential_resolver.py` | 🟢 | `[X]` |
| T005 | Implementar o orquestrador `PipelineRunner` em `app/core/pipeline_runner.py` gerenciando o ciclo completo contínuo (busca -> auditoria -> retries automáticos -> redação -> webhook assinado). | T003, T004 | - | `app/core/pipeline_runner.py` | 🟢 | `[X]` |
| T006 | Atualizar `app/schemas/plan.py` adicionando os campos `async_execute: bool = False` e `callback_url: Optional[str] = None` em `PlanRequest`, e status 202 com `PlanAsyncResponse`. | - | `[//]` | `app/schemas/plan.py` | 🟢 | `[X]` |
| T007 | Atualizar endpoint `POST /api/v1/plan` em `app/api/v1/endpoints/plan.py` integrando `BackgroundTasks` para disparo assíncrono do `PipelineRunner` quando `async_execute=True`. | T005, T006 | - | `app/api/v1/endpoints/plan.py` | 🟢 | `[X]` |
| T008 | Criar endpoint `GET /api/v1/pipeline/{id_pesquisa}/status` em `app/api/v1/endpoints/pipeline.py` para consulta de progresso em tempo real da pesquisa contínua. | T005, T007 | `[//]` | `app/api/v1/endpoints/pipeline.py` | 🟢 | `[X]` |
| T009 | Proteger as rotas sob `/api/v1` em `app/api/v1/router.py` injetando a dependência `verify_api_key`. | T001, T007, T008 | - | `app/api/v1/router.py` | 🟢 | `[X]` |
| T010 | Criar testes de integração automatizados em `tests/integration/test_pipeline_autonomo.py` validando o fluxo contínuo plan -> webhook assinado e a autenticação protegida. | T009 | - | `tests/integration/test_pipeline_autonomo.py` | 🟢 | `[X]` |
