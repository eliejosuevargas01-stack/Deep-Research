import { chromium } from 'playwright';

const base = process.argv[2] || 'http://127.0.0.1:3002';
const browser = await chromium.launch();
const out = {};
for (const [w, h] of [[1440, 900], [390, 844]]) {
  const ctx = await browser.newContext({ viewport: { width: w, height: h } });
  const page = await ctx.newPage();
  await page.goto(`${base}/`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(300);

  const trigger = w < 640 ? '.composer-tools button, .dock-trigger, .composer-tools [role="button"]' : '[data-composer-tools] button';
  const before = await page.evaluate(() => {
    const ta = document.querySelector('.composer-input');
    const r = ta.getBoundingClientRect();
    return { y: Math.round(r.y), h: Math.round(r.height), bottom: Math.round(r.bottom), ih: innerHeight };
  });
  const clicked = await page.evaluate((sel) => {
    const b = document.querySelector(sel);
    if (!b) return null;
    b.click();
    return (b.textContent || '').trim().slice(0, 30) || b.getAttribute('aria-label');
  }, trigger);
  await page.waitForTimeout(350);
  const after = await page.evaluate(() => {
    const ta = document.querySelector('.composer-input');
    const r = ta.getBoundingClientRect();
    const rect = ta.getBoundingClientRect();
    const cx = rect.x + rect.width / 2;
    const cy = rect.y + rect.height / 2;
    const hit = document.elementFromPoint(cx, cy);
    const panel = document.querySelector('.dock-panel, .composer-panel, [data-dock-panel]');
    const pr = panel ? panel.getBoundingClientRect() : null;
    const cs = panel ? getComputedStyle(panel) : null;
    return {
      ta: { y: Math.round(r.y), bottom: Math.round(r.bottom) },
      hitIsTextarea: hit ? hit === ta || ta.contains(hit) : null,
      hitTag: hit ? hit.tagName : null,
      panel: pr ? { y: Math.round(pr.y), h: Math.round(pr.height), pos: cs.position } : null,
      overlapY: pr ? Math.max(0, Math.min(rect.bottom, pr.bottom) - Math.max(rect.y, pr.y)) : null,
      scrollers: [...document.querySelectorAll('*')].filter((el) => {
        const s = getComputedStyle(el);
        return /auto|scroll/.test(s.overflowY) && el.scrollHeight > el.clientHeight + 2;
      }).length,
    };
  });
  await page.screenshot({ path: `/tmp/w8-panel-${w}.png` });
  out[w] = { clicked, before, after };
  await ctx.close();
}
await browser.close();
console.log(JSON.stringify(out, null, 1));
