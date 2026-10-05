# Deep Research Engine - Canonical Project Goal & Mission Definition

## 1. Problem Statement & Mission

Build an autonomous, distributed, full-stack Deep Research Engine capable of executing rigorous, multi-agent investigative workflows across the live web. The system combines:
1. **Cognitive 4-Phase Research Pipeline**: Scout & Briefing → 4-Persona Parallel Investigation → Fact-Checking Auditor → Markdown Report Synthesizer.
2. **Interactive Chat Frontend**: A precision Linear-styled UI (React 19, Tailwind CSS, TanStack Router) providing a one-time human-in-the-loop brief review/edit, real-time agent process summaries, and interactive report rendering.
3. **API-First Backend**: The complete research lifecycle must also be usable without the frontend through authenticated backend-to-backend API calls using `X-API-Key`. Frontend and API are two supported surfaces over the same research engine.
4. **Persisted Encrypted Settings**: Database storage for LLM provider keys, optional search/proxy credentials and per-agent model assignments with AES-256-GCM encryption and immediate runtime effect.
5. **Self-Managed Deployment**: The repository must include a Docker Compose stack that provisions its own PostgreSQL service, persistent volume, backend, frontend/reverse proxy, runtime dependencies, health checks and database migrations. Local infrastructure bootstraps itself without manual database/schema/table creation.
6. **Production Deployment Target**: Locally verified Docker Compose environment with automated database migrations, plus an investigated Traefik/Coolify deployment specification for `research.dominuslabs.online`. Public DNS/TLS execution requires real infrastructure access and separate authorization.

The engine must produce high-density, fact-checked research reports backed by rigorous, traceable citations mapped to extracted source content, evidence-grounded synthesis, explicit uncertainty scoring, adversarial contradiction auditing, resumable durable execution and bounded provider-aware performance.

---

## 2. Scope Reconciliation (Revocation of Legacy Exclusions)

Previous planning documents mistakenly marked the frontend interface, real LLM execution, and cloud deployment as out-of-scope. **Those exclusions are formally revoked.** The canonical scope is defined as follows:

| Component | Legacy Status | Canonical Reconciled Status | Rationale |
|-----------|---------------|-----------------------------|-----------|
| **Chat Frontend UI** | *Out of scope* | **IN SCOPE (Mandatory)** | Operators require a chat UI to submit research topics, edit/approve the 5-point brief in one round, monitor live agent process summaries, configure settings, resume work and inspect reports. |
| **Backend API Surface** | *Partially specified* | **IN SCOPE (Mandatory)** | The system must remain fully operable without the frontend for backend-to-backend clients authenticated by `X-API-Key`. |
| **Live LLM Execution** | *Out of scope (mocked)* | **IN SCOPE (Mandatory)** | The pipeline must execute real LLM calls for Scout, 4 Persona Workers, Auditor, and Writer using dynamic model configuration through the common backend gateway. |
| **Encrypted Settings** | *Not specified* | **IN SCOPE (Mandatory)** | API keys, proxy authentication secrets and per-agent model selections must be persisted in PostgreSQL with AES-256-GCM encryption and dynamic runtime hot-reload. Local personal secrets (`SESSION_SECRET`, `APP_ENCRYPTION_KEY`) auto-generated on first run only. |
| **Self-Managed Docker Compose** | *Partial/local* | **IN SCOPE (Mandatory)** | A single documented build/up flow must provision Postgres, persistent storage, migrations, backend and frontend without manual DB/schema/table setup. |
| **Docker Compose & Deployment** | *Out of scope (local only)* | **IN SCOPE (Mandatory)** | The complete system must be containerized locally with health checks and auto-migration. Public cloud deployment to `research.dominuslabs.online` requires specification, distinct from actual execution because external DNS/TLS configuration require explicit authorization and real access. |
| **Agent Process Streaming** | *Not specified* | **IN SCOPE (Mandatory)** | Server-Sent Events (SSE) must stream explicitly generated structured public status summaries, learning summaries and declared next steps while strictly preventing private reasoning tokens or raw completion streams from entering the pipeline. |
| **Dual Search Mode** | *Not specified* | **IN SCOPE (Mandatory)** | The engine must work with zero search credentials by default and optionally switch to an authenticated Jina relay/proxy for high-speed search-and-read execution. |
| **Durable Resume** | *Restart-only recovery* | **IN SCOPE (Mandatory)** | Interrupted or `failed` research must be explicitly resumable from the latest valid persisted checkpoint without discarding approved points or collected evidence. |

---

## 3. Operator Experience & Security Workflow (UX Walkthrough)

1. **Access & Administrator Authentication**:
   - Operator navigates to `https://research.dominuslabs.online` (or local development URL).
   - Access is secured under a single-admin application model via `POST /api/auth/login`.
   - Browser receives the user's signed JWT in an `HttpOnly`, `SameSite=Lax` (or `Strict`), `Secure` cookie with anti-CSRF protection. PostgreSQL stores only the JWT identifier (`jti`) hash, expiry, revocation, and CSRF metadata. Client-side code never reads the JWT or receives raw API keys (`API_AUTH_SECRET`).
   - Backend-to-backend API clients authenticate with `X-API-Key`; this credential is not required from browser clients. Each request uses exactly one authentication method according to its client type: user JWT cookie for the frontend, or API key for backend clients.
   - The backend API must expose the complete research lifecycle required by non-browser clients: create research, inspect status, approve/edit briefing, consume events, fetch reports, configure callback per request and resume eligible interrupted/failed research.
   - Tenant context is strictly server-derived (`default`), ignoring any spoofed client headers like `X-Tenant-ID`.
2. **Settings Configuration**:
   - Operator navigates to the Settings page (`/settings`).
   - Local cryptographic keys (`APP_ENCRYPTION_KEY`, `SESSION_SECRET`, local DB password) are initialized on first run and persisted safely only if absent. Existing values are strictly preserved.
   - External provider keys (OpenAI, Anthropic, Gemini, SerpAPI, Apify, Jina) are entered via the UI when those providers are intentionally configured and persisted to PostgreSQL encrypted with AES-256-GCM.
   - Search works in **free mode by default**, with no search-provider credential required. Free mode uses a credential-free search source and Jina Reader without authentication for readable page extraction when applicable, subject to provider rate limits.
   - The operator may enable **Jina Proxy accelerated mode** by configuring only a Jina relay/Cloudflare Worker base URL and the relay authentication secret. The Deep Research application must not require, expose, rotate, or manage the Jina API-key pool behind that relay; key rotation/failover belongs to the relay implementation.
   - SerpAPI and Apify remain supported as optional alternative search/extraction providers and are not mandatory for the zero-configuration default search path.
   - Frontend operators may configure an optional callback URL in Settings, persisted by the backend. Backend-to-backend clients have no Settings UI and may instead submit an optional `callback_url` with each authenticated `POST /api/research` request.
   - Operator selects currently available provider/model identifiers for each role: Scout, Historian, Skeptic, Pragmatist, Futurist, Auditor, and Writer. Values come from configuration/provider discovery rather than speculative hardcoded versions.
   - Changes take immediate runtime effect without container restart.
3. **Research Submission**:
   - Frontend operators enter only the research topic/theme; the backend uses the optional callback URL saved in Settings. Backend-to-backend clients submit the topic and may include a per-request `callback_url`, which is validated and persisted with that research for delivery and retry; otherwise they retrieve the report by ID.
   - The same engine must be reachable through the frontend flow and through the authenticated REST API.
4. **Scout & One-Time Human Brief Review**:
   - Scout agent runs concise web exploration, extracts recurring themes, and drafts exactly 5 investigation points with dependency and parallelism flags.
   - The UI presents the 5-point brief in an interactive review card; API clients receive the same draft structurally through the backend.
   - Operator can reorder points, edit titles/descriptions, toggle parallel execution, or add missing angles.
   - Approval persists the canonical research points and starts execution.
5. **Live Process Streaming (Privacy-Guarded)**:
   - Orchestrator spawns 4 specialist personas per point (up to 20 concurrent workers).
   - The UI and authenticated API event stream expose live progress per point and persona:
     - status badges (`Searching`, `Reading sources`, `Synthesizing`, `Auditing`);
     - source/result counts;
     - explicitly generated public learning summaries;
     - declared next search/action;
     - audit score/verdict and retry instructions.
   - **Privacy Boundary**: Public streams emit only explicitly generated structured lifecycle events. Raw model completion streams and private chain-of-thought tokens are never queued or streamed.
6. **Auditor Fact-Check & Quality Loop**:
   - As workers finish a point, the Auditor evaluates the 4 perspectives for that single point against 12 canonical criteria.
   - Each criterion is recorded as satisfied/not satisfied. **10 of 12 or more (≥80%) means `APPROVED`; fewer than 10 means `RETRY` unless the retry ceiling has been reached.**
   - On retry, the Auditor emits concrete missing-research instructions and workers reuse valid persisted evidence, researching only remaining gaps whenever possible.
   - There are up to 3 retries after the initial worker execution (4 total executions per point).
   - If the fourth execution remains insufficient, the point transitions to `BLOCKED`, retains evidence and audit findings, and advances with explicit caveats instead of preventing the Writer forever.
7. **Durable Resume & Recovery**:
   - All valid progress is durably persisted in PostgreSQL: briefing, points, point status, attempt counters, evidence, audits, events and reports.
   - Startup recovery resumes in-flight states after process restart.
   - A separate explicit resume capability must allow eligible `failed`/interrupted research to continue from the latest valid checkpoint. Already `APPROVED` or `BLOCKED` points are not automatically redone.
8. **Report Delivery & Inspection**:
   - Writer starts after every point has reached a terminal research state (`APPROVED` or `BLOCKED`).
   - Writer synthesizes the final Markdown report grounded strictly in persisted evidence, audited outlines and explicit caveats for blocked/inconclusive points.
   - The final report is persisted and remains retrievable through `GET /api/reports/{id}`. Frontend users inspect it in the research UI; backend API clients fetch it by research/report ID.
   - If a callback URL is configured in frontend Settings or supplied by a backend-to-backend client on the research request, the system validates the destination and dispatches an asynchronous HTTP POST payload. Callback delivery is optional and does not replace report retrieval by ID.

---

## 4. Definition of Done (Testable Acceptance Criteria)

1. **FastAPI Backend Core & Complete API Surface**:
   - Clean architecture implemented in `app/{core,db,models,schemas,services,routers,prompts,tools,docs,main.py}` or a documented refined equivalent produced by the architecture refactor.
   - Browser/frontend and backend-to-backend clients both exercise the same research engine.
   - Operational API includes authentication/session operations as appropriate, research creation/status, briefing approval/edit, authenticated event stream, report retrieval, callback retry, settings operations needed by frontend, health and an explicit research-resume operation for eligible failed/interrupted jobs.
2. **Security & Session Authentication**:
   - Single-admin security model. Server derives context without trusting client `X-Tenant-ID` headers.
   - Authentication validates the user JWT in the HttpOnly cookie for browser clients and `X-API-Key` for backend-to-backend clients, rejecting unauthenticated requests with `401 Unauthorized`. The two credentials are alternatives, not cumulative requirements.
   - CSRF protection enforced on mutating browser requests.
3. **Encrypted Settings & Dynamic Precedence**:
   - `app_settings` stores provider API keys and proxy authentication secrets encrypted with AES-256-GCM at rest.
   - Search mode defaults to `free` and requires no search credential.
   - Optional `jina_proxy` mode stores a configurable proxy/Worker base URL and encrypted proxy authentication secret. Jina upstream keys managed by the proxy must not be copied into the Deep Research application.
   - Configuration precedence strictly enforced: Database Stored Settings > Environment / `.env` defaults.
   - Changes take immediate runtime effect without container restart.
   - Local secrets generated on first run, preserving existing values.
4. **SSRF Guardrails & IP Pinning**:
   - `callback_url`, web reader/scraping URLs and configurable proxy endpoints enforce connection-level IP validation/pinning where technically applicable.
   - Outbound redirects are re-validated before following or disabled.
   - Requests targeting loopback, private/link-local networks and cloud metadata destinations are blocked.
5. **Real Multi-Agent Orchestration, Concurrency & Durable State**:
   - Scout agent uses real LLM calls to generate 5 distinct research points.
   - Orchestrator manages worker execution under a hard ceiling of **20 concurrent workers** (`asyncio.Semaphore(20)` or a functionally equivalent global limiter).
   - Durable job state stored in PostgreSQL.
   - Startup recovery detects in-flight research records and resumes them safely.
   - Explicit resume supports eligible interrupted/`failed` jobs without throwing away persisted valid progress.
6. **Search-Read-Clean Tooling, Performance & BaseWorker DAG**:
   - Shared worker/search abstractions implemented before concrete persona workers.
   - **Default free path:** with no search credentials configured, workers use a credential-free web-search source and Jina Reader without authentication for readable page extraction. Provider rate limits must be respected through bounded concurrency, queuing and backoff rather than intentional limit bypass.
   - **Accelerated Jina Proxy path:** when `jina_proxy` is enabled, workers send search/read requests to the configured Cloudflare Worker/Jina relay using the configured relay authentication secret. The relay is responsible for its own upstream Jina-key pool, rotation and provider-level failover.
   - If Jina Search returns usable page content together with search results, workers consume that returned content directly and do not automatically re-read the same URLs through Jina Reader unless needed.
   - SerpAPI and Apify remain optional alternate providers/fallbacks.
   - A worker search round (query + source acquisition + reading/extraction + public learning summary) has a target hard deadline of approximately **30 seconds**. With at most 3 rounds, one worker should not normally exceed approximately **90 seconds** of search-round wall time; independent personas and research points continue concurrently according to the DAG and global ceiling.
   - Auditor retries reuse persisted valid evidence and search only identified gaps whenever possible.
7. **Fact-Checking Auditor & Blocker Loop**:
   - Auditor records the 12 canonical checks and calculates the score explicitly.
   - `APPROVED` requires at least **10/12** criteria satisfied.
   - Below 10/12 yields targeted `RETRY` until the ceiling of 4 total point executions.
   - After the fourth insufficient execution the point becomes `BLOCKED`, retains findings/evidence and forwards caveats to Writer instead of halting the whole research.
8. **Privacy-Sanitized Live Process Stream**:
   - SSE endpoint streams explicitly generated structured events for scout progress, worker searches, source results, public learning summaries, next steps, audit scores/verdicts/retries and report readiness.
   - Zero leakage of raw internal reasoning, chain of thought, secret tool content or system prompt internals.
   - Stream reconnection resumes from the last event ID without duplication.
9. **Full-Stack Chat Frontend**:
   - React 19 + TanStack Router + Tailwind CSS interface with a chat-centered agent experience.
   - Chat view supports submission, interactive 5-point brief review/edit, real-time persona activity, public learning/next-step summaries, resume flow, markdown report view and settings management.
   - Settings expose the default `free` search mode plus optional `jina_proxy` fields for relay base URL and relay authentication secret; the UI does not ask for the relay's internal Jina-key pool.
   - Uses the user's JWT in an HttpOnly cookie with CSRF; never exposes the JWT to client-side code or backend API secrets to the frontend.
10. **Self-Managed Docker Compose & Deployment Gates**:
    - Multi-container Compose includes `postgres`, single `backend` replica and `frontend`/reverse proxy as applicable.
    - Compose automatically creates and mounts a named persistent PostgreSQL volume.
    - Health checks ensure Postgres is ready before backend initialization.
    - Backend automatically executes `alembic upgrade head` before serving traffic; migrations are the canonical creation/evolution mechanism for schemas, tables, indexes and constraints.
    - Image builds install all Python/Node/runtime dependencies; the operator does not manually install packages inside containers.
    - First-run bootstrap safely creates missing local system secrets/passwords required by the stack without overwriting existing values.
    - The documented local happy path is a single `docker compose up --build` (or equivalent) flow; no manual PostgreSQL database, volume, schema, table or SQL preparation is required.
    - External credentials remain necessary only for deliberately chosen external LLM/integration providers; the canonical free search path itself requires no search credential.
    - Cloud deployment, public DNS for `research.dominuslabs.online`, and TLS verification remain separate infrastructure actions requiring real access/authorization.

---

## 5. What Exists & Adaptation Plan

### Codebase & Reference Inventory

1. **Current Codebase**:
   - `app/core/config.py`: Pydantic settings and environment fallback; must coexist with dynamic encrypted database settings and first-run local secret bootstrap.
   - `app/db/database.py`: async SQLAlchemy engine/session layer; must support migration-first self-managed boot.
   - `app/models/domain_models.py`: canonical persistence for research, points, evidence, events, reports, audits, sessions and settings.
   - `app/schemas/`: request/response schemas for frontend and backend API consumers.
   - `app/routers/`: API boundaries for auth, research, settings, events/reports and explicit resume.
   - `app/services/`: business/application services, including research orchestration, LLM gateway, audit, settings, crypto and webhook functionality.
   - `app/tools/search_pipeline.py`: search/reader functions; needs the canonical `free`/`jina_proxy` split, direct reuse of content returned by accelerated Jina Search, provider-aware limits and explicit per-round deadlines.
   - Worker/agent modules: common BaseWorker/WorkerResult contracts plus the four persona implementations, Scout, Auditor and Writer.
   - `frontend/`: full UI target; current monolithic implementation remains a refactor target.
   - `alembic/`: canonical database evolution mechanism.
   - `docker-compose.yml`/`compose.yml`: must become the zero-manual-database-setup local bootstrap path.
2. **Reference Projects**:
   - `/root/projects/Dominuslabs`: Dockerfile patterns, Nginx proxy configuration, and Coolify/Traefik integration for `*.dominuslabs.online`.
   - `/root/RENDER_LLM_ROUTER`: Multi-provider LLM routing patterns, schema validation, and provider fallback logic.
   - `eliejosuevargas01-stack/cloudflare_worker`: Reference implementation for the authenticated Jina relay/proxy, including upstream key rotation/failover. Deep Research consumes only its base URL and relay authentication secret when `jina_proxy` mode is enabled.

### Adaptation Mapping

| Existing Asset | Canonical Adaptation |
|----------------|----------------------|
| `app/models/domain_models.py` | Ensure durable job state, evidence/audit retention, settings, event log, sessions and checkpoint/resume data required by the canonical flow. |
| `app/core/config.py` | Preserve environment fallback while adding safe first-run bootstrap and dynamic encrypted settings resolution. |
| `app/services/` / worker-agent layer | Separate orchestration from worker/auditor/writer behavior using explicit contracts; orchestration must remain resumable and thin enough to test. |
| `app/tools/search_pipeline.py` | Implement free/default mode, optional authenticated Jina proxy mode, provider-aware rate limiting, direct Jina Search content reuse and bounded query deadlines. |
| `app/routers/` | Maintain complete API-first research lifecycle, including frontend/session routes and backend-to-backend `X-API-Key` access plus explicit resume. |
| `frontend/` | Implement/reshape chat-centered UI with real-time safe agent activity, briefing artifacts, reports, settings and resume UX. |
| `docker-compose.yml` / `compose.yml` | Provision Postgres + persistent named volume + backend + frontend, health checks and migration gate with one documented build/up flow. |
| `alembic/` | Own all schema/table/index/constraint creation and evolution; no manual SQL prerequisite. |

---

## 6. Out of Scope (Explicit Exclusions)

To protect delivery velocity and focus on core research capabilities, the following features are strictly excluded from this epic:
- Multi-party conversational audio/voice streaming.
- Unbounded autonomous web scraping ignoring `robots.txt` or executing client-side JavaScript crawler clusters.
- Payment processing, billing subscriptions, and customer checkout portals.
- Native mobile applications (iOS/Android).
- Fine-tuning or local training of proprietary neural weights.

---

## 7. Architectural Constraints & Security Guarantees

1. **Single-Admin Security Boundary & Dual Access**: Application is secured under a single-admin authentication model with server-derived context. Frontend authenticates with the user's JWT in a secure HttpOnly cookie with CSRF protection; backend-to-backend clients authenticate with `X-API-Key`. Both are first-class supported access surfaces over the same backend capabilities.
2. **Zero Plaintext Secrets & First-Run Initialization**: LLM/search/provider credentials plus optional proxy authentication secrets stored in PostgreSQL must be encrypted using AES-256-GCM. Decryption occurs strictly in memory. Missing local system secrets/passwords are bootstrapped safely on first run without overwriting existing values.
3. **SSRF Defense**: Outbound network requests for web reading, scraping, proxy access and webhook notifications must validate destinations and block loopback/private/link-local/metadata endpoints; redirects must be disabled or revalidated.
4. **Reasoning Privacy Boundary**: Public streaming APIs emit only explicitly generated structured status summaries, learning summaries and declared next actions. Raw model scratchpads, chain-of-thought tokens and internal prompt templates must never enter the event queue.
5. **Durable Concurrency Bounds, Checkpoints & Recovery**: Maximum 20 concurrent worker executions system-wide across all points. Job state is durably persisted in PostgreSQL. Startup recovery and explicit resume must prevent loss of valid progress and must not automatically redo terminal points.
6. **Audit Retry Ceiling & Traceable Citations**: Auditor scores 12 criteria; ≥10/12 approves. Maximum 3 retries after initial execution (4 total worker executions) per point. Persistent insufficiency becomes `BLOCKED` and proceeds to Writer with caveats. All factual claims remain traceable to extracted evidence text.
7. **Provider-Aware Rate Limiting & Search Deadlines**: Default free mode and configured paid/proxy modes respect provider RPM/TPM/concurrency limits through queues, bounded concurrency, retry/backoff and explicit timeouts. The system never intentionally exceeds or circumvents provider limits. Worker query rounds target approximately 30 seconds maximum wall time.
8. **Self-Managing Local Infrastructure**: Local Compose owns the database container, persistent volume, dependency installation, health ordering and migration execution. Starting the stack must not require the operator to manually create PostgreSQL databases, volumes, schemas, tables or run SQL.
