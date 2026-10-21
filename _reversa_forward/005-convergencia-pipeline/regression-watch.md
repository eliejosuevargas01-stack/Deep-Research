# Regression watch — 005-convergencia-pipeline

Data de fechamento: 2026-10-21. Âncora: PRD + sdd/briefing, addenda 001–004 e diretrizes de convergência.
Feature 005 concluída com implementação validada e suítes 100% GREEN.

## Watch principal

| ID | Origem (arquivo, seção) | Regra esperada após mudança | Tipo de verificação | Sinal de violação |
|---|---|---|---|---|
| W001 | `app/investigation/tools.py` (RF-501 / RN-501) | Coleta de 10 páginas integrais via Jina (`num=10`), parser HTML via `_JinaHTMLCleaner` (stdlib) e SSRF guard em URLs. | Unitário / Integração (`tests/investigation/test_jina_tool.py`) | Retorno < 10 páginas sem falha explícita, quebra por ReDoS ou bypass de SSRF. |
| W002 | `app/investigation/worker.py` (RF-502, RF-503 / RN-502, RN-503) | Orçamento de 1 a 3 queries por persona, primeira busca obrigatória antes da resposta final e citações comprovadas verbatim. | Unitário / Integração (`tests/investigation/test_persona_worker.py`) | Resposta sem busca prévia aceita, estouro de 3 queries ou citação não correspondente ao texto fonte. |
| W003 | `alembic/versions/0008_...`, `app/models/domain_models.py` (RF-503 / RN-504) | Colunas `investigation_round` em `research_points`, `round` em `research_step_results` e tabela `investigation_merges` com constraints únicas. | Migration (`tests/investigation/test_round_migration.py`) | Falha em migração limpa ou populada em PostgreSQL efêmero, perda de integridade relacional ou ausência de constraint única. |
| W004 | `app/investigation/storage.py` (RF-504, RF-506 / RN-504, RN-506) | Barreira atômica de 4 personas por ponto/rodada para gravação de `InvestigationMerge`. Falhas técnicas não incrementam `attempt_count` do ponto. | Armazenamento (`tests/investigation/test_round_storage.py`, `tests/investigation/test_round_lifecycle.py`) | Auditoria disparada com menos de 4 personas na rodada ou incremento de tentativa por erro de infraestrutura. |
| W005 | `app/audit/service.py` (RF-504, RF-505 / RN-504, RN-505) | Auditoria consome snapshot committed de merge sem corte de 60k; teto de 4 tentativas (`MAX_AUDIT_ATTEMPTS=4`); 4ª reprovação gera `AUDIT_CAVEAT`. | Auditoria (`tests/audit/test_audit_round_merge.py`, `tests/audit/test_audit_api.py`) | Agendamento de 5ª rodada de pesquisa, truncamento silencioso de texto ou veredito sem snapshot committed. |
| W006 | `app/services/pipeline/writer.py` (RF-506, RF-507 / RN-507) | Bundle unificado Evidence + InvestigationMerge sem truncamento arbitrário; guardrails aceitam seções de limitação e propostas conceituais sem URLs inventadas. | Writer (`tests/unit/test_pipeline_writer_convergence.py`) | Erro de contagem mínima de palavras em notas de limitação ou aceitação de URLs inline não constantes do bundle. |
| W007 | `app/services/research.py`, `app/investigation/service.py` (RF-508 / RN-508) | `run_research` atua como adaptador modular para `InvestigationService`; execução de lotes topológicos (`ready_point_batches`); CAS WRITE com sessão fechada antes de LLM. | Integração (`tests/investigation/test_round_lifecycle.py`, `tests/integration/test_pipeline_convergence_http.py`) | Lock de banco durante inferência de LLM, ordem DAG desrespeitada ou concorrência descontrolada entre pontos. |
| W008 | `app/briefing/router.py`, `app/briefing/service.py` (RF-509 / RN-509) | Briefing síncrono e decisão única: POST 201 gerado, PATCH 200 revisado e autoaprovado, investigate 202 exclusivo; repetição retorna 409 Conflict. | API HTTP (`tests/test_briefing_*.py`) | Retorno 202 com polling assíncrono para criação de briefing ou criação de rotas alternativas de approve. |
| W009 | `app/routers/research.py` (RF-508 / RN-510) | Compatibilidade legada, consulta GET `/api/reports/{id}` e `/retry-callback` sem duplicar relatório nem alterar status `DONE`. | E2E HTTP (`tests/integration/test_full_pipeline.py`, `tests/integration/test_pipeline_convergence_http.py`) | Regeneração ou duplicação de `Report` em retry-callback ou falha na consulta de relatórios gerados. |

## Observações — sem peso de regressão

- O001: Tema 3–300, pontos 3–7 e aprovação não reaberta mantêm conformidade estrita com sdd/briefing §3.
- O002: Requisitos RF-501..509 e não-funcionais RN-501..510 plenamente comprovados por testes automatizados em runner isolado (172 passed, 162 subtests passed).
- O003: Validação de ciclo PostgreSQL efêmero executada via Docker sem impacto no ambiente de produção.
- O004: Todos os 4 arquivos protegidos do repositório (`app/routers/research.py`, `frontend/src/api.ts`, `frontend/src/main.tsx`, `frontend/src/research-utils.ts`) tiveram seus hashes SHA-256 preservados intactos.

## Histórico de re-extrações

- 2026-10-21: Fechamento final pós-implementação e auditorias S28/S29.

## Arquivadas

Nenhum item arquivado. Todos os 9 watches W001..W009 encontram-se ativos e cobertos pela suíte permanente de testes.
