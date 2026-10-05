# Regression Watch — Deep Research Engine (modularizacao-backend)

> Gerado por `/reversa-coding`
> Feature: `modularizacao-backend`
> Data: 2026-10-05

---

## 🔍 Itens de Vigilância de Regressão

| ID | Origem | Regra Esperada Após Mudança | Tipo de Verificação | Sinal de Violação |
|---|---|---|---|---|
| `W001` | `app/services/search.py` | `search_read` e `Source` devem exportar interface idêntica ao legado | Presença de Contrato | Falha de import em `app/routers/research.py` ou `test_backend.py` |
| `W002` | `app/models/domain_models.py` | `ResearchStatus.REVISING` deve ser aceito nas queries de status e transições | Presença | Erro de validação ao salvar pesquisa em revisão |
| `W003` | `app/services/audit_agent.py` | Exigir as 4 personas completas e verbatim match para emitir APPROVED | Presença de Regra | Auditoria aprovar com personas faltantes |
| `W004` | `app/services/workers/` | Workers devem retornar instâncias válidas de `WorkerResult` | Contrato de Retorno | Atributos `evidences` ou `persona` ausentes no resultado |
| `W005` | `app/services/research.py` | API pública (17 símbolos re-exportados) deve manter assinatura e semântica exata | Contrato Público | `AttributeError` em routers ou testes ao importar `scout`, `run_worker`, `_run_point`, etc. |
| `W006` | `app/services/pipeline/scout.py` | `scout()` preserva A2-01 (3-5 fontes), A2-02 (timeout 120s), A1-03 (untrusted tags) | Presença de Regra | Scout retorna ≠5 pontos ou ignora timeout global |
| `W007` | `app/services/pipeline/worker.py` | `run_worker()` respeita `MAX_WORKER_QUERIES`, verbatim `_quote_supported`, sanitization A1-02 | Presença de Regra | Worker cita excerpt não presente na fonte ou ignora guardrails |
| `W008` | `app/services/pipeline/audit_stage.py` | `_audit_point()` aplica MA-08 (instruções concretas no retry), `sanitize_audit_dict` não vaza segredos | Presença de Regra | Retry sem `missing_research` ou vazamento de chave em `audit.llm` |
| `W009` | `app/services/pipeline/point_executor.py` | `_run_point()` executa 4 personas em paralelo via `WORK_LIMIT`, retry até `MAX_AUDIT_ATTEMPTS` | Presença de Regra | Pesquisa não bloqueia após 4 tentativas ou workers sequenciais |
| `W010` | `app/services/pipeline/writer.py` | `_write_report()` exige citações inline `[texto](url)` para todo fato, ≥400 palavras, headings por ponto | Presença de Regra | Relatório sem citação ou < 200 palavras ou heading faltante |
| `W011` | `app/services/research.py` | `ready_point_batches()` MA-01: paralelos + primeiro sequencial no mesmo batch; sem ciclos | Presença de Regra | Batch com dependência cíclica ou paralelo isolado sem release |

---

## 📜 Histórico de Re-extrações

*(Vazio. Será preenchido nas próximas execuções de `/reversa`)*
