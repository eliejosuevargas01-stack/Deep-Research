# Checkpoint 1 — frontend síncrono

## Brief and decisions

User selected comp C at `.impeccable/mocks/c-canvas.png`, rejecting the blue-heavy palette and generic AI aesthetics. Preserve C's topology, refine color/typography/containment using Impeccable and popular-web-designs. Plain React + TypeScript + Vite + CSS is the delegated stack. Documentation colors and existing backend changes are outside the write scope.

## Deliverable 1 — research workspace

Horizontal navigation: brand, new research, research history, settings, documentation. Responsive mobile navigation. New-research empty state with useful topic examples that populate rather than automatically submit. Composer validates 5–500 characters, Enter submits, Shift+Enter adds a line; prevent duplicate requests and IME submission.

`POST /api/v1/plan` with `{tema, async_execute:false}` only. Render actual structured plan and point details with the sole continuation action `Iniciar pesquisa`. No automatic research on plan creation, fake progress, unsupported controls, fake users, or invented data.

## Deliverable 2 — synchronous execution and reports

On explicit start, await real search -> audit -> writer endpoints using research ID, rendering only request-level states. Respect `pronto_para_writer` and backend retry limits; stop and show corresponding failure when no writer approval is possible. Never label HTTP 200 with `status: incompleto/falha` as success. Writer report is rendered as sanitized Markdown with safe external links and real source list; allow copy and Markdown download. Do not expose raw internal reasoning or secrets. SSE/event streaming and simulated token streaming belong to checkpoint 2.

Non-secret research history can persist locally, clearly labeled as this browser's history. Preserve report/plan when navigating settings and history. A failed research can recover safely without duplicating plan or rewriting a completed report. A browser reload during an outstanding HTTP request must never imply background cancellation or successful recovery.

## Deliverable 3 — settings and connection

Use existing encrypted credential endpoints and X-API-Key authentication. API access key lives in memory only and is never read from server .env or embedded in client assets. No provider credential in localStorage/sessionStorage/logs. GET metadata is masked and is not a source of real values; never repopulate forms with masks. Save only changed fields, clear sensitive inputs after successful save, surface per-field failures and environment precedence accurately. Support OPENAI_API_KEY, LLM_BASE_URL, LLM_MODEL_LIGHT/STRONG, JINA_API_KEY/BASE_URL, N_PONTOS, PERSONAS_CONFIG, CALLBACK_WEBHOOK_URL and WEBHOOK_HMAC_SECRET. URL and positive-point validation. Do not invent deletion support. Browser-only appearance preferences may use localStorage. Provide real docs/usage page without changing existing docs assets.

## Implementation boundaries

Worker owns `frontend/**` plus product-specific run/readme and checkpoint evidence under `docs/frontend/**`. New Impeccable development context may live under `.impeccable/**`. Do not modify current app/, existing tests/, .env, databases, git state, backend credentials, production services or remote repos. No deploy, commit or push needed. All dependencies installed locally to frontend.

## Visual requirements

Use semantic controls, keyboard focus, readable labels, contrast >=4.5:1, 44px touch controls, reduced motion, 320px through desktop layouts, no horizontal page overflow. Keep CSS tokenized. Self-host font using npm package if available; Geist is suitable. Accent subdued plum or charcoal rather than electric blue. Primary action can be charcoal. Documentation palette is unchanged. Use GSAP for a single meaningful plan-to-execution transition, with cleanup and reduced-motion handling; keep content visible without animation.

## Execution loop and acceptance

1. Orchestrator prepares this plan and the worker packet.
2. Hermes worker uses `ag/gemini-3.8-flash-high` with reasoning high and implements fully, runs strict TypeScript/build and authors meaningful Cucumber/Gherkin browser tests.
3. Independent Hermes auditor with the same model reads the actual code, selected comp, latest user feedback, Impeccable and popular-web-designs references; returns a concrete verdict and scored findings. No claimed perfect score without evidence.
4. Findings return to Hermes worker; repeat until all material findings are resolved.
5. Execute Cucumber tests in Chromium with screenshots at desktop/mobile, actual HTTP fixtures, request order/assertions, errors, auth, settings, history, malformed reports, keyboard and reduced motion. Distinguish deterministic fixtures from real provider calls. Include real backend contract verification where possible using existing test transport and isolated database.
6. Run mechanical Impeccable detector once, incorporate genuine findings, then finish review, DESIGN.md and design.json. Persist exact commands/results/screenshots/audit evidence.

## Checkpoint 2 — future SSE scope

Add authenticated event transport, replayable event IDs, disconnect/reconnect behavior, per-research routing and sanitized operational/model summaries. Stream search results, points, audit decisions and final report without exposing private model chain-of-thought. This checkpoint is documented only in this delivery; implementation begins separately.
