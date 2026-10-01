# Deep Research Engine - Inviolable Contracts

## 1. Tenant Isolation Contract

* Toda pesquisa é isolada por um `research_id` (UUID) que atua como tenant ID.
* Nenhuma query ao DB é feita sem incluir o `research_id` no escopo do filtro.
* Acesso entre pesquisas é proibido pelo ORM — queries sempre usam `WHERE research_id = :current`.

## 2. Security / Credential Handling Contract

* Todos os segredos (API Keys, Bearer Token, DB URI) são carregados exclusivamente via Pydantic `Settings` a partir do `.env`.
* **Nunca** persistir credenciais reais no DB: apenas metadados de uso (`source_provider`, `request_id`).
* Autenticação Bearer Token é validada em middleware antes de qualquer consumo de CPU, LLM ou DB.
* Em caso de token inválido, a requisição é abortada com **HTTP 401 Unauthorized** antes mesmo de tocar a camada de orquestração.

## 3. Compatibility Contract (Must Not Change)

* O schema de entrada do endpoint `POST /api/research` deve ser retrocompatível: `tema` e `callback_url` são os campos obrigatórios.
* O formato de saída do relatório final (`Report.content_markdown`) é uma string Markdown — não pode ser alterado sem bump de versão da API.
* Nenhuma fase posterior do pipeline (Auditor, Redator) pode adicionar novos pontos ou alterar o `theme` original definido pelo usuário no *Briefing*.

## 4. Configuration-Ownership Contract

* **Authoritative Source (config):** O único lugar para providers de LLM, URLs de scraping e chaves é `.env`, carregado no singleton `Settings`.
* **Allowed migration/import paths:** `config.toml` do Reversa (se existir) pode sobrepor `[models]` e `[providers]`, mas não sobrescrever secrets.
* **Override precedence:** `.env.local` > `.env` > `config.toml`.
* **No hardcoding de endpoints ou chaves de API em nenhum arquivo Python.**
* Toda alteração na configuração de providers requer reinício do servidor.

## 5. Protocol Compliance Contract

* O *Subfluxo de Busca* deve usar os mesmos formatos de request/response esperados por SerpAPI (`{q, num}`, `{results: [{title, link, snippet}]}`) e Jina Reader (`GET https://r.jina.ai/<URL>` → texto limpo).
* O *Unified Search Subflow* deve unir e limpar respostas de 5 a 10 páginas em um único bloco Markdown sanitizado.

## 6. UX / Operator Experience Contract

* O chamador nunca lida com OAuth, webhooks internos, ou configurações técnicas.
* A interação com o operador é reduzida a:
  1. Envio do `POST /api/research` (tema + callback).
  2. Aprovação única da pré-visão de pontos (via `POST /api/briefing/approve/{id}`).
  3. Consulta do relatório final (`GET /api/reports/{id}`).

## 7. Testing Contract

* Testes de integração cobrindo:
  * Caminho feliz: submissão → aprovação → 3 workers simulados → auditoria aprovada → redação.
  * Caso de rejeição auth (401).
  * Caso de *blocker* (3 tentativas sem aprovação).
  * Verificação de links de fontes na saída do redator.

## 8. Race Condition / Concurrency Contract

* O pool de workers usa `asyncio.gather` (concorrência, não paralelismo de thread).
* Gravação de evidências usa *Optimistic Locking* (`version` column). Em caso de conflito, a atualização é revertida e o worker reenvia a coleta.
* A fase de auditoria para um ponto só inicia quando `len(completed_workers) == 4`.

## 9. Rollback Contract

* Em caso de falha no callback webhook:
  1. Registrar em `AuditTrail` o erro com timestamp.
  2. Marcar status do `Research` para `completed_but_callback_failed`.
  3. O `Report` está sempre persistido no DB antes do envio.
  4. Fornecer endpoint `/api/callback/retry/{id}` para despacho manual.

## 10. Data Lifecycle / Cleanup Contract

* Evidências de pesquisas concluídas são mantidas por **90 dias**.
* Logs de execução dos workers (brutos) são purgados automaticamente a cada 48h.
* Relatórios aprovados são mantidos indefinidamente.
* Em caso de *blocker*, os dados são preservados para auditoria humana e marcados com `status = blocked` + notas de auditoria no `AuditTrail`.
