const path = require('path');
const fs = require('fs');
const { chromium } = require(path.resolve(__dirname, '../frontend/node_modules/playwright'));

const CHROME_PATH = '/opt/data/projects/deep-research/Deep-Research-wt-mobile-exec/scripts/chrome_wrapper.sh';
const BASE_URL = 'http://127.0.0.1:3002';
const OUT_DIR = '/opt/data/projects/deep-research/Deep-Research-wt-mobile-exec/artifacts/audit-mobile';

fs.mkdirSync(OUT_DIR, { recursive: true });

const VIEWPORTS = [
  { name: '390x844', width: 390, height: 844, dpr: 2.0 },
  { name: '360x740', width: 360, height: 740, dpr: 2.0 },
];

const ROUTES = [
  { id: 'execution-audit', hash: '#execution-audit', name: 'Execução - Auditoria' },
  { id: 'execution-rejected', hash: '#execution-rejected', name: 'Execução - Reprovada' },
  { id: 'execution-failed', hash: '#execution-failed', name: 'Execução - Falha' },
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
      console.log(`[Ciclo 3] Navigating to ${url} at ${vp.name}...`);
      await page.goto(url, { waitUntil: 'networkidle', timeout: 15000 });
      await page.waitForTimeout(500);

      // Expand all nodes if present
      const toggleBtn = page.locator('.tl-btn-toggle-all');
      if (await toggleBtn.count()) {
        await toggleBtn.click();
        await page.waitForTimeout(500);
      }

      const audit = await page.evaluate((rId) => {
        const doc = document.documentElement;
        const pageOverflowX = doc.scrollWidth > window.innerWidth;

        // Banner evaluation
        const banner = document.querySelector('.exec-error-card, .alert-banner.danger');
        let bannerInfo = null;
        if (banner) {
          const rect = banner.getBoundingClientRect();
          const title = banner.querySelector('strong, .error-notice__title');
          const copy = banner.querySelector('.execution-banner-copy, .error-notice__message');
          const pills = Array.from(banner.querySelectorAll('.gdr-criteria-pill')).map(p => ({
            text: p.textContent.trim(),
            width: Math.round(p.getBoundingClientRect().width),
            height: Math.round(p.getBoundingClientRect().height),
          }));
          const buttons = Array.from(banner.querySelectorAll('button')).map(b => ({
            text: b.textContent.trim(),
            width: Math.round(b.getBoundingClientRect().width),
            height: Math.round(b.getBoundingClientRect().height),
            meets44px: b.getBoundingClientRect().height >= 44,
          }));

          bannerInfo = {
            visible: rect.width > 0 && rect.height > 0,
            rect: { width: Math.round(rect.width), height: Math.round(rect.height) },
            titleText: title ? title.textContent.trim() : null,
            copyText: copy ? copy.textContent.trim() : null,
            pillsCount: pills.length,
            pillsSample: pills.slice(0, 4),
            buttons,
          };
        }

        // Auditor criteria evaluation
        const callouts = Array.from(document.querySelectorAll('.tl-detalhe, .tl-callout'));
        const calloutInfos = callouts.map(c => {
          const rect = c.getBoundingClientRect();
          const score = c.querySelector('.tl-callout-score');
          const status = c.querySelector('.tl-callout-status');
          const criteria = Array.from(c.querySelectorAll('.tl-criterio')).map(cr => ({
            text: cr.textContent.trim().slice(0, 60),
            rect: { width: Math.round(cr.getBoundingClientRect().width), height: Math.round(cr.getBoundingClientRect().height) },
          }));
          return {
            rect: { width: Math.round(rect.width), height: Math.round(rect.height) },
            scoreText: score ? score.textContent.trim() : null,
            statusText: status ? status.textContent.trim() : null,
            criteriaCount: criteria.length,
            criteria,
          };
        });

        // Overflow check
        const overflows = [];
        for (const el of document.querySelectorAll('*')) {
          if (el.scrollWidth > el.clientWidth + 1) {
            const s = window.getComputedStyle(el);
            if (s.overflowX !== 'auto' && s.overflowX !== 'scroll' && s.overflowX !== 'hidden') {
              overflows.push({
                tag: el.tagName.toLowerCase(),
                className: (el.className || '').toString().slice(0, 50),
                diff: el.scrollWidth - el.clientWidth,
              });
            }
          }
        }

        return {
          windowWidth: window.innerWidth,
          docScrollWidth: doc.scrollWidth,
          pageOverflowX,
          overflowsCount: overflows.length,
          overflows: overflows.slice(0, 5),
          bannerInfo,
          calloutsCount: calloutInfos.length,
          calloutInfos: calloutInfos.slice(0, 3),
        };
      }, route.id);

      // Screenshot top
      const shotTopPath = path.join(OUT_DIR, `cycle3-${route.id}-${vp.name}-top.png`);
      await page.screenshot({ path: shotTopPath, fullPage: false });

      // Screenshot scrolled
      await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight / 2));
      await page.waitForTimeout(300);
      const shotMidPath = path.join(OUT_DIR, `cycle3-${route.id}-${vp.name}-mid.png`);
      await page.screenshot({ path: shotMidPath, fullPage: false });

      // Screenshot bottom
      await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
      await page.waitForTimeout(300);
      const shotBottomPath = path.join(OUT_DIR, `cycle3-${route.id}-${vp.name}-bottom.png`);
      await page.screenshot({ path: shotBottomPath, fullPage: false });

      report.push({
        viewport: vp.name,
        route: route.id,
        audit,
        screenshots: [shotTopPath, shotMidPath, shotBottomPath],
      });

      await context.close();
    }
  }

  await browser.close();
  fs.writeFileSync(path.join(OUT_DIR, 'cycle3-report.json'), JSON.stringify(report, null, 2));
  console.log('[Ciclo 3] Run complete! Report written to cycle3-report.json');
  console.log(JSON.stringify(report, null, 2));
}

run().catch((err) => {
  console.error(err);
  process.exit(1);
});
