# Deep Research Engine - Canonical Project Goal & Mission Definition

## 1. Problem Statement & Mission

Build an autonomous, distributed, full-stack Deep Research Engine capable of executing rigorous, multi-agent investigative workflows across the live web. The system combines:
1. **Cognitive 4-Phase Research Pipeline**: Scout & Briefing → 4-Persona Parallel Investigation → Fact-Checking Auditor → Markdown Report Synthesizer.
2. **Interactive Chat Frontend**: A precision Linear-styled UI (React 19, Tailwind CSS, TanStack Router) providing a one-time human-in-the-loop brief review/edit, real-time agent process summaries, and interactive report rendering.
3. **Persisted Encrypted Settings**: Database storage for LLM provider keys and per-agent model assignments with AES-256-GCM encryption and immediate runtime effect.
4. **Production Deployment Target**: Locally verified Docker Compose environment with automated database migrations, plus an investigated Traefik/Coolify deployment specification for `research.dominuslabs.online`. Public DNS/TLS execution requires real infrastructure access and separate authorization.

The engine must produce high-density, fact-checked research reports backed by rigorous, traceable citations mapped to extracted source content, evidence-grounded synthesis, explicit uncertainty scoring, and adversarial contradiction auditing.

---

## 2. Scope Reconciliation (Revocation of Legacy Exclusions)

Previous planning documents mistakenly marked the frontend interface, real LLM execution, and cloud deployment as out-of-scope. **Those exclusions are formally revoked.** The canonical scope is defined as follows:

| Component | Legacy Status | Canonical Reconciled Status | Rationale |
|-----------|---------------|-----------------------------|-----------|
| **Chat Frontend UI** | *Out of scope* | **IN SCOPE (Mandatory)** | Operators require a chat UI to submit research topics, edit/approve the 5-point brief in one round, monitor live agent process summaries, configure settings, and inspect reports. |
| **Live LLM Execution** | *Out of scope (mocked)* | **IN SCOPE (Mandatory)** | The pipeline must execute real LLM calls (OpenAI, Anthropic, Gemini, LiteLLM) for Scout, 4 Persona Workers, Auditor, and Writer using dynamic model configuration. |
| **Encrypted Settings** | *Not specified* | **IN SCOPE (Mandatory)** | API keys and per-agent model selections must be persisted in PostgreSQL with AES-256-GCM encryption and dynamic runtime hot-reload. Local personal secrets (`SESSION_SECRET`, `APP_ENCRYPTION_KEY`) auto-generated on first run only. |
| **Docker Compose & Deployment** | *Out of scope (local only)* | **IN SCOPE (Mandatory)** | The complete system must be containerized locally with health checks and auto-migration. Public cloud deployment to `research.dominuslabs.online` requires specification, distinct from actual execution because external DNS/TLS configuration require explicit authorization and real access. |
| **Agent Process Streaming** | *Not specified* | **IN SCOPE (Mandatory)** | Server-Sent Events (SSE) must stream explicitly generated structured public status summaries while strictly preventing private reasoning tokens or raw completion streams from entering the pipeline. |
| **Dual Search Mode** | *Not specified* | **IN SCOPE (Mandatory)** | The engine must work with zero search credentials by default and optionally switch to an authenticated Jina relay/proxy for high-speed search-and-read execution. |

---

## 3. Operator Experience & Security Workflow (UX Walkthrough)

1. **Access & Administrator Authentication**:
   - Operator navigates to `https://research.dominuslabs.online` (or local development URL).
   - Access is secured under a single-admin application model via `POST /api/auth/login`.
   - Browser receives the user's signed JWT in an `HttpOnly`, `SameSite=Lax` (or `Strict`), `Secure` cookie with anti-CSRF protection. PostgreSQL stores only the JWT identifier (`jti`) hash, expiry, revocation, and CSRF metadata. Client-side code never reads the JWT or receives raw API keys (`API_AUTH_SECRET`).
   - Backend-to-backend API clients authenticate with `X-API-Key`; this credential is not required from browser clients. Each request uses exactly one authentication method according to its client type: user JWT cookie for the frontend, or API key for backend clients.
   - Tenant context is strictly server-derived (`default`), ignoring any spoofed client headers like `X-Tenant-ID`.
2. **Settings Configuration**:
   - Operator navigates to the Settings page (`/settings`).
   - Local cryptographic keys (`APP_ENCRYPTION_KEY`, `SESSION_SECRET`, local DB password) are initialized on first run via `scripts/generate_env.py` and saved to `.env` only if absent. Existing `.env` files are strictly preserved.
   - External provider keys (OpenAI, Anthropic, Gemini, SerpAPI, Apify, Jina) are entered via the UI when those providers are intentionally configured and persisted to PostgreSQL encrypted with AES-256-GCM.
   - Search works in **free mode by default**, with no search-provider credential required. Free mode uses a credential-free search source and the public Jina Reader path for page extraction, subject to provider rate limits.
   - The operator may enable **Jina Proxy accelerated mode** by configuring only a Jina relay/Cloudflare Worker base URL and the relay authentication secret. The Deep Research application must not require, expose, rotate, or manage the Jina API-key pool behind that relay; key rotation/failover belongs to the relay implementation.
   - SerpAPI and Apify remain supported as optional alternative search/extraction providers and are not mandatory for the zero-configuration default path.
   - Frontend operators may configure an optional callback URL in Settings, persisted by the backend. Backend-to-backend clients have no Settings UI and may instead submit an optional `callback_url` with each authenticated `POST /api/research` request.
   - Operator selects currently available provider/model identifiers for each role: Scout, Historian, Skeptic, Pragmatist, Futurist, Auditor, and Writer. Values come from configuration/provider discovery rather than speculative hardcoded versions.
   - Changes take immediate runtime effect via in-memory provider cache refresh without container restart.
3. **Research Submission**:
   - Frontend operators enter only the research topic/theme; the backend uses the optional callback URL saved in Settings. Backend-to-backend clients submit the topic and may include a per-request `callback_url`, which is validated and persisted with that research for delivery and retry; otherwise they retrieve the report by ID.
   - Clicks "Start Deep Research" (`POST /api/research`).
4. **Scout & One-Time Human Brief Review**:
   - Scout agent runs web exploration, extracts recurring themes, and drafts 5 investigation points with dependency and parallelism flags.
   - The UI presents the 5-point brief in an interactive review card.
   - Operator can reorder points, edit titles/descriptions, toggle parallel execution, or add missing angles.
   - Operator clicks "Approve Brief" (`POST /api/research/{id}/briefing/approve`).
5. **Live Process Streaming (Privacy-Guarded)**:
   - Orchestrator spawns 4 specialist personas per point (up to 20 concurrent workers).
   - The UI displays live progress cards for each point and persona:
     - Real-time status badges (`Searching`, `Reading 6 sources`, `Synthesizing`, `Auditing`).
     - Live process summaries (e.g., *"Historical consensus identified across 4 academic sources"*).
     - **Privacy Boundary**: Public streams emit strictly explicitly generated structured lifecycle events. Raw model completion streams and private chain-of-thought tokens are never queued or streamed.
6. **Auditor Fact-Check & Quality Loop**:
   - As workers finish a point, the Auditor evaluates evidence completeness, detects contradictions (e.g., Skeptic vs Futurist), and verifies citations against extracted source content (not merely URL accessibility).
   - If evidence is deficient, the Auditor triggers a targeted retry, up to 3 retries after the initial worker execution (4 total executions per point).
   - If all 3 retries fail, the Auditor raises a blocker flag and advances with explicit caveats and uncertainty reporting.
7. **Report Delivery & Inspection**:
   - Writer synthesizes the final Markdown report grounded strictly in audited outlines and extracted quotes.
   - The final report is persisted and remains retrievable through `GET /api/reports/{id}`. Frontend users can inspect it in the research UI; backend API clients can fetch it by research/report ID.
   - If a callback URL is configured in frontend Settings or supplied by a backend-to-backend client on the research request, the system validates the destination using connection-level IP pinning and dispatches an asynchronous HTTP POST payload. Callback delivery is optional and does not replace report retrieval by ID.

---

## 4. Definition of Done (Testable Acceptance Criteria)

1. **FastAPI Backend Core & Routers**:
   - Clean architecture implemented in `app/{core,db,models,schemas,services,routers,prompts,tools,docs,main.py}`.
   - Endpoints operational: `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me`, `POST /api/research`, `GET /api/research/{id}`, `POST /api/research/{id}/briefing/approve`, `GET /api/research/{id}/stream`, `GET /api/reports/{id}`, `POST /api/reports/{id}/retry-callback`, `GET /api/settings`, `PUT /api/settings`, `GET /health`.
2. **Security & Session Authentication**:
   - Single-admin security model. Server derives context without trusting client `X-Tenant-ID` headers.
   - Authentication middleware validates the user JWT in the HttpOnly cookie for browser clients and `X-API-Key` for backend-to-backend clients, rejecting unauthenticated requests with `401 Unauthorized`. The two credentials are alternatives, not cumulative requirements.
   - CSRF protection enforced on mutating browser requests.
3. **Encrypted Settings & Dynamic Precedence**:
   - `app_settings` table stores provider API keys and proxy authentication secrets encrypted with AES-256-GCM at rest.
   - Search mode defaults to `free` and requires no search credential.
   - Optional `jina_proxy` mode stores a configurable proxy/Worker base URL and encrypted proxy authentication secret. Jina upstream keys managed by the proxy must not be copied into the Deep Research application.
   - Configuration precedence strictly enforced: Database Stored Settings > Environment / `.env` defaults.
   - Changes via `PUT /api/settings` take immediate runtime effect without container restart.
   - Local secrets generated on first run, preserving existing `.env`.
4. **SSRF Guardrails & IP Pinning**:
   - `callback_url` and web reader/scraping URLs enforce connection-level IP pinning at socket creation.
   - Outbound redirects are re-validated before following or disabled (`follow_redirects=False`).
   - Requests targeting RFC1918 private subnets (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), loopback (`127.0.0.0/8`), link-local (`169.254.0.0/16`), cloud metadata (`169.254.169.254`), and IPv6 unicast/loopback (`::1`, `fc00::/7`, `fe80::/10`) are blocked with `SSRFSecurityViolation`.
5. **Real Multi-Agent Orchestration, Concurrency & Restart Durability**:
   - Scout agent uses real LLM calls to generate 5 distinct research points.
   - Orchestrator manages worker execution under a hard ceiling of **20 concurrent workers** (`asyncio.Semaphore(20)`).
   - Durable job state stored in PostgreSQL. On restart, startup recovery detects in-flight research records (`scouting`, `in_progress`) to prevent silent job loss.
   - Single backend replica in Compose to prevent uncoordinated multi-instance race conditions.
   - Optimistic locking on `evidences` table using `version` column prevents race conditions.
6. **Search-Read-Clean Tooling, Performance & BaseWorker DAG**:
   - `BaseWorker` implemented before concrete persona workers (`Historian`, `Skeptic`, `Pragmatist`, `Futurist`).
   - **Default free path:** with no search credentials configured, workers use a credential-free web-search source and Jina Reader without authentication for readable page extraction. Provider rate limits must be respected through bounded concurrency, queuing and backoff rather than intentional limit bypass.
   - **Accelerated Jina Proxy path:** when `jina_proxy` is enabled, workers send the search/read request to the configured Cloudflare Worker/Jina relay using the configured relay authentication secret. The relay is responsible for its own upstream Jina-key pool, rotation and provider-level failover.
   - If Jina Search returns usable page content together with search results, workers must consume that returned content directly. They must not automatically perform a second Jina Reader request for each same URL unless the returned content is missing, insufficient, stale for the audit requirement, or explicitly needs revalidation.
   - SerpAPI and Apify remain optional alternate providers/fallbacks.
   - A worker search round (query + source acquisition + reading/extraction required for that round) has a target hard deadline of approximately **30 seconds**. With at most 3 rounds, one worker should not normally exceed approximately **90 seconds** of search-round wall time; independent personas and research points continue to run concurrently according to the DAG and global concurrency ceiling.
   - Retries requested by the Auditor must reuse persisted valid evidence and search only for identified gaps whenever possible rather than repeating already-satisfied research.
7. **Stateless Fact-Checking Auditor & Blocker Loop**:
   - Auditor validates persona completeness, maps contradictions, audits citations against extracted source content snippets, scores uncertainty, and generates writer outlines.
   - Max 3 retry attempts after the initial worker execution per point (4 total executions); automatically activates `BLOCKED` status after the third retry fails and forwards caveats to writer.
8. **Privacy-Sanitized Live Process Stream**:
   - SSE endpoint `/api/research/{id}/stream` streams strictly explicitly generated structured events (`scout_started`, `worker_progress`, `audit_verdict`, `report_ready`).
   - Zero leakage of raw internal reasoning, chain of thought, or system prompt internals.
9. **Full-Stack Chat Frontend**:
   - React 19 + TanStack Router + Tailwind CSS interface matching Linear dark-mode tokens.
   - Chat view supporting submission, interactive 5-point brief review/edit, real-time persona cards, markdown report view, and settings management.
   - Settings expose the default `free` search mode plus optional `jina_proxy` configuration fields for relay base URL and relay authentication secret; the UI does not ask for the relay's internal Jina-key pool.
   - Uses the user's JWT in an HttpOnly cookie with CSRF; never exposes the JWT to client-side code or `API_AUTH_SECRET` to the frontend.
10. **Docker Compose & Deployment Gates**:
    - Multi-container `docker-compose.yml` with `postgres`, single `backend` replica, and `frontend` (Nginx reverse proxy).
    - Database auto-migrates on startup via `alembic upgrade head`.
    - Health checks ensure Postgres is ready before backend boots.
    - Local implementation and container verification run autonomously without approval pause gates.
    - Cloud deployment, public DNS for `research.dominuslabs.online`, and Let's Encrypt TLS verification gates distinguish local verification from cloud deployment requiring real infrastructure credentials and separate authorization.

---

## 5. What Exists & Adaptation Plan

### Codebase & Reference Inventory

1. **Current Codebase (`/root/projects/deep-research`)**:
   - `app/core/config.py`: Basic Pydantic settings loading `.env`. Needs `APP_ENCRYPTION_KEY` (for secrets encryption), `SESSION_SECRET` (for signing user JWTs), and dynamic override integration. Local secrets generated on first run preserving existing `.env`.
   - `app/db/database.py`: SQLAlchemy async engine and sessionmaker.
   - `app/models/domain_models.py`: Partial SQLAlchemy models (`Research`, `ResearchPoint`, `EvidenceRecord`, `AuditTrail`, `Report`). Needs `AppSettings`, `AgentEventLog`, revocable `AdminSession`, and server-scoped `tenant_id="default"` columns (no client trust). Ensure durable job states.
   - `app/schemas/`: Pydantic schemas for request/response. Needs settings, SSE event, and auth session schemas.
   - `app/routers/research.py`: Basic CRUD endpoints. Needs authentication routes (`/api/auth/login`, `/api/auth/logout`, `/api/auth/me`), SSE streaming, settings management, and callback retry.
   - `app/middleware/security.py`: Basic token check. Needs connection-level SSRF validation, user JWT validation from the frontend's HttpOnly cookie, `X-API-Key` validation for backend-to-backend clients, and CSRF protection (no client-supplied `X-Tenant-ID` trust).
   - `app/prompts/personas.json`: Prompts for 4 personas, scout, auditor, writer.
   - `app/tools/search_pipeline.py`: Search and reader functions with fallbacks. Needs connection-level SSRF socket pinning and the canonical `free`/`jina_proxy` search-mode split, including direct reuse of content returned by accelerated Jina Search.
   - `app/agents/workers/`: `BaseWorker` and 4 persona subclasses (`HistorianWorker`, `SkepticWorker`, `PragmatistWorker`, `FuturistWorker`). BaseWorker must precede personas in implementation.
   - `app/engine/`: `WorkerPool`, `Auditor`, `Orchestrator`. Needs semaphore concurrency cap (20), durable job state recovery on startup, live event emission, and real LLM client integration. Orchestrator final integration after workers/auditor/writer.
   - `app/services/webhook.py`: Webhook dispatcher. Needs connection-pinned SSRF validation.
   - `frontend/`: Partial scaffolding with `package.json` (React 19, TanStack Router, Zustand) and `PLAN.md`.
   - `alembic/`: `env.py` and `alembic.ini`. Migration versions directory must be created.
2. **Reference Projects**:
   - `/root/projects/Dominuslabs`: Dockerfile patterns, Nginx proxy configuration, and Coolify/Traefik integration for `*.dominuslabs.online`.
   - `/root/RENDER_LLM_ROUTER`: Multi-provider LLM routing patterns, schema validation, and provider fallback logic.
   - `eliejosuevargas01-stack/cloudflare_worker`: Reference implementation for the authenticated Jina relay/proxy, including upstream key rotation/failover. Deep Research consumes only its base URL and relay authentication secret when `jina_proxy` mode is enabled.

### Adaptation Mapping

| Existing Asset | Current State | Required Canonical Adaptation |
|----------------|---------------|-------------------------------|
| `app/models/domain_models.py` | 5 partial entities | Maintain server-scoped `tenant_id="default"`; add `AppSettings` (encrypted credentials, model mappings), `AgentEventLog` (explicit public summaries), and revocable `AdminSession`. Ensure durable job states. |
| `app/core/config.py` | Static `.env` loading | Add encryption secret, session secret, dynamic override resolver, and preserve existing `.env`. |
| `app/services/` | `webhook.py` only | Add `llm.py` (unified provider gateway using LiteLLM/OpenAI/Anthropic/Gemini) and `crypto.py` (AES-256-GCM settings encryption). |
| `app/middleware/security.py` | Basic token string match | Add connection-pinned SSRF guardrails (blocking private IPs), user JWT validation from HttpOnly cookies, `X-API-Key` validation for backend-to-backend clients, CSRF protection, and reject client `X-Tenant-ID`. |
| `app/engine/orchestrator.py` | Basic linear flow | Final integration after workers/auditor/writer; add `asyncio.Semaphore(20)`, durable state recovery on startup, SSE event dispatcher, and real Scout outline generation. |
| `app/routers/` | Partial research router | Add auth endpoints (`/api/auth/login`, `/api/auth/logout`, `/api/auth/me`), `/api/research/{id}/stream` (SSE), `/api/settings` (GET/PUT), and `/api/reports/{id}/retry-callback`. |
| `frontend/` | Only `package.json` & `PLAN.md` | Implement complete React 19 UI: Chat submission, 5-point brief editor, live persona panels, markdown report renderer, settings page. Authenticate with the user's JWT in an HttpOnly cookie; no JWT or `API_AUTH_SECRET` in the frontend bundle. |
| `docker-compose.yml` | Not present | Create production multi-service Compose (Postgres, single Backend replica, Frontend Nginx) with health checks, auto-migration, and Traefik labels. |
| `alembic/` | Initialized without version files | Generate initial migration `001_initial_schema.py` covering all canonical tables. |

---

## 6. Out of Scope (Explicit Exclusions)

To protect delivery velocity and focus on core research capabilities, the following features are strictly excluded from this epic:
- Multi-party conversational audio/voice streaming.
- Unbounded autonomous web scraping ignoring `robots.txt` or executing client-side JavaScript crawlers (e.g. headless Chrome clusters).
- Payment processing, billing subscriptions, and customer checkout portals.
- Native mobile applications (iOS/Android).
- Fine-tuning or local training of proprietary neural weights.

---

## 7. Architectural Constraints & Security Guarantees

1. **Single-Admin Security Boundary**: Application is secured under a single-admin authentication model with server-derived context. Client-supplied `X-Tenant-ID` headers are ignored and rejected. Frontend authenticates with the user's JWT in a secure HttpOnly cookie with CSRF protection; backend-to-backend clients authenticate with `X-API-Key`. These methods are alternatives by client type, and raw credentials are never exposed in frontend code.
2. **Zero Plaintext Secrets & First-Run Initialization**: LLM and search provider credentials plus optional proxy authentication secrets stored in PostgreSQL must be encrypted using AES-256-GCM. Decryption occurs strictly in-memory during request dispatch. First-run scripts generate local secrets only (`APP_ENCRYPTION_KEY`, `SESSION_SECRET`, DB password) and preserve existing `.env`.
3. **SSRF Immune (Connection-Level Pinning)**: Outbound network requests for web reading, scraping, proxy access, and webhook notifications must enforce IP validation and socket-level pinning at connection time, reject any destination mapping to loopback, private IPv4/IPv6, or cloud metadata endpoints (`169.254.169.254`), and re-validate redirects.
4. **Reasoning Privacy Boundary**: Public streaming APIs emit only explicitly generated structured status summaries and lifecycle events. Raw model scratchpads, chain-of-thought tokens, and internal prompt templates must never enter the event queue.
5. **Durable Concurrency Bounds & Restart Recovery**: Maximum 20 concurrent worker executions system-wide across all points (`asyncio.Semaphore(20)`). Job state is durably persisted in PostgreSQL with startup recovery sweep preventing job loss across process restarts. Compose runs a single backend replica to avoid uncoordinated multi-instance conflicts.
6. **Audit Retry Ceiling & Traceable Citations**: Maximum 3 retries after the initial execution (4 total worker executions) per research point before forcing a blocker transition with explicit caveats. All factual claims must be traceable to extracted evidence text; source URL existence does not constitute factual verification. Uncertainty is reported explicitly rather than assuming zero hallucinations.
7. **Provider-Aware Rate Limiting & Search Deadlines**: The default free mode and every configured paid/proxy mode must respect provider RPM/TPM/concurrency limits using queues, bounded concurrency, retry/backoff and explicit timeouts. The system must never intentionally exceed or circumvent provider limits. Worker query rounds target a maximum wall time of approximately 30 seconds and should fall back or fail explicitly when the selected provider cannot satisfy the deadline.