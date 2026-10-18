# Ações: Módulo de Auditoria Factual e Julgamento de Evidências

> Identificador: `003-modulo-auditoria`  
> Data: `2026-10-16`  
> Requirements: `_reversa_forward/003-modulo-auditoria/requirements.md`  
> Roadmap: `_reversa_forward/003-modulo-auditoria/roadmap.md`

---

## Tabela de Ações Atômicas

| ID | Ação | Sprint | Responsável | Arquivos Permitidos | Status | Check |
|---|---|---|---|---|---|---|
| **T041** | Implementar `app/audit/domain.py` com a lógica pura dos 12 critérios, cálculo de score (≥10/12 para aprovação), checagem determinística de citações e máquina de estados de pontos. | C9 | Worker | `app/audit/domain.py`, `app/audit/__init__.py` | 🟢 CONFIRMADO | [X] |
| **T042** | Implementar `app/audit/schemas.py` com modelos Pydantic estritos para checklist `q1`–`q12`, veredito estruturado, findings, incertezas e missing research. | C9 | Worker | `app/audit/schemas.py` | 🟢 CONFIRMADO | [X] |
| **T043** | Implementar `app/audit/service.py` com `AuditService`, agregação dos resultados das 4 personas a partir de `research_step_results`, binding LiteLLM do papel `auditor` e até 4 retries de infraestrutura (1 inicial + 3 retries) com backoff exponencial sem queimar o `attempt_count` do ponto. | C10 | Worker | `app/audit/service.py` | 🟢 CONFIRMADO | [X] |
| **T044** | Implementar persistência atômica do veredito em `audit_trails`, atualização de `research_points.audit` e `research_points.status`, com sanitização estrita de segredos via `apply_output_guardrail`. | C10 | Worker | `app/audit/service.py`, `app/audit/domain.py` | 🟢 CONFIRMADO | [X] |
| **T045** | Implementar `app/audit/router.py` expondo `POST /api/audit/{research_id}/run` e `POST /api/audit/{research_id}/points/{point_id}/run` protegidos por autenticação de administrador e registrar o roteador em `app/main.py`. | C11 | Worker | `app/audit/router.py`, `app/main.py` | 🟢 CONFIRMADO | [X] |
| **T046** | Conectar disparo reativo no término de workers por ponto em `app/investigation/service.py`: assim que as 4 personas de um ponto finalizam, disparar imediatamente a auditoria daquele ponto. | C11 | Worker | `app/investigation/service.py` | 🟢 CONFIRMADO | [X] |
| **T047** | Implementar mecanismo de RETRY: se reprovado e `attempt_count < 4`, re-executar os workers com `missing_research` no prompt e aplicar filtro anti-duplicação impedindo re-visita a URLs já presentes em `read_urls`. | C11 | Worker | `app/investigation/service.py`, `app/investigation/worker.py` | 🟢 CONFIRMADO | [X] |
| **T048** | Implementar regra de teto de 4 tentativas: se na 4ª tentativa o ponto for reprovado, transitar para `AUDIT_CAVEAT` registrando formalmente as limitações e liberar o material para o Redator sem travar a pesquisa. | C11 | Worker | `app/audit/domain.py`, `app/audit/service.py`, `app/investigation/service.py` | 🟢 CONFIRMADO | [X] |
| **T049** | Implementar transição da pesquisa de `ResearchStatus.AUDIT` para `ResearchStatus.WRITE` quando 100% dos pontos atingirem estado conclusivo (`AUDIT_APPROVED` ou `AUDIT_CAVEAT`). | C11 | Worker | `app/investigation/service.py`, `app/audit/service.py` | 🟢 CONFIRMADO | [X] |
| **T050** | Criar suíte de testes BDD Cucumber / Behave em `features/003_auditoria.feature` e testes de integração em `tests/audit/test_audit_api.py`, validando todos os cenários com 100% de aprovação (exit code 0). | C12 | Worker | `features/003_auditoria.feature`, `features/steps/auditoria_steps.py`, `tests/audit/test_audit_api.py` | 🟢 CONFIRMADO | [X] |
