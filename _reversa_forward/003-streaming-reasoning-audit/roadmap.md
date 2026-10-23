# Roadmap: Suporte a Streaming Universal e Captura de Reasoning para Auditoria

> Identificador: `003-streaming-reasoning-audit`
> Data: `2026-10-22`
> Requisitos: `_reversa_forward/003-streaming-reasoning-audit/requirements.md`

## Fases de Implementação

### Fase 1: Suporte Universal a Streaming e Reasoning no LLMClient
- Suportar `stream=True` de ponta a ponta em `chat_completion_message`, suportando agregação de `content`, `reasoning_content` e `tool_calls`.
- Implementar suporte em `LLMClient.chat_completion_with_reasoning` ou retorno de tupla `(content, reasoning)`.
- Atualizar mock de transporte para suportar emissão SSE de testes ou compatibilidade garantida.

### Fase 2: Evolução do Esquema Relacional e Repositório
- Migração no SQLite:
  - `ALTER TABLE pesquisa ADD COLUMN reasoning_dossier TEXT;`
  - `ALTER TABLE pontos ADD COLUMN reasoning_planejamento TEXT;`
  - `ALTER TABLE pontos ADD COLUMN reasoning_auditoria TEXT;`
  - `ALTER TABLE conteudo_coletado ADD COLUMN reasoning_coleta TEXT;`
- Atualização em `app/db/models.py` e `app/db/research_repository.py`.

### Fase 3: Integração nos Domínios e Schemas
- **Planner:** Captura `reasoning_planejamento` e grava no ponto.
- **Searcher:** Captura `reasoning` das 4 personas e persiste em `conteudo_coletado.reasoning_coleta`.
- **Auditor:** Captura `reasoning_auditoria` do Step 5 e grava em `pontos.reasoning_auditoria`.
- **Writer:** Captura `reasoning_dossier` do Step 5 e grava em `pesquisa.reasoning_dossier`.
- **Schemas:** Adicionar campos `reasoning` nos schemas Pydantic correspondentes.

### Fase 4: PipelineRunner e Webhook de Entrega
- Atualizar `WebhookClient` e `PipelineRunner` para incluir `reasoning_dossier` no payload de entrega.
- Atualizar endpoints `/api/v1/plan`, `/api/v1/search`, `/api/v1/audit`, `/api/v1/writer` e `/api/v1/pipeline/{id}/status`.

### Fase 5: Validação, Testes Automatizados e Convergência
- Executar testes unitários e de integração (`pytest`).
- Atualizar container Docker na porta 8085 e testar chamada live.
