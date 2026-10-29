import { chromium } from 'playwright';
import { writeFileSync } from 'node:fs';

/**
 * Portão estrutural da paridade GDR (rodada 3).
 * Mede os alvos D1–D4 do docs/audit/parity-plan-r3.md em números.
 * Uso: node scripts/audit/structural-gate.mjs http://127.0.0.1:3002 [out.json]
 */
const base = process.argv[2] || 'http://127.0.0.1:3002';
const outPath = process.argv[3] || null;

const browser = await chromium.launch();
const results = {};

async function open(url, width, height) {
  const ctx = await browser.newContext({ viewport: { width, height }, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  await page.goto(url, { waitUntil: 'networkidle' });
  await page.waitForTimeout(500);
  return { ctx, page };
}

// ---------- D1 rail / D2 rows na rota de execução ----------
for (const [w, h] of [[1440, 900], [390, 844]]) {
  const { ctx, page } = await open(`${base}/#execution-search`, w, h);
  const d1d2 = await page.evaluate(() => {
    const isVisible = (el) => {
      if (!el) return false;
      const r = el.getBoundingClientRect();
      const cs = getComputedStyle(el);
      return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none';
    };
    const rail = document.querySelector('.context-sidebar, .right-rail');
    const tabs = [...document.querySelectorAll('[role="tab"]')].filter(isVisible);
    const panels = [...document.querySelectorAll('[role="tabpanel"]')].filter(isVisible);
    const tokenEls = [...document.querySelectorAll('.rr-rail__tokens, .token-usage-meter, [data-rail-tokens]')].filter(isVisible);
    const strip = tokenEls.map((el) => el.getBoundingClientRect()).sort((a, b) => b.height - a.height)[0];
    const rows = [...document.querySelectorAll('.tl-entrada')].filter(isVisible);
    const rowHeights = rows.map((r) => Math.round(r.getBoundingClientRect().height));
    const isOpenRow = (r) => Boolean(r.querySelector('[aria-expanded="true"]'));
    const closedRows = rows.filter((r) => !isOpenRow(r));
    const timeInClosed = closedRows.filter((r) => {
      const t = r.querySelector('time');
      return t && isVisible(t);
    }).length;
    const pillInClosed = closedRows.filter((r) => {
      const p = r.querySelector('.tl-pill');
      return p && isVisible(p);
    }).length;
    let pseudoArrows = 0;
    for (const el of document.querySelectorAll('.tl-entrada, .tl-entrada *')) {
      const c = getComputedStyle(el, '::after').content;
      if (c && /→|›|»/.test(c)) pseudoArrows += 1;
    }
    return {
      railWidth: rail ? Math.round(rail.getBoundingClientRect().width) : 0,
      railVisible: rail ? isVisible(rail) : false,
      tabs: tabs.map((t) => (t.textContent || '').trim().replace(/\s+/g, ' ')),
      tabsAria: tabs.map((t) => t.getAttribute('aria-selected')),
      visiblePanels: panels.length,
      tokenStripHeight: strip ? Math.round(strip.height) : 0,
      rowCount: rows.length,
      closedRows: closedRows.length,
      rowHeights,
      closedRowTimeVisible: timeInClosed,
      closedRowPillVisible: pillInClosed,
      pseudoArrowNodes: pseudoArrows,
      docScrollW: document.documentElement.scrollWidth,
      docClientW: document.documentElement.clientWidth,
    };
  });
  results[`execution_${w}x${h}`] = d1d2;
  await ctx.close();
}

// ---------- D3 composer + D4 sidebar na raiz ----------
for (const [w, h] of [[1440, 900], [390, 844]]) {
  const { ctx, page } = await open(`${base}/`, w, h);

  // Semeia o histórico na chave real do serviço (lida em runtime) e recarrega.
  const seedInfo = await page.evaluate(() => {
    const agora = Date.now();
    const registros = [1, 2, 3].map((n) => ({
      id_pesquisa: `seed-${n}`,
      tema: `Pesquisa semeada ${n}: automação bancária e emprego formal`,
      criado_em: new Date(agora - n * 3600_000).toISOString(),
      status: n === 1 ? 'concluido' : 'buscando',
      planResponse: {
        id_pesquisa: `seed-${n}`,
        tema: `Pesquisa semeada ${n}: automação bancária e emprego formal`,
        n_pontos: 1,
        criado_em: new Date(agora - n * 3600_000).toISOString(),
        status_pipeline: n === 1 ? 'concluido' : 'buscando',
        preferencias: { n_pontos: 1, personas: ['historiador'] },
        pontos: [],
      },
    }));
    const chaves = Object.keys(localStorage);
    const key = 'deep_research_local_history_v1';
    localStorage.setItem(key, JSON.stringify(registros));
    return { chaves, key };
  });
  if (seedInfo.key) {
    await page.reload({ waitUntil: 'networkidle' });
    await page.waitForTimeout(500);
  }

  const d3d4 = await page.evaluate((key) => {
    const isVisible = (el) => {
      if (!el) return false;
      const r = el.getBoundingClientRect();
      const cs = getComputedStyle(el);
      return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none';
    };
    const ta = document.querySelector('textarea.composer-input, .composer-input');
    const taRect = ta ? ta.getBoundingClientRect() : null;
    const dockBars = [...document.querySelectorAll('.dock-bar')].filter(isVisible);
    const dockInside = dockBars.filter((b) => b.closest('.composer-anchor, .composer-box')).length;
    const slot = document.querySelector('[data-composer-tools]');
    const legal = [...document.querySelectorAll('.composer-legal')].filter(isVisible)[0];
    const conv = [...document.querySelectorAll('.sidebar-conversation')].filter(isVisible);
    const active = [...document.querySelectorAll('[aria-current="page"]')].filter(isVisible).length;
    const footerNote = [...document.querySelectorAll('.sidebar-footer-note')].filter(isVisible).length;
    const statusStrip = [...document.querySelectorAll('.composer-meta, .composer-toolbar')].filter((el) =>
      /ponto|persona|rigor/i.test(el.textContent || '')
    ).length;
    return {
      textareaY: taRect ? Math.round(taRect.y) : null,
      innerHeight: window.innerHeight,
      textareaInFirstViewport: taRect ? taRect.y + taRect.height <= window.innerHeight : null,
      dockBarsVisible: dockBars.length,
      dockBarsInsideComposer: dockInside,
      composerToolsSlot: Boolean(slot),
      legalFootnote: Boolean(legal),
      statusStripWithCounts: statusStrip,
      sidebarConversations: conv.length,
      sidebarActive: active,
      footerDataTypeNote: footerNote,
      storageKeyUsed: key,
      docScrollW: document.documentElement.scrollWidth,
      docClientW: document.documentElement.clientWidth,
    };
  }, seedInfo.key);
  results[`root_${w}x${h}`] = d3d4;
  await ctx.close();
}

await browser.close();
const report = { base, capturedAt: new Date().toISOString(), results };
const text = JSON.stringify(report, null, 2);
if (outPath) writeFileSync(outPath, text);
console.log(text);
