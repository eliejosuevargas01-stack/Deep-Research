import { chromium } from 'playwright';

const base = process.argv[2] || 'http://127.0.0.1:3002';
const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: 'dark' });
const page = await ctx.newPage();
await page.addInitScript(() => localStorage.setItem('deepResearch.theme', 'dark'));

const measure = async (url) => {
  await page.goto(url, { waitUntil: 'networkidle' });
  await page.waitForTimeout(400);
  return page.evaluate(() => {
    const parse = (c) => {
      const m = c.match(/rgba?\(([^)]+)\)/);
      if (!m) return null;
      const [r, g, b, a = 1] = m[1].split(',').map(Number);
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
    const ratio = (el) => {
      const fg = parse(getComputedStyle(el).color);
      const bg = bgOf(el);
      if (!fg || !bg) return null;
      const L1 = lum(fg), L2 = lum(bg);
      return +((Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05)).toFixed(2);
    };
    const sels = [
      '.rr-rail__title', '.rr-rail__tab', '.rr-tokens__total', '.rr-tokens__unit', '.rr-tokens__model',
      '.rr-tokens__legend', '.rr-status__badge', '.rr-meta__label', '.rr-meta__value', '.rr-scope__value',
      '.rr-source__title', '.rr-source__domain', '.rr-source__badge', '.rr-sources__empty',
      '.sidebar-conversation-title', '.sidebar-conversation-meta', '.sidebar-conversations-empty',
      '.sidebar-history-link', '.tl-grupo-tema', '.tl-entrada-texto', '.tl-persona',
      '.composer-input', '.composer-legal', '.composer-model-pill', '.dock-btn-label',
    ];
    const out = {};
    for (const sel of sels) {
      const el = document.querySelector(sel);
      if (!el) { out[sel] = null; continue; }
      const cs = getComputedStyle(el);
      out[sel] = { ratio: ratio(el), fs: cs.fontSize, color: cs.color, bg: getComputedStyle(document.body).backgroundColor };
    }
    const bodyBg = getComputedStyle(document.body).backgroundColor;
    return { bodyBg, theme: document.documentElement.getAttribute('data-theme'), out };
  });
};

const execDark = await measure(`${base}/#execution-search`);
console.log('EXEC DARK', JSON.stringify(execDark, null, 1));

await page.evaluate(() => {
  const agora = Date.now();
  const regs = [1, 2].map((n) => ({
    id_pesquisa: `seed-${n}`,
    tema: `Pesquisa semeada ${n}: automação bancária e emprego formal`,
    criado_em: new Date(agora - n * 3600_000).toISOString(),
    status: 'buscando',
    planResponse: {
      id_pesquisa: `seed-${n}`, tema: `Pesquisa semeada ${n}`, n_pontos: 1,
      criado_em: new Date(agora - n * 3600_000).toISOString(), status_pipeline: 'buscando',
      preferencias: { n_pontos: 1, personas: ['historiador'] }, pontos: [],
    },
  }));
  localStorage.setItem('deep_research_local_history_v1', JSON.stringify(regs));
});
const rootDark = await measure(`${base}/`);
console.log('ROOT DARK', JSON.stringify(rootDark, null, 1));
await browser.close();
