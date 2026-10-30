import { createRequire } from 'node:module';
import { execFileSync } from 'node:child_process';

// Resolve o playwright da árvore em que o comando foi disparado (o frontend),
// nunca o de ~/node_modules, que aponta para um build sem browser instalado.
const { chromium } = createRequire(`${process.cwd()}/`)('playwright');

/**
 * Portão de zero achados da paridade GDR.
 * Roda `impeccable detect` por rota e mede os invariantes visuais que o
 * detector não cobre (overflow, tipo mínimo, cursor piscante, rail).
 *
 * Uso: node scripts/audit/zero-gate.mjs http://127.0.0.1:3002 [--json]
 */

const base = (process.argv[2] || 'http://127.0.0.1:3002').replace(/\/$/, '');
const asJson = process.argv.includes('--json');
const DETECT = '/home/eliezer/.claude/skills/impeccable/scripts/impeccable';

const ROUTES = ['/', '/#research', '/#history', '/#settings', '/#docs', '/#execution-search', '/#execution-audit', '/#execution-rejected', '/#execution-failed', '/#harness', '/#plan'];
const VIEWPORTS = [
  [1440, 900],
  [768, 900],
  [390, 844],
];

const SKIP_SELECTORS = new Set(); // vazio quando o portão roda na árvore mesclada

function detect(url) {
  try {
    const out = execFileSync('bash', [DETECT, 'detect', url, '--json'], {
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'ignore'],
      timeout: 120_000,
    });
    const parsed = JSON.parse(out);
    return parsed.filter((f) => !SKIP_SELECTORS.has(f.selector));
  } catch (err) {
    return [{ antipattern: 'detect-falhou', selector: err.message.slice(0, 120), severity: 'warning' }];
  }
}

const browser = await chromium.launch();
const report = { base, capturedAt: new Date().toISOString(), detects: [], invariants: [], failures: [] };

for (const route of ROUTES) {
  const findings = detect(`${base}${route}`);
  report.detects.push({ route, count: findings.length, findings: findings.map((f) => `${f.antipattern} ${f.selector || ''}`.trim()) });
  if (findings.length) report.failures.push(`${route}: detect ${findings.length} achado(s)`);
}

for (const [w, h] of VIEWPORTS) {
  const ctx = await browser.newContext({ viewport: { width: w, height: h }, colorScheme: 'light' });
  const page = await ctx.newPage();
  for (const route of ROUTES) {
    await page.goto(`${base}${route}`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(400);
    const m = await page.evaluate(() => {
      const visible = (el) => {
        const r = el.getBoundingClientRect();
        const c = getComputedStyle(el);
        return r.width > 0 && r.height > 0 && c.visibility !== 'hidden' && c.display !== 'none';
      };
      const tiny = [];
      for (const el of document.querySelectorAll('main, .main-content, .docs-view, .settings-container, .context-sidebar, .sidebar-container, .tl-linear')) {
        for (const node of el.querySelectorAll('p, span, li, dt, dd, a, button, label, time, div')) {
          if (!visible(node)) continue;
          if (node.classList.contains('sr-only')) continue;
          if (node.closest('.sr-only')) continue;
          if (node.getAttribute('aria-hidden') === 'true') continue;
          const own = [...node.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim().length > 1);
          if (!own) continue;
          const fs = parseFloat(getComputedStyle(node).fontSize);
          if (fs < 12) {
            const prose = /^(P|LI|DD|BLOCKQUOTE)$/.test(node.tagName);
            tiny.push({ cls: node.className.toString().slice(0, 36), fs: Math.round(fs * 100) / 100, prose, text: node.textContent.trim().slice(0, 24) });
          }
        }
      }
      const uniqTiny = [...new Map(tiny.map((t) => [t.cls + t.fs, t])).values()].slice(0, 8);
      const tinyProse = uniqTiny.filter((t) => t.prose || t.fs < 11);
      const blinking = [...document.querySelectorAll('*')].filter((el) => {
        const a = getComputedStyle(el).animationName;
        return a && a !== 'none' && visible(el) && /pisca|blink|cursor/i.test(a + ' ' + el.className);
      }).length;
      const rail = document.querySelector('.context-sidebar');
      const tokens = document.querySelector('.rr-tokens');
      const personas = document.querySelectorAll('.tl-linear svg').length;
      const overflowEls = [];
      for (const el of document.querySelectorAll('main *')) {
        if (el instanceof SVGElement) continue; // <text> SVG reporta scrollWidth irreal (medido: bbox cabe)
        if (el.getAttribute('aria-hidden') === 'true') continue;
        const c = getComputedStyle(el);
        if (c.overflowX === 'visible' && el.scrollWidth > el.clientWidth + 4 && el.clientWidth > 0) {
          const t = (el.textContent || '').trim();
          if (t.length > 0) overflowEls.push({ cls: el.className.toString().slice(0, 36), sw: el.scrollWidth, cw: el.clientWidth });
        }
      }
      return {
        docOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
        tiny: uniqTiny,
        tinyProse,
        microCount: uniqTiny.length - tinyProse.length,
        blinking,
        railTabs: rail ? [...rail.querySelectorAll('[role="tab"]')].filter(visible).map((t) => t.textContent.trim().replace(/\s+/g, ' ')) : [],
        railWidth: rail ? Math.round(rail.getBoundingClientRect().width) : 0,
        tokensVisible: tokens ? visible(tokens) : null,
        personaSvgs: personas,
        overflowEls: overflowEls.slice(0, 6),
      };
    });
    const key = `${route} @${w}x${h}`;
    report.invariants.push({ key, ...m });
    if (m.docOverflow > 0) report.failures.push(`${key}: documento transborda ${m.docOverflow}px`);
    if (m.tinyProse.length) report.failures.push(`${key}: ${m.tinyProse.length} texto(s) de corpo < 12px (${m.tinyProse.map((t) => t.cls + ':' + t.fs).join(', ')})`);
    if (m.blinking) report.failures.push(`${key}: ${m.blinking} animação de cursor piscante`);
    if (m.overflowEls.length) report.failures.push(`${key}: ${m.overflowEls.length} elemento(s) com conteúdo clipado (${m.overflowEls.map((e) => e.cls).join(', ')})`);
    if (route === '/#execution-search' && w === 1440) {
      if (!m.tokensVisible) report.failures.push(`${key}: medidor de tokens invisível`);
      if (m.personaSvgs < 4) report.failures.push(`${key}: só ${m.personaSvgs} svg(s) na timeline (ícones de persona ausentes)`);
      if (!m.railTabs.length) report.failures.push(`${key}: rail sem abas visíveis`);
    }
  }
  await ctx.close();
}

// Tema escuro: contraste do texto secundário na sidebar e no rail.
{
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: 'dark' });
  const page = await ctx.newPage();
  await page.goto(`${base}/#execution-search`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(500);
  const dark = await page.evaluate(() => {
    const lum = (c) => {
      const [r, g, b] = c.map((v) => {
        const s = v / 255;
        return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
      });
      return 0.2126 * r + 0.7152 * g + 0.0722 * b;
    };
    const parse = (s) => (s.match(/[\d.]+/g) || []).slice(0, 3).map(Number);
    const baseOf = (el) => {
      let n = el;
      while (n) {
        const c = getComputedStyle(n).backgroundColor;
        if (c && !/rgba?\(0, 0, 0, 0\)|transparent/.test(c)) return parse(c);
        n = n.parentElement;
      }
      return [255, 255, 255];
    };
    const ratio = (el) => {
      const fg = parse(getComputedStyle(el).color);
      const bg = baseOf(el);
      const [a, b] = [lum(fg), lum(bg)].sort((x, y) => y - x);
      return Math.round(((a + 0.05) / (b + 0.05)) * 100) / 100;
    };
    const samples = [...document.querySelectorAll('.sidebar-container p, .sidebar-container span, .context-sidebar dt, .context-sidebar dd, .tl-linear span')]
      .filter((el) => visibleCheck(el))
      .slice(0, 40);
    function visibleCheck(el) {
      const r = el.getBoundingClientRect();
      return r.width > 0 && r.height > 0 && (el.textContent || '').trim().length > 0;
    }
    return {
      bodyBg: getComputedStyle(document.body).backgroundColor,
      worst: samples.map((el) => ({ cls: el.className.toString().slice(0, 30), r: ratio(el) })).sort((a, b) => a.r - b.r).slice(0, 6),
    };
  });
  report.dark = dark;
  const bad = dark.worst.filter((x) => x.r < 4.5);
  if (bad.length) report.failures.push(`escuro: ${bad.length} texto(s) < 4.5:1 (pior ${dark.worst[0].cls} ${dark.worst[0].r}:1)`);
  await ctx.close();
}

await browser.close();
report.verdict = report.failures.length === 0 ? 'PASS' : 'FAIL';
if (asJson) {
  console.log(JSON.stringify(report, null, 2));
} else {
  for (const d of report.detects) console.log(`detect ${d.route.padEnd(22)} ${d.count === 0 ? 'ok' : d.count + ' -> ' + d.findings.join(' | ')}`);
  for (const i of report.invariants) {
    const flag = i.docOverflow || i.tiny.length || i.blinking || i.overflowEls.length ? 'FAIL' : 'ok  ';
    console.log(`${flag} ${i.key.padEnd(34)} over=${i.docOverflow} tiny=${i.tiny.length} blink=${i.blinking} clip=${i.overflowEls.length}`);
  }
  console.log('dark worst contrast:', report.dark.worst.map((w) => `${w.cls} ${w.r}:1`).join(' · '));
  console.log(report.verdict === 'PASS' ? 'ZERO FINDINGS' : `FAILURES (${report.failures.length}):\n - ${report.failures.join('\n - ')}`);
}
process.exit(report.verdict === 'PASS' ? 0 : 1);
