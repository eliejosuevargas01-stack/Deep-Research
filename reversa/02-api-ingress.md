# S2 — API Ingress: main.py + routers (auth, research, settings)

## 1. Propósito

Mapear superfície HTTP real do backend: lifespan/startup/recovery em `app/main.py`, todos endpoints de `app/routers/` (auth, research, settings), SSE/stream, auth cookie vs Bearer vs X-API-Key, CSRF. Comparar rota-a-rota contra `contracts.md` §7 e `plan.md` §4 e `GOAL.md` §4 itens 1–2/8. Nível 2 Completo (sem C4/ERD/ADR).

## 2. Arquivos + LOC

Verificado via `wc -l` (checks executados):

| Arquivo | Linhas | Papel |
|---|---|---|
| `app/main.py` | 81 | FastAPI app, lifespan (recovery), CORS, `GET /health`, monta 3 routers, handler 422 |
| `app/routers/auth.py` | 49 | Sessão admin: login/me/csrf/logout |
| `app/routers/research.py` | 427 | CRUD research, briefing edit/approve, SSE, reports, retry-callback, resume + schedulers |
| `app/routers/settings.py` | 99 | GET/PUT settings, test key, discovery/list models |
| `app/core/security.py` (apoio, fora do escopo S2 mas lido p/ auth) | 114 | `require_admin`, `Principal`, CSRF, JWT/opaque, Bearer/X-API-Key |
| `app/middleware/` | — | **Não existe** (verificado: diretório ausente). CORS é `CORSMiddleware` em `main.py:62-68` |

Total escopo S2: 656 linhas.

## 3. Lifespan / startup / recovery (`app/main.py`)

- `lifespan` (`main.py:19-42`): se `DATABASE_URL` sqlite → `Base.metadata.create_all`. Depois abre sessão e coleta 3 grupos:
  - `status == "scouting"` → `schedule_scout(research_id)` (`:27-28`)
  - `status == "revising"` → `schedule_revision(research_id)` (`:29-30`)
  - `status IN ("approved","in_progress")` → `schedule(research_id)` (`:31-32`)
- Schedulers definidos em `research.py:25-28` (`schedule`), `:62-65` (`schedule_scout`), `:129-132` (`schedule_revision`): `asyncio.create_task` + registro em `_running: set[asyncio.Task]` (`research.py:22`).
- Shutdown (`main.py:34-42`): cancela tasks pendentes em `_running`, `await asyncio.gather(..., return_exceptions=True)`, `engine.dispose()` exceto `ENVIRONMENT == "test"`.
- `GET /health` (`main.py:74-81`): `SELECT 1`; 503 se DB indisponível; retorna `{status, database, version}`.
- CORS (`main.py:62-68`): `allow_origins=settings.origins`, `allow_credentials=True`, métodos GET/POST/PUT/PATCH/DELETE, headers `Content-Type, Authorization, X-CSRF-Token, Last-Event-ID`.
- Handler 422 (`main.py:48-59`): remove chave `input` dos erros de validação.

## 4. Tabela de endpoints (método / path / auth / file:linha)

Todas rotas confirmadas por leitura direta do decorator. Auth em todas (exceto `/health` e `POST /login`): `Depends(require_admin)` = cookie `dr_session` (JWT/opaque) **ou** `Authorization: Bearer` **ou** `X-API-Key` (ver §6). `X-Tenant-ID` → 400.

### 4.1 auth — `prefix="/api/auth"` (`auth.py:11`)

| # | Método + path | Auth | Request / Response | Definição |
|---|---|---|---|---|
| A1 | `POST /api/auth/login` | pública (valida `ADMIN_PASSWORD`) | Req `{password}` (`LoginRequest`). Resp `{authenticated, role:"admin", csrf_token}` + `Set-Cookie dr_session` HttpOnly, `Secure=settings.production`, `SameSite=lax`, `max_age=SESSION_TTL_HOURS*3600` | `auth.py:14` |
| A2 | `GET /api/auth/me` | `require_admin` | Resp `{authenticated:true, role:"admin"}`; sem credencial → 401 | `auth.py:29` |
| A3 | `GET /api/auth/csrf` | `require_admin` **cookie apenas** (sessão `None` → 403) | Regenera CSRF (`secrets.token_urlsafe(32)`), grava `csrf_hash=digest`. Resp `{csrf_token}` | `auth.py:34` |
| A4 | `POST /api/auth/logout` | `require_admin` (+ CSRF se cookie, via `require_admin`) | Revoga sessão (`revoked_at`), `delete_cookie`. Status 204, sem corpo | `auth.py:44` |

### 4.2 research — `prefix="/api"` (`research.py:21`)

| # | Método + path | Auth | Request / Response | Definição |
|---|---|---|---|---|
| R1 | `POST /api/research` `201` | `require_admin` (+CSRF se cookie) | Req `ResearchCreate{theme (≥3 chars, validado), callback_url?}`. Browser-cookie: `callback_url` no payload → **422** (só via Settings). Bearer/API-key: `callback_url` opcional validado por `validate_public_url` → 422 se inválido. Resp `{research_id, status:"scouting", briefing_url:/api/research/{id}, stream_url:/api/research/{id}/events}` + agenda scout + evento `scout_started` | `research.py:135` |
| R2 | `GET /api/research` | `require_admin` | Lista até 100 (`created_at desc`). Resp `[{research_id, theme, status, created_at}]` | `research.py:170` |
| R3 | `GET /api/research/{research_id}` | `require_admin` | 404 se ausente. Resp `{research_id, theme, status, callback_configured, callback_status (delivered/failed/pending), briefing_draft, error, briefing_edit_available (=status==pending_approval), points[{id,title,status,attempt_count,audit}], created_at, updated_at}` | `research.py:176` |
| R4 | `POST /api/research/{research_id}/briefing/edit` | `require_admin` (+CSRF se cookie) | Req `BriefingEdit{note (3-4000 chars, obrigatório), points?}`. Só se `status==pending_approval` e `approved_at is None` senão 409. Transição atômica → `status="revising"` + agenda `schedule_revision` + evento `briefing_edited`. Resp `{research_id, status:"revising"}` | `research.py:228` |
| R5 | `POST /api/research/{research_id}/briefing/approve` | `require_admin` (+CSRF se cookie) | Req `BriefingApproval{approved_points: exatamente 5, títulos únicos, deps válidas}`. UPDATE atômico `pending_approval→approved` + cria 5 `ResearchPoint` + agenda `schedule` + evento `briefing_approved`. Resp `{research_id, status:"approved"}`. 404/409 conforme estado | `research.py:287` |
| R6 | `GET /api/research/{research_id}/events` (canônico; é o `stream_url` retornado) | `require_admin` (sem CSRF: GET) | SSE `text/event-stream` (ver §5). 404 se research ausente | `research.py:322` |
| R7 | `GET /api/research/{research_id}/stream` (`include_in_schema=False`, alias de R6, mesma função) | idem R6 | Mesmo handler `events()` | `research.py:323` |
| R8 | `GET /api/reports/{identifier}` | `require_admin` | `identifier` = `report.id` **ou** `research_id` (`or_`). 404 se ausente. Resp `{report_id, research_id, content_markdown, citation_metrics, audit_findings, generated_at}` | `research.py:358` |
| R9 | `POST /api/reports/{identifier}/retry-callback` | `require_admin` (+CSRF se cookie) | Resolve report→research. 404 sem research; 409 sem `callback_url` ou sem report pronto. Chama `dispatch_callback`. Resp `{success, delivered}` | `research.py:367` |
| R10 | `POST /api/research/{research_id}/resume` | `require_admin` (+CSRF se cookie) | 404 ausente; 409 se `completed/completed_but_callback_failed` ou `in_progress/scouting`. Sem points → `status="scouting"` + `schedule_scout`; com points → `status="in_progress"` + `schedule`. Limpa `error`, emite `research_resumed` | `research.py:385` |

### 4.3 settings — `prefix="/api/settings"` (`settings.py:15`)

| # | Método + path | Auth | Request / Response | Definição |
|---|---|---|---|---|
| S1 | `GET /api/settings` (path `""`) | `require_admin` | Resp `public_settings(db)` (mascarado/booleano, sem segredo) | `settings.py:18` |
| S2 | `PUT /api/settings` (path `""`) | `require_admin` (+CSRF se cookie) | Req `SettingsUpdate{provider_keys, models, callback_url, openai_base_url, jina_base_url, jina_proxy_url, jina_proxy_auth_key, jina_proxy_timeout_seconds}` (`extra=forbid`; campos ausentes = `_UNSET`). 422 em `ValueError`. Hot-reload registry | `settings.py:23` |
| S3 | `POST /api/settings/test` | `require_admin` (+CSRF se cookie) | Req `ProviderTestRequest{provider: openai\|anthropic\|gemini\|litellm\|jina\|jina_proxy\|serpapi\|apify, api_key, base_url?}`. `jina_proxy`: ignora `api_key` do payload, usa `runtime_jina_proxy(db)`. Se sucesso + provider LLM → lista modelos (best-effort) | `settings.py:48` |
| S4 | `POST /api/settings/models` | `require_admin` (+CSRF se cookie) | Req `ModelDiscoveryRequest{provider: openai\|anthropic\|gemini\|litellm, api_key (≥1), base_url?}`. 400 em falha | `settings.py:71` |
| S5 | `GET /api/settings/models` (`?provider=`) | `require_admin` | Usa chaves do DB (`runtime_settings`), não do query. Default lista openai/anthropic/gemini/litellm. Resp `{models_by_provider}` | `settings.py:80` |

### 4.4 infra

| # | Método + path | Auth | Definição |
|---|---|---|---|
| H1 | `GET /health` | nenhuma | `main.py:74` |

Total mapeado: **20 handlers em 19 paths únicos** (R6/R7 compartilham função) + H1.

## 5. SSE / eventos

- Handler único `events()` (`research.py:324`): valida research (404), depois `StreamingResponse(generate(), media_type="text/event-stream", headers={Cache-Control:no-cache, X-Accel-Buffering:no})` (`research.py:355`).
- Resume: header `Last-Event-ID` → `last_event_id: int|None` (`research.py:324`); `cursor = last_event_id or 0`, poll `Event WHERE research_id AND id > cursor ORDER BY id` a cada 0.5s (`:329-354`).
- Envelope fixo: `id: {row.id}\nevent: progress\ndata: {id, persona, event_type, summary, metrics, created_at}` (`:336-338`). **Sempre `event: progress`**; tipo real vai dentro do JSON (`type`).
- Tipos emitidos pelo ingress: `scout_started` (R1), `briefing_ready` (`run_scout`, research.py:57), `scout_failed`, `briefing_edited` (:280), `briefing_approved` (:316), `research_resumed`, `research_failed`, `briefing_approved` (revision :106-112). Eventos de worker/auditor/writer/callback vêm de `app/services/*` (fora S2).
- Término: quando `status ∈ {completed, completed_but_callback_failed, blocked, failed}` e sem linhas novas → `break`, exceto se `callback_url` configurado e status `completed|blocked` sem evento `callback_delivered|callback_failed` → continua polling (`:339-353`).
- Fonte: tabela `agent_event_logs` (`Event`: `id` int autoincrement, `research_id`, `persona`, `event_type`, `summary≤500`, `metrics` JSON). Desconexão: `await request.is_disconnected()`.

## 6. Auth / CSRF (lido em `app/core/security.py`)

- `require_admin` (`security.py:31`): rejeita `X-Tenant-ID` com **400**; conta credenciais simultâneas (cookie + `Authorization` + `X-API-Key`) → >1 = **400** "Ambiguous authentication".
- Ordem: `Authorization: Bearer <API_AUTH_SECRET>` → `Principal(None, via_bearer=True)` (`:49-55`); `X-API-Key: <API_AUTH_SECRET>` → `Principal(None, via_api_key=True)` (`:57-61`); senão cookie `dr_session` = JWT HS256 `{sub, jti, iat, exp}` assinado com `SESSION_SECRET`, com fallback legado opaque (`digest(raw_cookie)`) (`:66-78`). Linha DB `AdminSession[token_hash]`; expirado/revogado → 401 (`:80-84`).
- CSRF (`security.py:86-90`): só para cookie-sessão em `MUTATIONS={POST,PUT,PATCH,DELETE}` (`security.py:17`); exige header `x-csrf-token` com `hmac.compare_digest(row.csrf_hash, digest(supplied))`, senão 403 + rollback. Bearer/API-key **isentam** CSRF (sem sessão). Login isento (ainda sem sessão); `GET /csrf` (GET) isento por método mas exige cookie válido.
- `Principal.session is not None` distingue browser (cookie) de máquina (Bearer/key) — usado em R1 para proibir `callback_url` no payload de browser.
- Cookie: nome `dr_session` (`security.py:16`).

## 7. Dependências (imports diretos)

- `main.py:10-15`: `app.core.config.settings`, `app.db.database (AsyncSessionLocal, engine)`, `app.models (Base, Research)`, routers auth/research/settings + `schedule, schedule_revision, schedule_scout`.
- `auth.py:6-9`: `config.settings`, `core.security (COOKIE, Principal, digest, new_session_values, require_admin)`, `db.get_db`, `schemas.LoginRequest`.
- `research.py:11-19`: `core.security`, `db (AsyncSessionLocal, get_db)`, `models (AuditTrail, Event, Report, Research, ResearchPoint)`, `schemas (BriefingApproval, BriefingEdit, ResearchCreate)`, `services.llm.ProviderConfigurationError` (importado, sem uso no arquivo), `services.research (add_event, point_dependencies, run_research, sanitize_error, scout)`, `services.webhook.dispatch_callback`, `tools.outbound (SSRFSecurityViolation [importado, sem uso], validate_public_url)`, `services.search.SearchProviderError` (importado, sem uso).
- `settings.py:3-13`: `core.security`, `db.get_db`, `schemas (ModelDiscoveryRequest/Response, ProviderTestRequest/Response, SettingsUpdate)`, `services.llm (list_provider_models, test_provider_key)`, `services.settings (_UNSET, get_record, public_settings, runtime_settings, update_settings)`.
- Schemas (lidos p/ contrato req/resp): `ResearchCreate` (theme ≥3, `extra=forbid`), `BriefingApproval` (exatamente 5 points, títulos únicos), `BriefingEdit` (note 3-4000), `SettingsUpdate` (`extra=forbid`), `ProviderTestRequest`, `ModelDiscoveryRequest`.

## 8. Doc-vs-código etiquetado (rota-a-rota)

Legenda: 🟢 CONFIRMADO (código ≡ doc) / 🟡 INFERIDO (código estende/renomeia, compatível) / 🔴 LACUNA/DIVERGÊNCIA.

### 8.1 `contracts.md` §7 vs código

| Doc (§7) | Código | Etiqueta + motivo |
|---|---|---|
| `POST /api/auth/login` → cookie HttpOnly + user meta | A1 (`auth.py:14`): cookie + `{authenticated, role, csrf_token}` | 🟢 CONFIRMADO (detalhe: doc diz `user:"admin"`, código diz `role:"admin"` — mesma semântica) |
| `POST /api/auth/logout` revoga + limpa | A4 (`auth.py:44`): 204 + `revoked_at` + `delete_cookie` | 🟢 CONFIRMADO |
| `GET /api/auth/me` → status/401 | A2 (`auth.py:29`) | 🟢 CONFIRMADO |
| `POST /api/research` `{theme, callback_url?}` → 201 `{research_id, status, briefing_url, stream_url}` | R1 (`research.py:135`): `stream_url` = `/api/research/{id}/events` (doc §7 diz `/stream`); resp **sem** `theme`/`message` que `plan.md` §4 promete | 🟡 INFERIDO c/ 🔴 DIVERGÊNCIA de payload: rota existe, mas `stream_url` canônico é `/events` (`/stream` só alias oculto `:323`); `theme`+`message` ausentes |
| `GET /api/research/{id}` → status + draft + progresso | R3 (`research.py:176`) + extras `callback_configured/callback_status/error/points` | 🟢 CONFIRMADO (código é superconjunto) |
| `POST .../briefing/approve {approved_points}` → 200 | R5 (`research.py:287`): resp só `{research_id, status:"approved"}`; doc/plan prometem `message` + `worker_count:20` | 🔴 DIVERGÊNCIA de response (rota ok, corpo menor) |
| `GET .../stream` SSE `event: progress` | R6+R7 (`research.py:322-323`): dual `/events` (documentado no `stream_url`) + `/stream` (`include_in_schema=False`); envelope **sempre** `event: progress` | 🟡 INFERIDO (compatível via alias; tipos plan §4 `brief_ready/worker_progress/audit_decision/report_ready` vão no JSON interno, não no campo `event`) |
| `GET /api/reports/{id}` → markdown + métricas + audit | R8 (`research.py:358`): aceita `report.id` **ou** `research_id`; campos `citation_metrics`/`audit_findings` (doc diz `citation_stats`) | 🟡 INFERIDO (lookup estendido; nome de campo difere) |
| `POST /api/reports/{id}/retry-callback` → 200 | R9 (`research.py:367`): resp `{success, delivered}`; doc promete `{success, dispatched_at, status_code}` | 🔴 DIVERGÊNCIA de response |
| `GET /api/settings` mascarado | S1 (`settings.py:18`) | 🟢 CONFIRMADO |
| `PUT /api/settings` AES-256-GCM + hot-reload | S2 (`settings.py:23`) delega `update_settings` (criptografia fora S2) | 🟢 CONFIRMADO (ingress; cripto verificada em outro escopo) |
| Webhook `POST callback_url {research_id, theme, content_markdown, generated_at}` + SSRF | Outbound em `services/webhook` (fora S2); ingress valida `callback_url` via `validate_public_url` (R1) | 🟢 CONFIRMADO no ingress (validação); payload de dispatch fora S2 |

### 8.2 `plan.md` §4 vs código (só deltas além de §8.1)

| Plan §4 | Etiqueta |
|---|---|
| Auth: "cookie **ou** Bearer; `X-Tenant-ID` rejeitado; CSRF em mutações browser" | 🟢 CONFIRMADO (`security.py:31-90`; código ainda aceita `X-API-Key` como 3ª forma — ver GOAL) |
| `POST /api/research` resp com `theme/message/stream_url=/stream` | 🔴 DIVERGÊNCIA (mesma de §8.1) |
| Approve resp `worker_count:20` | 🔴 LACUNA (código não retorna) |
| SSE eventos `progress/brief_ready/worker_progress/audit_decision/report_ready` | 🟡 INFERIDO (envelope único `progress`; semântica no JSON) |
| Settings GET/PUT mascarado | 🟢 CONFIRMADO |

### 8.3 `GOAL.md` §4 itens 1–2/8 vs código

| GOAL | Código | Etiqueta |
|---|---|---|
| Item 1: auth/session + create + status + approve/edit + event stream + report + retry + settings + health + **resume explícito** | Todos presentes: A1-A4, R1, R3, R5, **R4 edit**, R6/R7, R8, R9, S1-S2, H1, **R10 resume** | 🟢 CONFIRMADO (resume e edit existem no código embora ausentes em contracts §7/plan §4) |
| Item 2: cookie JWT HttpOnly + `X-API-Key` alternativo (não cumulativo), 401, CSRF mutações | `security.py`: JWT/opaque + Bearer + X-API-Key, exclusividade (400 se múltiplo), 401 sem credencial, CSRF só cookie-mutações | 🟢 CONFIRMADO (código cobre Bearer **e** X-API-Key; contracts §1 citava só Bearer — doc-doc diverge, código atende GOAL) |
| Item 8: SSE sanitizado, `Last-Event-ID` resume sem duplicação | `Last-Event-ID` → cursor (`research.py:324,330`); poll `id > cursor` | 🟢 CONFIRMADO (sanitização de conteúdo fora S2) |

### 8.4 Rotas no código sem doc (doc-sem-cobertura)

| Rota | Status doc | Etiqueta |
|---|---|---|
| `GET /api/research` (R2) | Ausente em contracts §7 e plan §4 | 🟡 INFERIDO (listagem; exigida implicitamente por GOAL "status" e UI home) |
| `POST .../briefing/edit` (R4) | Ausente em contracts/plan; GOAL item 1 exige "approval/edit" | 🟡 INFERIDO (coberto por GOAL, lacuna em contracts/plan) |
| `POST .../resume` (R10) | Ausente em contracts §7/plan §4; **exigido** GOAL item 1 | 🔴 LACUNA doc-sem-código-inverso (código-à-frente: existe, docs §7/§4 não listam) |
| `GET /api/auth/csrf` (A3) | Ausente nos docs | 🟡 INFERIDO (detalhe de protocolo CSRF) |
| `POST /api/settings/test`, `POST /api/settings/models`, `GET /api/settings/models` (S3-S5) | Ausentes em contracts §7/plan §4 | 🟡 INFERIDO (operações de apoio UI) |
| `GET /health` (H1) | Citado em contracts §10 (`GET /health`), não em §7 | 🟢 CONFIRMADO via §10 |

## 9. Gaps (consolidação acionável)

1. 🔴 **Response `POST /api/research`**: alinhar doc (`theme`, `message`, `stream_url=/stream`) ou código (`/events`, sem `theme/message`). Fonte: `research.py:167` vs contracts §7/plan §4.
2. 🔴 **Response approve**: doc promete `{message, worker_count:20}`; código retorna `{research_id, status}` (`research.py:319`). Decidir: incluir `worker_count` ou corrigir doc.
3. 🔴 **Response retry-callback**: doc `{dispatched_at, status_code}`; código `{success, delivered}` (`research.py:382`). Alinhar.
4. 🔴 **Docs §7/§4 não listam `resume`/`edit`/`GET /api/research`** embora GOAL exija resume/edit. Atualizar contracts §7 ou aceitar código-à-frente.
5. 🔴 **Recovery**: contracts §5 fala `scouting/in_progress → interrupted/resume`; código recupera `scouting/revising/approved/in_progress` via re-agendamento **sem** marcar `INTERRUPTED` (`main.py:23-32`). Status extras (`revising`, `failed`, `blocked`, `completed_but_callback_failed`) não constam do enum documentado em plan §3.
6. 🟡 **Campo report**: doc `citation_stats`; código `citation_metrics` + `audit_findings` (`research.py:364`). Renomear ou documentar.
7. 🟡 **SSE envelope**: doc sugere múltiplos `event:`; código emite sempre `event: progress` com tipo no JSON (`research.py:338`). Documentar envelope real.
8. 🟡 **Auth tripla**: contracts §1 cita só Bearer; código + GOAL aceitam `X-API-Key` (e Bearer). Uniformizar texto contracts §1.
9. 🟡 **`X-Tenant-ID`**: docs "ignored and rejected"; código **rejeita com 400** (`security.py:33-34`) — mais estrito que "ignorar". Confirmar como comportamento canônico.
10. 🟡 **Imports mortos em `research.py`**: `ProviderConfigurationError` (`:15`), `SSRFSecurityViolation` (`:18`), `SearchProviderError` (`:19`) importados sem uso no arquivo — ruído, sem impacto funcional.

*Checks: `wc -l` executado (81/49/427/99); cada rota acima confirmada por leitura direta do decorator (`@router.*` / `@app.get`). Sem rede, sem commit, sem alteração de código.*
