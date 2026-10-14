---
schema_version: 1
id: BUG-20261014-4B9F
display_number: 3
context: modulo-briefing
title: "POST /briefings/{research_id}/investigate retorna 404 em produção devido à ausência de deploy da Feature 002"
status: open
phase: triaging
severity: high
priority: P1
security_suspected: false
visibility: public
area:
  - research-pipeline
  - scout
module:
  - research-orchestrator
feature:
  - scout-discovery
  - deep-research-execution
origin:
  type: manual-report
  external_ref: "https://research.dominuslabs.online/briefings"
reported_by: "user (produção)"
reported_at: "2026-10-14T02:30:00-03:00"
environment:
  app: deep-research (research.dominuslabs.online)
  backend_image: "j0kvxhooxnusvlyoascewxvw_backend:2e8809aabf0ff57ae8c17b8f9e610d7a044f54e4"
  database: postgres:16-alpine
traceability:
  specs:
    - "docs/api/investigation-personas.md#post-briefingsresearch_idinvestigate"
    - "_reversa_forward/002-investigacao-personas/requirements.md#rf-05"
  expected_behavior: |
    Após aprovação formal do briefing via POST /briefings/{research_id}/approve,
    a chamada POST /briefings/{research_id}/investigate deve retornar HTTP 202 Accepted
    e iniciar a investigação paralela das 4 personas por ponto analítico.
  observed_behavior: |
    POST /briefings/{research_id}/investigate retorna HTTP 404 Not Found ({"detail": "Not Found"}).
    O contêiner em produção está rodando imagem construída em 12/10/2026 (Feature 001),
    não contendo as rotas de investigação, a tabela research_step_results nem os módulos
    de personas integrados na branch main (commit 9c1cef1).
  affected_code:
    - "app/investigation/router.py:1"
    - "app/briefing/router.py:1"
    - "docker-compose.yml"
  tests_existing:
    - "tests/investigation/test_investigation_e2e.py"
    - "tests/investigation/test_investigation_runtime_regressions.py"
labels:
  - deploy-gap
  - production-smoke-test
  - feature-002
---

# BUG-20261014-4B9F — POST /briefings/{research_id}/investigate retorna 404 em produção

## Descrição do Defeito

Durante o teste real em produção solicitado pelo usuário no domínio `https://research.dominuslabs.online`, o fluxo de briefing demonstrou funcionamento parcial:

1. **Briefing (`POST /briefings`):** Funciona perfeitamente. O Scout consulta Jina e OpenAI ao vivo, extraindo 5 pontos técnicos coerentes e retornando HTTP 201 com status `draft`.
2. **Aprovação (`POST /briefings/{id}/approve`):** Funciona perfeitamente. Retorna HTTP 200 e avança status para `approved`.
3. **Início da Pesquisa (`POST /briefings/{id}/investigate`):** Falha com **HTTP 404 Not Found**.

## Causa Raiz

O serviço de produção gerenciado pelo Coolify está executando o contêiner `backend-j0kvxhooxnusvlyoascewxvw-20261012T162645` compilado em 12 de outubro de 2026. As rotas da Feature 002 (`/briefings/{research_id}/investigate`), a migração Alembic `0007_investigation_step_results_and_status` e a integração com as 4 personas paralelas foram finalizadas e commitadas na branch `main` (`9c1cef1`), mas **não foram submetidas ao build/deploy de produção no Coolify**.

Adicionalmente, na versão em execução em produção, `BriefingRecord` é isolado e não cria linha correspondente na tabela `Research`, o que impede o início da pesquisa por essa via até que o deploy da Feature 002 seja aplicado.

## Passos para Reproduzir

1. Enviar requisição autenticada:
   ```bash
   curl -X POST https://research.dominuslabs.online/briefings \
     -H "Authorization: Bearer <API_AUTH_SECRET>" \
     -H "Content-Type: application/json" \
     -d '{"theme": "Impacto da IA na Medicina"}'
   ```
2. Aprovar briefing retornado:
   ```bash
   curl -X POST https://research.dominuslabs.online/briefings/<research_id>/approve \
     -H "Authorization: Bearer <API_AUTH_SECRET>"
   ```
3. Chamar investigate:
   ```bash
   curl -X POST https://research.dominuslabs.online/briefings/<research_id>/investigate \
     -H "Authorization: Bearer <API_AUTH_SECRET>"
   ```
   **Resultado:** `HTTP 404 Not Found`.

## Ação Recomendada

1. Executar trigger de redeploy no Coolify para a aplicação `deep-researchmain-b7f1fpvfc8lyepurn1kgza5y` a partir do commit `origin/main` (`9c1cef1`).
2. Garantir execução automática de `alembic upgrade head` no entrypoint do contêiner para criar a tabela `research_step_results` e atualizar os tipos de status.
