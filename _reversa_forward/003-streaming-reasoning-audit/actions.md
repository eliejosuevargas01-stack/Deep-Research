# Actions: Streaming Universal e Captura de Reasoning para Auditoria

> Identificador: `003-streaming-reasoning-audit`
> Data: `2026-10-22`
> Roadmap: `_reversa_forward/003-streaming-reasoning-audit/roadmap.md`

## Resumo

| Métrica | Valor |
|---------|-------|
| Total de ações | 10 |
| Concluídas | 0 |
| Em aberto | 10 |
| Paralelizáveis (`[//]`) | 4 |

## Ações Atômicas

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T001 | Atualizar `LLMClient` em `app/tools/llm_client.py` para forçar `stream=True` por padrão em todas as chamadas e fornecer métodos que retornam `(content, reasoning_content)`. | - | `[//]` | `app/tools/llm_client.py` | 🟢 | `[X]` |
| T002 | Atualizar `MockNetwork` em `tests/mocks/http_mock.py` para suportar streaming simulado com `content` e `reasoning_content`. | T001 | `[//]` | `tests/mocks/http_mock.py` | 🟢 | `[X]` |
| T003 | Atualizar modelos SQLAlchemy em `app/db/models.py` adicionando as colunas `reasoning_dossier` em `Pesquisa`, `reasoning_planejamento` e `reasoning_auditoria` em `Ponto`, e `reasoning_coleta` em `ConteudoColetado`. | - | - | `app/db/models.py` | 🟢 | `[X]` |
| T004 | Executar migração segura no SQLite persistente `/root/projects/deep-research/data/deep_research.db` via `ALTER TABLE` para as novas colunas de reasoning. | T003 | - | `data/deep_research.db` | 🟢 | `[X]` |
| T005 | Atualizar `ResearchRepository` em `app/db/research_repository.py` com suporte à gravação e leitura dos campos de reasoning. | T003, T004 | - | `app/db/research_repository.py` | 🟢 | `[X]` |
| T006 | Atualizar `Planner` em `app/core/planner.py` e schemas em `app/schemas/plan.py` para capturar e expor `reasoning_planejamento`. | T001, T005 | `[//]` | `app/core/planner.py` | 🟢 | `[X]` |
| T007 | Atualizar `Searcher` em `app/core/searcher.py` e schemas em `app/schemas/search.py` para capturar e persistir `reasoning_coleta` das personas. | T001, T005 | - | `app/core/searcher.py` | 🟢 | `[X]` |
| T008 | Atualizar `Auditor` em `app/core/auditor.py` e schemas em `app/schemas/audit.py` para capturar e persistir `reasoning_auditoria`. | T001, T005 | - | `app/core/auditor.py` | 🟢 | `[X]` |
| T009 | Atualizar `Writer` em `app/core/writer.py`, `WebhookClient` em `app/services/webhook_client.py`, schemas em `app/schemas/writer.py` e `PipelineRunner` em `app/core/pipeline_runner.py` para salvar e despachar `reasoning_dossier`. | T001, T005 | - | `app/core/writer.py` | 🟢 | `[X]` |
| T010 | Executar suíte completa de testes (`pytest`), sincronizar no container ativo na porta 8085 e validar em execução live. | T001-T009 | - | `tests/` | 🟢 | `[X]` |
