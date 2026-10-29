import { chromium } from 'playwright';
import { mkdirSync } from 'node:fs';

const base = process.argv[2] || 'http://127.0.0.1:3002';
const out = process.argv[3] || '/tmp/dr-shots';
const routes = (process.argv[4] || '/,#harness,#execution-search,#execution-audit,#execution-rejected').split(',');
const viewports = [
  [1440, 900],
  [390, 844],
];

mkdirSync(out, { recursive: true });
const browser = await chromium.launch();
const errors = [];
for (const [w, h] of viewports) {
  const ctx = await browser.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  page.on('console', (m) => {
    if (m.type() === 'error') errors.push(`${w}x${h} ${m.text().slice(0, 120)}`);
  });
  for (const route of routes) {
    const url = `${base}/${route}`;
    await page.goto(url, { waitUntil: 'networkidle' });
    await page.waitForTimeout(600);
    const name = `${route.replace(/[^a-z0-9]+/gi, '_') || 'root'}_${w}x${h}.png`;
    await page.screenshot({ path: `${out}/${name}`, fullPage: false });
    console.log(`${out}/${name}`);
    if (route === '#execution-search' || route === '#execution-audit') {
      // estado expandido: mede accordion aberto
      const opened = await page.evaluate(() => {
        const btns = [...document.querySelectorAll('.tl-linha, .step-row, button[aria-expanded]')];
        const target = btns.find((b) => b.getAttribute('aria-expanded') === 'false');
        if (target) {
          target.click();
          return target.getAttribute('aria-controls') || target.className;
        }
        return null;
      });
      if (opened) {
        await page.waitForTimeout(400);
        await page.screenshot({ path: `${out}/${route.replace(/[^a-z0-9]+/gi, '_')}_expanded_${w}x${h}.png` });
        console.log(`expanded: ${opened}`);
      }
    }
  }
  await ctx.close();
}
await browser.close();
if (errors.length) console.log('CONSOLE ERRORS:\n' + [...new Set(errors)].join('\n'));
