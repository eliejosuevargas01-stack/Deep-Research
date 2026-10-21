# Relatório de QA Independente: Auditor, Ciclo de Rodadas, Writer e Adaptador (S16-S21)

Data: 2026-10-21  
Feature: `005-convergencia-pipeline`  
Ação: T024 / S24  
Responsável: QA Specialist Independente  
Ambiente de Execução: Banco SQLite em memória isolado via StaticPool com `asyncpg/aiosqlite` dedicado, sem contaminação entre testes.

---

## 1. Resumo Executivo

**Veredito Global: 🟢 APROVADO (100% GREEN)**

Todas as 5 suítes de teste cobrindo o recorte funcional de Auditoria por Merge, Teto de Rodadas (inicial + 3), Guardrails do Writer e Ciclo Único de Execução foram executadas com sucesso no runner seguro.
- **Total de testes executados no recorte S16-S21**: 51 testes.
- **Sucesso**: 51 passed (0 failed, 0 errors).
- **Tempo de execução**: 5.29s.
- **Exit Code**: 0.

---

## 2. Cobertura e Matriz de Provas

| Suíte de Testes | Testes | Status | Critérios Comprovados |
|---|---|---|---|
| `tests/audit/test_audit_api.py` | 16 | 🟢 PASSED | Auth, permissões, endpoints `/audit` com resposta 200/404/409, validação de transição para `WRITE` e avanço de tentativa em `SCRAPER_RETRY`. |
| `tests/audit/test_audit_round_merge.py` | 6 | 🟢 PASSED | Leitura de merge committed da rodada, prompt do auditor preservado acima de 60.000 chars sem truncamento arbitrário, CAS com rejeição de veredito obsoleto e commit atômico de `AuditTrail` + `ResearchPoint.audit`. |
| `tests/investigation/test_round_lifecycle.py` | 6 | 🟢 PASSED | Isolamento de erro de persona sem incrementar `attempt_count`, 4ª reprovação factual culminando em `AUDIT_CAVEAT`, bloqueio de 5ª rodada, ciclo de 2 pontos com caveat conjunto liberando `WRITE`, preservação de falhas em Q-502, batches topológicos e retomada idempotente do Writer. |
| `tests/investigation/test_investigation_runtime_regressions.py` | 6 | 🟢 PASSED | Retomada executando apenas personas ausentes, resolução estrita de credenciais por persona/provedor, proteção de concorrência com 409 em corrida de investigate, preservação de agendamentos. |
| `tests/unit/test_pipeline_writer_convergence.py` | 17 | 🟢 PASSED | RF-506 (seções curtas honestas aceitas sem 200 palavras mínimas), RF-507 (rejeição de fatos sem citação em 10 variantes de layout: prosa, negrito, listas, tabelas e rótulos), aceitação de propostas didáticas não-factuais e notas de limitação, rejeição de URLs desconhecidas e incorporação unificada de merges. |

---

## 3. Verificação de Regras Críticas de Negócio

### 3.1. Teto de Auditoria (Inicial + 3 Retries = 4 Tentativas)
- **Cenário**: Ponto sofre 4 reprovações factuais consecutivas.
- **Evidência**: `test_fourth_rejection_produces_audit_caveat_without_fifth_round` comprovou que na 4ª tentativa o veredito recebido é convertido para `AUDIT_CAVEAT` com `is_caveat=True`. Nenhuma tarefa adicional de investigação é disparada.
- **Avanço para Writer**: `test_two_points_four_rejections_reach_caveat_and_transition_to_write` comprovou que a pesquisa transiciona para `WRITE` somente quando 100% dos pontos atingem estado conclusivo (`AUDIT_APPROVED` ou `AUDIT_CAVEAT`). Pontos em andamento impedem transição prematura.

### 3.2. Writer Guardrail e Bundle de Evidências
- **Cenário 1 (Zero Evidência)**: `test_rf506_zero_evidence_conclusive_points` confirmou que um ponto em `AUDIT_CAVEAT` sem evidências aproveitáveis produz seção com aviso de limitação honesto sem forçar links inventados.
- **Cenário 2 (Fatos sem Fonte)**: `test_rf507_uncited_fact_rejected` validou que qualquer afirmação de fato empírico sem link inline no formato `[texto](url)` gera `RuntimeError: Writer published uncited factual content (prose, list, or table)`.
- **Cenário 3 (Proposta Não-Factual)**: `test_rf507_bold_nonfactual_proposal_accepted` confirmou que propostas didáticas e metodológicas não-factuais não geram falso positivo no guardrail de citações.
- **Cenário 4 (Bundle de Merges)**: `test_bundle_writer_incorporates_merges` confirmou que as citações registradas nos snapshots de `InvestigationMerge` de todas as rodadas são incorporadas ao bundle do Writer e reconhecidas em `known_urls`.

### 3.3. Ciclo Único RF-508 e Concorrência Idempotente
- **Topologia de Batches**: `test_rf508_ready_point_batches_and_adapter` comprovou que pontos dependentes aguardam estritamente o término de seus pontos antecedentes, enquanto as 4 personas de cada ponto rodam de forma concorrente.
- **Idempotência**: `test_t021_write_resumption_and_done_noop` comprovou que se a pesquisa já atingiu `DONE` com relatório gerado, chamadas subsequentes do orquestrador são no-op absoluto, prevenindo sobrescrita de relatório ou duplicação de callbacks.

---

## 4. Integridade de Arquivos Protegidos

Os hashes SHA-256 dos 4 arquivos protegidos foram confirmados antes e após a execução dos testes:
- `app/routers/research.py`: `5584c7f46d8fcaad5266f063a0d837b0002cf887a68e653ff2dd38e49b980ea9` (Íntegro)
- `frontend/src/api.ts`: `400ceeabe7a681cecffa2f39d05cff325b458395e05c18f50ea0f35a4ed77702` (Íntegro)
- `frontend/src/main.tsx`: `78a243b73d604f505c8c92c9de9f3f5e29638f3edc0801d349da7d36064b754f` (Íntegro)
- `frontend/src/research-utils.ts`: `1a6454e1f5e5a706b64de163668a09b3796fdeb7e15c3dd6f7f300267df0f650` (Íntegro)

---

## 5. Conclusão

A suíte está 100% aprovada. O pipeline atende com exatidão aos critérios de convergência exigidos para a entrega da Feature 005. Liberado para avanço aos testes síncronos de Briefing (T025).
