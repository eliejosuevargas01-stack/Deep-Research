# Design documentation record

Generated on 2026-10-26 from the shipped Checkpoint 1 frontend, after the independent Hermes review in `audits/review-r2.md` returned `disposition: ship`. This is a documentation pass; it does not replace that review or introduce another product interview.

## Files written

- `DESIGN.md`: normative YAML tokens followed by the eight canonical design-system sections.
- `.impeccable/design.json`: schema version 2 extensions, narrative and ten standalone HTML/CSS component examples. Primitives remain in DESIGN.md rather than a duplicated legacy `tokens` object.

## Source and decisions checked

Read PRODUCT.md, the approved direction in `.impeccable/surface-brief.md`, `frontend/src/styles/{tokens,main,components}.css`, the entry/App and representative composer, navigation, plan, sidebar, report, settings and empty-state components, built `frontend/dist/index.html`, the independent R2 report and `evidence/font-verification.json`.

The record follows the actual slate-neutral light canvas and charcoal actions rather than copying the earlier brief's approximate neutral values. The approved Comp C topology and rejected electric-blue/generic styling are preserved as decisions. The north-star wording derives from the approved research reading desk form. The exact self-hosted family is **Geist Sans**, with **Geist Mono** for technical text. The existing font evidence verifies loading in Chromium; this pass did not re-certify rendering. Native button samples preserve the source's lack of an explicit font-family override instead of introducing a new source rule.

Only used base color/radius/spacing roles were extracted; dormant dark overrides and unused declarations were not promoted to default tokens. Sidecar tonal ramps are synthesized OKLCH visualization metadata, not additional application palette steps. There are zero shipping raster assets; semantic text and inline SVG icons define the interface.

Existing uppercase query/plan/point-detail labels, including the plan eyebrow, are explicitly recorded as drift not canonized into a reusable kicker system. No implementation was repaired or changed during this pass.

## Documentation validation

- YAML and JSON parse successfully. Frontmatter and component sub-token keys stay within the documented schema, and all token references resolve.
- All 28 extracted color roles and every extracted radius/spacing value match the actual base CSS declarations.
- Eight canonical Markdown sections appear in order; narrative overview, characteristics, rules and do/don't lists match the sidecar.
- Schema version 2 metadata keys match the frontmatter roles; each tonal ramp has eight steps; all ten examples refer to existing component tokens and use scoped `ds-` classes without framework runtime or remote raster images.
- All ten component CSS strings parse successfully with PostCSS.
- Eight representative source hashes (the three stylesheets, Composer, ContextSidebar, Navbar, ReportView and SettingsView) still match the reviewed R2 hashes.

A fresh isolated Playwright snippet-render check was attempted but Chromium could not launch under this process sandbox (`sandbox_host_linux.cc`, operation not permitted). No new visual-render certification is claimed. The independent reviewed evidence remains Chromium desktop and mobile emulation; there is no cross-browser or physical-device certification. The recorded 21 scenarios / 100 steps and 20/20 review score belong to the existing independent audit, not a rerun by the documenter.

The user said “Feito” for component review, but the machine receipt remains pending. This pass neither creates that receipt nor changes build-phase state. No source, backend, test, configuration, deployment or commit changes were made.


## Subsequent bounded correction

After this documentation pass, the orchestrator corrected the responsive plan grid to `minmax(0, 1fr)` and `min-width: 0` on direct children at the existing 1080px breakpoint. This prevents intrinsic content sizing from clipping the plan at 375px. Palette, typography and component tokens are unchanged; the eight-hash statement above describes the documentation pass at its recorded time, not a claim that main.css remained unchanged after this correction. Final follow-up evidence lives in the R3 review and final test logs when available.
