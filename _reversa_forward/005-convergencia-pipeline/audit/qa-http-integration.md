# Relatório de QA: Integração Total, Regressões Finais e Matriz de Convergência (T029 / S29)

Data: 2026-10-21  
Feature: `005-convergencia-pipeline`  
Ação: T029 / S29  
Ambientes de execução: Runner isolado com SQLite in-memory/file-backed e container efêmero PostgreSQL 16 (`postgres:16-alpine` na porta 55432).  
Veredito Global: **🟢 APROVADO**

---

## 1. Resumo Executivo da Matriz de Testes

| Bloco de Testes | Suítes Executadas | Testes / Subtestes | Status | Duração |
|---|---|---|---|---|
| **Investigação & Workers** | `tests/investigation/` (jina_tool, persona_worker, round_storage, credential_dispatch, e2e, runtime_regressions) | 104 passed | 🟢 GREEN | 22.33s |
| **Auditoria & Merge CAS** | `tests/audit/` (test_audit_api, test_audit_round_merge) | 22 passed | 🟢 GREEN | 5.12s |
| **Writer & Guardrails** | `tests/unit/test_pipeline_writer_convergence.py` | 17 passed | 🟢 GREEN | 3.77s |
| **Briefing Síncrono** | `tests/test_briefing_*.py` (api, boundaries, lifecycle) | 23 passed, 162 subtests | 🟢 GREEN | 7.56s |
| **Integração HTTP End-to-End** | `tests/integration/` (test_pipeline_convergence_http, test_full_pipeline) | 2 passed | 🟢 GREEN | 6.27s |
| **PostgreSQL Efêmero** | `tests/investigation/test_round_migration.py` (clean, populated, downgrade, reupgrade) | 4 passed | 🟢 GREEN | 6.56s |
| **TOTAL CONSOLIDADO** | **Todas as suítes da matriz RF-501..509 / RN-501..510** | **172 passed, 162 subtests passed (0 failed, 0 skipped)** | **🟢 100% GREEN** | **51.61s** |

---

## 2. Validação da Matriz de Requisitos (RF-501..509 / RN-501..510)

### RF-501 / RN-501 (Jina Search Tool e Parser HTML)
- Validados 10 corpos integrais retornados sem corte arbitrário ou snippet substituto.
- Sanitização de HTML com `_JinaHTMLCleaner` (stdlib `HTMLParser`) removendo scripts, styles, iframes, nav, header e footer sem vulnerabilidade de ReDoS.
- SSRF guard (`_is_safe_url`) bloqueia endereços privados (RFC 1918), loopback, link-local e metadados de nuvem antes do dispatch.

### RF-502 / RN-502 (Orçamento de Buscas e Busca Obrigatória)
- Orçamento estrito de 1 a 3 queries por persona por ponto por rodada.
- Primeira busca comprovadamente obrigatória antes de qualquer resposta final da persona. Chamadas diretas de síntese no turno 1 são rejeitadas.

### RF-503 / RN-503 (Estrutura Factual e Citações Verbatim)
- Schemas estritos `CitationItem` e `WorkerResult` rejeitam respostas vazias ou strings de citação em branco.
- Citações exatas verificadas verbatim contra o texto limpo retornado pela Jina.

### RF-504 / RN-504 (Barreira das 4 Personas e Merge committed)
- Persistência das 4 análises válidas por ponto/rodada antes da liberação para auditoria.
- Gravação atômica da tabela `investigation_merges` (colunas `research_id`, `step_id`, `round`, `content`) com unicidade `uq_investigation_merges_step_round`.
- O auditor factual consome exclusivamente o snapshot committed de merge.

### RF-505 / RN-505 (Teto Inicial + 3 Retries de Auditoria)
- Orçamento máximo de 4 tentativas (`MAX_AUDIT_ATTEMPTS = 4`).
- Quarta reprovação pelo auditor factual não agenda 5ª rodada de investigação: transiciona o ponto para `AUDIT_CAVEAT` (`is_caveat=True`) e encaminha ao Writer com notas de limitação.

### RF-506 / RN-506 (Isolamento de Falhas Técnicas)
- Falhas de infraestrutura, rate limit ou timeout na execução de uma persona gravam `status="FAILED"`, mas preservam `attempt_count` do ponto em 0.
- O orçamento de tentativas de auditoria é decrementado apenas por vereditos explícitos `SCRAPER_RETRY` emitidos pelo auditor factual.

### RF-507 / RN-507 (Writer Flexível e Guardrail Anti-Alucinação)
- Removido o piso fixo de 200 palavras por seção de ponto.
- Avisos explícitos de limitação de evidência (`_LIMITATION_PATTERNS`) e propostas conceituais (`_is_nonfactual_proposal`) não exigem citações forçadas.
- Afirmações empíricas sem citação em qualquer formato (prosa, bullet, tabela, negrito) continuam barradas com `RuntimeError`.
- URLs citadas devem pertencer estritamente a URLs conhecidas no bundle (`Evidence` + `InvestigationMerge`).

### RF-508 / RN-508 (Convergência do Pipeline e Adaptador Modular)
- `run_research` atua como adaptador modular transparente delegando a orquestração a `InvestigationService`.
- Execução por lotes topológicos (`ready_point_batches`) respeitando árvores de dependência entre pontos.
- Transição atômica via CAS para o status `WRITE` quando todos os pontos atingem estados conclusivos (`AUDIT_APPROVED`, `AUDIT_CAVEAT`).
- Sessão de banco fechada antes de acionar a LLM do Writer.
- Persistência de um único registro `Report` e transição definitiva para `DONE`.

### RF-509 / RN-509 (Briefing Síncrono e Decisão Única)
- POST `/briefings` retorna 201 com o briefing totalmente persistido (sem polling assíncrono).
- PATCH `/briefings/{id}` revisa e autoaprova síncronamente.
- POST `/briefings/{id}/investigate` inicia investigação exclusiva em background com 202.
- Revisão repetida ou chamada duplicada retorna 409 Conflict. Nenhuma rota de aprovação redundante criada.

### RN-510 (Segurança Outbound e Idempotência de Callbacks)
- Sessão browser proíbe `callback_url` com 422.
- B2B valida URL pública com SSRF guard.
- Endpoint `/api/reports/{id}/retry-callback` executa entrega sem regerar nem duplicar o registro `Report`.

---

## 3. Validação de Migração em Banco PostgreSQL Efêmero
- Container Docker temporário `postgres:16-alpine` na porta 55432.
- Ciclo de vida verificado:
  - Base limpa: `alembic upgrade head` (criação de `investigation_round`, `round`, constraints e tabela `investigation_merges`).
  - Base populada: upgrade a partir da revisão 0007 com dados legados existentes.
  - Downgrade: `alembic downgrade -1` (reversão limpa da migração 0008).
  - Re-upgrade: `alembic upgrade head` restaura estrutura e integridade relacional.
  - Teste automatizado permanente: `tests/investigation/test_round_migration.py::test_postgres_ephemeral_clean_and_populated_lifecycle` aprovado em 6.56s.

---

## 4. Integridade dos Arquivos Protegidos (Hashes SHA-256)
- `app/routers/research.py`: `5584c7f46d8fcaad5266f063a0d837b0002cf887a68e653ff2dd38e49b980ea9` (intacto)
- `frontend/src/api.ts`: `400ceeabe7a681cecffa2f39d05cff325b458395e05c18f50ea0f35a4ed77702` (intacto)
- `frontend/src/main.tsx`: `78a243b73d604f505c8c92c9de9f3f5e29638f3edc0801d349da7d36064b754f` (intacto)
- `frontend/src/research-utils.ts`: `1a6454e1f5e5a706b64de163668a09b3796fdeb7e15c3dd6f7f300267df0f650` (intacto)

---

## 5. Conclusão de QA

A totalidade dos critérios de aceitação e testes de regressão passou com 100% de sucesso. Não há falhas abertas, skips ou pendências técnicas. Aprovado para avanço aos passos finais de polimento e documentação (T030 / T031).
