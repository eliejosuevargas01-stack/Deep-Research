# Deep Research Engine - Live Execution Backlog

## Status

- Planning contracts repaired; implementation remains pending.
- Local implementation, Compose, and E2E are authorized. Public deployment/DNS/TLS require separate authorization and real access.
- Counting: 38 numbered work items (T001–T038), 41 executable rows because T018 is split into T018a–T018d.

| ID | Short Outcome | Depends On | Status |
|---|---|---|---|
| T001 | Inspect/preserve partial sources; fill missing structure | — | ⬜ |
| T002 | Dependency manifests + safe first-run local secret generation; preserve `.env`; no fake provider keys | — | ⬜ |
| T003 | Async DB engine/session and real readiness | T002 | ⬜ |
| T004 | Canonical models + `admin_sessions` + initial migration + durable job fields | T003 | ⬜ |
| T005 | AES-256-GCM settings encryption | T002 | ⬜ |
| T006 | Connection-pinned SSRF transport for readers/callbacks; redirects revalidated/disabled | T002 | ⬜ |
| T007 | Single-admin login/logout/me, HttpOnly session, CSRF, API Bearer option; reject `X-Tenant-ID` identity | T002, T004 | ⬜ |
| T008 | Masked/encrypted settings API with provider cache reload | T004, T005, T007 | ⬜ |
| T009 | Multi-provider LLM gateway | T008 | ⬜ |
| T010 | Explicit public event schema/builder; raw model streams excluded | T004 | ⬜ |
| T011 | Prompts requiring evidence/uncertainty, not private chain-of-thought | — | ⬜ |
| T012 | Durable Scout + create/status routes | T006, T009–T011 | ⬜ |
| T017 | Search-read-clean with extracted evidence text and metadata | T006 | ⬜ |
| T019 | `BaseWorker` (must precede personas) | T009, T010, T017 | ⬜ |
| T018a | Historian from `BaseWorker` | T019 | ⬜ |
| T018b | Skeptic from `BaseWorker` | T019 | ⬜ |
| T018c | Pragmatist from `BaseWorker` | T019 | ⬜ |
| T018d | Futurist from `BaseWorker` | T019 | ⬜ |
| T013 | WorkerPool + global in-process cap 20 | T018a–T018d | ⬜ |
| T014 | Evidence optimistic locking | T004 | ⬜ |
| T015 | Authenticated SSE from allowlisted public events | T007, T010 | ⬜ |
| T020 | Auditor completeness/contradiction/uncertainty | T013, T014 | ⬜ |
| T021 | Claim-to-extracted-evidence Citation Auditor; URL reachability insufficient | T006, T014 | ⬜ |
| T022 | Max-three retry, BLOCKED/caveats persistence | T020, T021 | ⬜ |
| T023 | Evidence-grounded Writer with blockers/uncertainty | T009, T022 | ⬜ |
| T024 | Connection-pinned callback dispatch | T006 | ⬜ |
| T025 | Report retrieval + callback retry routes | T023, T024 | ⬜ |
| T016 | Final Orchestrator + one-time approval route + durable recovery (after workers/auditor/writer) | T012–T015, T018a–T025 | ⬜ |
| T026 | React shell + login; no browser API secret | T007, T016 | ⬜ |
| T027 | Typed API/session stores + CSRF/logout | T026 | ⬜ |
| T028 | Create/status/recent research UI | T027 | ⬜ |
| T029 | Editable one-time approval UI | T027 | ⬜ |
| T030 | SSE public status/persona UI | T027 | ⬜ |
| T031 | Report + evidence/uncertainty/blocker UI | T027 | ⬜ |
| T032 | Masked settings UI + logout | T027 | ⬜ |
| T033 | Images + same-origin Nginx/SSE proxy | T002, T026 | ⬜ |
| T034 | Compose: Postgres + exactly one backend + frontend; migration/health gates | T003, T004, T033 | ⬜ |
| T035 | Investigate actual Coolify/Traefik config before proposing labels | T034 | ⬜ |
| T036 | Local gate; production DNS/TLS gate only when authorized/access available | T035 | ⬜ |
| T037 | Local E2E including auth, routes, SSRF, cap, callback, restart recovery | T016, T025, T032, T034 | ⬜ |
| T038 | Conditional authorized live E2E; sampled factual validation; record blockers if unavailable | T036, T037 | ⬜ |

## Dependency Invariants

1. T019 (`BaseWorker`) before T018a–T018d.
2. T016 final integration after concrete workers, T020–T022 Auditor path, T023 Writer, T024 callback, and T010/T015 event path.
3. API routes required: `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me`, `POST /api/research`, `GET /api/research/{id}`, `POST /api/research/{id}/briefing/approve`, `GET /api/research/{id}/stream`, `GET /api/reports/{id}`, `POST /api/reports/{id}/retry-callback`, `GET /api/settings`, `PUT /api/settings`, `GET /health`.
4. Startup recovery and durable milestones required; `asyncio.Task` alone is not durable.
5. Compose launches one backend instance until atomic DB lease or distributed queue exists.
6. No approval pause for local implementation. Public DNS/deploy/TLS remains separately authorized.