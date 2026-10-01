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

---

## 3. Operator Experience & Security Workflow (UX Walkthrough)

1. **Access & Administrator Authentication**:
   - Operator navigates to `https://research.dominuslabs.online` (or local development URL).
   - Access is secured under a single-admin application model via `POST /api/auth/login`.
   - Browser receives an opaque session identifier in an `HttpOnly`, `SameSite=Lax` (or `Strict`), `Secure` session cookie with anti-CSRF protection. PostgreSQL stores only the session identifier hash, expiry, revocation, and CSRF metadata. Client-side code never receives raw secret keys (`API_AUTH_SECRET`).
   - Tenant context is strictly server-derived (`default`), ignoring any spoofed client headers like `X-Tenant-ID`.
2. **Settings Configuration**:
   - Operator navigates to the Settings page (`/settings`).
   - Local cryptographic keys (`APP_ENCRYPTION_KEY`, `SESSION_SECRET`, local DB password) are initialized on first run via `scripts/generate_env.py` and saved to `.env` only if absent. Existing `.env` files are strictly preserved.
   - External provider keys (OpenAI, Anthropic, Gemini, SerpAPI, Apify, Jina) are entered via the UI and persisted to PostgreSQL encrypted with AES-256-GCM.
   - Operator selects currently available provider/model identifiers for each role: Scout, Historian, Skeptic, Pragmatist, Futurist, Auditor, and Writer. Values come from configuration/provider discovery rather than speculative hardcoded versions.
   - Changes take immediate runtime effect via in-memory provider cache refresh without container restart.
3. **Research Submission**:
   - Operator enters the research topic/theme in the chat interface and optionally provides a webhook `callback_url`.
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
   - If evidence is deficient, the Auditor triggers a targeted retry (up to 3 attempts).
   - If 3 attempts fail, the Auditor raises a blocker flag and advances with explicit caveats and uncertainty reporting.
7. **Report Delivery & Inspection**:
   - Writer synthesizes the final Markdown report grounded strictly in audited outlines and extracted quotes.
   - The final report renders in the chat UI with an outline drawer, verified citation links, and copy/export options.
   - If a `callback_url` was registered, the system validates the destination using connection-level IP pinning and dispatches an asynchronous HTTP POST payload.

---

## 4. Definition of Done (Testable Acceptance Criteria)

1. **FastAPI Backend Core & Routers**:
   - Clean architecture implemented in `app/{core,db,models,schemas,services,routers,prompts,tools,docs,main.py}`.
   - Endpoints operational: `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me`, `POST /api/research`, `GET /api/research/{id}`, `POST /api/research/{id}/briefing/approve`, `GET /api/research/{id}/stream`, `GET /api/reports/{id}`, `POST /api/reports/{id}/retry-callback`, `GET /api/settings`, `PUT /api/settings`, `GET /health`.
2. **Security & Session Authentication**:
   - Single-admin security model. Server derives context without trusting client `X-Tenant-ID` headers.
   - Session authentication middleware validates HttpOnly session cookies for browser clients and Bearer tokens for API clients, rejecting unauthenticated requests with `401 Unauthorized`.
   - CSRF protection enforced on mutating browser requests.
3. **Encrypted Settings & Dynamic Precedence**:
   - `app_settings` table stores provider API keys encrypted with AES-256-GCM at rest.
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
6. **Search-Read-Clean Tooling & BaseWorker DAG**:
   - `BaseWorker` implemented before concrete persona workers (`Historian`, `Skeptic`, `Pragmatist`, `Futurist`).
   - Workers query SerpAPI, Apify, or Jina Search with automated fallback to free Jina Search.
   - URLs read via Jina Reader or Apify scraper with connection-level SSRF checks, cleaned and fused into consolidated markdown (5-10 sources per worker).
7. **Stateless Fact-Checking Auditor & Blocker Loop**:
   - Auditor validates persona completeness, maps contradictions, audits citations against extracted source content snippets, scores uncertainty, and generates writer outlines.
   - Max 3 retry attempts per point; automatically activates `BLOCKED` status on third failure and forwards caveats to writer.
8. **Privacy-Sanitized Live Process Stream**:
   - SSE endpoint `/api/research/{id}/stream` streams strictly explicitly generated structured events (`scout_started`, `worker_progress`, `audit_verdict`, `report_ready`).
   - Zero leakage of raw internal reasoning, chain of thought, or system prompt internals.
9. **Full-Stack Chat Frontend**:
   - React 19 + TanStack Router + Tailwind CSS interface matching Linear dark-mode tokens.
   - Chat view supporting submission, interactive 5-point brief review/edit, real-time persona cards, markdown report view, and settings management.
   - Uses HttpOnly cookie session auth with CSRF; never exposes `API_AUTH_SECRET`.
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
   - `app/core/config.py`: Basic Pydantic settings loading `.env`. Needs `APP_ENCRYPTION_KEY` (for secrets encryption), `SESSION_SECRET` (for session cookies), and dynamic override integration. Local secrets generated on first run preserving existing `.env`.
   - `app/db/database.py`: SQLAlchemy async engine and sessionmaker.
   - `app/models/domain_models.py`: Partial SQLAlchemy models (`Research`, `ResearchPoint`, `EvidenceRecord`, `AuditTrail`, `Report`). Needs `AppSettings`, `AgentEventLog`, revocable `AdminSession`, and server-scoped `tenant_id="default"` columns (no client trust). Ensure durable job states.
   - `app/schemas/`: Pydantic schemas for request/response. Needs settings, SSE event, and auth session schemas.
   - `app/routers/research.py`: Basic CRUD endpoints. Needs authentication routes (`/api/auth/login`, `/api/auth/logout`, `/api/auth/me`), SSE streaming, settings management, and callback retry.
   - `app/middleware/security.py`: Basic token check. Needs connection-level SSRF validation, session cookie handling, and CSRF protection (no client-supplied `X-Tenant-ID` trust).
   - `app/prompts/personas.json`: Prompts for 4 personas, scout, auditor, writer.
   - `app/tools/search_pipeline.py`: Search and reader functions with fallbacks. Needs connection-level SSRF socket pinning.
   - `app/agents/workers/`: `BaseWorker` and 4 persona subclasses (`HistorianWorker`, `SkepticWorker`, `PragmatistWorker`, `FuturistWorker`). BaseWorker must precede personas in implementation.
   - `app/engine/`: `WorkerPool`, `Auditor`, `Orchestrator`. Needs semaphore concurrency cap (20), durable job state recovery on startup, live event emission, and real LLM client integration. Orchestrator final integration after workers/auditor/writer.
   - `app/services/webhook.py`: Webhook dispatcher. Needs connection-pinned SSRF validation.
   - `frontend/`: Partial scaffolding with `package.json` (React 19, TanStack Router, Zustand) and `PLAN.md`.
   - `alembic/`: `env.py` and `alembic.ini`. Migration versions directory must be created.
2. **Reference Projects**:
   - `/root/projects/Dominuslabs`: Dockerfile patterns, Nginx proxy configuration, and Coolify/Traefik integration for `*.dominuslabs.online`.
   - `/root/RENDER_LLM_ROUTER`: Multi-provider LLM routing patterns, schema validation, and provider fallback logic.

### Adaptation Mapping

| Existing Asset | Current State | Required Canonical Adaptation |
|----------------|---------------|-------------------------------|
| `app/models/domain_models.py` | 5 partial entities | Maintain server-scoped `tenant_id="default"`; add `AppSettings` (encrypted credentials, model mappings), `AgentEventLog` (explicit public summaries), and revocable `AdminSession`. Ensure durable job states. |
| `app/core/config.py` | Static `.env` loading | Add encryption secret, session secret, dynamic override resolver, and preserve existing `.env`. |
| `app/services/` | `webhook.py` only | Add `llm.py` (unified provider gateway using LiteLLM/OpenAI/Anthropic/Gemini) and `crypto.py` (AES-256-GCM settings encryption). |
| `app/middleware/security.py` | Basic token string match | Add connection-pinned SSRF guardrails (blocking private IPs), HttpOnly session cookies, CSRF protection, and reject client `X-Tenant-ID`. |
| `app/engine/orchestrator.py` | Basic linear flow | Final integration after workers/auditor/writer; add `asyncio.Semaphore(20)`, durable state recovery on startup, SSE event dispatcher, and real Scout outline generation. |
| `app/routers/` | Partial research router | Add auth endpoints (`/api/auth/login`, `/api/auth/logout`, `/api/auth/me`), `/api/research/{id}/stream` (SSE), `/api/settings` (GET/PUT), and `/api/reports/{id}/retry-callback`. |
| `frontend/` | Only `package.json` & `PLAN.md` | Implement complete React 19 UI: Chat submission, 5-point brief editor, live persona panels, markdown report renderer, settings page. Authenticate via HttpOnly cookie; no `API_AUTH_SECRET` in bundle. |
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

1. **Single-Admin Security Boundary**: Application is secured under a single-admin authentication model with server-derived context. Client-supplied `X-Tenant-ID` headers are ignored and rejected. Frontend uses secure HttpOnly session cookies with CSRF protection; raw API secrets are never exposed in client code.
2. **Zero Plaintext Secrets & First-Run Initialization**: LLM and search provider credentials stored in PostgreSQL must be encrypted using AES-256-GCM. Decryption occurs strictly in-memory during request dispatch. First-run scripts generate local secrets only (`APP_ENCRYPTION_KEY`, `SESSION_SECRET`, DB password) and preserve existing `.env`.
3. **SSRF Immune (Connection-Level Pinning)**: Outbound network requests for web reading, scraping, and webhook notifications must enforce IP validation and socket-level pinning at connection time, reject any destination mapping to loopback, private IPv4/IPv6, or cloud metadata endpoints (`169.254.169.254`), and re-validate redirects.
4. **Reasoning Privacy Boundary**: Public streaming APIs emit only explicitly generated structured status summaries and lifecycle events. Raw model scratchpads, chain-of-thought tokens, and internal prompt templates must never enter the event queue.
5. **Durable Concurrency Bounds & Restart Recovery**: Maximum 20 concurrent worker executions system-wide across all points (`asyncio.Semaphore(20)`). Job state is durably persisted in PostgreSQL with startup recovery sweep preventing job loss across process restarts. Compose runs a single backend replica to avoid uncoordinated multi-instance conflicts.
6. **Audit Retry Ceiling & Traceable Citations**: Maximum 3 attempts per research point before forcing a blocker transition with explicit caveats. All factual claims must be traceable to extracted evidence text; source URL existence does not constitute factual verification. Uncertainty is reported explicitly rather than assuming zero hallucinations.