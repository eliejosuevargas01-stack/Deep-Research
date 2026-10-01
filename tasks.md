# Deep Research Engine - Phased Atomic Task Breakdown

## Counting Convention

- **38 numbered work items**: T001–T038.
- **41 executable rows**: T018 is deliberately split into T018a–T018d (four persona implementations).
- `[//]` marks work that can run in parallel after listed dependencies pass.
- Local implementation, Compose, and E2E execution are authorized. Public deployment, external DNS, and TLS changes require applicable separate authorization and real infrastructure access.

## Phase 0 - Baseline & Database

| ID | Description | Target | Dependencies | Parallel | Status |
|---|---|---|---|---|---|
| T001 | Inspect and preserve existing untracked/partial backend, frontend, and Alembic work; fill only missing structure. | `app/`, `frontend/`, `alembic/` | — | `[//]` T002 | ⬜ |
| T002 | Confirm dependency manifests before imports. Add only required dependencies. Create first-run environment initializer that preserves existing `.env`, generates local `APP_ENCRYPTION_KEY`, `SESSION_SECRET`, admin bootstrap secret, and DB password only when absent; never fabricates provider credentials. | dependency manifests, `scripts/generate_env.py`, `.env.example` | — | `[//]` T001 | ⬜ |
| T003 | Configure async SQLAlchemy engine/session and real readiness query. | `app/db/database.py` | T002 | — | ⬜ |
| T004 | Finalize canonical models and initial Alembic migration for research, points, evidence, audits, reports, encrypted settings, public event logs, and revocable `admin_sessions`, including durable job claim/heartbeat/stage fields. | `app/models/domain_models.py`, `alembic/versions/001_initial_schema.py` | T003 | — | ⬜ |

## Phase 1 - Security, Settings & Outbound Network

| ID | Description | Target | Dependencies | Parallel | Status |
|---|---|---|---|---|---|
| T005 | Implement AES-256-GCM settings encryption with authenticated round-trip tests. | `app/services/crypto.py` | T002 | `[//]` T006, T007 | ⬜ |
| T006 | Implement one connection-pinned outbound HTTP transport: reject private/reserved IPv4/IPv6 and metadata addresses at connection time, preserve TLS hostname validation, disable or revalidate redirects, and apply it to readers and callbacks. DNS pre-resolution alone is insufficient. | `app/tools/ssrf_guard.py` | T002 | `[//]` T005, T007 | ⬜ |
| T007 | Implement single-admin authentication: `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me`; secure HttpOnly/SameSite cookies, session revocation, CSRF checks, optional server-managed Bearer API auth, and explicit rejection of `X-Tenant-ID` as identity. | `app/middleware/security.py`, `app/routers/auth.py`, auth schemas | T002, T004 | `[//]` T005, T006 | ⬜ |
| T008 | Implement masked `GET /api/settings` and encrypted `PUT /api/settings`; server assigns fixed admin context and refreshes provider cache. | settings model/schemas/router | T004, T005, T007 | — | ⬜ |

## Phase 2 - Providers, Public Events & Scout

| ID | Description | Target | Dependencies | Parallel | Status |
|---|---|---|---|---|---|
| T009 | Build multi-provider LLM gateway and per-agent model selection using DB settings, then environment fallback. Avoid invented precise provider model/version defaults. | `app/services/llm.py` | T008 | — | ⬜ |
| T010 | Define public event schema/builder. Generate lifecycle summaries separately from model completions; raw model streams never enter logs/SSE. Sanitization is defense-in-depth only. | `app/services/event_stream.py`, event schemas | T004 | `[//]` T011 | ⬜ |
| T011 | Validate prompts for Scout, four personas, Auditor, and Writer; require evidence/uncertainty outputs without requesting private chain-of-thought. | `app/prompts/personas.json` | — | `[//]` T010 | ⬜ |
| T012 | Implement durable Scout stage plus `POST /api/research` and `GET /api/research/{id}`. Persist `scouting` before dispatch and `pending_approval` with five draft points. | `app/agents/scout.py`, `app/routers/research.py` | T006, T009, T010, T011 | — | ⬜ |

## Phase 3 - Tools, Workers & Audit

| ID | Description | Target | Dependencies | Parallel | Status |
|---|---|---|---|---|---|
| T017 | Implement search-read-clean through the connection-pinned transport; retain canonical URL, extracted text/quote, retrieval time, and source metadata. | `app/tools/search_pipeline.py` | T006 | — | ⬜ |
| T019 | Implement `BaseWorker` before any concrete persona; integrate search, LLM synthesis, evidence persistence, and public events. | `app/agents/workers/base_worker.py` | T009, T010, T017 | — | ⬜ |
| T018a | Implement `HistorianWorker` from `BaseWorker`. | `app/agents/workers/historian.py` | T019 | `[//]` T018b–T018d | ⬜ |
| T018b | Implement `SkepticWorker` from `BaseWorker`. | `app/agents/workers/skeptic.py` | T019 | `[//]` T018a, T018c, T018d | ⬜ |
| T018c | Implement `PragmatistWorker` from `BaseWorker`. | `app/agents/workers/pragmatist.py` | T019 | `[//]` T018a, T018b, T018d | ⬜ |
| T018d | Implement `FuturistWorker` from `BaseWorker`. | `app/agents/workers/futurist.py` | T019 | `[//]` T018a–T018c | ⬜ |
| T013 | Implement global in-process `asyncio.Semaphore(20)` worker pool with bounded timeouts and error capture. | `app/engine/worker_pool.py` | T018a–T018d | `[//]` T014 | ⬜ |
| T014 | Implement evidence repository optimistic locking and bounded jittered retry. | `app/repository/evidence_repo.py` | T004 | `[//]` T013 | ⬜ |
| T015 | Implement authenticated `GET /api/research/{id}/stream` from persisted/allowlisted public events, with reconnect cursor support. | `app/services/event_stream.py`, research router | T007, T010 | — | ⬜ |
| T020 | Implement Auditor completeness, contradiction, and uncertainty logic over collected evidence. | `app/engine/auditor.py` | T013, T014 | `[//]` T021 | ⬜ |
| T021 | Implement Citation Auditor mapping each substantive claim to stored extracted text/quote and URL. Reachability alone never marks a claim verified; sample critical claims against source text. | `app/tools/citation_auditor.py` | T006, T014 | `[//]` T020 | ⬜ |
| T022 | Implement max-three-attempt audit/research loop; persist `BLOCKED`, caveats, uncertainty, and unresolved claims on final failure. | `app/engine/retry_handler.py` | T020, T021 | — | ⬜ |

## Phase 4 - Writer, Callback & Final Orchestration

| ID | Description | Target | Dependencies | Parallel | Status |
|---|---|---|---|---|---|
| T023 | Implement Writer grounded in approved evidence mappings; surface blockers and uncertainty; do not claim zero hallucinations. | `app/agents/writer.py` | T009, T022 | `[//]` T024 | ⬜ |
| T024 | Implement callback dispatch through the same connection-pinned SSRF transport, with timeout/failure audit records. | `app/services/webhook.py` | T006 | `[//]` T023 | ⬜ |
| T025 | Implement `GET /api/reports/{id}` and `POST /api/reports/{id}/retry-callback` with authentication and callback audit trail. | research/report router | T023, T024 | — | ⬜ |
| T016 | Final Orchestrator integration **after** Scout, BaseWorker/personas, pool, evidence repository, events, Auditor/retry, Writer, and callback. Add `POST /api/research/{id}/briefing/approve`; validate one-time transition, point dependency DAG, idempotent stage commits, startup recovery sweep for stale `scouting`/`in_progress`, and single-instance execution semantics. | `app/engine/orchestrator.py`, research router, startup lifecycle | T012–T015, T018a–T025 | — | ⬜ |

## Phase 5 - Frontend

| ID | Description | Target | Dependencies | Parallel | Status |
|---|---|---|---|---|---|
| T026 | Build React app shell and login route using credentialed same-origin requests; no API secret in bundle or browser storage. | frontend root/login | T007, T016 | `[//]` T027 | ⬜ |
| T027 | Build typed API/session stores, CSRF handling, logout, and auth-expiry behavior. | frontend stores/lib | T026 | — | ⬜ |
| T028 | Build topic submission, recent research, and status polling using create/status routes. | chat/home UI | T027 | `[//]` T029, T032 | ⬜ |
| T029 | Build one-time editable/reorderable five-point approval UI. | briefing UI | T027 | `[//]` T028, T030 | ⬜ |
| T030 | Build SSE persona/public status UI with reconnect cursor and no raw-reasoning display path. | persona/process UI | T027 | `[//]` T029, T031 | ⬜ |
| T031 | Build Markdown report viewer with claim/evidence drawer, uncertainty/blocker display, and copy action. | report UI | T027 | `[//]` T030 | ⬜ |
| T032 | Build secure settings UI and logout; provider secrets are write-only/masked. | settings UI | T027 | `[//]` T028 | ⬜ |

## Phase 6 - Containers & Deployment Specification

| ID | Description | Target | Dependencies | Parallel | Status |
|---|---|---|---|---|---|
| T033 | Build backend/frontend images and Nginx same-origin proxy; disable SSE buffering and set timeout. | Dockerfiles, `nginx.conf` | T002, T026 | — | ⬜ |
| T034 | Build local Compose with Postgres, exactly one backend process/replica, frontend, health checks, migration gate, persistent volume, and generated local DB password. | `docker-compose.yml` | T003, T004, T033 | — | ⬜ |
| T035 | Investigate actual Coolify/Traefik network/router conventions from authorized infrastructure before producing deployment labels; keep proposed config separate from verified deployed config. | deployment docs/config | T034 | — | ⬜ |
| T036 | Implement local deployment gate (build, migration, `GET /health`, auth/SSE smoke). Production mode additionally checks actual DNS/TLS only when credentials/access and separate authorization exist. | deployment gate script/docs | T035 | — | ⬜ |

## Phase 7 - End-to-End Verification

| ID | Description | Target | Dependencies | Parallel | Status |
|---|---|---|---|---|---|
| T037 | Run local containerized E2E: login, settings, create, one-time approval, status, public events, report, logout, callback failure, private-IP/redirect SSRF rejection, concurrency cap, and restart recovery. | E2E tests/report | T016, T025, T032, T034 | — | ⬜ |
| T038 | If and only if production access/authorization and real provider credentials exist, run live deployment E2E at `research.dominuslabs.online`; validate claim traceability and manually sample high-risk claims. Otherwise record concrete blockers without fabricating deployment or results. | live verification report | T036, T037 | — | ⬜ |

## Dependency Invariants

1. `BaseWorker` (T019) precedes concrete personas (T018a–T018d).
2. Final Orchestrator integration (T016) follows workers, Auditor, Citation Auditor, retry loop, Writer, callback, and events.
3. Required API surface includes login/logout/me, create, one-time approval, status, events, report, callback retry, and settings.
4. Durable DB states and startup recovery prevent silent job loss after process restart; in-process tasks alone are insufficient.
5. Compose runs one backend until database lease/distributed queue support exists.
6. Local execution is authorized; public deployment/DNS/TLS remain separately gated.