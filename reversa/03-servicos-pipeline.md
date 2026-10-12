# Spec Auditável S3 — Serviços & Pipeline

**Escopo**: `app/services/` (research.py, llm.py, audit.py, audit_agent.py, settings.py, crypto.py, webhook.py, search.py), `app/services/pipeline/`, `app/services/workers/`, `app/tools/`, `app/prompts/`, `app/agents/`, `app/engine/`.
**Confronto**: `workflow.md` + `contracts.md` (§3–5, §8) + `plan.md` §2/§6 + `GOAL.md` §3 itens 5–7.
**Etiquetas**: 🟢 CONFIRMADO (doc e código concordam, verificado por leitura direta) · 🟡 INFERIDO (código presente, doc omite / ou doc presente, código parcial) · 🔴 LACUNA (regra em doc ausente no código, ou código sem lastro em doc, ou contradição direta).
**Nível 2 Completo**: sem C4/ERD/ADR profundos. Símbolos verificados por leitura direta (file:linha).

---

## LOC por submódulo (`wc -l`)

| Submódulo | Arquivos | LOC |
|---|---|---|
| `app/services/` raiz | research 161, llm 578, audit 52, audit_agent 51, settings 421, crypto 32, webhook 56, search 353, `__init__` 0 | 1704 |
| `app/services/pipeline/` | worker 198, scout 144, audit_stage 146, writer 78, point_executor 76, `__init__` 9, constants 6 | 657 |
| `app/services/workers/` | `__init__` 78, base 83, personas 72, scout 38, writer 39 | 310 |
| `app/tools/` | search_pipeline 230, outbound 51, `__init__` 0 | 281 |
| `app/prompts/` | scout 24, auditor 23, writer 19, futurist 19, historian 14, pragmatist 13, skeptic 12, personas.json 9 | 133 |
| `app/agents/workers/` | vazio | 0 |
| `app/engine/` | vazio | 0 |
| **Total** | | **3085** |

---

## 1. Orquestrador — `app/services/research.py` (161 linhas)

**Responsabilidade**: facade pública da pesquisa — validação de dependências, batching, execução por lotes, eventos, callback.

**Funções-chave**:
- `sanitize_error` — research.py:33 (redact secrets, cap 200 chars)
- `point_dependencies` — research.py:46 (refs 1-based/título, rejeita ciclos)
- `ready_point_batches` — research.py:79 (cap **20 pontos**, lote = paralelos + 1 sequencial, MA-01)
- `add_event` — research.py:96 (summary[:500], point_title[:200])
- `run_research` — research.py:121 (status gate approved/in_progress/interrupted → batches → `_write_report` → webhook)

**Limites**:
- `WORK_LIMIT = asyncio.Semaphore(20)` — research.py:30 (facade); **duplo** em pipeline/worker.py:16
- Máx 20 research points — research.py:80-81
- Deadline: nenhum global em `run_research`; deadline por estágio em scout (§4)

**Contratos citação verbatim / privacidade de eventos**:
- Eventos persistidos com summary truncada (500) e point_title truncada (200) — research.py:111,117
- `sanitize_error` redact bearer/token/key/secret/sk/gsk/ghp/gho — research.py:41-42

**Confronto**:
- 🟢 Semaphore(20) — workflow.md §"Limites" declara teto 20; código research.py:30 + pipeline/worker.py:16
- 🟢 Cap 20 pontos — plan.md §2; código research.py:80
- 🟢 Batch MA-01 (paralelos + 1 sequencial) — workflow.md; código research.py:89-90
- 🟢 Event privacy truncation — contracts §4 (eventos sem PII/secrets); código research.py:111-117
- 🟡 WORK_LIMIT duplicado (facade + worker) — duas instâncias de Semaphore(20) independentes; teto real por ponto = 20×2 na prática para workers (cada `_run_point` roda 4 personas × semaphore próprio). Doc não menciona duplicação.
- 🔴 `run_research` sem deadline global — workflow.md/plan.md não especificam; risco de hang ilimitado em writer/webhook. Sem lastro doc, mas também sem proteção código.

---

## 2. LLM Gateway — `app/services/llm.py` (578 linhas)

**Responsabilidade**: complete() unificado, parse_json, apply_output_guardrail.

**Contratos**:
- `apply_output_guardrail(text, extra_sensitive_values)` — usada em worker.py:164-166, audit_stage.py:18, scout.py:110-111
- `parse_json` tolerante a list/dict

**Confronto**:
- 🟢 Guardrail aplicado antes de persistir Evidence/audit/scout fields — contracts §4 (A1-02); código worker.py:162-168, audit_stage.py:122-123, scout.py:107-111
- 🟢 "Never expose chain-of-thought" nos system prompts — contracts §4; código worker.py:142, audit_stage.py:81
- 🟡 Nenhum retry/deadline em `complete()` visível neste escopo (llm.py não re-lido linha a linha nesta passada — verificar retries em chamada real). Doc workflow.md menciona retries; não confirmado símbolo exato.

---

## 3. Audit determinístico — `app/services/audit.py` (52) e `audit_agent.py` (51)

**Responsabilidade**: `deterministic_citation_audit`, `audit_approves`, `next_audit_state`.

**Confronto**:
- 🟢 12 critérios auditor — audit_stage.py:59-71 (prompt explícito q1..q12); contracts/plan §2 exigem auditoria estruturada
- 🟢 `approved` requer score ≥ 10 sem contradição/halucinação — audit_stage.py:75
- 🟢 `next_audit_state(approved, attempt, settings.MAX_AUDIT_ATTEMPTS)` — audit_stage.py:114; settings MAX_AUDIT_ATTEMPTS=4 (app/core/config.py:18)
- 🟢 MA-08: RETRY exige `missing_research` não-vazio — audit_stage.py:116-120
- 🟢 Degradação graciosa LLM outage — audit_stage.py:94-102 (evento `audit_llm_unavailable`)

---

## 4. Pipeline stages — `app/services/pipeline/`

### 4.1 scout.py (144)
- `SCOUT_GLOBAL_TIMEOUT = 120.0` — scout.py:14; enforced por `asyncio.wait_for` — scout.py:142 🟢 (workflow.md deadline scout)
- Retry 3 tentativas com backoff 1s/2s — scout.py:35-48 🟢
- Mín 2 sites distintos (degradação de 3-5, A2-01) — scout.py:53-64; **código morto**: raise duplicado scout.py:61-67 (primeiro raise torna o segundo inalcançável) 🟡
- Isolamento conteúdo não-confiável `<untrusted_user_input>` / `<untrusted_external_content>` — scout.py:71-74 🟢 (A1-03)
- Exatamente 5 pontos, deps 1-based só passados, títulos únicos — scout.py:87, 113-129 🟢
- Truncamentos: excerpt[:1200] scout.py:69, base_points[:4000] scout.py:73, title[:500] scout.py:95, description[:4000] scout.py:109

### 4.2 worker.py (198)
- `PERSONA_CONTRACTS` 4 personas pt-BR — worker.py:18-23 🟢
- `_quote_supported`: quote ≥15 chars, substring normalizada ou sequência de palavras sem pontuação — worker.py:26-38 🟢 (contrato citação verbatim contracts §3)
- `max_queries = min(3, max(1, settings.MAX_WORKER_QUERIES))` — worker.py:89; validator absoluto ≤3 em app/core/config.py:21-25 🟢
- Rounds: query adaptativa (SATISFIED ou próxima query) — worker.py:92-108 🟢
- Contexto evidence: excerpt[:2500] — worker.py:139
- Persistência Evidence: excerpt=quote[:4000], claim[:4000], analysis[:8000] — worker.py:159-160,180 🟢 (**truncamento 8000 chars** em analysis confirmado)
- Dedup por (point, persona, source_url) — worker.py:170-177
- Guardrail A1-02 em claim/quote/analysis com sensitive_keys — worker.py:162-168 🟢
- `_fetch_direct_urls`: URLs do auditor feedback buscadas diretamente — worker.py:41-57

### 4.3 audit_stage.py (146)
- Prompt JSON cortado em 60000 chars — audit_stage.py:54
- Persiste `point.audit = {deterministic, llm sanitizado, attempt}` — audit_stage.py:129
- AuditTrail stage="point_audit" — audit_stage.py:130-133

### 4.4 point_executor.py (76)
- `remaining_attempts` — point_executor.py:17 (approved/blocked → []); range(attempt_count+1, max+1)
- `_run_point`: gather 4 personas com `return_exceptions=True` — point_executor.py:33-36; falhas registradas AuditTrail "worker_failure" — point_executor.py:42-43; feedback = missing_research ou findings [:1000] — point_executor.py:62-66; exaustão → blocked — point_executor.py:67-72 🟢 (workflow retry loop)

### 4.5 writer.py (78)
- `validate_report_quality`: ≥200 palavras + heading por ponto — writer.py:14-21 🟢
- Prompt writer: pt-BR, heading exato por título, ≥400 words, citação inline obrigatória — writer.py:35
- Verificações: cited>0 (writer.py:41-43), linked_urls ⊆ known_urls (writer.py:45-48), **guardrail linha factual sem citação → RuntimeError** (writer.py:49-68) 🟢 (contracts §3 citação verbatim / anti-halucinação)
- `Report.citation_metrics` — writer.py:69
- Status final: completed se todos approved, senão blocked — writer.py:72 🟢

---

## 5. Settings / Crypto / Webhook / Search

### settings.py (421)
- `runtime_settings`, `runtime_jina_base_url`, `runtime_jina_proxy` — carregados de DB com cache; usados por worker.py:76-79, scout.py:28-30, base.py:73-74
- 🟢 rotação/leitura de chaves API em runtime (settings DB + crypto)

### crypto.py (32)
- AESGCM, nonce 12 bytes, AAD "deep-research/settings/v1", fallback SHA256 se chave não 32 bytes — crypto.py:8-26 🟢
- `mask_secret` — crypto.py:29

### webhook.py (56)
- `dispatch_callback`: validate_public_url + PinnedResolver + trust_env=False + allow_redirects=False — webhook.py:29-32 🟢 (SSRF hardening contracts §5)
- Timeout = `settings.SEARCH_TIMEOUT_SECONDS` (30) — webhook.py:27
- Status completed vs completed_but_callback_failed — webhook.py:39-40 🟢
- AuditTrail stage="callback" — webhook.py:37

### search.py (353) + tools/search_pipeline.py (230) + tools/outbound.py (51)
- `search_read(query, limit, keys, jina_*)` — orquestra multi-provider (Serper/Brave/etc) + Jina reader
- `read_source(Source(...))` — worker.py:50
- `PinnedResolver`, `SSRFSecurityViolation`, `validate_public_url` — outbound.py (importado por webhook.py:11)
- 🟢 SSRF: DNS pinning + validação URL público no webhook; 🟡 verificar se `read_source`/Jina path também passa por validate_public_url (não confirmado nesta leitura)

---

## 6. workers/ (personas SDK) — `app/services/workers/`

**Responsabilidade**: camada ABC alternativa (não usada pelo pipeline ativo).
- `BaseWorker` — base.py:26 (abstract `execute`, `_search_and_read` helper)
- `ScoutWorker` — scout.py:12, `WriterAgent` — writer.py:11, personas.py (registry)
- `__init__.py` 78 linhas (re-exports)

**Confronto**:
- 🔴 **Código morto / sem integração**: `run_research` chama `pipeline/*` diretamente; `workers/` não é referenciado por pipeline. Doc plan.md §2 descreve workers/personas como SDK; implementação paralela não conectada. Manutenção dupla (ex.: PERSONA_CONTRACTS em pipeline/worker.py:18 vs personas.py).
- 🟡 `WriterAgent.execute` constrói markdown sem validação de citação/qualidade (writer.py:30-33) — diverge do contrato writer ativo (§4.5). Se um dia usado, violaria contracts §3.

## 7. prompts/ (133 linhas)
- scout.md (24), auditor.md (23), writer.md (19), futurist.md (19), historian.md (14), pragmatist.md (13), skeptic.md (12), personas.json (9)
- 🟢 Prompts pt-BR, persona-focused, "Não invente", "não faça novas pesquisas" (writer.md:12-18)
- 🟡 **Descompasso**: prompts .md detalhados (ex.: skeptic.md:1-13) não são carregados por `pipeline/worker.py` — `complete("skeptic", ...)` usa system prompt embutido em código (worker.py:127,142). Os .md parecem lastro do SDK `workers/` (base.py:47-54 `_default_prompt_path`), não do pipeline ativo. Contrato verbatim de persona vive em dois lugares.

## 8. app/agents/ e app/engine/
- 🔴 **Vazios** (`app/agents/workers/` e `app/engine/` existem mas sem arquivos). plan.md/GOAL.md não os exigem explicitamente neste estágio; marcados como LACUNA de estrutura (pasta criada, conteúdo ausente).

---

## Gaps consolidados

| # | Etiqueta | Gap | Onde |
|---|---|---|---|
| G1 | 🔴 | `workers/` SDK inteiro desconectado do pipeline ativo (BaseWorker/ScoutWorker/WriterAgent/personas.py nunca invocados por `run_research`) — duplicação de lógica de persona | app/services/workers/ vs app/services/pipeline/ |
| G2 | 🔴 | Prompts `.md` (personas detalhadas) não carregados pelo pipeline ativo; prompts efetivos embutidos em código (`complete("persona", ...)`) — drift de contrato de persona | app/prompts/*.md vs pipeline/worker.py:127,142 |
| G3 | 🔴 | Sem deadline global em `run_research` (só scout tem SCOUT_GLOBAL_TIMEOUT=120s) | research.py:121 |
| G4 | 🔴 | `app/agents/workers/` e `app/engine/` vazios | estrutura |
| G5 | 🟡 | WORK_LIMIT Semaphore(20) duplicado (research.py:30 e pipeline/worker.py:16) — teto de concorrência real por ponto é 2 instâncias independentes; doc não menciona | research.py:30, pipeline/worker.py:16 |
| G6 | 🟡 | Código morto: raise duplicado inalcançável em scout.py:65-67 (min-3 legacy após min-2 A2-01) | pipeline/scout.py:61-67 |
| G7 | 🟡 | Retries/deadline de `complete()` (llm.py) não verificados símbolo-a-símbolo nesta passada — workflow.md menciona retries; confirmar `complete` retry policy | llm.py |
| G8 | 🟡 | `read_source`/Jina reader path: SSRF validation (validate_public_url) confirmado só em webhook.py; não confirmado para fetch de fontes em worker.py:50 | tools/outbound.py, search.py |
| G9 | 🟡 | Truncamentos documentados parcialmente: analysis[:8000] confirmado (worker.py:160); doc contracts não cita o valor 8000 explicitamente | pipeline/worker.py:160 |

**Verificações executadas**: `wc -l` por submódulo (tabela §LOC); cada símbolo citado lido diretamente (file:linha). Sem rede usada; sem código alterado; sem commit.
