# Requisitos: Pipeline Autônomo Seguro com Webhook de Callback e Autenticação por API Key

> Identificador: `002-pipeline-autonomo-seguro`
> Data de Início: `2026-10-22`
> Status: `requirements`
> Origem: Solicitação do usuário para execução autônoma contínua e proteção de endpoints.

## 1. Visão Geral e Objetivo

Esta feature estende o monólito Deep Research para permitir que o usuário inicie uma pesquisa fornecendo apenas o tema (ou parâmetros adicionais) no endpoint de planejamento e receba o dossiê executivo completo e auditado diretamente em seu Webhook de Callback configurado, sem necessidade de orquestração manual passo a passo no n8n ou frontend. Além disso, introduz proteção de segurança por Chave de API (`X-API-Key`) em todos os endpoints da aplicação e gerenciamento dinâmico da URL e segredo de callback nas credenciais do sistema.

## 2. Requisitos Funcionais (RF)

- **RF-01 (Webhook de Callback Configurável):** O sistema deve permitir o cadastro, atualização e leitura mascarada das variáveis `CALLBACK_WEBHOOK_URL` e `WEBHOOK_HMAC_SECRET` através do endpoint de credenciais (`POST /api/v1/admin/credentials`), com precedência de variáveis de ambiente quando presentes (RN-10).
- **RF-02 (Autenticação por API Key):** Todas as rotas sob `/api/v1/*` devem exigir autenticação via header `X-API-Key` (ou `Authorization: Bearer <chave>`) validada contra a chave mestra `API_SECRET_KEY` (configurada via env ou banco cifrado). Se nenhuma `API_SECRET_KEY` estiver configurada, a API opera em modo aberto/desenvolvimento. Rotas `/health`, `/docs` e `/openapi.json` devem permanecer públicas.
- **RF-03 (Rejeição de Acesso Não Autorizado):** Caso `API_SECRET_KEY` esteja ativa e a requisição contenha chave ausente ou divergente, o sistema deve responder com HTTP 401 Unauthorized (`{"detail": "Chave de API ausente ou inválida"}`).
- **RF-04 (Endpoint de Continuidade / Pipeline Assíncrono):** Disponibilizar o parâmetro opcional `"async_execute": true` no `POST /api/v1/plan` (e/ou endpoint dedicado `POST /api/v1/pipeline/execute`). Quando ativo, a requisição planeja a pesquisa e dispara o ciclo completo em segundo plano (`BackgroundTasks`), retornando imediatamente `HTTP 202 Accepted` com `id_pesquisa`, `status: "iniciado"` e `mensagem`.
- **RF-05 (Loop de Execução Autônoma em Segundo Plano):**
  1. Executa a busca com as 4 personas em paralelo (`Searcher`) e deduplicação de URLs.
  2. Executa a auditoria das evidências acumuladas (`Auditor`) com checklist e sarrafo de 85%.
  3. Em caso de reprovação, aciona nova rodada de busca com as lacunas apontadas (até o limite de 4 passagens de busca / 3 reprovações).
  4. Quando aprovado (ou esgotado o teto), executa a redação (`Writer`) com leitura 100% integral das rodadas.
  5. Despacha o Dossiê Final assinado via HMAC-SHA256 para `CALLBACK_WEBHOOK_URL`.
- **RF-06 (Rastreamento de Estado do Pipeline):** A tabela `pesquisa` deve registrar a coluna `status_pipeline` ("planejado", "buscando", "auditando", "redigindo", "concluido", "falha") e registrar o erro detalhado em `erro_pipeline` caso ocorra falha fatal.
- **RF-07 (Raciocínio Máximo Nativo):** Todas as etapas do pipeline continuam operando com capacidade analítica profunda e rigor metodológico.

## 3. Requisitos Não-Funcionais (RNF)

- **RNF-01 (Validação em Tempo Constante):** A verificação da API Key deve usar `secrets.compare_digest` para prevenir ataques de temporização (timing attacks).
- **RNF-02 (Não Bloqueio do Event Loop):** O background worker deve utilizar tarefas assíncronas nativas do FastAPI/asyncio sem travar a porta 8000.
- **RNF-03 (Resiliência do Webhook):** Falha no envio do webhook não descarta o dossiê final persistido no SQLite.

## 4. Cenários de Aceitação (Gherkin)

```gherkin
Cenário: Proteção de endpoint com API Key válida
  Dado que a API_SECRET_KEY "secret-token-123" está configurada
  Quando uma requisição POST /api/v1/plan é enviada com header X-API-Key "secret-token-123"
  Então a resposta deve ter código HTTP 201

Cenário: Rejeição de endpoint com API Key inválida
  Dado que a API_SECRET_KEY "secret-token-123" está configurada
  Quando uma requisição POST /api/v1/plan é enviada com header X-API-Key "chave-errada"
  Então a resposta deve ter código HTTP 401
  E a mensagem de detalhe deve indicar chave inválida

Cenário: Disparo de pipeline assíncrono contínuo até webhook
  Dado um tema válido e async_execute habilitado
  Quando o cliente envia POST /api/v1/plan
  Então o status retornado imediatamente é HTTP 202 Accepted
  E o pipeline executa em background: busca, auditoria e redação
  E o webhook de callback configurado recebe o evento "research.completed" com o dossiê final
```
