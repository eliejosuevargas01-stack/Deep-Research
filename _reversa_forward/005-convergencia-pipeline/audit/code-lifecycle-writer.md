# Inspeção Profunda: Auditor, Ciclo, Writer e Adaptador (S16-S21)

Data: 2026-10-21  
Feature: `005-convergencia-pipeline`  
Ação: T023 / S23  
Lentes aplicadas: Conformidade com spec (RF-505..508, RN-505..508), Concorrência & CAS, Isolamento Transacional (rede fora de transação), Negativos Markdown e Integridade de Credenciais.

---

## 1. Escopo inspecionado

Arquivos de produto:
- `app/audit/service.py` (auditoria por merge/rodada, remoção do truncamento 60000, CAS de status/ordinal)
- `app/audit/router.py` (propagação de round no endpoint de auditoria)
- `app/audit/domain.py` (teto MAX_AUDIT_ATTEMPTS=4, AUDIT_CAVEAT, next_audit_state)
- `app/investigation/service.py` (ready_point_batches topológicos, barreira 4 personas, CAS WRITE, sessão fechada antes de LLM)
- `app/services/research.py` (run_research adaptador modular, preservação de add_event, schedule e eventos)
- `app/services/pipeline/writer.py` (bundle unificado Evidence + InvestigationMerge, guardrails de limitação e proposta didática, validação de URLs conhecidas)

Arquivos de teste e suporte:
- `tests/audit/test_audit_round_merge.py`
- `tests/audit/test_audit_api.py`
- `tests/investigation/test_round_lifecycle.py`
- `tests/investigation/test_investigation_runtime_regressions.py`
- `tests/unit/test_pipeline_writer_convergence.py`

Contratos de referência:
- `_reversa_forward/005-convergencia-pipeline/requirements.md` (RF-505..508, RN-505..508)
- `_reversa_forward/005-convergencia-pipeline/actions.md` (Ações T016–T021)

---

## 2. Veredito Global

**Status: 🟢 APROVADO**

Todos os 6 requisitos funcionais e não-funcionais do bloco S16–S21 foram integralmente respeitados pelo código implementado. Não foram identificadas violações de segurança, regressões em endpoints ou vazamento de transações de banco para chamadas de rede.

---

## 3. Avaliação por Lente

### 3.1. Conformidade com a Especificação (RF-505..RF-508, RN-505..RN-508)
- **RF-505 / RN-505 (Teto Inicial + 3 Retries)**: `AuditService.audit_point` calcula `attempt = (point.attempt_count or 0) + 1`. Se `attempt >= MAX_AUDIT_ATTEMPTS` (4) e o veredito for reprovação factual, o status resultante transiciona estritamente para `AUDIT_CAVEAT` (`is_caveat=True`), nunca agendando 5ª rodada de investigação. Comprovado em `test_fourth_rejection_produces_audit_caveat_without_fifth_round`.
- **RF-506 / RN-506 (Isolamento de Falhas Técnicas)**: Erros técnicos de personas salvam `ResearchStepResult` com `status="FAILED"`, mas `attempt_count` do ponto não é incrementado. O orçamento de tentativas é consumido exclusivamente quando o Auditor emite `SCRAPER_RETRY`. Comprovado em `test_persona_technical_error_does_not_increment_attempt_count`.
- **RF-507 / RN-507 (Writer Flexível com Guardrail Anti-Alucinação)**:
  - Removido o piso artificial de 200 palavras por ponto (`validate_report_quality` exige a presença dos títulos de todos os pontos via `##`, mas permite seções curtas quando não há material aproveitável).
  - Padrões de aviso de limitação (`_LIMITATION_PATTERNS`) e propostas didáticas não-factuais (`_is_nonfactual_proposal`) não exigem citação forçada.
  - Alegações empíricas/factuais sem citação em qualquer formato (prosa, negrito, lista, tabela) continuam estritamente rejeitadas (`RuntimeError: Writer published uncited factual content`).
  - URLs de links inline devem pertencer estritamente a `known_urls` (agregadas de `Evidence` e `InvestigationMerge`). Comprovado em 17 testes de `test_pipeline_writer_convergence.py`.
- **RF-508 / RN-508 (Ciclo Único e Adaptador Modular)**:
  - `InvestigationService.run_investigation` consome `ready_point_batches(points)` para escalonar lotes topológicos respeitando `dependencies` e `is_parallelizable`.
  - Personas rodam com paralelismo seguro por ponto (4 personas concorrentes via `asyncio.gather`), sem semáforos legados globais (`WORK_LIMIT`).
  - `run_research(research_id)` atua como adaptador limpo delegando para `InvestigationService`, preservando `_active_researches`, `add_event` e isolamento de exceções com `sanitize_error`.

### 3.2. Concorrência e Isolamento Transacional (CAS & Rede Fora de Transação)
- **Rede Fora de Transação**:
  - Em `AuditService.audit_point`: A chamada `_call_auditor_llm` é executada após fechar a sessão de leitura inicial. A persistência dos resultados (`AuditTrail` e atualização de `ResearchPoint`) ocorre em transação curta e atômica subsequente.
  - Em `InvestigationService.run_investigation`: As chamadas aos workers de personas e à auditoria ocorrem fora de blocos transacionais abertos.
  - Na fase Writer: `_write_report` é chamado com a sessão de investigação fechada (`# T021: CAS WRITE, sessão fechada antes Writer`).
- **CAS e Idempotência**:
  - `AuditService.audit_point` compara status e ordinal do ponto antes de persistir veredito.
  - `AuditService.check_all_points_completed` valida `all(point.status in CONCLUSIVE_STATES)` antes de transicionar `Research.status = WRITE`.
  - Retomada de pesquisas em `WRITE` sem relatório dispara o Writer; pesquisas em `DONE` com relatório existente operam como no-op estrito sem regravação. Comprovado em `test_t021_write_resumption_and_done_noop`.

### 3.3. Segurança, Integridade de Dados e Contratos
- Nenhuma chave de API ou segredo é exposto em mensagens de erro ou logs (função `sanitize_error` aplica regex de mascaramento).
- O payload de merge agrega dados de personas em formato JSON canônico preservando rastreabilidade de URL, título e citação verbatim exata.
- Remoção do corte arbitrário `[:60000]` no prompt do auditor e `[:100000]` no writer garante fidelidade total das evidências coletadas.
- Os 4 arquivos protegidos (`app/routers/research.py`, `frontend/src/api.ts`, `frontend/src/main.tsx`, `frontend/src/research-utils.ts`) permanecem com seus hashes SHA-256 intactos.

---

## 4. Findings e Apontamentos

| ID | Severidade | Localização | Descrição | Recomendação |
|---|---|---|---|---|
| F-001 | Baixa (informativa) | `app/investigation/service.py:257` | `JinaToolAdapter` instancia com fallback para `None` se chaves ausentes em testes unitários. | Manter como está; comportamento seguro para testes com mocks de worker. |
| F-002 | Baixa (informativa) | `app/services/pipeline/writer.py:115` | Tratamento tolerante a objetos sem atributo `step_id` em mocks heterogêneos de `InvestigationMerge`. | Boa prática defensiva que preserva retrocompatibilidade com fixtures legadas. |

---

## 5. Conclusão da Inspeção

O código entregue nos sprints S16–S21 cumpre rigorosamente os objetivos arquiteturais do Reversa e resolve em definitivo as causas-raiz identificadas na investigação da feature 005. Aprovado para avanço ao QA independente (T024).
