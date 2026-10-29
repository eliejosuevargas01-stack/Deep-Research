import { chromium } from 'playwright';

const base = process.argv[2] || 'http://127.0.0.1:3002';
const routes = (process.argv[3] || '/,#harness,#execution-search,#execution-audit,#execution-rejected').split(',');
const viewports = [[1440, 900], [390, 844]];

const probe = () => {
  const txt = (el) => (el?.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 80);
  const rect = (el) => {
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) };
  };
  const visible = (el) => {
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none';
  };

  // ---------- landmarks ----------
  const landmarks = {};
  for (const sel of ['header', 'nav', 'main', 'aside', 'footer', 'h1']) {
    landmarks[sel] = [...document.querySelectorAll(sel)].filter(visible).map((el) => ({ tag: el.tagName.toLowerCase(), label: el.getAttribute('aria-label'), text: txt(el) })).slice(0, 4);
  }

  // ---------- skip link ----------
  const skip = [...document.querySelectorAll('a')].find((a) => /pular|skip/i.test(a.textContent || ''));
  const skipInfo = skip ? { text: txt(skip), position: getComputedStyle(skip).position, rect: rect(skip) } : null;

  // ---------- fonts under 11px (functional text) ----------
  const small = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const seen = new Set();
  let node;
  while ((node = walker.nextNode())) {
    const parent = node.parentElement;
    if (!parent || seen.has(parent)) continue;
    seen.add(parent);
    const t = (node.textContent || '').trim();
    if (!t) continue;
    const cs = getComputedStyle(parent);
    const fs = parseFloat(cs.fontSize);
    if (fs > 0 && fs < 11 && !parent.closest('.sr-only,[aria-hidden="true"]')) {
      small.push({ text: t.slice(0, 40), fs: +fs.toFixed(1), tag: parent.tagName.toLowerCase(), cls: (parent.className || '').toString().slice(0, 50) });
    }
  }

  // ---------- scroll containers ----------
  const scrollers = [...document.querySelectorAll('*')].filter((el) => {
    const cs = getComputedStyle(el);
    return /auto|scroll/.test(cs.overflowY) && el.scrollHeight > el.clientHeight + 2 && visible(el);
  }).map((el) => ({ tag: el.tagName.toLowerCase(), cls: (el.className || '').toString().slice(0, 50), sh: el.scrollHeight, ch: el.clientHeight }));

  // ---------- per-element horizontal overflow ----------
  const overflow = [...document.querySelectorAll('body *')].filter((el) => {
    if (!visible(el)) return false;
    const cs = getComputedStyle(el);
    if (cs.overflowX !== 'visible') return false;
    return el.scrollWidth > el.clientWidth + 2;
  }).slice(0, 12).map((el) => ({ tag: el.tagName.toLowerCase(), cls: (el.className || '').toString().slice(0, 50), sw: el.scrollWidth, cw: el.clientWidth }));

  // ---------- small touch targets ----------
  const smallTargets = [...document.querySelectorAll('button, a, input, [role="button"], select, summary')]
    .filter(visible)
    .map((el) => ({ el, r: el.getBoundingClientRect() }))
    .filter(({ r }) => r.width < 24 || r.height < 24)
    .slice(0, 12)
    .map(({ el, r }) => ({ tag: el.tagName.toLowerCase(), label: (el.getAttribute('aria-label') || txt(el)).slice(0, 40), w: Math.round(r.width), h: Math.round(r.height) }));

  // ---------- contrast of text runs against first opaque ancestor ----------
  const parse = (c) => {
    const m = c.match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const [r, g, b, a = 1] = m[1].split(',').map((v) => parseFloat(v));
    return { r, g, b, a };
  };
  const lum = ({ r, g, b }) => {
    const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
  };
  const bgOf = (el) => {
    let cur = el;
    while (cur && cur !== document.documentElement) {
      const c = parse(getComputedStyle(cur).backgroundColor);
      if (c && c.a > 0.9) return c;
      cur = cur.parentElement;
    }
    return parse(getComputedStyle(document.body).backgroundColor);
  };
  const lowContrast = [];
  const seenC = new Set();
  const w2 = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let n2;
  while ((n2 = w2.nextNode())) {
    const p = n2.parentElement;
    if (!p || seenC.has(p)) continue;
    seenC.add(p);
    const t = (n2.textContent || '').trim();
    if (!t || t.length < 2 || p.closest('.sr-only,[aria-hidden="true"]')) continue;
    const cs = getComputedStyle(p);
    const fg = parse(cs.color);
    const bg = bgOf(p);
    if (!fg || !bg) continue;
    const L1 = lum(fg), L2 = lum(bg);
    const ratio = (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05);
    const fs = parseFloat(cs.fontSize);
    const bold = parseInt(cs.fontWeight, 10) >= 700;
    const need = fs >= 24 || (fs >= 18.66 && bold) ? 3 : 4.5;
    if (ratio < need) {
      lowContrast.push({ text: t.slice(0, 40), ratio: +ratio.toFixed(2), need, fs: +fs.toFixed(1), color: cs.color, bg: `rgb(${Math.round(bg.r)},${Math.round(bg.g)},${Math.round(bg.b)})` });
    }
  }

  const grid = document.querySelector('.workspace-grid');
  const gridCols = grid ? getComputedStyle(grid).gridTemplateColumns : null;
  const rail = document.querySelector('.sidebar-container');

  return {
    title: document.title,
    scrollH: document.documentElement.scrollHeight,
    docOverflowX: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    bodyBg: getComputedStyle(document.body).backgroundColor,
    bodyFont: getComputedStyle(document.body).fontFamily,
    h1Font: document.querySelector('h1') ? getComputedStyle(document.querySelector('h1')).fontFamily : null,
    gridCols,
    railRect: rect(rail),
    mainRect: rect(document.querySelector('.workspace-main') || document.querySelector('main')),
    landmarks: Object.fromEntries(Object.entries(landmarks).map(([k, v]) => [k, v.length])),
    h1s: landmarks.h1?.map((h) => h.text) || [],
    skipLink: skipInfo,
    smallText: small.slice(0, 10),
    smallTextCount: small.length,
    scrollers,
    overflow,
    smallTargets,
    lowContrast: lowContrast.slice(0, 12),
    lowContrastCount: lowContrast.length,
    counts: {
      buttons: document.querySelectorAll('button').length,
      cards: document.querySelectorAll('.card').length,
      personaSvgs: document.querySelectorAll('.persona-icon, svg[data-persona]').length,
      favicons: [...document.querySelectorAll('img[src*="favicons"]')].filter((i) => i.naturalWidth > 0).length,
    },
  };
};

const browser = await chromium.launch();
const out = { base, capturedAt: new Date().toISOString(), results: [] };
for (const route of routes) {
  for (const [w, h] of viewports) {
    const page = await browser.newPage({ viewport: { width: w, height: h }, colorScheme: 'light' });
    const errors = [];
    page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text().slice(0, 160)); });
    page.on('response', (r) => { if (r.status() >= 400) errors.push(`${r.status()} ${r.url().slice(0, 120)}`); });
    await page.goto(`${base}/${route === '/' ? '' : route}`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(900);
    const data = await page.evaluate(probe);
    data.route = route;
    data.viewport = `${w}x${h}`;
    data.errors = [...new Set(errors)].slice(0, 6);
    out.results.push(data);
    await page.close();
  }
}

// dark theme probe on home + harness
for (const route of ['/', '#harness']) {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, colorScheme: 'dark' });
  await page.goto(`${base}/${route === '/' ? '' : route}`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(600);
  const dark = await page.evaluate(() => {
    const b = getComputedStyle(document.body);
    const theme = document.documentElement.getAttribute('data-theme');
    const h1 = document.querySelector('h1');
    return { theme, bodyBg: b.backgroundColor, bodyColor: b.color, h1Color: h1 ? getComputedStyle(h1).color : null };
  });
  out.results.push({ route: `${route} (dark-emulated)`, viewport: '1440x900', ...dark });
  await page.close();
}

await browser.close();
console.log(JSON.stringify(out, null, 1));
