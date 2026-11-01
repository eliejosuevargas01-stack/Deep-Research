const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

async function auditCycle3() {
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

    await page.goto('http://127.0.0.1:3003/#execution-audit', { waitUntil: 'networkidle' });
    await page.waitForTimeout(600);

    // Expand all items to inspect the auditor callouts & actions
    const toggleBtn = page.locator('.tl-btn-toggle-all');
    if (await toggleBtn.count() > 0) {
      await toggleBtn.click();
      await page.waitForTimeout(500);
    }

    // Ensure action buttons exist in the reprovado step to test their layout and focus ring
    await page.evaluate(() => {
      const bodies = Array.from(document.querySelectorAll('.tl-entrada-corpo'));
      // Find body with callout reprovado
      for (const body of bodies) {
        if (body.querySelector('.tl-callout-status.reprovado') && !body.querySelector('.tl-acoes')) {
          const acoes = document.createElement('div');
          acoes.className = 'tl-acoes';
          const btn1 = document.createElement('button');
          btn1.type = 'button';
          btn1.className = 'tl-acao tl-btn-test-busca';
          btn1.setAttribute('aria-label', 'Refazer busca do ponto 2');
          btn1.textContent = 'refazer busca';
          const btn2 = document.createElement('button');
          btn2.type = 'button';
          btn2.className = 'tl-acao tl-btn-test-audit';
          btn2.setAttribute('aria-label', 'Reauditar ponto 2');
          btn2.textContent = 'reauditar';
          acoes.appendChild(btn1);
          acoes.appendChild(btn2);
          body.appendChild(acoes);
        }
      }
    });

    const auditData = await page.evaluate(() => {
      const callouts = Array.from(document.querySelectorAll('.tl-callout, .tl-detalhe')).map(c => {
        const s = window.getComputedStyle(c);
        const score = c.querySelector('.tl-callout-score strong');
        const status = c.querySelector('.tl-callout-status');
        const statusStyle = status ? window.getComputedStyle(status) : null;
        const criterios = Array.from(c.querySelectorAll('.tl-criterio')).map(cr => ({
          text: cr.textContent.trim(),
          color: window.getComputedStyle(cr).color,
          fontSize: window.getComputedStyle(cr).fontSize
        }));

        return {
          bg: s.backgroundColor,
          border: s.border,
          borderRadius: s.borderRadius,
          padding: s.padding,
          maxWidth: s.maxWidth,
          scoreValue: score?.textContent.trim(),
          statusText: status?.textContent.trim(),
          statusColor: statusStyle?.color,
          statusBg: statusStyle?.backgroundColor,
          statusBorder: statusStyle?.border,
          criteriosCount: criterios.length
        };
      });

      const actionButtons = Array.from(document.querySelectorAll('.tl-acao')).map(btn => {
        const s = window.getComputedStyle(btn);
        return {
          text: btn.textContent.trim(),
          rect: btn.getBoundingClientRect(),
          height: btn.getBoundingClientRect().height,
          padding: s.padding,
          border: s.border,
          color: s.color,
          bg: s.backgroundColor,
          borderRadius: s.borderRadius
        };
      });

      const railNodes = Array.from(document.querySelectorAll('.tl-no')).map((no, idx) => {
        const trilho = no.querySelector('.tl-trilho');
        const beforeStyle = window.getComputedStyle(trilho, '::before');
        return {
          index: idx,
          isUltimo: no.classList.contains('ultimo'),
          isLastChild: no.matches(':last-child'),
          railDisplay: beforeStyle.display,
          trilhoRect: trilho ? trilho.getBoundingClientRect() : null
        };
      });

      return {
        callouts,
        actionButtons,
        railNodes
      };
    });

    console.log(`\n=== Cycle 3 Audit (#execution-audit) [${vp.name}] ===`);
    console.log('Callouts:', JSON.stringify(auditData.callouts, null, 2));
    console.log('Action Buttons:', JSON.stringify(auditData.actionButtons, null, 2));
    console.log('Rail nodes display & bounds:', JSON.stringify(auditData.railNodes, null, 2));

    await page.screenshot({ path: path.join(outDir, `c3-audit-${vp.name}-expanded.png`) });

    // Focus first action button
    const actionBtn = page.locator('.tl-btn-test-busca');
    if (await actionBtn.count() > 0) {
      await actionBtn.focus();
      await page.waitForTimeout(200);

      const focusRing = await page.evaluate(() => {
        const active = document.activeElement;
        const s = active ? window.getComputedStyle(active) : null;
        return {
          tag: active?.tagName,
          text: active?.textContent.trim(),
          outline: s?.outline,
          outlineOffset: s?.outlineOffset,
          zIndex: s?.zIndex
        };
      });
      console.log('Action Button Focus Ring:', focusRing);
      await page.screenshot({ path: path.join(outDir, `c3-audit-${vp.name}-focused.png`) });
    }

    await page.close();
  }

  await browser.close();
}

auditCycle3().catch(e => {
  console.error(e);
  process.exit(1);
});
