# Business Knowledge — Deep Research Engine

> Detective — conhecimento implícito extraído de código, prompts, testes, logs  
> Confidência: 🟢 CONFIRMADO (código lido) + 🟡 INFERIDO (padrões observados)

---

## 1. Fluxo de Negócio (User Journey)

### 1.1 Operador (UI)
1. **Login** → cookie HttpOnly + CSRF token em header.
2. **Settings** → configura API keys (encrypted), modelos por role, callback_url global, openai_base_url.
3. **Nova Pesquisa** → `POST /api/research {theme}` → status `scouting` → SSE stream.
4. **Scout** → busca 3-5 sites → gera 5 pontos com dependências → `pending_approval`.
5. **Aprova/Edita Briefing**:
   - Aprova → `approved` → execução paralela.
   - Edita → `revising` → Scout refaz com feedback → auto-aprova → `approved`.
6. **Acompanha Pipeline** via SSE: workers → auditor → writer.
7. **Relatório Final** → Markdown com citações [texto](url) → download/view.
8. **Webhook** → se `callback_url` configurado, POST JSON com report.

### 1.2 Cliente Backend (API)
- Autenticação: `Authorization: Bearer <API_AUTH_SECRET>` OU `X-API-Key: <API_AUTH_SECRET>`.
- `POST /api/research {theme, callback_url}` → callback_url no payload permitido (diferente de UI).
- Polling `/api/research/{id}` ou SSE `/events/stream` com `Last-Event-ID`.

---

## 2. Regras de Negócio Críticas (extraídas do código)

| Regra | Onde | Comportamento |
|-------|------|---------------|
| **Briefing = 5 pontos fixos** | `schemas:BriefingApproval` valida `len(points) == 5` | Não configurável; hardcoded no contrato. |
| **Máx 20 pontos/pesquisa** | `ready_point_batches` levanta `ValueError` se >20 | Limite de segurança/recursos. |
| **Dependências topológicas** | `point_dependencies` | Aceita índice 1-based, "point N", ou título exato; rejeita ciclos. |
| **Citação verbatim obrigatória** | `audit.py:deterministic_citation_audit` | `exact_quote` deve ser substring exata (casefold) do excerpt coletado. |
| **Máx 3 tentativas/ponto** | `remaining_attempts` + `MAX_AUDIT_ATTEMPTS` (settings) | 4ª reprovação → `BLOCKED` com ressalvas no report. |
| **4 personas fixas** | `PERSONAS` tuple | historian, skeptic, pragmatist, futurist — não configurável runtime. |
| **Tenant header proibido** | `security.py:32-34` + `api.ts` | `x-tenant-id` → HTTP 400 (critério A-04). |
| **Credencial única/request** | `security.py:41-47` | Cookie OU Bearer OU API Key; múltiplas → 400 "Ambiguous authentication". |
| **CSRF em mutações** | `security.py:86-90` | POST/PUT/PATCH/DELETE exigem `X-CSRF-Token` válido (HMAC). |
| **Webhook anti-SSRF** | `webhook.py` + `outbound.py` | `validate_public_url` + `PinnedResolver` + no redirects. |
| **Settings hot-reload** | `settings.py:runtime_settings` | DB > ENV > defaults; mudança imediata sem restart. |

---

## 3. Personas Cognitivas (Contratos)

| Persona | Foco | Prompt Base (personas.json + research.py) |
|---------|------|------------------------------------------|
| **Historian** | Cronologia, origem, benchmarks históricos, timeline verificado | "chronological evolution, origin context, historical benchmarks, verified timeline records" |
| **Skeptic** | Falsificação, counter-evidence, conflitos, limitações, falhas metodológicas | "falsifying claims, surfacing counter-evidence, conflicts of interest, limitations, methodological flaws" |
| **Pragmatist** | Implementação real, benchmarks concretos, parâmetros operacionais, custos, outcomes mensuráveis | "real-world implementations, benchmark figures, concrete operational parameters, costs, measurable outcomes" |
| **Futurist** | Roadmaps documentados, implicações projetadas, consenso emergente, marcos estruturais vindouros | "documented roadmap targets, projected implications, emerging consensus, upcoming structural milestones" |
| **Scout** | 5 pontos de briefing a partir de 3-5 fontes distintas | busca live, seleção fontes, dependências, paralelismo |
| **Auditor** | Verifica citação verbatim, cobertura, contradições, atualidade, escopo | determinístico (claim⊂excerpt) + LLM |
| **Writer** | Relatório Markdown pt-BR, headings = títulos dos pontos, citações 1:1 | "substantive report... inline markdown link [texto](url) for every factual sentence" |

---

## 4. Configurações Dinâmicas (Settings)

| Config | Origem | Prioridade | Validação |
|--------|--------|------------|-----------|
| API Keys (7 providers) | DB (encrypted) > ENV > fallback | 1. DB 2. ENV | `test_provider_key` antes de salvar |
| Modelos por role (7 roles) | DB > ENV > `DEFAULT_ROLE_MODELS` | 1. DB 2. ENV | string não-vazia |
| `callback_url` global | DB (AppSettings) | 1. DB | `validate_public_url` (SSRF) |
| `openai_base_url` | DB (AppSettings) | 1. DB | `validate_base_url` (SSRF + trusted router) |
| `SESSION_TTL_HOURS` | ENV | ENV | int > 0 |
| `SEARCH_TIMEOUT_SECONDS` | ENV | ENV | int > 0 |

---

## 5. Estados de Pesquisa (State Machine)

```
scouting → pending_approval → [revising] → approved → in_progress
                                                    ↓
                                            completed / blocked / failed
                                                    ↓
                                            [completed_but_callback_failed]
                                                    ↓
                                            completed (retry-callback)
```
- `interrupted`: lifespan marca pesquisas órfãs no startup para retomada manual.
- `revising`: **runtime-only** (não no enum Python — 🔴 LACUNA 1).

---

## 6. Eventos SSE (Observable Stream)

| Event Type | Emissor | Payload (metrics) |
|------------|---------|-------------------|
| `scout_started` | scout | — |
| `briefing_ready` | scout | `{"points": 5}` |
| `briefing_edited` | system | — |
| `briefing_approved` | system | `{"points": N}` |
| `worker_started` | persona | `point_id, point_title` |
| `sources_scanned` | persona | `sources_fetched, citations_retained` |
| `verdict_rendered` | auditor | `attempt, supported, unsupported` |
| `synthesis_completed` | writer | `evidence_records, citations` |
| `callback_delivered/failed` | system | `delivered: bool` |
| `research_failed` | system | `error` sanitizado |

**Resume**: `Last-Event-ID` cursor (auto-increment `Event.id`) → re-sync gapless.

---

## 7. Segurança (Observabilidade de Risco)

| Vetor | Mitigação | Gap |
|-------|-----------|-----|
| SSRF (webhook/search/base_url) | DNS pin + IP validation + no redirects + trusted allowlist | 🟢 Profundidade |
| Prompt injection | `<untrusted_*>` tags nos prompts + guardrails output | 🟢 Isolamento |
| Secret leak (logs/DB/output) | `sanitize_error` + `apply_output_guardrail` (regex API keys) | 🟢 Redação |
| Auth hijack | JWT HttpOnly + CSRF + credencial única | 🟢 |
| Metadata cloud (169.254.x.x) | `is_forbidden_ip` bloqueia hardcoded | 🟢 |

---

## 8. Observações Operacionais

1. **Recovery automático**: `lifespan` no startup varre `scouting/revising/approved/in_progress` → re-agenda.
2. **Worker failure isolado**: 1 persona falha não bloqueia ponto; `AuditTrail` registra, continua.
3. **Report quality gate**: `validate_report_quality` exige ≥200 words + headings por ponto + citações válidas; rejeita stub.
4. **Callback retry**: `POST /api/reports/{id}/retry-callback` manual; status `completed_but_callback_failed` → `completed` se sucesso.
5. **Concorrência**: `Semaphore(20)` global + batch topológico evita thundering herd.

---

## 9. Lacunas de Conhecimento (→ questions.md)

1. **LACUNA 1**: `revising` status runtime-only vs enum.
2. **LACUNA 2**: `prompts/__init__.py` vazio — dead code ou placeholder?
3. **LACUNA 3**: `read_source` 8000 chars truncamento vs verbatim contract.
4. **LACUNA 4**: pytest não instalado.
5. **LACUNA 5**: Frontend monolítico 2.5k LOC (refactoring T005).

---

## 10. Decisões de Design Implícitas

| Decisão | Evidência |
|---------|-----------|
| **Single-admin** (não multi-tenant) | `x-tenant-id` proibido; `AdminSession` sem tenant_id |
| **Briefing 5 pontos fixo** | Schema valida `min_length=5, max_length=5` |
| **4 personas fixas** | Tuple `PERSONAS` + `complete_personas` check no auditor |
| **Fail-closed SSRF** | `RuntimeError` se transport não suportar `follow_redirects` |
| **Optimistic lock Evidence** | `version_id_col` mas sem teste de concorrência |
| **SSE + Polling dual** | Frontend usa SSE primário, polling 5s fallback |

---

## 11. Métricas de Qualidade (Code-level)

| Métrica | Valor | Fonte |
|---------|-------|-------|
| LOC backend | ~3,074 | contagem arquivos |
| LOC frontend | 5,357 | contagem arquivos |
| Testes (LOC) | ~2,500 | test_backend + e2e + postgres |
| Cobertura implícita | Auth, Settings, SSRF, Scout, Pipeline, Writer | test_e2e_criteria + test_backend |
| Migrations | 3 | alembic 0001-0003 |
