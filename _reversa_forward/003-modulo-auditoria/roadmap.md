# Roadmap: Módulo de Auditoria Factual e Julgamento de Evidências

> Identificador: `003-modulo-auditoria`  
> Data: `2026-10-16`  
> Requirements: `_reversa_forward/003-modulo-auditoria/requirements.md`  
> Confidência: 🟢 Decisões confirmadas pelo operador em 2026-10-16.

---

## 1. Resumo da Abordagem Técnica

A Feature 003 introduz o pacote modular `app/audit/` desacoplado do código monolítico e integrado de forma nativa ao modelo assíncrono de `app/investigation/`:

1. **Camada de Domínio Puro (`app/audit/domain.py`):**
   - Implementa a checagem determinística de citações confrontando `claim` e `exact_quote` contra o texto dos resultados.
   - Avalia o checklist das 12 perguntas canônicas e calcula o score $S \in [0, 12]$.
   - Aplica as regras de transição de estado de ponto (`AUDIT_APPROVED`, `SCRAPER_RETRY`, `AUDIT_CAVEAT`).
   - Sanitização de strings e mascaramento de segredos via `apply_output_guardrail`.

2. **Serviço de Auditoria Assíncrono (`app/audit/service.py`):**
   - Executa a avaliação de evidências via chamada estruturada LiteLLM (papel `auditor`, padrão `gemini/gemini-3.8-flash` ou override de configuração).
   - Implementa até 4 retentativas com backoff exponencial para falhas de rede/LLM (500/502/503/timeout), registrando estado inconclusivo sem queimar `attempt_count` do ponto de pesquisa.
   - Persiste os registros na tabela relacional `audit_trails` e atualiza atomicamente `research_points.audit` e `research_points.status`.

3. **Integração e Orquestração Reativa (`app/investigation/service.py` & `app/audit/router.py`):**
   - Monitoramento reativo por ponto: no exato instante em que as 4 personas de um ponto concluem a pesquisa, o ponto é auditado automaticamente.
   - Em caso de `RETRY`, dispara os workers daquele ponto com as instruções de `missing_research` e o conjunto consolidado de `read_urls` proibidas de repetição.
   - Após a 4ª tentativa, converte a reprovação em `AUDIT_CAVEAT` com relatório de limitações e avança.
   - Quando todos os pontos estiverem concluídos (`AUDIT_APPROVED` ou `AUDIT_CAVEAT`), a pesquisa transita para `ResearchStatus.WRITE`.
   - Endpoints HTTP `POST /api/audit/{research_id}/run` e `POST /api/audit/{research_id}/points/{point_id}/run` protegidos por autenticação de administrador.

---

## 2. Decisões Técnicas Consolidadas

| ID | Decisão | Justificativa | Alternativas descartadas | Confidência |
|---|---|---|---|---|
| **D-301** | Auditoria automática por ponto e endpoints dedicados | Despacho imediato por ponto sem retenção desnecessária dos outros pontos | Aguardar todos os pontos terminarem para iniciar auditoria | 🟢 |
| **D-302** | Re-execução com filtro anti-duplicação de URLs | Garante que o retry traga fatos inéditos em vez de reler as mesmas páginas | Repetir a leitura das mesmas páginas ou apenas trocar o prompt | 🟢 |
| **D-303** | 4 retries de infraestrutura sem queimar tentativa do ponto | Separa falha de provedor de falha analítica das evidências | Tratar erro de rede como reprovação do ponto | 🟢 |
| **D-304** | Sequência modular: 003 -> 004 -> 005 -> 006 -> 007 | Fluxo linear de dependências: Backend cognitivo antes de Streaming e UI | Iniciar pela UI antes do pipeline de escrita | 🟢 |
| **D-305** | Teto de 4 tentativas sem bloqueio fatal (AUDIT_CAVEAT) | Toda pesquisa gera relatório; limitações são registradas explicitamente | Travar a pesquisa em BLOCKED permanente | 🟢 |
| **D-306** | Módulo independente `app/audit/` | Segue o padrão de arquitetura modular estabelecido em `app/briefing/` | Manter a lógica dentro de scripts soltos no pipeline legado | 🟢 |

---

## 3. Fases e Sprints de Implementação

### Sprint C9: Domínio, Schemas e Veredito Factual
- `app/audit/domain.py`: 12 perguntas, cálculo de score, validação de contradições, transição de estados.
- `app/audit/schemas.py`: Schemas Pydantic estritos para veredito, checklist, findings, missing_research.
- `app/audit/prompt_loader.py` e template `app/prompts/auditor.md`.

### Sprint C10: Serviço de Auditoria e Resiliência
- `app/audit/service.py`: `AuditService` assíncrono com LiteLLM, 4 retries de infraestrutura com backoff.
- Integração com `audit_trails`, `research_points` e sanitização de segredos.

### Sprint C11: Endpoints HTTP e Conexão de Pipeline
- `app/audit/router.py`: Rotas `POST /api/audit/{id}/run` e `POST /api/audit/{id}/points/{pid}/run`.
- Conexão em `app/investigation/service.py`: Disparo automático por ponto + re-pesquisa com filtro anti-duplicação.
- Transição da pesquisa para `ResearchStatus.WRITE` quando 100% dos pontos finalizarem.

### Sprint C12: Validação BDD (Cucumber / Behave) e Regressão
- Suíte BDD em `features/003_auditoria.feature` executada via Behave e Cucumber.
- Testes de integração em `tests/audit/` cobrindo aprovação, retry, teto de 4 tentativas e resiliência de rede.
