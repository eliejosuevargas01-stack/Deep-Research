# Orchestrator evidence

## Backend contracts

Executed existing `tests/integration/test_endpoints.py` with isolated SQLite `/tmp/deep-research-frontend-contract-elevated.db`, test Fernet key and dummy provider values. External calls use existing test mock transport. Result: **6 passed in 1.63s**. Coverage: credential save/masked list, plan, search, audit, writer and full endpoint sequence.

The first sandboxed attempt stalled in aiosqlite's thread/asyncio wakeup during fixture initialization. Diagnostic bounded to 15 seconds confirmed that environment problem. Stalled attempt interrupted; rerun outside sandbox completed. No backend source modification or real provider calls involved.

## Design approval

Impeccable decision page answer: `canvas`, comp `.impeccable/mocks/c-canvas.png`. Chat feedback confirms the third comp is chosen and original colors/generic AI aesthetic are rejected. Approval binds topology, with explicitly requested palette and craft refinement using popular-web-designs.

## Boundaries

Existing backend changes preserved. No deployment requested for this checkpoint. New frontend must use actual API contracts; deterministic UI tests are distinguished from live provider validation.

## Final checkpoint verification

The independent Hermes R2 Markdown verdict is `ship`, 20/20 health and 16/16 acceptance criteria. Its JSON companion is explicitly an orchestrator transcription; the completed Markdown remains authoritative.

The final build passed. A fresh isolated API restart exposed an acceptance-test setup dependency: the credentials table scenario expected records left over from earlier runs. Its Given now creates two public fixture parameters through the real encrypted credentials endpoint on the designated test origin. No application or backend source changed. A second fresh SQLite restart followed by the full suite passed **21 scenarios / 101 steps**, in 25.828 seconds. Logs and machine summaries are in `evidence/final-build.*` and `evidence/final-cucumber.*`; the preceding failed run is retained as `evidence/cucumber-before-fixture-fix.*`.

DESIGN.md and schema-v2 `.impeccable/design.json` describe the implemented tokens and components. Human component review still has no machine receipt; implementation/audit/test success does not close that separate Impeccable gate.

Local transient user services keep the actual backend on 8010 and production preview on 3002 accessible. They have no boot autostart. The component review is a separate localhost service. No remote deployment was performed.

## Responsive plan correction after R2

Final screenshot inspection found a real gap in the initial R2 review: the mobile plan extended beyond the viewport while document-level overflow was hidden. The responsive grid now uses `minmax(0, 1fr)` and direct children have `min-width: 0`. Actual bounds of the banner, reset action, plan card, sidebar and start button are all within the viewport at 375, 768 and 1440px; see `evidence/responsive-plan-geometry.json` and `plan-final-{375,768,1440}.png`. The stronger Gherkin check measures these element rectangles instead of trusting document.scrollWidth. Desktop/mobile plan screenshot names no longer overwrite each other. Build and 21 scenarios / 101 steps passed after this source correction (28.039s). R2 remains historical until the bounded follow-up audit is complete.

The local Hermes router was unavailable because its user service launched Node18 while the installed runtime needs a newer Node. A reversible runtime-only systemd drop-in at `/run/user/1000/systemd/user/9router.service.d/90-codex-compatible-node.conf` selects the existing Node26 binary. The persistent service file and account/provider settings were not edited. Router HTTP returned200 after restart. The temporary override disappears with the user runtime directory; a permanent service adjustment is outside this frontend change.

## Final result

Hermes worker accepted the responsive fix; independent fresh Hermes R3 returned ship, 20/20 and16/16 acceptance. R3 Markdown SHA-256 matches its own JSON. A post-approval Cucumber run then passed21/21 scenarios and101/101 steps (30.708s). Build passed. Audited baseline screenshots were preserved; new captures/logs reside in evidence/post-audit. Test-only API8011 and Vite3001 stopped after successful completion; actual backend8010 and preview3002 returnHTTP200. Human component-review receipt remains null, separate from technical acceptance. See checkpoint-1.md and .impeccable/checkpoint-1.json.

## Human component approval received

The user submitted the actual local panel and then confirmed “feito, de novo”. Status now returns visualDecision=approved, captureVerified=true, inventoryConfirmed=true, no missing items and 15/15 approve decisions. The original receipt is copied unmodified in meaning to evidence/component-review-approved.json; checkpoint metadata and handoff were updated. Historical audit documents remain unchanged.
