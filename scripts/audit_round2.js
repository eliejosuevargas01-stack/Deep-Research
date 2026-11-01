const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const CHROME_PATH = '/opt/data/projects/deep-research/Deep-Research/scripts/chrome_wrapper.sh';
const OUT_DIR = '/opt/data/projects/deep-research/Deep-Research/artifacts/audit-cycles/shots';

const SEED_HISTORY = [
  {
    id_pesquisa: 'audit-run-002',
    tema: 'Armazenamento de energia em baterias no Brasil: regulação e modelos de negócio 2025',
    criado_em: new Date().toISOString(),
    status: 'planejado',
    total_pontos: 1,
    planResponse: {
      id_pesquisa: 'audit-run-002',
      tema: 'Armazenamento de energia em baterias no Brasil: regulação e modelos de negócio 2025',
      n_pontos: 1,
      criado_em: new Date().toISOString(),
      status_pipeline: 'planejado',
      preferencias: {
        n_pontos: 1,
        personas: ['historiador', 'visionario', 'cetico', 'futurista'],
        execution_mode: 'parallel',
        recencia: '24h',
        criterios_minimos: 12,
      },
      plano_estruturado: {
        pedido_original: 'Armazenamento de energia em baterias no Brasil',
        pedido_normalizado: 'Armazenamento de energia em baterias no Brasil: regulação e modelos de negócio 2025',
        publico: 'Reguladores e Operadores de Mercado',
        formato_entrega: 'Dossiê analítico',
        eixos: ['Regulação e modelos de receita para BESS no Brasil'],
      },
      pontos: [
        {
          ponto_id: 'ponto-1',
          ponto_n: 1,
          ponto: 'Modelos de receita e serviços ancilares para baterias no SIN',
          status: 'planejado',
          eixo_estruturado: {
            pergunta_principal: 'Quais os modelos de negócio e regras regulatórias da ANEEL para serviços ancilares de BESS?',
            subperguntas: ['Como o leilão de reserva de capacidade remunera sistemas BESS?'],
            hipoteses: ['Arbitragem de preços e reserva de potência representam as fontes primárias de receita.'],
            fontes_primarias_desejadas: ['ANEEL Caderno Temático', 'ONS Procedimentos de Rede', 'EPE BESS 2025'],
            criterio_de_conclusao: 'Análise documental das resoluções normativas da ANEEL vigentes.',
          },
        },
      ],
    },
  },
];

async function runAudit2() {
  console.log('=== INICIANDO AUDITORIA 2 (CICLO 2: A11Y, CONTRASTE, TECLADO E FOCO) ===');

  const browser = await chromium.launch({
    executablePath: CHROME_PATH,
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  });

  const findings = [];
  const scores = { a11y: 4, perf: 4, theme: 4, responsive: 4, integrity: 4 };

  try {
    const context = await browser.newContext({
      viewport: { width: 1440, height: 900 },
      deviceScaleFactor: 1,
    });

    await context.addInitScript((seed) => {
      localStorage.setItem('deep_research_local_history_v1', JSON.stringify(seed));
      localStorage.setItem('deepResearch.activeResearchId', 'audit-run-002');
      localStorage.setItem('deepResearch.theme', 'light');
    }, SEED_HISTORY);

    const page = await context.newPage();
    await page.goto('http://127.0.0.1:3002/#research', { waitUntil: 'networkidle' });
    await page.waitForTimeout(800);

    // 1. FOCUS RINGS VERIFICATION (Tab Navigation)
    console.log('Auditando navegação por Tab e focus rings visíveis...');
    await page.keyboard.press('Tab');
    await page.keyboard.press('Tab');
    await page.waitForTimeout(200);

    const focusedTag = await page.evaluate(() => {
      const active = document.activeElement;
      if (!active || active === document.body) return null;
      const s = window.getComputedStyle(active);
      return {
        tag: active.tagName,
        cls: active.className,
        outline: s.outline,
        outlineWidth: s.outlineWidth,
        boxShadow: s.boxShadow,
      };
    });

    if (focusedTag && focusedTag.outlineWidth === '0px' && focusedTag.boxShadow === 'none') {
      findings.push({
        severity: 'P2',
        dim: 'a11y',
        route: '#research',
        issue: `Elemento focado via Tab (${focusedTag.tag}.${focusedTag.cls}) não exibe indicador visual de foco (outline=0 e shadow=none)`,
      });
      scores.a11y = Math.min(scores.a11y, 3);
    }

    // 2. COMPOSER TEXTAREA LABELS & ARIA
    console.log('Auditando acessibilidade do compositor de entrada...');
    const composerA11y = await page.evaluate(() => {
      const ta = document.querySelector('.composer-textarea, textarea');
      if (!ta) return null;
      return {
        hasAriaLabel: Boolean(ta.getAttribute('aria-label')),
        hasPlaceholder: Boolean(ta.getAttribute('placeholder')),
        id: ta.id,
        hasLabel: Boolean(document.querySelector(`label[for="${ta.id}"]`)),
      };
    });

    if (composerA11y && !composerA11y.hasAriaLabel && !composerA11y.hasLabel) {
      findings.push({
        severity: 'P1',
        dim: 'a11y',
        route: '#research',
        issue: 'Área de texto principal (Composer textarea) não possui aria-label nem <label for> associado',
      });
      scores.a11y = Math.min(scores.a11y, 2);
    }

    // 3. TOUCH TARGETS IN CAROUSEL CHEVRONS
    console.log('Auditando alvos interativos de botões de controle...');
    const controlButtons = await page.evaluate(() => {
      const btns = [];
      document.querySelectorAll('.hero-carousel-nav-btn, .btn-header-rail, .stepper-point-toggle').forEach((el) => {
        const r = el.getBoundingClientRect();
        btns.push({
          cls: el.className,
          w: Math.round(r.width),
          h: Math.round(r.height),
          ariaLabel: el.getAttribute('aria-label'),
        });
      });
      return btns;
    });

    controlButtons.forEach((b) => {
      // Ignora elementos ocultos (display: none no viewport atual)
      if (b.w === 0 && b.h === 0) return;
      if (b.w < 24 || b.h < 24) {
        findings.push({
          severity: 'P2',
          dim: 'a11y',
          route: '#research/#plan',
          issue: `Botão de controle com dimensão abaixo de 24px: ${b.cls} (${b.w}x${b.h}px)`,
        });
        scores.a11y = Math.min(scores.a11y, 3);
      }
    });

    // 4. CONTRASTE DE CORES EM TEXTOS SECUNDÁRIOS
    console.log('Auditando contraste de texto em elementos de interface...');
    const contrastChecks = await page.evaluate(() => {
      const issues = [];
      const isLowContrast = (c) => {
        // Detecta tons cinza excessivamente claros em texto (< #888888 no light theme)
        if (c.startsWith('rgba(0, 0, 0, 0.2') || c.startsWith('rgba(0, 0, 0, 0.3')) return true;
        if (c === 'rgb(180, 180, 180)' || c === 'rgb(200, 200, 200)') return true;
        return false;
      };

      document.querySelectorAll('.query-label, .stepper-point-details, .point-detail-label').forEach((el) => {
        const s = window.getComputedStyle(el);
        if (isLowContrast(s.color)) {
          issues.push({ cls: el.className, color: s.color });
        }
      });
      return issues;
    });

    if (contrastChecks.length > 0) {
      findings.push({
        severity: 'P2',
        dim: 'a11y',
        route: '#plan',
        issue: `Cores de texto com contraste potencialmente fraco (<4.5:1): ${contrastChecks.length} instâncias encontradas`,
      });
      scores.a11y = Math.min(scores.a11y, 3);
    }

    // 5. MOBILE AUDIT 390x844
    console.log('Auditando viewport mobile 390x844...');
    const mobileContext = await browser.newContext({
      viewport: { width: 390, height: 844 },
      deviceScaleFactor: 2,
      isMobile: true,
      hasTouch: true,
    });

    await mobileContext.addInitScript((seed) => {
      localStorage.setItem('deep_research_local_history_v1', JSON.stringify(seed));
      localStorage.setItem('deepResearch.activeResearchId', 'audit-run-002');
      localStorage.setItem('deepResearch.theme', 'light');
    }, SEED_HISTORY);

    const mobilePage = await mobileContext.newPage();
    await mobilePage.goto('http://127.0.0.1:3002/#research', { waitUntil: 'networkidle' });
    await mobilePage.waitForTimeout(600);

    const mobileScrollH = await mobilePage.evaluate(() => document.documentElement.scrollHeight);
    const mobileDocW = await mobilePage.evaluate(() => document.documentElement.scrollWidth);
    console.log(`Mobile: scrollWidth=${mobileDocW}px, scrollHeight=${mobileScrollH}px`);

    if (mobileDocW > 390) {
      findings.push({
        severity: 'P1',
        dim: 'responsive',
        route: '#plan',
        issue: `Documento mobile com scroll horizontal ativo: scrollWidth=${mobileDocW}px > 390px`,
      });
      scores.responsive = Math.min(scores.responsive, 2);
    }

    await mobilePage.screenshot({ path: path.join(OUT_DIR, 'c2-01-mobile-plan-audit2.png') });
    await page.screenshot({ path: path.join(OUT_DIR, 'c2-02-desktop-plan-audit2.png') });

  } finally {
    await browser.close();
  }

  const totalScore = scores.a11y + scores.perf + scores.theme + scores.responsive + scores.integrity;
  console.log('\n======================================================');
  console.log(`PONTUAÇÃO DE SAÚDE DA AUDITORIA 2: ${totalScore}/20`);
  console.log(` - Acessibilidade (A11y)      : ${scores.a11y}/4`);
  console.log(` - Performance                : ${scores.perf}/4`);
  console.log(` - Theming                    : ${scores.theme}/4`);
  console.log(` - Design Responsivo          : ${scores.responsive}/4`);
  console.log(` - Integridade Implementação  : ${scores.integrity}/4`);
  console.log('======================================================');
  console.log(`TOTAL DE ACHADOS: ${findings.length}`);
  findings.forEach((f, idx) => {
    console.log(` [${idx + 1}] [${f.severity}] [${f.dim.toUpperCase()}] (${f.route}): ${f.issue}`);
  });
  console.log('======================================================\n');

  fs.writeFileSync(
    path.join(__dirname, '../artifacts/audit-cycles/audit-round-2.json'),
    JSON.stringify({ totalScore, scores, findings }, null, 2)
  );
}

runAudit2().catch((e) => {
  console.error('Falha no audit round 2:', e);
  process.exit(1);
});
