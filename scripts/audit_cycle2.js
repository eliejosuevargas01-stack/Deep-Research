const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

async function auditCycle2() {
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

    await page.goto('http://127.0.0.1:3003/#execution-search', { waitUntil: 'networkidle' });
    await page.waitForTimeout(600);

    // Expand all items
    const toggleBtn = page.locator('.tl-btn-toggle-all');
    await toggleBtn.click();
    await page.waitForTimeout(600);

    const data = await page.evaluate(() => {
      const wsMain = document.querySelector('.workspace-main');
      const rail = document.querySelector('.sidebar-container.rr-rail');
      const toolbarRow = document.querySelector('.tl-toolbar-row');
      const toggleAll = document.querySelector('.tl-btn-toggle-all');
      const headRow = document.querySelector('.execution-heading-row');
      const fontList = Array.from(document.querySelectorAll('.tl-fonte')).map(f => {
        const s = window.getComputedStyle(f);
        const icon = f.querySelector('.tl-fonte-icone');
        const dom = f.querySelector('.tl-fonte-dominio');
        const pag = f.querySelector('.tl-fonte-paginas');
        return {
          text: f.textContent.trim(),
          border: s.border,
          bg: s.backgroundColor,
          fontSize: s.fontSize,
          padding: s.padding,
          borderRadius: s.borderRadius,
          domText: dom?.textContent,
          pagText: pag?.textContent,
          hasIcon: !!icon,
          rect: f.getBoundingClientRect()
        };
      });

      const liveTags = Array.from(document.querySelectorAll('.tl-estado-vivo, .tl-live-pulse')).map(el => {
        const s = window.getComputedStyle(el);
        return {
          class: el.className,
          color: s.color,
          bg: s.backgroundColor,
          fontSize: s.fontSize,
          fontWeight: s.fontWeight,
          letterSpacing: s.letterSpacing
        };
      });

      const toolbarStyles = toolbarRow ? {
        padding: window.getComputedStyle(toolbarRow).padding,
        margin: window.getComputedStyle(toolbarRow).margin,
        gap: window.getComputedStyle(toolbarRow).gap,
        height: toolbarRow.getBoundingClientRect().height
      } : null;

      const toggleStyles = toggleAll ? {
        height: toggleAll.getBoundingClientRect().height,
        padding: window.getComputedStyle(toggleAll).padding,
        fontSize: window.getComputedStyle(toggleAll).fontSize,
        border: window.getComputedStyle(toggleAll).border,
        bg: window.getComputedStyle(toggleAll).backgroundColor,
        color: window.getComputedStyle(toggleAll).color
      } : null;

      const headerStyles = headRow ? {
        height: headRow.getBoundingClientRect().height,
        padding: window.getComputedStyle(headRow).padding,
        gap: window.getComputedStyle(headRow).gap
      } : null;

      return {
        fontCount: fontList.length,
        fontSample: fontList.slice(0, 4),
        liveTags,
        toolbarStyles,
        toggleStyles,
        headerStyles,
        wsMainHeight: wsMain ? {
          scrollHeight: wsMain.scrollHeight,
          clientHeight: wsMain.clientHeight,
          scrollTop: wsMain.scrollTop
        } : null,
        railPos: rail ? {
          rect: rail.getBoundingClientRect(),
          top: window.getComputedStyle(rail).top,
          position: window.getComputedStyle(rail).position
        } : null
      };
    });

    console.log(`\n=== Cycle 2 Audit [${vp.name}] ===`);
    console.log('Source tags sample:', JSON.stringify(data.fontSample, null, 2));
    console.log('Live tags:', JSON.stringify(data.liveTags, null, 2));
    console.log('Toolbar & Header styles:', JSON.stringify({
      toolbar: data.toolbarStyles,
      toggle: data.toggleStyles,
      header: data.headerStyles
    }, null, 2));
    console.log('Main scroll height vs client height:', data.wsMainHeight);
    console.log('Rail position:', data.railPos);

    // Deep scroll test: scroll down to 600px and 1200px
    await page.evaluate(() => {
      const wsMain = document.querySelector('.workspace-main');
      if (wsMain) wsMain.scrollTop = 600;
    });
    await page.waitForTimeout(400);
    await page.screenshot({ path: path.join(outDir, `c2-deep-scroll-600-${vp.name}.png`) });

    await page.evaluate(() => {
      const wsMain = document.querySelector('.workspace-main');
      if (wsMain) wsMain.scrollTop = wsMain.scrollHeight;
    });
    await page.waitForTimeout(400);
    await page.screenshot({ path: path.join(outDir, `c2-deep-scroll-bottom-${vp.name}.png`) });

    // Also test simulated live research
    await page.goto('http://127.0.0.1:3003/#research-sim', { waitUntil: 'networkidle' });
    await page.waitForTimeout(3500);
    await page.screenshot({ path: path.join(outDir, `c2-sim-live-${vp.name}.png`) });

    await page.close();
  }

  await browser.close();
}

auditCycle2().catch(e => {
  console.error(e);
  process.exit(1);
});
