disposition: fix

persistence: pass. PRODUCT.md exists and is up to date with product purpose, constraints, and platform requirements. Comp C (.impeccable/mocks/c-canvas.png) has recorded user approval binding topology with explicitly requested palette refinement. Direction contract exists in .impeccable/surface-brief.md. Shipped implementation in frontend/ has zero TypeScript compilation errors and bundle builds cleanly in dist/. All 11 Cucumber acceptance scenarios (62 steps) pass in Chromium.

fidelity:
| Element | Status | Evidence / Notes |
| :--- | :--- | :--- |
| TYPE | match | Self-hosted Geist Sans and Geist Mono typography via @fontsource. High contrast, clean geometric scales, precise tracking on micro-labels, crisp hierarchy across headers and body copy. |
| MATERIAL | match | Replaced original neon-blue and AI-slop gradients with disciplined neutral slate surfaces (#09090b to #ffffff), 1px solid borders (#e4e4e7 / #27272a), subtle elevation shadows, and deep charcoal actions. |
| GROUND | match | Cool-neutral off-white canvas (#f8fafc) matching modern analytical workbench ergonomics (Vercel/Linear discipline) without artificial glow. |
| Navigation Shell | match | Fixed top horizontal navigation with Deep Research brand icon, "+ Nova pesquisa" CTA, tabs (Pesquisa, Histórico, Configurações, Documentação), and volatile memory key status badge. |
| Topic Banner | match | Top banner anchoring the active research query with metadata tag "TEMA DA INVESTIGAÇÃO" and reset action "Novo tema". |
| Stepper (1..N Points) | match | Connected vertical stepper with numbered circular badges (1 to 5), linked via continuous vertical hairline spine, displaying hypotheses, analytical sub-questions, canonical sources, and conclusion criteria. |
| Context Panel | match | Collapsible accordion drawer ("Contexto e parâmetros da pesquisa") detailing target audience, deliverable format, time horizon, and methodological assumptions. |
| Primary Continuation Action | match | Sole explicit continuation button "[▶ Iniciar pesquisa]" anchoring the bottom of the plan card. No automatic execution on plan creation. |
| Contextual Sidebar (~28%) | acceptable adaptation | Split into two discrete cards: "Status da pesquisa" (status chip, point count, timestamp, ID) and "Escopo da pesquisa" (audience, horizon, 11/12 criteria cutoff, deliverable). Adapts beneath canvas on mobile. |
| Bottom Composer | acceptable adaptation | Docked input bar validating 5–500 characters, character counter, IME protection, and Enter submission. Note: sticky positioning requires margin/docking adjustment to prevent scroll occlusion. |

ceiling: unused native devices: mobile horizontal button toolbar wrapping, responsive card padding reduction on 375px viewports, and non-destructive prefers-reduced-motion alternatives.

material_fixes:
1. Fix mobile text clipping and horizontal overflow in dossier report view (frontend/src/styles/components.css:788,817,845; headings cut off mid-word, body sentences clipped at right margin, and action buttons overflowing viewport).
2. Localize sidebar pipeline status badges to Portuguese (frontend/src/components/ContextSidebar.tsx:44-58; raw English strings "searching", "auditing", "writing", "completed", "rejected", "failed" leak directly into the interface).
3. Replace global 0.001ms reduced-motion kill with intentional accessible transitions (frontend/src/styles/main.css:108-116; violates craft floor motion guidelines).
4. Remove exaggerated security claim in Settings intro (frontend/src/components/SettingsView.tsx:248; replace "garantindo segurança total em ambientes compartilhados" with honest, accurate description of in-memory volatility).
5. Fix criteria denominator in point audit badge (frontend/src/components/ExecutionView.tsx:170,175; renders "Reprovado (10/11)" instead of "10/12 critérios (mínimo 11)" when 12 criteria are evaluated).
6. Capture missing mobile viewport evidence (recapture required: mobile-planned.png, mobile-settings.png, mobile-failure.png).
7. Synchronize immediate navbar key badge feedback upon memory key save (frontend/src/components/Navbar.tsx:19 and frontend/src/App.tsx:26,357; badge fails to update immediately on test/save until navigation).
8. Re-anchor composer to prevent mid-scroll card occlusion (frontend/src/styles/components.css:979-987; sticky positioning within document flow causes floating obstruction over plan cards).

keep: Disciplined Vercel/Linear monochrome and charcoal visual language, strict typed Pydantic contract alignment, and zero-compromise audit gating preventing unapproved data from reaching writer.

---

# Independent Quality Audit Report (Review Round 1)

- **Date:** 2026-10-26
- **Auditor Profile:** Independent Quality Auditor (`ag/gemini-3.8-flash-high`, reasoning high)
- **Target Repository:** `/home/eliezer/Escritorio/deep-research/Deep-Research`
- **Audit Scope:** Checkpoint 1 Frontend (`frontend/src/**`, `frontend/features/**`, `docs/frontend/**`)
- **Comp Binding:** `.impeccable/mocks/c-canvas.png` (Topology binding; palette refined to popular-web-designs)
- **Disposition:** `disposition: fix`

---

## 1. Audit Health Scores (0 – 4)

| # | Dimension | Score | Rating | Key Finding |
|---|---|---|---|---|
| 1 | **Accessibility (A11y)** | **2 / 4** | Partial | Global `0.001ms` animation kill in `prefers-reduced-motion` violates craft floor; action buttons clipped on mobile. Focus rings, semantic HTML, and ARIA labels are otherwise solid. |
| 2 | **Performance** | **3 / 4** | Good | Zero runtime bloat, Vite bundle is 108kB JS / 24kB CSS gzip, pure CSS tokens, instant route transitions. Minor: auto-resize on composer fires on every keystroke without debouncing. |
| 3 | **Theming & Craft** | **3 / 4** | Good | Excellent adoption of Vercel/Linear sober charcoal palette, pure monochrome surfaces, zero AI-slop gradients. Minor: several inline style overrides instead of dedicated utility classes. |
| 4 | **Responsive Design** | **1 / 4** | Poor | Severe horizontal text clipping and button truncation on mobile dossier report (`mobile-finished.png`); missing mobile captures for planned, settings, and failure states. |
| 5 | **Implementation Integrity** | **2 / 4** | Partial | Strict backend contract mapping and honest audit-to-writer gating implemented. However, raw English status leaks in sidebar, settings makes inflated security claims, and criteria count displays confusing denominator. |
| **Total** | **Overall Quality Score** | **11 / 20** | **Acceptable (55%)** | **Significant work needed prior to ship approval.** |

*Explicit Acceptance Matrix Satisfaction:* **68.75%** (11/16 core audit criteria fully satisfied with concrete evidence; 5 criteria partially satisfied or requiring fixes).

---

## 2. Implementation Integrity Verdict

**Status: FAIL (Fixes Required)**
The frontend implementation successfully delivers the core structural architecture of Checkpoint 1: synchronous pipeline execution, explicit start action without automatic background research, typed Pydantic v2 schemas, Fernet-encrypted admin parameters, in-memory volatile authentication, and robust Cucumber/Playwright acceptance tests.

However, the build cannot be approved for release in its current state due to material responsive layout breakage on mobile viewports, unlocalized pipeline status telemetry, inflated security copy, an inaccessible reduced-motion hack, and missing visual evidence for three mobile states.

---

## 3. Executive Summary of Detailed Findings

- **P0 (Blocking Release):** 2 issues
- **P1 (Major Quality / Compliance):** 4 issues
- **P2 (Minor / Usability Polish):** 2 issues

### Priority Breakdown:
1. **[P0] Mobile Report Text Truncation & Action Toolbar Overflow** (`frontend/src/styles/components.css:788,817,845`)
2. **[P0] Missing Mobile State Capture Evidence** (`docs/frontend/evidence/`)
3. **[P1] Unlocalized Raw English Pipeline Status in Sidebar** (`frontend/src/components/ContextSidebar.tsx:44-58`)
4. **[P1] Destructive Global Reduced-Motion Rule** (`frontend/src/styles/main.css:108-116`)
5. **[P1] Inflated "Segurança Total" Claim in Settings** (`frontend/src/components/SettingsView.tsx:248`)
6. **[P1] Audit Denominator Misleading Formulation** (`frontend/src/components/ExecutionView.tsx:170,175`)
7. **[P2] Navbar Key Status Badge Delayed State Synchronization** (`frontend/src/components/Navbar.tsx:19`)
8. **[P2] Composer Sticky Occlusion During Mid-Scroll** (`frontend/src/styles/components.css:979-987`)

---

## 4. Detailed Findings Catalog

### [P0] Mobile Report Viewport Containment & Text Clipping
- **Location:** `frontend/src/styles/components.css:788, 817, 845`
- **Category:** Responsive Design / Usability
- **Impact:** Critical usability failure on mobile devices. Users on viewports $\le 375\text{px}$ cannot read complete sentences in the executive summary, thematic axes, or caveats. Headings (`Eixos Tem...`, `Limitações Metodol...`) and body text (`sign...`, `capaci...`) clip abruptly at the right margin. The action buttons toolbar (`Copiar Markdown`, `Baixar .md`, `Nova pesquisa`) overflows the viewport horizontally, rendering the third button inaccessible.
- **Evidence:** Verified via `vision_analyze` on `docs/frontend/evidence/mobile-finished.png`.
- **Root Cause:** `.report-card` applies rigid desktop padding (`padding: var(--space-8);` = 32px), reducing the available width on 375px screens to 279px. `.report-buttons` has `display: flex; gap: var(--space-2);` without `flex-wrap: wrap`. `.markdown-body` lacks `overflow-wrap: break-word` and `word-break: break-word`.
- **Remediation:**
  1. In `components.css`, add a mobile media query `@media (max-width: 640px)` for `.report-card` setting `padding: var(--space-4);`.
  2. For `.report-buttons`, add `flex-wrap: wrap; width: 100%;`.
  3. In `.markdown-body`, add `overflow-wrap: break-word; word-break: break-word;`.

---

### [P0] Missing Mobile Viewport Evidence Captures
- **Location:** `docs/frontend/evidence/`
- **Category:** Verification & Evidence Integrity
- **Impact:** Check 0 of the audit specification requires visual proof across the platform's viewport set for all operational states (empty, planned, finished, settings, failure). The worker provided desktop captures for all states, but only provided mobile captures for empty and finished. Mobile planned, mobile settings, and mobile failure states remain completely unverified.
- **Evidence:** Directory scan of `docs/frontend/evidence/` reveals absence of `mobile-planned.png`, `mobile-settings.png`, and `mobile-failure.png`.
- **Remediation:** Worker must execute Playwright/Cucumber capture runs targeting mobile viewport (375x812) for the planned, settings, and failure screens, saving them to `docs/frontend/evidence/`.

---

### [P1] Raw English Pipeline Status Strings Leaking into Portuguese UI
- **Location:** `frontend/src/components/ContextSidebar.tsx:44-58`
- **Category:** Localization / Implementation Integrity
- **Impact:** Degrades professional craft. When the pipeline enters synchronous execution, the sidebar displays raw English internal status names (`searching`, `auditing`, `writing`, `completed`, `rejected`, `failed`) instead of user-facing Portuguese labels.
- **Evidence:** Confirmed in `docs/frontend/evidence/browser-smoke-observations.md` (Observation #2) and verified visually on `desktop-finished.png` (status: `completed`) and `desktop-failure.png` (status: `rejected`).
- **Root Cause:** `ContextSidebar.tsx` checks only Portuguese legacy keys (`planejado`, `aguardando`, `buscando`, etc.), but `App.tsx` sets `pipelineStage` using English keys (`'searching'`, `'auditing'`, `'writing'`, `'completed'`, `'rejected'`, `'failed'`). The fallback `: statusNormalized` outputs the untranslated key.
- **Remediation:** Map all `PipelineStage` enum values in `ContextSidebar.tsx`:
  - `searching` $\rightarrow$ `"Buscando evidências..."`
  - `auditing` $\rightarrow$ `"Em auditoria..."`
  - `writing` $\rightarrow$ `"Redigindo dossiê..."`
  - `completed` $\rightarrow$ `"Dossiê concluído"`
  - `rejected` $\rightarrow$ `"Reprovado na auditoria"`
  - `failed` $\rightarrow$ `"Falha na execução"`

---

### [P1] Destructive Global Reduced-Motion CSS Kill
- **Location:** `frontend/src/styles/main.css:108-116`
- **Category:** Accessibility (A11y)
- **Impact:** Users with vestibular and motion sensitivities lose all visual state feedback and transition cues across the entire application.
- **Evidence:**
  ```css
  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
      animation-duration: 0.001ms !important;
      animation-iteration-count: 1 !important;
      transition-duration: 0.001ms !important;
      scroll-behavior: auto !important;
    }
  }
  ```
- **Root Cause:** This blunt universal wildcard override is explicitly flagged in Impeccable reference `reference/audit.md` as an anti-pattern: *"prefers-reduced-motion needs an intentional alternative that preserves state change and hierarchy; flag a global 0.01ms kill that destroys useful feedback"*.
- **Remediation:** Remove the universal wildcard `0.001ms` override. Rely on GSAP's existing `prefersReducedMotion` check in `App.tsx` and provide subtle opacity/color cross-fades rather than killing all transitions globally.

---

### [P1] Inflated Security Claim in Settings Copy
- **Location:** `frontend/src/components/SettingsView.tsx:248`
- **Category:** Truth in Advertising / Craft Floor
- **Impact:** Misleads operators and enterprise users regarding client-side cryptographic guarantees. Memory-only storage in a browser process prevents persistence to disk/localStorage, but does not guarantee "total security in shared environments" (it remains vulnerable to memory inspection, browser tab sharing, and active XSS).
- **Evidence:** Confirmed in `docs/frontend/evidence/browser-smoke-observations.md` (Observation #5) and inspection of `SettingsView.tsx:248`:
  > *"é salva em disco, localStorage ou cookies, garantindo segurança total em ambientes compartilhados."*
- **Remediation:** Revise copy to: *"A chave é mantida exclusivamente na memória volátil da sessão ativa e nunca é gravada em disco, cookies ou localStorage."*

---

### [P1] Misleading Criteria Denominator in Point Audit Badge
- **Location:** `frontend/src/components/ExecutionView.tsx:170, 175`
- **Category:** Implementation Integrity / User Communication
- **Impact:** Mathematical confusion. In `desktop-failure.png`, Point 1 displays `Reprovado (10/11)`. The user sees a grid of 12 evaluated criteria (10 green checks, 2 red crosses). Presenting `10/11` leads the user to believe 11 criteria were evaluated, when in fact 12 were evaluated and 11 was the threshold for approval.
- **Evidence:** Visual analysis of `desktop-failure.png`.
- **Remediation:** Change badge format to explicitly separate evaluated score from passing cutoff:
  `Aprovado (${item.criterios_aprovados}/12 critérios • mín. ${item.criterios_minimos})` or `Reprovado (${item.criterios_aprovados}/12 critérios • mín. ${item.criterios_minimos})`.

---

### [P2] Navbar Key Status Badge Delayed State Synchronization
- **Location:** `frontend/src/components/Navbar.tsx:19` and `frontend/src/App.tsx:26, 357`
- **Category:** Usability / UI State Consistency
- **Impact:** Immediately after entering a valid key and clicking "Definir em memória" or "Testar Conexão com API", the top navbar badge continues to display "Sem Chave (Aberto)". The badge only updates to "Chave em Memória" after the user clicks away and navigates to another route.
- **Evidence:** Documented in `docs/frontend/evidence/browser-smoke-observations.md` (Observation #1).
- **Root Cause:** `Navbar.tsx` receives `keyConfigured={Boolean(apiKey)}` from `App.tsx`. When `apiKey` state in `App` is not re-rendered synchronously with `SettingsView` actions, the badge remains stale.
- **Remediation:** Expose a direct state synchronization callback or custom event `window.dispatchEvent(new Event('apikey-changed'))` so `Navbar` updates immediately when the memory key is set, cleared, or verified.

---

### [P2] Composer Sticky Occlusion During Mid-Scroll
- **Location:** `frontend/src/styles/components.css:979-987`
- **Category:** Visual Hierarchy / Layout Ergonomics
- **Impact:** Because `.composer-anchor` uses `position: sticky; bottom: var(--space-4); margin: var(--space-6) auto 0 auto;`, during smooth scrolling on long pages (such as the 5-point plan or the full dossier report), the composer floats over and partially occludes content cards.
- **Evidence:** Visible in `desktop-planned.png` where the composer box hovers over Point 2 during scroll.
- **Remediation:** Anchor the composer cleanly to the viewport bottom (`position: fixed; bottom: 0; left: 0; right: 0;`) within an isolated footer dock with background blur/fade (`background: linear-gradient(to top, var(--color-canvas) 80%, transparent);`) and add matching `padding-bottom: 120px;` to `.workspace-main` so content cards can scroll completely clear of the composer dock.

---

## 5. Verification Commands and File Hashes

### Recorded Verification Execution
1. **TypeScript Build & Typecheck:**
   - Command: `npm run build`
   - Exit Code: `0`
   - Output: `2216 modules transformed. dist/assets/index-DcH91Li0.js (108.42 kB / gzip: 35.12 kB), dist/assets/index-D6uOqods.css (24.16 kB / gzip: 5.12 kB)`.
2. **Acceptance Test Suite:**
   - Command: `npm run test:e2e`
   - Exit Code: `0`
   - Output: `11 scenarios (11 passed), 62 steps (62 passed) in 14.64s`.
3. **HTTP Contract Verification against Real FastAPI API:**
   - Command: `./.venv/bin/python docs/frontend/verify_http_contract.py`
   - Exit Code: `0`
   - Output: `4/4 requests passed (Plan: 201, Search: 200, Audit: 200, Writer: 200)`.

### Cryptographic Hashes of Shipped Artifacts (SHA-256)
```
# Configuration & Manifests
e3d8fee3d0c3a46abc48f62971f7b3ac66e58b57cfebe762415bff5eba7bdf33  frontend/package.json
3aeb3ce07e7fb2992a9766af7ae7c0ff5a8e69d891c09cd09a5e1a14c6b3414d  frontend/index.html
f2b3aeb676e5a32efe581c0cd6b47a1d7ba8204a581692accf664cbeef277970  frontend/vite.config.ts
43797bbc3258d9363a3a76a7d93abebcff0e84f42687fe5376f9e1a1f84af356  frontend/tsconfig.json
7b36a300121c2d084821c54f602cdc7ad47740d396e241b14600d83f4da944c8  frontend/cucumber.json
a97c3ebc2ee54cee7e2f98f4923dac0ec7bb01dfbdaa2033eb7c7bd4e7dbc04f  frontend/README.md

# Frontend Source Code
bcba9392f194ab98e33c3c8729b2c9019dde846ecfe784300325361378a8e601  frontend/src/App.tsx
703d1a13b475870988e31805b0bd9805522b9f7c4e85877709701ff1ba63a95a  frontend/src/main.tsx
13ffef6fe9b8b013ad04c690602bc4f20393fda4fe7343b9543c92e904266a8b  frontend/src/components/Composer.tsx
f098566553d3227eb82e9a7784dcf0fe80d5e49d5e334019c5012157252b8282  frontend/src/components/ContextSidebar.tsx
306301ee790d0a49ee73a5812cc5c44f412ca662fbdbbce469b1b6029b38cfa4  frontend/src/components/DocsView.tsx
5def662b94b108caac6339a0da0a39b704c1879b605397084b83582ec1309c21  frontend/src/components/EmptyState.tsx
f5bfd559930fcf8d515f8bdbca47632ee1a661fc5a14854c76b5529d13d9a44b  frontend/src/components/ExecutionView.tsx
3f2f23c2e3c952ae93d40e899639440452251fb3173434cf2c27ba66dd3ac219  frontend/src/components/HistoryView.tsx
9bf45dda8fc982057ee3ebb5c88b6c8e0170ac304ffcd86a0b17a0b470e104c2  frontend/src/components/Navbar.tsx
4d0b40d10d541e701ff241468eff8c8a904531f8562c4c52154cb2b004810cf1  frontend/src/components/PlanView.tsx
0b6334ce15af2744d23953d5d17172eff88e3496b07bcd895b71e5db67a41fed  frontend/src/components/ReportView.tsx
65803333122b2f98f308a9c7e848135e13c8ad1a6e1c0167d5b12a361698e868  frontend/src/components/SettingsView.tsx
da144986cfc2ecfca0810404742306dec7e08ea7aeb79cb519d90111ba722c18  frontend/src/services/api.ts
fbb605fdfb3468a8459c14c97c69aefd0ce791ec4ff455333277e33be0b58788  frontend/src/services/history.ts
052a8bfef96339e7d4681888e4af6c3c335617b9a76dfadab8961d732cb8e3a1  frontend/src/styles/components.css
b589908f46a6c7107606968ccfad81133c88621704c65afec37481e94ba18547  frontend/src/styles/main.css
3ec40a0a32bced802cd45d6989e9d0b29627f7045ddeaaf0f395a825d9d8c8a5  frontend/src/styles/tokens.css
908ea5f009f85b64e0d67ee0a731405861aba21cabf3a749e5bc45e5c92a539d  frontend/src/types/api.ts

# Acceptance Test Suites
6d70e0ac3f402014cd9e2785932aaf6664135420bf756d3cff2e480bb8613f4c  frontend/features/01_research_workspace.feature
3313d499b6a018e7357c988e0bead5823b71a424a4e9c3fed0eb663abd35a2eb  frontend/features/02_audit_gating_and_failures.feature
5250b5cb951c3501c068dc828558f89857dcbe0ef66871fc8c71d7c1b94fd9b7  frontend/features/03_settings_and_credentials.feature
fdf60096fdded7da6335717dfa37c9a07d7549bd5fa1ecd57b78a2e63f632734  frontend/features/04_history_and_persistence.feature
55cb788275e8434ca6e18a2c909344f0fc1a95952349ce0290c0b55426bd25e5  frontend/features/step_definitions/steps.ts
61c0624c15a7cc7039e7180ffe711e6c1877bdf4900efad955632d8bb1a6f0f1  frontend/features/support/hooks.ts
278e91cc967c8fd27546224878d6773d81998644ed798e2eba37406fa8d61017  frontend/features/support/world.ts

# Visual Evidence & Observations
118cfb4c49757be3d6c2e3b4d8082acae678f7c2634856a4c46a9e59fc3c7548  docs/frontend/evidence/browser-smoke-observations.md
1d50c7480be8f3a2f9357b46013fbfda4f3e5f7d64f08e2c69ca35f9737b038a  docs/frontend/evidence/desktop-empty.png
78efab912db9335a66469e9eb2991a7c5fb85606d27f151d02e7c963a57cf146  docs/frontend/evidence/desktop-failure.png
eecb7543c62fdf442136e82df090ed0f0255f858dfebdf0cf0c3cd3b21997823  docs/frontend/evidence/desktop-finished.png
e917885207558ac427ce35ac4eaa600a64e2cc761909aadae92b058e7c370d7d  docs/frontend/evidence/desktop-history.png
0ff8dd6532b910351e225b63260c290c9d16f86ce69e78dccfde9a97e48b3c34  docs/frontend/evidence/desktop-planned.png
bf53eef32091252ff81647bd673a66679985b716482f43edcc8d14fa3a065c52  docs/frontend/evidence/desktop-settings.png
787de3e6f119a143b0519cb779bf56f0f2988cf5732f91c3fda2c7f58b5307ec  docs/frontend/evidence/mobile-empty.png
cac74db382d4e9215717d432d7911e6494c3bb33854c15fd376b3067af857cec  docs/frontend/evidence/mobile-finished.png
3bc0a0c010e5fb187f12ea7174995fe631588c9db0a6c3f7a96b8c0e4ca3584c  docs/frontend/evidence/real-fastapi-http.json

# Documentation and Progress Reports
9695c69442543f87131212b2ff5d1b8b6cc5e7b9532179af1ddca6ab5da3060e  docs/frontend/orchestrator-evidence.md
a791348ee97a7c86d74f528e539a0dad470912059ad165959e0e30c9cda54874  docs/frontend/worker-progress.md
a44e66c14299b7ab57ee7e2a0c11e3c04a30e1b3c6c182baa120e50d3ca35c6f  docs/frontend/worker-result.md
```

---

## 6. Reconciliation of Browser Smoke Observations

| Item | Smoke Observation | Auditor Code & Evidence Verification | Audit Status |
|---|---|---|---|
| 1 | Top badge remained "Sem Chave (Aberto)" immediately after saving memory key until navigation. | Confirmed in `App.tsx:26,357` and `Navbar.tsx:19`. State update in `SettingsView` is not propagated reactively to `App`'s state without a navigation event. | **Confirmed Finding (P2)** |
| 2 | Sidebar state displayed raw English `searching` and `completed` in Portuguese interface. | Confirmed in `ContextSidebar.tsx:44-58`. Missing mapping for English `PipelineStage` values results in verbatim English text on Portuguese UI. | **Confirmed Finding (P1)** |
| 3 | Report metadata displayed `Fontes canônicas citadas: 0`, while body contained 3 links. | Resolved by Worker in build 00:14. `ReportView.tsx:24-40` now uses updated URL extraction regex and `mobile-finished.png` displays 3 verified sources correctly. | **Verified Resolved** |
| 4 | UI displayed report and exposed copy/download controls; behavior not exercised in smoke. | Verified by Auditor in `ReportView.tsx:48-81`. Both clipboard copy with fallback and Blob-based markdown file download are implemented safely. | **Verified Working** |
| 5 | Settings claimed "garantindo segurança total em ambientes compartilhados". | Confirmed in `SettingsView.tsx:248`. Misleading copy requires editorial refinement. | **Confirmed Finding (P1)** |

---

## 7. Ordered Actionable Fix List for Worker (Round 2)

1. **[CSS/Responsive]** Add mobile styles in `frontend/src/styles/components.css`:
   - `@media (max-width: 640px) { .report-card { padding: var(--space-4); } }`
   - `.report-buttons { flex-wrap: wrap; width: 100%; }`
   - `.markdown-body { overflow-wrap: break-word; word-break: break-word; }`
2. **[i18n/Sidebar]** In `frontend/src/components/ContextSidebar.tsx`, complete the status translation dictionary for `'searching'`, `'auditing'`, `'writing'`, `'completed'`, `'rejected'`, and `'failed'`.
3. **[A11y/CSS]** In `frontend/src/styles/main.css`, delete the destructive `0.001ms` universal wildcard rule under `@media (prefers-reduced-motion: reduce)`.
4. **[Copy/Settings]** In `frontend/src/components/SettingsView.tsx:248`, replace the "segurança total" phrase with truthful factual phrasing about in-memory volatility.
5. **[UI/Criteria]** In `frontend/src/components/ExecutionView.tsx:170,175`, update badge text to `${item.criterios_aprovados}/12 critérios (mín. ${item.criterios_minimos})`.
6. **[Evidence/Recapture]** Re-run Playwright captures in mobile viewport (375x812) to produce `mobile-planned.png`, `mobile-settings.png`, and `mobile-failure.png`.
7. **[State/Navbar]** In `frontend/src/components/SettingsView.tsx` and `frontend/src/App.tsx`, trigger immediate reactive update of `apiKey` state so `Navbar` badge updates instantly upon key assignment.
8. **[Layout/Composer]** In `frontend/src/styles/components.css`, adjust `.composer-anchor` to fixed bottom docking with scroll padding to prevent card obstruction during scroll.
