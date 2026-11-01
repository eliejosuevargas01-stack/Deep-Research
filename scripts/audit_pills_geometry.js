#!/usr/bin/env node
/**
 * scripts/audit_pills_geometry.js
 * Auditoria e medição geométrica das 7 pílulas de personas do Hero (Playwright).
 *
 * Validações:
 * a) Alinhamento de centro: |(rect.left + rect.width / 2) - (text.left + text.width / 2)| < 1.0 px
 * b) Zero overflow / respiro interno: rect.width >= text.width + 12 px
 * c) Respiro entre vizinhos: gap = nextRect.left - prevRect.right >= 6 px para pares:
 *    - Historiador -> Visionário
 *    - Visionário -> Futurista
 *    - Futurista -> Cético
 * d) Alinhamento horizontal: diferença de Y entre as pílulas < 2.0 px
 *
 * Evidências visuais geradas:
 * - artifacts/audit-mobile-impeccable-2026-10-31/shots/38a-hero-pills-desktop.png (1440x900)
 * - artifacts/audit-mobile-impeccable-2026-10-31/shots/38b-hero-pills-mobile.png (390x844)
 */

const fs = require('fs');
const path = require('path');

let playwright;
try {
  playwright = require('playwright');
} catch (e) {
  playwright = require(path.resolve(__dirname, '../frontend/node_modules/playwright'));
}
const { chromium } = playwright;

const CHROME_PATH = '/opt/data/projects/deep-research/Deep-Research/scripts/chrome_wrapper.sh';
const TARGET_URL = process.env.TARGET_URL || 'http://127.0.0.1:3002/#research';

const REL_OUT_DIR = path.resolve(__dirname, '../artifacts/audit-mobile-impeccable-2026-10-31/shots');
const ABS_OUT_DIR = '/opt/data/projects/deep-research/Deep-Research/artifacts/audit-mobile-impeccable-2026-10-31/shots';

const PERSONAS = [
  'Planejador',
  'Historiador',
  'Visionário',
  'Futurista',
  'Cético',
  'Auditor',
  'Redator',
];

const ADJACENT_PAIRS = [
  ['Historiador', 'Visionário'],
  ['Visionário', 'Futurista'],
  ['Futurista', 'Cético'],
];

function saveScreenshot(sourceBuffer, filename) {
  for (const dir of [REL_OUT_DIR, ABS_OUT_DIR]) {
    try {
      fs.mkdirSync(dir, { recursive: true });
      fs.writeFileSync(path.join(dir, filename), sourceBuffer);
      console.log(`[CAPTURA] Salvo: ${path.join(dir, filename)}`);
    } catch (err) {
      console.warn(`[AVISO] Falha ao salvar em ${dir}: ${err.message}`);
    }
  }
}

/**
 * Validação pura das regras geométricas a partir dos retângulos medidos.
 */
function validateGeometry(measurements) {
  const findings = [];
  const checks = {
    center: [],
    overflow: [],
    neighborGaps: [],
    horizontalAlignment: [],
  };

  // 1. Validar existência de rect e text para todas as 7 personas
  for (const name of PERSONAS) {
    const item = measurements.find((m) => m.name.toLowerCase() === name.toLowerCase());
    if (!item) {
      findings.push(`[ERRO] Persona não encontrada: ${name}`);
      continue;
    }
    if (!item.textFound) {
      findings.push(`[ERRO] Elemento <text> não encontrado para: ${name}`);
    }
    if (!item.rectFound) {
      findings.push(`[ERRO] Elemento <rect> da pílula não encontrado para: ${name}`);
    }
  }

  // 2. Validações por persona (a: centro, b: respiro interno)
  for (const name of PERSONAS) {
    const item = measurements.find((m) => m.name.toLowerCase() === name.toLowerCase());
    if (!item || !item.rectFound || !item.textFound) continue;

    const r = item.rectBox;
    const t = item.textBox;

    // a) Alinhamento de centro: |(rect.left + rect.width / 2) - (text.left + text.width / 2)| < 1.0 px
    const rectCenterX = r.left + r.width / 2;
    const textCenterX = t.left + t.width / 2;
    const centerDelta = Math.abs(rectCenterX - textCenterX);
    const centerOk = centerDelta < 1.0;
    checks.center.push({
      persona: name,
      rectCenterX: Number(rectCenterX.toFixed(2)),
      textCenterX: Number(textCenterX.toFixed(2)),
      delta: Number(centerDelta.toFixed(2)),
      pass: centerOk,
    });
    if (!centerOk) {
      findings.push(
        `[DESALINHADO-CENTRO] ${name}: |rect.cx (${rectCenterX.toFixed(2)}) - text.cx (${textCenterX.toFixed(2)})| = ${centerDelta.toFixed(2)}px >= 1.0px`
      );
    }

    // b) Zero overflow / respiro interno: rect.width >= text.width + 12 px
    const internalBreathing = r.width - t.width;
    const overflowOk = internalBreathing >= 12.0;
    checks.overflow.push({
      persona: name,
      rectWidth: Number(r.width.toFixed(2)),
      textWidth: Number(t.width.toFixed(2)),
      breathing: Number(internalBreathing.toFixed(2)),
      pass: overflowOk,
    });
    if (!overflowOk) {
      findings.push(
        `[OVERFLOW/RESPIRO] ${name}: rect.width (${r.width.toFixed(2)}) < text.width (${t.width.toFixed(2)}) + 12px (respiro: ${internalBreathing.toFixed(2)}px)`
      );
    }
  }

  // c) Respiro entre vizinhos: gap = nextRect.left - prevRect.right >= 6 px
  for (const [prevName, nextName] of ADJACENT_PAIRS) {
    const prevItem = measurements.find((m) => m.name.toLowerCase() === prevName.toLowerCase());
    const nextItem = measurements.find((m) => m.name.toLowerCase() === nextName.toLowerCase());

    if (!prevItem || !nextItem || !prevItem.rectFound || !nextItem.rectFound) {
      findings.push(`[GAP-VIZINHO] Impossível calcular gap entre ${prevName} e ${nextName}: rect ausente`);
      continue;
    }

    const prevR = prevItem.rectBox;
    const nextR = nextItem.rectBox;
    const gap = nextR.left - prevR.right;
    const gapOk = gap >= 6.0;

    checks.neighborGaps.push({
      pair: `${prevName} -> ${nextName}`,
      prevRight: Number(prevR.right.toFixed(2)),
      nextLeft: Number(nextR.left.toFixed(2)),
      gap: Number(gap.toFixed(2)),
      pass: gapOk,
    });

    if (!gapOk) {
      findings.push(
        `[GAP-INSUFICIENTE] ${prevName} -> ${nextName}: gap = ${gap.toFixed(2)}px < 6.0px (next.left ${nextR.left.toFixed(2)} - prev.right ${prevR.right.toFixed(2)})`
      );
    }
  }

  // d) Alinhamento horizontal: diferença de Y entre as pílulas < 2.0 px
  const presentPills = measurements.filter((m) => m.rectFound);
  if (presentPills.length >= 2) {
    const yTops = presentPills.map((p) => p.rectBox.top);
    const yCenters = presentPills.map((p) => p.rectBox.top + p.rectBox.height / 2);

    const minYTop = Math.min(...yTops);
    const maxYTop = Math.max(...yTops);
    const diffYTop = maxYTop - minYTop;

    const minYCenter = Math.min(...yCenters);
    const maxYCenter = Math.max(...yCenters);
    const diffYCenter = maxYCenter - minYCenter;

    const horizontalOk = diffYTop < 2.0;

    checks.horizontalAlignment.push({
      sampleCount: presentPills.length,
      minYTop: Number(minYTop.toFixed(2)),
      maxYTop: Number(maxYTop.toFixed(2)),
      diffYTop: Number(diffYTop.toFixed(2)),
      diffYCenter: Number(diffYCenter.toFixed(2)),
      pass: horizontalOk,
    });

    if (!horizontalOk) {
      findings.push(
        `[DESALINHAMENTO-HORIZONTAL] Diferença de Y entre pílulas: max(Y) - min(Y) = ${diffYTop.toFixed(2)}px >= 2.0px`
      );
    }
  }

  const passed = findings.length === 0;
  return { passed, findings, checks };
}

/**
 * Mede as pílulas diretamente no contexto do DOM com getBoundingClientRect().
 */
async function measurePillsInPage(page) {
  return await page.evaluate((personas) => {
    const normalize = (s) =>
      s
        .toLowerCase()
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .trim();

    const allTexts = Array.from(document.querySelectorAll('svg text'));

    return personas.map((name) => {
      const normTarget = normalize(name);

      const textEl = allTexts.find((t) => {
        const txt = normalize(t.textContent || '');
        return txt === normTarget;
      });

      if (!textEl) {
        return {
          name,
          textFound: false,
          rectFound: false,
        };
      }

      const tBox = textEl.getBoundingClientRect();

      // Localização do <rect> correspondente da pílula
      let rectEl = null;

      // 1. Busca no container <g> imediato
      const parentG = textEl.parentElement;
      if (parentG) {
        const localRects = Array.from(parentG.querySelectorAll('rect'));
        if (localRects.length === 1) {
          rectEl = localRects[0];
        } else if (localRects.length > 1) {
          rectEl =
            localRects.find((r) => {
              const rb = r.getBoundingClientRect();
              return Math.abs(rb.top + rb.height / 2 - (tBox.top + tBox.height / 2)) < 25;
            }) || localRects[0];
        }
      }

      // 2. Busca nos nós irmãos do <text>
      if (!rectEl && parentG) {
        let prev = textEl.previousElementSibling;
        while (prev) {
          if (prev.tagName.toLowerCase() === 'rect') {
            rectEl = prev;
            break;
          }
          prev = prev.previousElementSibling;
        }
        if (!rectEl) {
          let next = textEl.nextElementSibling;
          while (next) {
            if (next.tagName.toLowerCase() === 'rect') {
              rectEl = next;
              break;
            }
            next = next.nextElementSibling;
          }
        }
      }

      // 3. Busca por atributo semântico ou classe
      if (!rectEl) {
        rectEl = document.querySelector(
          `rect[data-persona="${normTarget}"], rect[data-persona="${name}"], rect.persona-pill-${normTarget}`
        );
      }

      // 4. Busca no grupo ancestral da persona no SVG
      if (!rectEl && parentG) {
        let cur = parentG.parentElement;
        while (cur && cur.tagName.toLowerCase() !== 'svg') {
          const candidates = Array.from(
            cur.querySelectorAll('rect.persona-pill, rect.pill-bg, rect[rx]')
          );
          if (candidates.length > 0) {
            rectEl = candidates.find((r) => {
              const rb = r.getBoundingClientRect();
              return (
                Math.abs(rb.left + rb.width / 2 - (tBox.left + tBox.width / 2)) < 60 &&
                Math.abs(rb.top + rb.height / 2 - (tBox.top + tBox.height / 2)) < 30
              );
            });
            if (rectEl) break;
          }
          cur = cur.parentElement;
        }
      }

      const rBox = rectEl ? rectEl.getBoundingClientRect() : null;

      return {
        name,
        textFound: true,
        rectFound: !!rectEl,
        textBox: {
          left: tBox.left,
          right: tBox.right,
          top: tBox.top,
          bottom: tBox.bottom,
          width: tBox.width,
          height: tBox.height,
        },
        rectBox: rBox
          ? {
              left: rBox.left,
              right: rBox.right,
              top: rBox.top,
              bottom: rBox.bottom,
              width: rBox.width,
              height: rBox.height,
            }
          : null,
      };
    });
  }, PERSONAS);
}

/**
 * Suíte de testes unitários embutida para certificar as regras matemáticas do probe.
 */
function runSelfTest() {
  console.log('=== EXECUTANDO SELF-TEST GEOMÉTRICO (VERIFICAÇÃO DO PROBE) ===');

  const validSample = [
    {
      name: 'Planejador',
      textFound: true,
      rectFound: true,
      textBox: { left: 470, right: 520, top: 480, bottom: 490, width: 50, height: 10 },
      rectBox: { left: 463, right: 527, top: 476, bottom: 494, width: 64, height: 18 }, // cx = 495, breathing = 14
    },
    {
      name: 'Historiador',
      textFound: true,
      rectFound: true,
      textBox: { left: 588, right: 642, top: 480, bottom: 490, width: 54, height: 10 },
      rectBox: { left: 581, right: 649, top: 476, bottom: 494, width: 68, height: 18 }, // cx = 615, right = 649
    },
    {
      name: 'Visionário',
      textFound: true,
      rectFound: true,
      textBox: { left: 664, right: 712, top: 480, bottom: 490, width: 48, height: 10 }, // cx = 688
      rectBox: { left: 658, right: 718, top: 476.5, bottom: 494.5, width: 60, height: 18 }, // cx = 688, left = 658 (gap = 658 - 649 = 9px)
    },
    {
      name: 'Futurista',
      textFound: true,
      rectFound: true,
      textBox: { left: 734, right: 778, top: 480, bottom: 490, width: 44, height: 10 }, // cx = 756
      rectBox: { left: 728, right: 784, top: 476.2, bottom: 494.2, width: 56, height: 18 }, // cx = 756, left = 728 (gap = 728 - 718 = 10px)
    },
    {
      name: 'Cético',
      textFound: true,
      rectFound: true,
      textBox: { left: 820, right: 852, top: 480, bottom: 490, width: 32, height: 10 }, // cx = 836
      rectBox: { left: 813, right: 859, top: 476.1, bottom: 494.1, width: 46, height: 18 }, // cx = 836, left = 813 (gap = 813 - 784 = 29px)
    },
    {
      name: 'Auditor',
      textFound: true,
      rectFound: true,
      textBox: { left: 1040, right: 1076, top: 480, bottom: 490, width: 36, height: 10 }, // cx = 1058
      rectBox: { left: 1033, right: 1083, top: 476, bottom: 494, width: 50, height: 18 }, // cx = 1058
    },
    {
      name: 'Redator',
      textFound: true,
      rectFound: true,
      textBox: { left: 1150, right: 1188, top: 480, bottom: 490, width: 38, height: 10 }, // cx = 1169
      rectBox: { left: 1143, right: 1195, top: 476.4, bottom: 494.4, width: 52, height: 18 }, // cx = 1169
    },
  ];

  const resultOk = validateGeometry(validSample);
  if (!resultOk.passed) {
    throw new Error('Self-test falhou ao aprovar caso válido: ' + resultOk.findings.join('; '));
  }
  console.log('✓ Caso perfeitamente alinhado: PASSOU');

  // Testar detecção de defeito de centro
  const badCenterSample = JSON.parse(JSON.stringify(validSample));
  badCenterSample[0].rectBox.left += 4; // Desloca centro em 4px
  const resultBadCenter = validateGeometry(badCenterSample);
  if (resultBadCenter.passed || !resultBadCenter.findings.some((f) => f.includes('DESALINHADO-CENTRO'))) {
    throw new Error('Self-test falhou: não detectou desalinhamento de centro');
  }
  console.log('✓ Detecção de desalinhamento de centro (>1px): PASSOU');

  // Testar detecção de overflow (<12px)
  const badOverflowSample = JSON.parse(JSON.stringify(validSample));
  badOverflowSample[0].rectBox.width = badOverflowSample[0].textBox.width + 8; // Apenas 8px de respiro
  const resultBadOverflow = validateGeometry(badOverflowSample);
  if (resultBadOverflow.passed || !resultBadOverflow.findings.some((f) => f.includes('OVERFLOW/RESPIRO'))) {
    throw new Error('Self-test falhou: não detectou respiro insuficiente');
  }
  console.log('✓ Detecção de overflow / respiro insuficiente (<12px): PASSOU');

  // Testar detecção de gap insuficiente (<6px)
  const badGapSample = JSON.parse(JSON.stringify(validSample));
  badGapSample[2].rectBox.left = badGapSample[1].rectBox.right + 3; // Gap de 3px entre Historiador e Visionário
  const resultBadGap = validateGeometry(badGapSample);
  if (resultBadGap.passed || !resultBadGap.findings.some((f) => f.includes('GAP-INSUFICIENTE'))) {
    throw new Error('Self-test falhou: não detectou gap insuficiente entre vizinhos');
  }
  console.log('✓ Detecção de gap insuficiente entre vizinhos (<6px): PASSOU');

  // Testar detecção de desalinhamento horizontal de Y (>= 2px)
  const badYSample = JSON.parse(JSON.stringify(validSample));
  badYSample[3].rectBox.top += 3.5; // Diferença de 3.5px
  const resultBadY = validateGeometry(badYSample);
  if (resultBadY.passed || !resultBadY.findings.some((f) => f.includes('DESALINHAMENTO-HORIZONTAL'))) {
    throw new Error('Self-test falhou: não detectou desnível vertical em Y');
  }
  console.log('✓ Detecção de desnível vertical em Y (>=2px): PASSOU');

  console.log('=== TODOS OS 5 SELF-TESTS DO PROBE PASSARAM COM SUCESSO ===\n');
}

async function main() {
  const isTestMode = process.argv.includes('--self-test');
  if (isTestMode) {
    runSelfTest();
    process.exit(0);
  }

  // Executar self-test preliminar para garantir integridade matemática do auditor
  runSelfTest();

  console.log(`Iniciando auditoria geométrica das pílulas no Hero...`);
  console.log(`URL Alvo: ${TARGET_URL}`);
  console.log(`Wrapper Chromium: ${CHROME_PATH}`);

  const browser = await chromium.launch({
    executablePath: CHROME_PATH,
    args: ['--no-sandbox', '--disable-dev-shm-usage', '--disable-setuid-sandbox'],
  });

  let measurements = null;
  let validationResult = null;

  try {
    // -------------------------------------------------------------
    // 1. CAPTURA E AUDITORIA DESKTOP (1440 x 900)
    // -------------------------------------------------------------
    console.log('\n--- 1. DESKTOP (1440x900) ---');
    const desktopContext = await browser.newContext({
      viewport: { width: 1440, height: 900 },
      deviceScaleFactor: 1,
    });
    const desktopPage = await desktopContext.newPage();

    console.log(`Navegando para ${TARGET_URL}...`);
    await desktopPage.goto(TARGET_URL, { waitUntil: 'networkidle' });
    await desktopPage.waitForTimeout(1000);

    // Capturar screenshot desktop 38a
    const shot38aBuffer = await desktopPage.screenshot({ fullPage: false });
    saveScreenshot(shot38aBuffer, '38a-hero-pills-desktop.png');

    // Medição geométrica das 7 personas
    console.log('Medindo geometria das pílulas no viewport desktop...');
    measurements = await measurePillsInPage(desktopPage);
    validationResult = validateGeometry(measurements);

    await desktopContext.close();

    // -------------------------------------------------------------
    // 2. CAPTURA MOBILE (390 x 844)
    // -------------------------------------------------------------
    console.log('\n--- 2. MOBILE (390x844) ---');
    const mobileContext = await browser.newContext({
      viewport: { width: 390, height: 844 },
      deviceScaleFactor: 1,
      isMobile: true,
      hasTouch: true,
    });
    const mobilePage = await mobileContext.newPage();

    await mobilePage.goto(TARGET_URL, { waitUntil: 'networkidle' });
    await mobilePage.waitForTimeout(1000);

    // Capturar screenshot mobile 38b
    const shot38bBuffer = await mobilePage.screenshot({ fullPage: false });
    saveScreenshot(shot38bBuffer, '38b-hero-pills-mobile.png');

    await mobileContext.close();
  } finally {
    await browser.close();
  }

  // -------------------------------------------------------------
  // 3. EXIBIÇÃO DO RELATÓRIO DE AUDITORIA
  // -------------------------------------------------------------
  console.log('\n=============================================================');
  console.log('       RELATÓRIO DE MEDIÇÃO GEOMÉTRICA DAS 7 PERSONAS        ');
  console.log('=============================================================');

  console.log('\n[ESTADO DOS ELEMENTOS DETECTADOS]');
  for (const item of measurements) {
    const textStatus = item.textFound ? `OK (largura: ${item.textBox.width.toFixed(1)}px)` : 'NÃO ENCONTRADO';
    const rectStatus = item.rectFound
      ? `OK (largura: ${item.rectBox.width.toFixed(1)}px, x: ${item.rectBox.left.toFixed(1)}, y: ${item.rectBox.top.toFixed(1)})`
      : 'NÃO ENCONTRADO (<rect> ausente)';
    console.log(` • ${item.name.padEnd(12)} -> <text>: ${textStatus} | <rect>: ${rectStatus}`);
  }

  if (validationResult.checks.center.length > 0) {
    console.log('\n[a) ALINHAMENTO DE CENTRO (tolerância < 1.0px)]');
    for (const c of validationResult.checks.center) {
      console.log(
        ` • ${c.persona.padEnd(12)}: rect.cx=${c.rectCenterX}px | text.cx=${c.textCenterX}px | delta=${c.delta}px [${c.pass ? 'PASS' : 'FAIL'}]`
      );
    }
  }

  if (validationResult.checks.overflow.length > 0) {
    console.log('\n[b) ZERO OVERFLOW / RESPIRO INTERNO (rect.width >= text.width + 12px)]');
    for (const o of validationResult.checks.overflow) {
      console.log(
        ` • ${o.persona.padEnd(12)}: rect.w=${o.rectWidth}px | text.w=${o.textWidth}px | respiro=${o.breathing}px [${o.pass ? 'PASS' : 'FAIL'}]`
      );
    }
  }

  if (validationResult.checks.neighborGaps.length > 0) {
    console.log('\n[c) RESPIRO ENTRE VIZINHOS (gap >= 6.0px)]');
    for (const g of validationResult.checks.neighborGaps) {
      console.log(
        ` • ${g.pair.padEnd(25)}: prev.right=${g.prevRight}px | next.left=${g.nextLeft}px | gap=${g.gap}px [${g.pass ? 'PASS' : 'FAIL'}]`
      );
    }
  }

  if (validationResult.checks.horizontalAlignment.length > 0) {
    console.log('\n[d) ALINHAMENTO HORIZONTAL (diferença de Y < 2.0px)]');
    for (const h of validationResult.checks.horizontalAlignment) {
      console.log(
        ` • ${h.sampleCount} pílulas medidas: min(Y)=${h.minYTop}px | max(Y)=${h.maxYTop}px | diffY=${h.diffYTop}px [${h.pass ? 'PASS' : 'FAIL'}]`
      );
    }
  }

  console.log('\n=============================================================');
  if (validationResult.passed) {
    console.log('RESULTADO FINAL: ✓ APROVADO EM TODAS AS REGRAS GEOMÉTRICAS');
    console.log('=============================================================');
    process.exit(0);
  } else {
    console.log(`RESULTADO FINAL: ✗ FALHA NA VALIDAÇÃO (${validationResult.findings.length} achados):`);
    for (const f of validationResult.findings) {
      console.log(`  - ${f}`);
    }
    console.log('=============================================================');
    // Encerra com código 1 para funcionar como portão / gate de CI e aceitação
    process.exit(1);
  }
}

if (require.main === module) {
  main().catch((err) => {
    console.error('[ERRO CRÍTICO]', err);
    process.exit(1);
  });
}

module.exports = {
  validateGeometry,
  measurePillsInPage,
  runSelfTest,
};
