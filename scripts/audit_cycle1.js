const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

async function auditCycle1() {
  const browser = await chromium.launch({
    executablePath: '/opt/data/projects/deep-research/Deep-Research-wt-desktop-exec/scripts/chrome_wrapper.sh',
    headless: true
  });

  const outDir = '/opt/data/projects/deep-research/Deep-Research-wt-desktop-exec/artifacts/audit-desktop';
  fs.mkdirSync(outDir, { recursive: true });

  const viewports = [
    { width: 1440, height: 900, name: '1440x900' },
    { width: 1280, height: 720, name: '1280x720' }
  ];

  for (const vp of viewports) {
    const page = await browser.newPage({ viewport: { width: vp.width, height: vp.height } });

    // 1. Audit #execution-search
    await page.goto('http://127.0.0.1:3003/#execution-search', { waitUntil: 'networkidle' });
    await page.waitForTimeout(500);

    const dataSearch = await page.evaluate(() => {
      const wsMain = document.querySelector('.workspace-main');
      const wsGrid = document.querySelector('.workspace-grid');
      const execCard = document.querySelector('.execution-card');
      const rail = document.querySelector('.sidebar-container.rr-rail');
      const timeline = document.querySelector('.tl-linear');
      const queryLines = Array.from(document.querySelectorAll('.tl-query-line'));
      const toolbarRow = document.querySelector('.tl-toolbar-row');
      const toggleAllBtn = document.querySelector('.tl-btn-toggle-all');

      // Scroll containers check
      const allElements = Array.from(document.querySelectorAll('*'));
      const scrollers = allElements.filter(el => {
        const style = window.getComputedStyle(el);
        const ovY = style.overflowY;
        return (ovY === 'auto' || ovY === 'scroll') && el.scrollHeight > el.clientHeight;
      }).map(el => ({
        tag: el.tagName,
        className: el.className,
        id: el.id,
        scrollHeight: el.scrollHeight,
        clientHeight: el.clientHeight,
        overflowY: window.getComputedStyle(el).overflowY
      }));

      // Check workspace styles
      const wsMainStyle = wsMain ? window.getComputedStyle(wsMain) : null;
      const wsGridStyle = wsGrid ? window.getComputedStyle(wsGrid) : null;
      const railStyle = rail ? window.getComputedStyle(rail) : null;
      const execCardStyle = execCard ? window.getComputedStyle(execCard) : null;

      // Expand first item to inspect queries & reasoning
      return {
        scrollers,
        docScrollHeight: document.documentElement.scrollHeight,
        docClientHeight: document.documentElement.clientHeight,
        wsMainScroll: wsMain ? {
          scrollHeight: wsMain.scrollHeight,
          clientHeight: wsMain.clientHeight,
          overflowY: wsMainStyle?.overflowY,
          scrollBehavior: wsMainStyle?.scrollBehavior,
          padding: wsMainStyle?.padding
        } : null,
        grid: wsGridStyle ? {
          display: wsGridStyle.display,
          gridTemplateColumns: wsGridStyle.gridTemplateColumns,
          gap: wsGridStyle.gap
        } : null,
        rects: {
          execCard: execCard ? execCard.getBoundingClientRect() : null,
          rail: rail ? rail.getBoundingClientRect() : null
        },
        queriesCount: queryLines.length,
        hasToggleAll: !!toggleAllBtn
      };
    });

    console.log(`\n=== Cycle 1 Audit (#execution-search) [${vp.name}] ===`);
    console.log('Scrollers detected:', JSON.stringify(dataSearch.scrollers, null, 2));
    console.log('wsMain scroll info:', JSON.stringify(dataSearch.wsMainScroll, null, 2));
    console.log('Grid info:', JSON.stringify(dataSearch.grid, null, 2));
    console.log('Rects:', JSON.stringify(dataSearch.rects, null, 2));

    await page.screenshot({ path: path.join(outDir, `c1-search-${vp.name}-initial.png`), fullPage: false });

    // Click "Expandir todos os raciocínios"
    const toggleBtn = page.locator('.tl-btn-toggle-all');
    if (await toggleBtn.count() > 0) {
      await toggleBtn.click();
      await page.waitForTimeout(400);

      const expandedData = await page.evaluate(() => {
        const queryLines = Array.from(document.querySelectorAll('.tl-query-line')).map(q => ({
          text: q.textContent,
          computed: {
            fontFamily: window.getComputedStyle(q).fontFamily,
            fontSize: window.getComputedStyle(q).fontSize,
            lineHeight: window.getComputedStyle(q).lineHeight,
            padding: window.getComputedStyle(q).padding,
            background: window.getComputedStyle(q).backgroundColor,
            color: window.getComputedStyle(q).color
          },
          rect: q.getBoundingClientRect()
        }));

        const reasoningMarkdown = Array.from(document.querySelectorAll('.tl-entrada-corpo .markdown-content, .tl-reasoning-corpo, .tl-analise')).map(r => ({
          tag: r.tagName,
          className: r.className,
          computed: {
            fontSize: window.getComputedStyle(r).fontSize,
            lineHeight: window.getComputedStyle(r).lineHeight,
            maxWidth: window.getComputedStyle(r).maxWidth,
            color: window.getComputedStyle(r).color
          },
          rect: r.getBoundingClientRect()
        }));

        const corpo = Array.from(document.querySelectorAll('.tl-entrada-corpo:not([hidden])')).map(c => ({
          padding: window.getComputedStyle(c).padding,
          rect: c.getBoundingClientRect()
        }));

        return { queryLines: queryLines.slice(0, 3), reasoningMarkdown: reasoningMarkdown.slice(0, 3), corpo: corpo.slice(0, 2) };
      });

      console.log('Expanded Query Lines sample:', JSON.stringify(expandedData.queryLines, null, 2));
      console.log('Expanded Reasoning Markdown sample:', JSON.stringify(expandedData.reasoningMarkdown, null, 2));
      console.log('Expanded Corpo padding:', JSON.stringify(expandedData.corpo, null, 2));

      await page.screenshot({ path: path.join(outDir, `c1-search-${vp.name}-expanded.png`), fullPage: false });

      // Test scroll on workspace-main
      await page.evaluate(() => {
        const wsMain = document.querySelector('.workspace-main');
        if (wsMain) wsMain.scrollTop = 400;
        else window.scrollTo(0, 400);
      });
      await page.waitForTimeout(300);
      await page.screenshot({ path: path.join(outDir, `c1-search-${vp.name}-scrolled.png`), fullPage: false });
    }

    // 2. Audit #research-sim
    await page.goto('http://127.0.0.1:3003/#research-sim', { waitUntil: 'networkidle' });
    await page.waitForTimeout(2000); // Wait for live simulation to advance
    await page.screenshot({ path: path.join(outDir, `c1-sim-${vp.name}.png`), fullPage: false });

    await page.close();
  }

  await browser.close();
}

auditCycle1().catch(err => {
  console.error(err);
  process.exit(1);
});
