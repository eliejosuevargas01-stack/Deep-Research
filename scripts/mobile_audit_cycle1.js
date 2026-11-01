const path = require('path');
const fs = require('fs');
const { chromium } = require(path.resolve(__dirname, '../frontend/node_modules/playwright'));

const CHROME_PATH = '/opt/data/projects/deep-research/Deep-Research/scripts/chrome_wrapper.sh';
const BASE_URL = 'http://127.0.0.1:3002';
const OUT_DIR = '/opt/data/projects/deep-research/Deep-Research/artifacts/audit-mobile';

fs.mkdirSync(OUT_DIR, { recursive: true });

const VIEWPORTS = [
  { name: '390x844', width: 390, height: 844, dpr: 2.0 },
  { name: '360x740', width: 360, height: 740, dpr: 2.0 },
];

const ROUTES = [
  { id: 'execution-search', hash: '#execution-search', name: 'Execução - Busca' },
  { id: 'research-sim', hash: '#research-sim', name: 'Simulação - Pesquisa' },
];

async function run() {
  const browser = await chromium.launch({
    executablePath: CHROME_PATH,
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  });

  const report = [];

  for (const vp of VIEWPORTS) {
    for (const route of ROUTES) {
      const context = await browser.newContext({
        viewport: { width: vp.width, height: vp.height },
        deviceScaleFactor: vp.dpr,
        isMobile: true,
        hasTouch: true,
      });

      const page = await context.newPage();
      const url = `${BASE_URL}/${route.hash}`;
      console.log(`Navigating to ${url} at ${vp.name}...`);
      await page.goto(url, { waitUntil: 'networkidle', timeout: 15000 });
      await page.waitForTimeout(1000);

      // Measure metrics
      const metrics = await page.evaluate(() => {
        const doc = document.documentElement;
        const body = document.body;
        const pageScrollable = doc.scrollHeight > window.innerHeight;
        const pageOverflowX = doc.scrollWidth > window.innerWidth;

        // Check horizontal overflow of all elements
        const overflowElements = [];
        const allElements = Array.from(document.querySelectorAll('*'));
        for (const el of allElements) {
          if (el.scrollWidth > el.clientWidth + 1) {
            const style = window.getComputedStyle(el);
            const isVisible = el.offsetParent !== null || style.position === 'fixed';
            if (isVisible && style.overflowX !== 'auto' && style.overflowX !== 'scroll' && style.overflowX !== 'hidden') {
              const rect = el.getBoundingClientRect();
              overflowElements.push({
                tag: el.tagName.toLowerCase(),
                className: (el.className || '').toString().slice(0, 80),
                scrollWidth: el.scrollWidth,
                clientWidth: el.clientWidth,
                rect: { x: Math.round(rect.x), y: Math.round(rect.y), width: Math.round(rect.width), height: Math.round(rect.height) },
                textSnippet: (el.textContent || '').trim().slice(0, 60),
              });
            }
          }
        }

        // Header metrics
        const headerEl = document.querySelector('.card-header.execution-heading-row');
        let headerMetrics = null;
        if (headerEl) {
          const rect = headerEl.getBoundingClientRect();
          const title = headerEl.querySelector('.execution-heading-title');
          const theme = headerEl.querySelector('.execution-theme-inline');
          const badge = headerEl.querySelector('.status-badge-chip');
          const elapsed = headerEl.querySelector('.execution-elapsed');
          headerMetrics = {
            rect: { width: Math.round(rect.width), height: Math.round(rect.height) },
            titleRect: title ? { width: Math.round(title.getBoundingClientRect().width), height: Math.round(title.getBoundingClientRect().height) } : null,
            themeRect: theme ? { width: Math.round(theme.getBoundingClientRect().width), height: Math.round(theme.getBoundingClientRect().height), isMultiLine: theme.scrollHeight > 24 } : null,
            badgeRect: badge ? { width: Math.round(badge.getBoundingClientRect().width), height: Math.round(badge.getBoundingClientRect().height) } : null,
            elapsedRect: elapsed ? { width: Math.round(elapsed.getBoundingClientRect().width), height: Math.round(elapsed.getBoundingClientRect().height) } : null,
          };
        }

        // Linear rail metrics
        const railNodes = Array.from(document.querySelectorAll('.tl-linear .tl-no'));
        const railMetrics = railNodes.map((no, idx) => {
          const rect = no.getBoundingClientRect();
          const trilho = no.querySelector('.tl-trilho');
          const trilhoRect = trilho ? trilho.getBoundingClientRect() : null;
          return {
            index: idx,
            height: Math.round(rect.height),
            trilhoHeight: trilhoRect ? Math.round(trilhoRect.height) : null,
          };
        });

        // Scrollers count
        const scrollContainers = [];
        for (const el of allElements) {
          const style = window.getComputedStyle(el);
          if ((style.overflowY === 'auto' || style.overflowY === 'scroll') && el.scrollHeight > el.clientHeight + 1) {
            scrollContainers.push({
              tag: el.tagName.toLowerCase(),
              className: (el.className || '').toString().slice(0, 80),
              scrollHeight: el.scrollHeight,
              clientHeight: el.clientHeight,
            });
          }
        }

        return {
          windowInnerWidth: window.innerWidth,
          windowInnerHeight: window.innerHeight,
          docScrollWidth: doc.scrollWidth,
          docScrollHeight: doc.scrollHeight,
          pageScrollable,
          pageOverflowX,
          overflowElementsCount: overflowElements.length,
          overflowElements: overflowElements.slice(0, 10),
          headerMetrics,
          railMetrics,
          scrollContainers,
        };
      });

      // Capture top screenshot
      const shotTopPath = path.join(OUT_DIR, `cycle1-${route.id}-${vp.name}-top.png`);
      await page.screenshot({ path: shotTopPath, fullPage: false });

      // Test scroll down
      await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight / 2));
      await page.waitForTimeout(300);
      const shotMidPath = path.join(OUT_DIR, `cycle1-${route.id}-${vp.name}-mid.png`);
      await page.screenshot({ path: shotMidPath, fullPage: false });

      // Scroll to bottom
      await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
      await page.waitForTimeout(300);
      const shotBottomPath = path.join(OUT_DIR, `cycle1-${route.id}-${vp.name}-bottom.png`);
      await page.screenshot({ path: shotBottomPath, fullPage: false });

      report.push({
        viewport: vp.name,
        route: route.id,
        metrics,
        screenshots: [shotTopPath, shotMidPath, shotBottomPath],
      });

      await context.close();
    }
  }

  await browser.close();
  fs.writeFileSync(path.join(OUT_DIR, 'cycle1-report.json'), JSON.stringify(report, null, 2));
  console.log('Cycle 1 run complete! Report written to cycle1-report.json');
  console.log(JSON.stringify(report, null, 2));
}

run().catch((err) => {
  console.error(err);
  process.exit(1);
});
