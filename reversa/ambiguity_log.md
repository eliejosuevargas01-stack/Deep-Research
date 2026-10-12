# Ambiguity Log — Repo vs Documentação (Nível 2 Completo)

> Gerado pela auditoria reversa completa (S0–S4) em `/root/projects/deep-research/reversa/`
> Cada entrada: arquivo, etiqueta 🔴/🟡/🟢, descrição, origem (código:linha / doc:seção)

---

## S0 — Índice + Testes/Infra (`00-index.md`, `05-testes-infra.md`)

| # | Etiqueta | Gap | Origem |
|---|----------|-----|--------|
| S0-1 | 🔴 | `outbound.py:validate_public_url` — bypass em edge cases (ex.: `http://[::1]`) | `00-index.md` Gap 1 |
| S0-2 | 🟡 | `llm.py` — LiteLLM SafeTransport patch incompleto (alguns ramos não cobertos) | `00-index.md` Gap 2 |
| S0-3 | 🟡 | `pipeline/scout.py:65-67` — dead code: segundo `raise RuntimeError` inalcançável | `00-index.md` Gap 3 / `03-servicos-pipeline.md` G6 |
| S0-4 | 🟡 | Cobertura testes < 80% (CI exige ≥80%); `llm.py` (578 LOC) e `search.py` (353 LOC) sub-testados | `00-index.md` Gap 4 / `05-testes-infra.md` Gap 4 |
| S0-5 | 🟡 | Frontend tests (`frontend/tests/frontend.test.mjs`) existem mas não no CI | `05-testes-infra.md` Gap 1 |
| S0-6 | 🟡 | Integration tests dependem de chaves externas (Jina/SerpAPI/LLM) | `05-testes-infra.md` Gaps 2-3 |
| S0-7 | 🟡 | `.env` vs `.env.example` podem dessincronizar | `05-testes-infra.md` infra status |

---

## S1 — Núcleo & Persistência (`01-nucleo-persistencia.md`)

| # | Etiqueta | Gap | Origem |
|---|----------|-----|--------|
| S1-1 | 🟡 | `settings.py` hot-reload de `jina_base_url`/`jina_proxy_url` mas `AppSettings` não tem `jina_proxy_timeout_seconds` com default; migration 0005 sem `server_default` | `01-nucleo-persistencia.md` G1 |
| S1-2 | 🔴 | `AppSettings.id` é `Integer PK=1` (singleton) mas migration 0001 não mostra `pk=1` default — verificar seed | `01-nucleo-persistencia.md` G2 |
| S1-3 | 🟡 | `domain.md` cita "8 entidades" mas `domain_models.py` tem 9 classes (Base excluída); `Event` (`agent_event_logs`) é a 9ª | `01-nucleo-persistencia.md` G3 |

---

## S2 — API Ingress (`02-api-ingress.md`)

| # | Etiqueta | Gap | Origem |
|---|----------|-----|--------|
| S2-1 | 🔴 | `POST /api/research` resp: doc promete `{theme, message, stream_url:/stream}`; código retorna `stream_url=/events`, sem `theme/message` | `02-api-ingress.md` Gap 1 / `research.py:167` |
| S2-2 | 🔴 | `POST .../briefing/approve` resp: doc/plan prometem `{message, worker_count:20}`; código retorna `{research_id, status}` | `02-api-ingress.md` Gap 2 / `research.py:319` |
| S2-3 | 🔴 | `POST /api/reports/{id}/retry-callback` resp: doc `{dispatched_at, status_code}`; código `{success, delivered}` | `02-api-ingress.md` Gap 3 / `research.py:382` |
| S2-4 | 🔴 | Docs §7/§4 não listam `resume`/`edit`/`GET /api/research` embora GOAL exija | `02-api-ingress.md` Gap 4 |
| S2-5 | 🔴 | Recovery: código re-agenda `scouting/revising/approved/in_progress` **sem** marcar `INTERRUPTED`; docs §5 citam `scouting/in_progress → interrupted/resume` | `02-api-ingress.md` Gap 5 / `main.py:23-32` |
| S2-6 | 🟡 | Campo report: doc `citation_stats`; código `citation_metrics` + `audit_findings` | `02-api-ingress.md` Gap 6 / `research.py:364` |
| S2-7 | 🟡 | SSE envelope: doc múltiplos `event:`; código sempre `event: progress` com tipo no JSON | `02-api-ingress.md` Gap 7 / `research.py:338` |
| S2-8 | 🟡 | Auth: contracts §1 cita só Bearer; código aceita `X-API-Key` (GOAL item 2) | `02-api-ingress.md` Gap 8 |
| S2-9 | 🟡 | `X-Tenant-ID`: docs "ignored"; código **rejeita 400** — mais estrito | `02-api-ingress.md` Gap 9 / `security.py:33-34` |
| S2-10 | 🟡 | Imports mortos em `research.py`: `ProviderConfigurationError`, `SSRFSecurityViolation`, `SearchProviderError` | `02-api-ingress.md` Gap 10 / `research.py:15,18,19` |

---

## S3 — Serviços & Pipeline (`03-servicos-pipeline.md`)

| # | Etiqueta | Gap | Origem |
|---|----------|-----|--------|
| S3-1 | 🔴 | `workers/` SDK desconectado do pipeline ativo (`BaseWorker`, `ScoutWorker`, `WriterAgent`, `personas.py` nunca invocados por `run_research`) — duplicação de lógica | `03-servicos-pipeline.md` G1 |
| S3-2 | 🔴 | Prompts `.md` (personas) não carregados pelo pipeline ativo; prompts embutidos em `complete("persona", ...)` — drift de contrato | `03-servicos-pipeline.md` G2 / `pipeline/worker.py:127,142` |
| S3-3 | 🔴 | Sem deadline global em `run_research` (só scout tem `SCOUT_GLOBAL_TIMEOUT=120s`) | `03-servicos-pipeline.md` G3 / `research.py:121` |
| S3-4 | 🔴 | `app/agents/workers/` e `app/engine/` vazios | `03-servicos-pipeline.md` G4 |
| S3-5 | 🟡 | `WORK_LIMIT = Semaphore(20)` duplicado (`research.py:30` + `pipeline/worker.py:16`) — teto real por ponto = 2 instâncias independentes | `03-servicos-pipeline.md` G5 |
| S3-6 | 🟡 | Retries/deadline de `complete()` (llm.py) não verificados — workflow.md menciona retries | `03-servicos-pipeline.md` G7 |
| S3-7 | 🟡 | `read_source`/Jina reader path: SSRF validation confirmado só em `webhook.py`; não confirmado para fetch em `worker.py:50` | `03-servicos-pipeline.md` G8 |
| S3-8 | 🟡 | Truncamentos: `analysis[:8000]` confirmado (`worker.py:160`); contracts não cita valor 8000 | `03-servicos-pipeline.md` G9 |
| S3-9 | 🟡 | `WriterAgent.execute` (SDK) constrói markdown sem validação de citação/qualidade — diverge do writer ativo | `03-servicos-pipeline.md` inline |

---

## S4 — Frontend (`04-frontend.md`)

| # | Etiqueta | Gap | Origem |
|---|----------|-----|--------|
| S4-1 | 🔴 | Arquitetura real ≠ plan §7: monolito `main.tsx` 2697 + `style.css` 2090; sem `routes/`, `components/`, `stores/` Zustand | `04-frontend.md` G1 |
| S4-2 | 🔴 | SSE: client usa `/events` + evento único `progress` com `event.type` interno; contrato diz `/stream` + múltiplos `event:` nomeados | `04-frontend.md` G2 / `main.tsx:736` |
| S4-3 | 🔴 | `frontend/PLAN.md` desatualizado: manda settings em localStorage + payload research; código usa HttpOnly cookie + sessionStorage | `04-frontend.md` G3 |
| S4-4 | 🟡 | `briefing/edit` sem contrato: `POST .../briefing/edit {note, points}` não em contracts §7/plan | `04-frontend.md` G4 |
| S4-5 | 🟡 | `ui.tsx` primitivos não adotados — main.tsx usa classes CSS diretas | `04-frontend.md` G5 |
| S4-6 | 🟡 | Polling 4s fallback além do SSE sem spec; sem Last-Event-ID/resume explícito no client | `04-frontend.md` G6 |

---

## Resumo Quantitativo

| Módulo | 🔴 LACUNA (crítica) | 🟡 INFERIDO (atenção) | 🟢 CONFIRMADO |
|--------|---------------------|----------------------|---------------|
| S0 | 1 | 6 | — |
| S1 | 1 | 2 | — |
| S2 | 5 | 5 | 14 |
| S3 | 4 | 5 | 14 |
| S4 | 3 | 3 | 11 |
| **Total** | **14** | **21** | **39** |

---

## Próximos Passos Recomendados (prioridade)

1. **S2-1, S2-2, S2-3** — Alinhar responses de API (doc↔código) → breaking change ou doc update
2. **S2-5** — Recovery marcar `INTERRUPTED` ou atualizar docs §5
3. **S3-1, S3-2** — Conectar/remover `workers/` SDK; unificar source de prompts
4. **S3-3** — Adicionar deadline global em `run_research`
5. **S4-2** — SSE path/evento: unificar frontend/backend (`/events` vs `/stream`)
6. **S0-1** — Harden `validate_public_url` contra bypass IPv6
7. **S1-2** — Seed `AppSettings` id=1 na migration 0001 ou startup

---

*Artefatos fonte:* `/root/projects/deep-research/reversa/0{0..5}-*.md`
*Data:* 2026-10-06