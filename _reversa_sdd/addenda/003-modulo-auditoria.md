# Adendo de Convergência — Feature 003: Módulo de Auditoria Factual e Julgamento de Evidências

> Feature: `003-modulo-auditoria`  
> Data: 2026-10-17  
> Status: 🟢 CONFIRMADO (100% Aprovado em Auditoria e Testes)  
> Base Git: branch `main`

---

## 1. Escopo e Propósito

Este adendo registra formalmente a convergência e conclusão da **Feature 003 — Módulo de Auditoria Factual e Julgamento de Evidências**, responsável por atuar como árbitro analítico independente das 4 personas investigativas (**historian**, **skeptic**, **pragmatist**, **futurist**).

---

## 2. Componentes Entregues

1. **Domínio Puro (`app/audit/domain.py`):**
   - 12 critérios canônicos `q1` a `q12` avaliados de forma estrita.
   - Cálculo de score $S \in [0, 12]$ com aprovação condicionada a `score >= 10`, ausência de contradições e citações válidas.
   - Máquina de estados: `AUDIT_APPROVED`, `SCRAPER_RETRY` (com diretrizes concretas de `missing_research`), `AUDIT_CAVEAT` (teto na 4ª tentativa sem bloquear a pesquisa).
   - Sanitização de dados com mascaramento de segredos via `sanitize_audit_dict`.

2. **Contratos Pydantic (`app/audit/schemas.py`):**
   - `AuditChecklist`: modelo com campos booleanos `q1`..`q12`.
   - `AuditVerdictResponse`: espelho do veredito para respostas HTTP e documentação OpenAPI.
   - `AuditRunResponse`: payload de disparo com estatísticas e vereditos consolidados.

3. **Serviço Assíncrono (`app/audit/service.py`):**
   - Agregação de evidências das 4 personas a partir de `research_step_results`.
   - Invocação LiteLLM com resiliência de infraestrutura: até 4 tentativas consecutivas (1 inicial + 3 retries com backoff 1s, 2s, 4s) contra erros 500/502/503 e timeouts.
   - Registro de falha persistente como `AUDIT_INCONCLUSIVE` em `audit_trails` sem queimar o `attempt_count` do ponto.
   - Atualização atômica de `research_points.audit`, `research_points.status` e `audit_trails`.
   - Verificação de conclusão total (`check_all_points_completed`): transita a pesquisa para `ResearchStatus.WRITE` quando 100% dos pontos estão em `AUDIT_APPROVED` ou `AUDIT_CAVEAT`.

4. **Endpoints de API (`app/audit/router.py` e `app/main.py`):**
   - `POST /api/audit/{research_id}/run`: Dispara auditoria de todos os pontos pendentes.
   - `POST /api/audit/{research_id}/points/{point_id}/run`: Dispara auditoria de um ponto isolado.
   - Ambos protegidos por autenticação de administrador (`require_admin`).

5. **Integração no Pipeline de Investigação (`app/investigation/`):**
   - `PersonaWorker` em `app/investigation/worker.py`: injeção de diretrizes de `missing_research` no prompt e filtro anti-duplicação de URLs descartando leituras repetidas em retries.
   - `InvestigationService` em `app/investigation/service.py`: ciclo reativo por ponto disparando a auditoria imediatamente após a conclusão dos 4 workers daquele ponto.

6. **Validação BDD e Testes Automatizados:**
   - `features/003_auditoria.feature`: 8 cenários Gherkin em português cobrindo aprovação, reprovação, retry, teto de 4 tentativas, 503 transitório, disparo por ponto, endpoint manual e avanço para `WRITE`.
   - `features/steps/auditoria_steps.py`: Step definitions executados via `behave` com 100% de sucesso.
   - `tests/audit/test_audit_api.py`: 16 testes de integração cobrindo 200, 401, 404 e 409.

---

## 3. Evidências de Teste

- `behave features/003_auditoria.feature`: 8 cenários aprovados, 34 passos aprovados (exit code 0).
- `pytest tests/audit/test_audit_api.py -v`: 16 testes aprovados (exit code 0).
- `pytest tests/test_briefing_*.py tests/investigation/ tests/audit/ -q`: 257 testes aprovados (exit code 0).
- `pytest tests/test_backend.py -k "not test_e2e" -q`: 58 testes aprovados (exit code 0).
