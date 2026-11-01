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
  { id: 'execution-audit', hash: '#execution-audit', name: 'Execução - Auditoria' },
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
      console.log(`[Ciclo 2] Navigating to ${url} at ${vp.name}...`);
      await page.goto(url, { waitUntil: 'networkidle', timeout: 15000 });
      await page.waitForTimeout(500);

      // Expand all nodes
      const toggleBtn = page.locator('.tl-btn-toggle-all');
      if (await toggleBtn.count()) {
        await toggleBtn.click();
        await page.waitForTimeout(600);
      }

      // Measure touch targets & bottom clearance
      const audit = await page.evaluate(() => {
        const tabbar = document.querySelector('.mobile-tabbar');
        const tabRect = tabbar ? tabbar.getBoundingClientRect() : null;

        // Check touch targets
        const targets = [];
        const interactiveSelectors = [
          '.tl-btn-toggle-all',
          'button.tl-entrada-linha',
          '.tl-acao',
          '.btn-secondary',
          '.btn-compact',
          '.ponto-acao',
          '.execution-banner-actions button'
        ];

        for (const sel of interactiveSelectors) {
          const els = Array.from(document.querySelectorAll(sel));
          for (const el of els) {
            const rect = el.getBoundingClientRect();
            const isVisible = rect.width > 0 && rect.height > 0 && el.offsetParent !== null;
            if (isVisible) {
              const meetsFloor = rect.width >= 44 && rect.height >= 44;
              targets.push({
                selector: sel,
                text: (el.textContent || '').trim().slice(0, 30),
                width: Math.round(rect.width),
                height: Math.round(rect.height),
                meets44px: meetsFloor,
              });
            }
          }
        }

        // Measure scroller and bottom clearance
        const doc = document.documentElement;
        window.scrollTo(0, doc.scrollHeight);

        const allContent = Array.from(document.querySelectorAll('.tl-no, .execution-card, .alert-banner, .btn-secondary, .tl-acao, .tl-entrada-corpo, .tl-detalhe'));
        let maxBottom = 0;
        let lowestElement = null;
        for (const el of allContent) {
          const r = el.getBoundingClientRect();
          if (r.bottom > maxBottom) {
            maxBottom = r.bottom;
            lowestElement = {
              tag: el.tagName.toLowerCase(),
              className: (el.className || '').toString().slice(0, 50),
              bottom: Math.round(r.bottom),
            };
          }
        }

        const clearance = tabRect ? Math.round(tabRect.top - maxBottom) : null;
        const isOverlappingDock = tabRect ? (maxBottom > tabRect.top) : false;

        return {
          windowHeight: window.innerHeight,
          docScrollHeight: doc.scrollHeight,
          tabbar: tabRect ? { top: Math.round(tabRect.top), height: Math.round(tabRect.height) } : null,
          lowestElement,
          clearance,
          isOverlappingDock,
          touchTargetsSummary: {
            totalChecked: targets.length,
            failingCount: targets.filter(t => !t.meets44px).length,
            failingTargets: targets.filter(t => !t.meets44px),
            passingCount: targets.filter(t => t.meets44px).length,
          }
        };
      });

      // Capture screenshots
      const shotTopPath = path.join(OUT_DIR, `cycle2-${route.id}-${vp.name}-expanded-top.png`);
      await page.screenshot({ path: shotTopPath, fullPage: false });

      // Scroll to bottom and capture
      await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
      await page.waitForTimeout(400);
      const shotBottomPath = path.join(OUT_DIR, `cycle2-${route.id}-${vp.name}-expanded-bottom.png`);
      await page.screenshot({ path: shotBottomPath, fullPage: false });

      report.push({
        viewport: vp.name,
        route: route.id,
        audit,
        screenshots: [shotTopPath, shotBottomPath]
      });

      await context.close();
    }
  }

  await browser.close();
  fs.writeFileSync(path.join(OUT_DIR, 'cycle2-report.json'), JSON.stringify(report, null, 2));
  console.log('[Ciclo 2] Run complete! Report written to cycle2-report.json');
  console.log(JSON.stringify(report, null, 2));
}

run().catch((err) => {
  console.error(err);
  process.exit(1);
});
