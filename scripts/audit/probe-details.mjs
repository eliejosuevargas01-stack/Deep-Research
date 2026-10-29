import { chromium } from 'playwright';

const base = process.argv[2] || 'http://127.0.0.1:3002';
const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();

await page.goto(`${base}/#execution-search`, { waitUntil: 'networkidle' });
await page.waitForTimeout(400);

const exec = await page.evaluate(() => {
  const r = (sel, i = 0) => {
    const el = document.querySelectorAll(sel)[i];
    if (!el) return null;
    const b = el.getBoundingClientRect();
    return { x: Math.round(b.x), y: Math.round(b.y), w: Math.round(b.width), h: Math.round(b.height), text: (el.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 60) };
  };
  const rail = document.querySelector('.context-sidebar');
  const rb = rail.getBoundingClientRect();
  const children = [...rail.querySelectorAll(':scope > *')].map((el) => ({
    cls: (el.className || '').toString().slice(0, 40),
    h: Math.round(el.getBoundingClientRect().height),
  }));
  const last = rail.lastElementChild;
  const lb = last.getBoundingClientRect();
  const stage = document.querySelector('.tl-grupo-tema');
  return {
    rail: { y: Math.round(rb.y), h: Math.round(rb.height), w: Math.round(rb.width) },
    railChildren: children,
    railBottomGap: Math.round(rb.bottom - lb.bottom),
    stageLabelFont: stage ? getComputedStyle(stage).fontSize : null,
    stageLabelText: stage ? stage.textContent.trim().slice(0, 60) : null,
    tokenTotal: r('.rr-tokens__total'),
    tokenModel: r('.rr-tokens__model'),
    firstRow: r('.tl-entrada'),
    firstRowLine: r('.tl-entrada-linha'),
    textSpan: r('.tl-texto'),
    headerStage: r('.execution-stage-line, .execution-header, h1'),
    titleTrunc: [...document.querySelectorAll('.rr-rail__title, .tl-grupo-tema, .rr-source__title')].map((el) => ({
      cls: (el.className || '').toString().slice(0, 30),
      sw: el.scrollWidth,
      cw: el.clientWidth,
      truncated: el.scrollWidth > el.clientWidth + 1,
    })),
  };
});
console.log('EXEC', JSON.stringify(exec, null, 1));

await page.goto(`${base}/`, { waitUntil: 'networkidle' });
await page.waitForTimeout(300);
const root = await page.evaluate(() => {
  const box = (sel) => {
    const el = document.querySelector(sel);
    if (!el) return null;
    const b = el.getBoundingClientRect();
    return { x: Math.round(b.x), y: Math.round(b.y), w: Math.round(b.width), h: Math.round(b.height), right: Math.round(b.right) };
  };
  const composer = box('.composer-box');
  const counter = box('.composer-counter');
  const textarea = box('.composer-input');
  const legal = box('.composer-legal');
  const anchor = box('.composer-anchor');
  return {
    composer,
    counter,
    counterInside: composer && counter ? counter.right <= composer.right && counter.x >= composer.x : null,
    textarea,
    legal,
    anchor,
    gapBoxToLegal: composer && legal ? Math.round(legal.y - (composer.y + composer.height)) : null,
    counterFont: document.querySelector('.composer-counter') ? getComputedStyle(document.querySelector('.composer-counter')).fontSize : null,
  };
});
console.log('ROOT', JSON.stringify(root, null, 1));
await browser.close();
