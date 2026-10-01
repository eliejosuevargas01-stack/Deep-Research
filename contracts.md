# Deep Research Engine - Inviolable Architecture & Operational Contracts

## 1. Authentication & Security Boundary Contract

* **Single-Admin Security Model**: The application operates under an authenticated single-administrator security model. Multi-tenant partitioning headers (such as `X-Tenant-ID`) provided by clients are strictly ignored and rejected as an identity source. Browser clients cannot assert, switch, or claim tenant identities. The server assigns and maintains a fixed tenant context (`default` or authenticated administrator) internally.
* **Frontend Authentication via Secure Cookies**: The web frontend authenticates via `POST /api/auth/login` and receives an `HttpOnly`, `SameSite=Lax` (or `Strict`), and `Secure` (in production) session cookie. Browser client-side code never receives, handles, or stores raw secrets such as `API_AUTH_SECRET`.
* **CSRF Protection**: All mutating state operations (`POST`, `PUT`, `PATCH`, `DELETE`) initiated from web browsers must validate same-origin request headers or present a matching anti-CSRF token.
* **Programmatic API Authentication**: Direct machine-to-machine API integrations may authenticate using `Authorization: Bearer <token>` verified against server-managed credentials.
* **Session Lifecycle**: The API provides dedicated authentication lifecycle routes backed by server-side `admin_sessions` records. Cookies contain only an opaque random session identifier; PostgreSQL stores only its cryptographic hash plus expiry, revocation, and CSRF metadata:
  - `POST /api/auth/login`: Validates credentials, creates session record, issues session cookie.
  - `POST /api/auth/logout`: Revokes active session record, clears cookie.
  - `GET /api/auth/me`: Returns current authenticated administrator status.
* **Admin Bootstrap**: Initial administrator access credentials (`ADMIN_PASSWORD`, `SESSION_SECRET`, `APP_ENCRYPTION_KEY`) are generated on first run via `scripts/generate_env.py` and saved to `.env` only if absent. Existing `.env` configurations are strictly preserved.

---

## 2. Security & Credential Handling Contract

* **At-Rest Encryption**: Third-party API credentials (OpenAI, Anthropic, Gemini, LiteLLM, SerpAPI, Apify, Jina) stored in PostgreSQL (`app_settings.encrypted_credentials`) MUST be encrypted using authenticated AES-256-GCM.
* **Key Derivation & Separation**: The symmetric encryption master key `APP_ENCRYPTION_KEY` is loaded from the environment/`.env`. It must never be committed to source code or stored in the database.
* **Local Secrets Generation**: `scripts/generate_env.py` automatically generates only local cryptographic keys (`APP_ENCRYPTION_KEY`, `SESSION_SECRET`, local database password) when initializing a fresh environment. It never overwrites an existing `.env` file and never pretends to generate third-party provider keys. External provider keys are supplied post-boot via the secure Settings UI or manually configured by the operator.
* **In-Memory Decryption Only**: Decrypted secret keys must never be logged, persisted to disk, or returned in client responses. API responses on `GET /api/settings` must return strictly boolean presence flags or masked strings (e.g. `sk-proj-****`).
* **Authentication Enforcement**: Protected endpoints verify active session cookies or valid Bearer tokens. Requests failing this check MUST abort with `401 Unauthorized` before invoking any database or LLM services.

---

## 3. SSRF Prevention Contract (Connection-Level Pinning & Redirect Safety)

* **Connection-Level IP Validation & Pinning**: Pre-resolving DNS alone is insufficient against DNS rebinding (TOCTOU) and malicious redirects. All outbound requests (web search, Jina Reader, Apify scrapers, and webhook callbacks) must enforce IP policy at connection time by validating the resolved socket address before or during TCP socket connection, pinning the validated IP.
* **Strict CIDR Denylist**: Connections to the following IP spaces are blocked at socket level and raise `SSRFSecurityViolation`:
  - `127.0.0.0/8` (IPv4 Loopback)
  - `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16` (RFC1918 Private networks)
  - `169.254.0.0/16` (Link-local addresses and cloud metadata endpoints such as `169.254.169.254`)
  - `0.0.0.0/8` (Local system / broadcast)
  - `::1` (IPv6 Loopback), `fc00::/7` (IPv6 Unique Local), `fe80::/10` (IPv6 Link-Local)
  - IPv4-mapped IPv6 addresses (e.g., `::ffff:127.0.0.1`, `::ffff:169.254.169.254`)
* **Scheme & Port Restrictions**: Only `http` and `https` schemes are permitted. Standard ports (80, 443) are allowed; non-standard ports are rejected unless explicitly allowlisted in configuration.
* **Redirect Safety**: Outbound HTTP clients must disable automatic redirects (`follow_redirects=False`) or enforce recursive SSRF re-validation on every redirect hop to prevent redirection to private IPs or metadata endpoints.
* **Outbound Webhook Enforcement**: Outbound webhook dispatches (`POST callback_url`) are subject to the exact same SSRF validation and socket-level pinning rules as web reader requests.

---

## 4. Privacy Boundary & Public Event Summary Contract

* **Private Reasoning Protection**: Raw LLM internal chain-of-thought tokens, `<thought>` scratchpads, reasoning tokens, and internal prompt templates must NEVER be leaked to public endpoints, database event logs, or SSE streams.
* **Sanitization Inadequacy Guard**: Simply stripping `<thought>` tags with regex is insufficient, as modern LLM models employ diverse or unstructured reasoning formats.
* **Explicit Public Event Generation**: The SSE stream `/api/research/{id}/stream` and the `agent_event_logs` table are fed strictly through explicitly generated public operational status events and high-level summaries. Raw completion streams containing model reasoning never enter the public event pipeline. Permitted events include:
  - Agent persona identification (e.g. `scout`, `historian`, `skeptic`, `auditor`, `writer`).
  - High-level lifecycle action type (e.g. `scout_started`, `sources_scanned`, `synthesis_completed`, `verdict_rendered`).
  - High-level human-readable progress summaries (e.g. *"Identified 4 benchmark comparisons across verified sources"*).
  - Quantitative source metrics (sources fetched vs citations retained).

---

## 5. Concurrency, Durability & Restart Recovery Contract

* **Concurrency Ceiling**: Total simultaneous research worker executions across all points and personas are hard-capped at **20 concurrent tasks** via an application-level `asyncio.Semaphore(20)`.
* **Durable State Persistence**: Research status, briefing points, collected evidence, audit findings, and report drafts must be durably committed to PostgreSQL at each workflow milestone. In-memory async tasks alone are not trusted for durable execution state.
* **Process Restart Resilience**: On application startup, a recovery sweep inspects all active research records. Any session left in an unfinished state (`scouting`, `in_progress`) is detected and transitioned to an interrupted/recoverable state or resumed via an idempotent worker routine. Restarts do not cause silent job loss.
* **Single Live Instance in Compose**: Unless a distributed database lease or distributed worker queue is implemented, Docker Compose configurations must run a single backend replica to prevent race conditions and split-brain execution across multiple uncoordinated instances.
* **Optimistic Locking**: Concurrent writes to `evidences` enforce optimistic concurrency control via the `version` integer column. On conflict (`StaleDataError`), the transaction rolls back and retries with jittered exponential backoff.
* **Audit Retry Ceiling**: The Auditor quality loop enforces a maximum of **3 retry attempts** per research point.
* **Blocker Escalation**: If a point fails audit after 3 attempts:
  - The point status is permanently set to `BLOCKED`.
  - The Auditor appends explicit caveat notes and unresolved discrepancy summaries to the outline.
  - The pipeline does not crash; it advances accumulated evidence and blocker caveats to the Writer.

---

## 6. Configuration-Ownership & Dynamic Runtime Contract

* **Configuration Authority**: Persisted configuration in PostgreSQL (`app_settings`) is the authoritative source of truth for runtime providers and model routing.
* **Precedence Hierarchy**:
  1. `app_settings` stored in database (encrypted credentials, per-agent model mappings)
  2. Environment variables / `.env` file defaults
* **Dynamic Runtime Effect**: Updates via `PUT /api/settings` take effect immediately in the running application instance without requiring a server reboot or container restart. The in-memory `LLMProviderRegistry` invalidates cached clients upon receiving settings updates.
* **No Hardcoded Endpoints**: Model names, provider URLs, and API keys must never be hardcoded in Python code.

---

## 7. Protocol Compliance & API Compatibility Contract

* **Authentication Routes**:
  - `POST /api/auth/login`: Accepts credentials, sets secure HttpOnly session cookie, returns user metadata.
  - `POST /api/auth/logout`: Revokes session, clears cookie.
  - `GET /api/auth/me`: Returns session status and privileges.
* **Research Routes**:
  - `POST /api/research`: Accepts `{theme: str, callback_url: Optional[str]}` and responds with HTTP 201 and `{research_id, status, briefing_url, stream_url}`.
  - `GET /api/research/{id}`: Returns full status, draft briefing, and investigation progress.
  - `POST /api/research/{id}/briefing/approve`: Accepts `{approved_points: list}` and returns HTTP 200, unlocking parallel worker dispatch.
  - `GET /api/research/{id}/stream`: Real-time Server-Sent Events (`text/event-stream`) streaming structured lifecycle events (`event: progress`, `data: <json>`).
* **Report & Callback Routes**:
  - `GET /api/reports/{id}`: Returns finalized Markdown report, citation metrics, and audit findings.
  - `POST /api/reports/{id}/retry-callback`: Manually re-triggers webhook delivery for completed reports.
* **Settings Routes**:
  - `GET /api/settings`: Returns provider configuration status (masked) and model mappings.
  - `PUT /api/settings`: Updates provider keys (encrypted AES-256-GCM) and model selections.
* **Webhook Protocol**: Callback delivery sends an HTTP POST with `Content-Type: application/json` containing `research_id`, `theme`, `content_markdown`, and `generated_at`, guarded by SSRF connection-level checks.

---

## 8. Citation Verifiability & Anti-Hallucination Contract

* **Realistic Verifiability Standards**: The system acknowledges that 100% objective truth and complete elimination of LLM hallucination cannot be mathematically guaranteed. The anti-hallucination contract requires rigorous, testable traceability rather than impossible zero-hallucination assumptions.
* **Source Existence vs Factual Verification**: The presence of an accessible HTTP URL is NOT proof of a factual claim. The Auditor must verify that cited URLs contain matching extracted text snippets/quotes in the `evidences` record supporting the specific claim.
* **Traceable Citation Mapping**: All substantive factual claims in the final report must link to verified citations whose source content is recorded in the evidence database. Unattributed claims must be flagged during audit.
* **Uncertainty & Discrepancy Reporting**: When sources disagree (e.g. Skeptic vs Futurist) or evidence is inconclusive, the system requires the Auditor and Writer to explicitly document the uncertainty, divergence, or conflicting data points in the report rather than fabricating certainty.
* **References Compilation**: Reports must compile a consolidated references section with canonical source URLs, domain names, and access timestamps.

---

## 9. Operator Experience & Human-in-the-Loop Contract

* **One-Time Review Gate**: The pipeline pauses execution after the Scout phase, persisting the 5-point brief in `Research.briefing_draft` with status `pending_approval`.
* **No Automated Bypass**: Parallel worker execution cannot commence until an operator submits approval via the chat UI or `POST /api/research/{id}/briefing/approve`.
* **Full Editability**: The operator may rephrase titles, adjust descriptions, reorder points, or toggle parallelizability during the briefing review.
* **Authorized Local Implementation**: The user has explicitly authorized full local implementation across architecture, backend, frontend, Docker Compose, and local test validation. Local implementation steps run autonomously without artificial approval gates.
* **Production Deployment Authorization Boundary**: External DNS configuration and public cloud deployment to `research.dominuslabs.online` require real infrastructure credentials and separate applicable authorization.

---

## 10. Deployment, Migration & Ingress Contract

* **Single-Instance Compose Architecture**: `docker-compose.yml` orchestrates PostgreSQL 16, a single backend service instance, and a frontend Nginx proxy.
* **Entrypoint Migration**: Container startup executes `alembic upgrade head`. The backend service cannot accept HTTP traffic until schema migration exits with code 0.
* **Database Readiness**: Backend checks database readiness (`SELECT 1`) before reporting healthy status on `GET /health`.
* **Reverse Proxy Configuration**: Nginx and Traefik reverse proxies must set proxy read and send timeouts to at least 300 seconds to preserve long-lived SSE connections.
* **Distinction Between Local Verification and Cloud Deploy**: Local Docker Compose builds and containerized E2E tests are executed and verified locally. Production deployment, domain record creation, and public Let's Encrypt TLS binding at `research.dominuslabs.online` require valid deployment credentials and explicit host access.

---

## 11. Testing & Verification Contract

* **Automated Test Coverage**: The project must maintain an automated test suite verifying:
  - Session authentication rejection (`401 Unauthorized`) for missing/invalid credentials, and successful login/logout cookie handling.
  - Connection-level SSRF blocker rejecting private IPs (`127.0.0.1`, `10.0.0.1`, `169.254.169.254`, IPv6 equivalents) and unsafe redirects.
  - Settings encryption round-trip (AES-256-GCM) and dynamic model provider resolution.
  - Concurrency limiter ensuring active workers never exceed 20.
  - Durable state persistence and startup recovery sweep recovering interrupted jobs.
  - Auditor retry counter incrementing to 3 and triggering `BLOCKED` status with caveats.
  - Citation audit matching claims to extracted evidence content and flagging unverified claims.
  - Privacy streaming emitting strictly structured public events without raw CoT.
* **End-to-End Test Gate**: Complete integration tests must exercise the full lifecycle from submission, human brief approval, concurrent workers, citation audit, and report generation in a containerized environment before release approval.

---

## 12. Rollback, Error Handling & Blocker Lifecycle Contract

* **Webhook Failure Decoupling**: If outbound webhook callback fails:
  1. The report remains permanently stored in `reports`.
  2. Research status is updated to `completed_but_callback_failed`.
  3. The error is recorded in `audit_trails`.
  4. The operator can trigger redelivery via `POST /api/reports/{id}/retry-callback`.
* **Worker Failure Resilience**: If an individual worker throws an unhandled exception, the worker pool traps the exception, records a failed evidence record, and allows the remaining personas for that point to complete.
* **Preservation of Blocked Research**: Blocked research sessions are never discarded. They are preserved in PostgreSQL with full audit traces to enable operator inspection and manual debugging.
