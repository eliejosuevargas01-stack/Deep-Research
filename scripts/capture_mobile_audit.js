const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const ARTIFACTS_DIR = '/opt/data/projects/deep-research/Deep-Research/artifacts/audit-mobile-impeccable-2026-10-31';
const SHOTS_DIR = path.join(ARTIFACTS_DIR, 'shots');
const BASE_URL = 'http://127.0.0.1:3000';
const CHROME_PATH = '/opt/data/projects/deep-research/Deep-Research/scripts/chrome_wrapper.sh';

fs.mkdirSync(SHOTS_DIR, { recursive: true });

const SEED_HISTORY = [
  {
    id_pesquisa: 'harness-0001',
    tema: 'Automação bancária no Brasil: impactos no emprego e na requalificação profissional entre 2010 e 2026',
    criado_em: '2026-10-31T14:10:00.000Z',
    concluido_em: '2026-10-31T14:18:22.000Z',
    status: 'concluido',
    n_pontos: 3,
    total_caracteres_dossier: 1605,
    dossier_resumo: 'Dossiê analítico sobre a reestruturação bancária, canais digitais e impacto nos postos de trabalho.',
  },
  {
    id_pesquisa: 'harness-0002',
    tema: 'Transição energética e potencial da matriz eólica offshore na costa brasileira',
    criado_em: '2026-10-30T18:20:00.000Z',
    concluido_em: '2026-10-30T18:25:10.000Z',
    status: 'concluido',
    n_pontos: 4,
    total_caracteres_dossier: 2840,
    dossier_resumo: 'Avaliação de viabilidade regulatória e capacidade de geração eólica offshore.',
  },
  {
    id_pesquisa: 'harness-0003',
    tema: 'Regulamentação de inteligência artificial generativa em saúde suplementar',
    criado_em: '2026-10-29T11:00:00.000Z',
    status: 'falha',
    n_pontos: 3,
    diagnostico: 'Limite de requisições excedido no provedor de busca.',
  }
];

const domAuditScript = () => {
  const vis = (e) => {
    const r = e.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && getComputedStyle(e).visibility !== 'hidden' && e.checkVisibility({ visibilityProperty: true });
  };

  // 1. Landmarks e Títulos
  const headings = [...document.querySelectorAll('h1, h2, h3, h4, h5, h6')].filter(vis).map((e) => ({
    tag: e.tagName.toLowerCase(),
    text: e.textContent.trim().replace(/\s+/g, ' ').slice(0, 100),
  }));
  const h1Count = headings.filter((h) => h.tag === 'h1').length;

  // 2. Alvos de toque pequenos (< 44px de altura ou largura)
  const interactiveSelector = 'button, a[href], input, textarea, select, [role="button"], [role="tab"]';
  const smallTargets = [...document.querySelectorAll(interactiveSelector)]
    .filter(vis)
    .map((e) => {
      const r = e.getBoundingClientRect();
      const label = (e.getAttribute('aria-label') || e.textContent || e.getAttribute('title') || '').trim().slice(0, 40);
      return { tag: e.tagName.toLowerCase(), label, w: Math.round(r.width), h: Math.round(r.height) };
    })
    .filter((t) => t.w < 44 || t.h < 44);

  // 3. Overflow horizontal além dos 390px
  const viewportW = window.innerWidth;
  const overflows = [...document.querySelectorAll('*')]
    .filter(vis)
    .map((e) => {
      const r = e.getBoundingClientRect();
      const s = getComputedStyle(e);
      const isOverflowing = r.right > viewportW + 2 || e.scrollWidth > e.clientWidth + 2;
      return {
        tag: e.tagName.toLowerCase(),
        cls: e.className?.toString?.().slice(0, 50) || '',
        right: Math.round(r.right),
        scrollW: e.scrollWidth,
        clientW: e.clientWidth,
        overflowX: s.overflowX,
        isOverflowing: isOverflowing && s.overflowX === 'visible',
      };
    })
    .filter((o) => o.isOverflowing);

  // 4. Containers de rolagem (esperado no mobile: 1 scroller principal)
  const scrollers = [...document.querySelectorAll('*')]
    .filter(vis)
    .filter((e) => {
      const s = getComputedStyle(e);
      return (s.overflowY === 'auto' || s.overflowY === 'scroll') && e.scrollHeight > e.clientHeight + 4;
    })
    .map((e) => ({
      tag: e.tagName.toLowerCase(),
      cls: e.className?.toString?.().slice(0, 50) || '',
      scrollHeight: e.scrollHeight,
      clientHeight: e.clientHeight,
    }));

  // 5. Coleta de textos visíveis para auditoria de microcopy / AI-Slop
  const textNodes = [...document.querySelectorAll('h1, h2, h3, p, span, button, strong, label, .alert-banner, .execution-banner-copy')]
    .filter(vis)
    .map((e) => e.textContent.trim().replace(/\s+/g, ' '))
    .filter((t) => t.length > 5 && t.length < 300);

  const uniqueTexts = [...new Set(textNodes)].slice(0, 50);

  return {
    h1Count,
    headings,
    smallTargetsCount: smallTargets.length,
    smallTargetsSample: smallTargets.slice(0, 10),
    overflowCount: overflows.length,
    overflowsSample: overflows.slice(0, 5),
    scrollersCount: scrollers.length,
    scrollers,
    uniqueTexts,
    pageScrollHeight: document.documentElement.scrollHeight,
    viewportHeight: window.innerHeight,
  };
};

async function main() {
  console.log('Iniciando captura e auditoria mobile...');
  const browser = await chromium.launch({
    executablePath: CHROME_PATH,
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  });

  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 2,
    isMobile: true,
    hasTouch: true,
  });

  // Injetar localStorage antes de qualquer rota
  await context.addInitScript((seed) => {
    localStorage.setItem('deepResearch.history', JSON.stringify(seed));
    localStorage.setItem('deepResearch.theme', 'light');
    localStorage.setItem('deepResearch.ambientBackground', 'false');
  }, SEED_HISTORY);

  const page = await context.newPage();

  const auditResults = {};

  const screens = [
    {
      id: '01-mobile-home-pesquisa-inicial',
      route: '#research',
      name: 'Tela Inicial (Home / EmptyState)',
      action: async () => {
        await page.waitForSelector('.composer-textarea, [placeholder*="pesquisa"]', { timeout: 5000 });
      },
    },
    {
      id: '02-mobile-home-preferencias-sheet',
      route: '#research',
      name: 'Preferências de Investigação (Bottom Sheet)',
      action: async () => {
        const prefBtn = page.locator('button[aria-label*="Preferências"], button[title*="Preferências"], .composer-accessory-btn').first();
        if (await prefBtn.count()) {
          await prefBtn.click();
          await page.waitForTimeout(400);
        }
      },
    },
    {
      id: '03-mobile-planejamento',
      route: '#planning',
      name: 'Planejamento em Curso (PlanningView)',
      action: async () => {
        await page.waitForSelector('.planning-view', { timeout: 5000 });
      },
    },
    {
      id: '04-mobile-revisao-plano',
      route: '#plan',
      name: 'Revisão do Plano Estruturado (PlanView)',
      action: async () => {
        await page.waitForSelector('.plan-card, .plan-view-container', { timeout: 5000 });
      },
    },
    {
      id: '05-mobile-execucao-busca',
      route: '#execution-search',
      name: 'Execução - Fase de Busca (ExecutionView)',
      action: async () => {
        await page.waitForSelector('.execution-card, .tl-linear', { timeout: 5000 });
      },
    },
    {
      id: '06-mobile-execucao-busca-expandida',
      route: '#execution-search',
      name: 'Execução - Raciocínio Expandido com Fontes',
      action: async () => {
        await page.waitForSelector('.tl-linear button[aria-expanded]', { timeout: 5000 });
        const firstStep = page.locator('.tl-linear button[aria-expanded="false"]').first();
        if (await firstStep.count()) {
          await firstStep.click();
          await page.waitForTimeout(300);
        }
      },
    },
    {
      id: '07-mobile-execucao-auditoria',
      route: '#execution-audit',
      name: 'Execução - Fase de Auditoria e Critérios',
      action: async () => {
        await page.waitForSelector('.execution-card', { timeout: 5000 });
      },
    },
    {
      id: '08-mobile-execucao-redacao',
      route: '#execution-writing',
      name: 'Execução - Fase de Redação (Síntese)',
      action: async () => {
        await page.waitForSelector('.execution-card', { timeout: 5000 });
      },
    },
    {
      id: '09-mobile-execucao-rejeitada',
      route: '#execution-rejected',
      name: 'Execução - Reprovada na Auditoria',
      action: async () => {
        await page.waitForSelector('.execution-card', { timeout: 5000 });
      },
    },
    {
      id: '10-mobile-execucao-falha',
      route: '#execution-failed',
      name: 'Execução - Falha / Interrupção e Recuperação',
      action: async () => {
        await page.waitForSelector('.execution-card, .error-notice', { timeout: 5000 });
      },
    },
    {
      id: '11-mobile-relatorio-dossie',
      route: '#report',
      name: 'Dossiê Final Concluído (ReportView)',
      action: async () => {
        await page.waitForSelector('.report-card, .report-content, .markdown-content', { timeout: 8000 });
      },
    },
    {
      id: '12-mobile-relatorio-fontes',
      route: '#report',
      name: 'Dossiê - Auditoria de Fontes e Integridade SHA-256',
      action: async () => {
        await page.waitForSelector('.report-card', { timeout: 8000 });
        await page.evaluate(() => {
          window.scrollTo(0, 1200);
        });
        await page.waitForTimeout(300);
      },
    },
    {
      id: '13-mobile-historico',
      route: '#history',
      name: 'Histórico de Pesquisas (HistoryView)',
      action: async () => {
        await page.waitForSelector('.history-container', { timeout: 8000 });
      },
    },
    {
      id: '14-mobile-configuracoes',
      route: '#settings',
      name: 'Configurações e Ajustes (SettingsView)',
      action: async () => {
        await page.waitForSelector('.settings-container', { timeout: 8000 });
      },
    },
    {
      id: '15-mobile-documentacao',
      route: '#docs',
      name: 'Documentação do Sistema (DocsView)',
      action: async () => {
        await page.waitForSelector('.docs-view, .docs-container', { timeout: 5000 });
      },
    },
  ];

  for (const s of screens) {
    console.log(`Auditorando tela: ${s.name} (${s.route})...`);
    try {
      await page.goto(`${BASE_URL}/${s.route}`, { waitUntil: 'networkidle', timeout: 10000 });
      await page.waitForTimeout(300);
      if (s.action) {
        await s.action();
      }
      const shotPath = path.join(SHOTS_DIR, `${s.id}.png`);
      await page.screenshot({ path: shotPath, fullPage: false });

      const auditData = await page.evaluate(domAuditScript);
      auditResults[s.id] = {
        name: s.name,
        route: s.route,
        shotPath,
        ...auditData,
      };
      console.log(`✓ ${s.name} salva em ${shotPath}`);
    } catch (err) {
      console.error(`Erro ao capturar ${s.id}:`, err.message);
      auditResults[s.id] = {
        name: s.name,
        route: s.route,
        error: err.message,
      };
    }
  }

  // Capturar também uma tela no tema escuro para auditoria de contraste e tema
  try {
    console.log('Capturando estado escuro (Dark Mode) da tela inicial...');
    await page.goto(`${BASE_URL}/#research`, { waitUntil: 'networkidle' });
    await page.evaluate(() => {
      document.documentElement.setAttribute('data-theme', 'dark');
    });
    await page.waitForTimeout(300);
    const darkShotPath = path.join(SHOTS_DIR, '16-mobile-home-dark-theme.png');
    await page.screenshot({ path: darkShotPath, fullPage: false });
    auditResults['16-mobile-home-dark-theme'] = {
      name: 'Tela Inicial (Tema Escuro)',
      route: '#research [dark]',
      shotPath: darkShotPath,
      ...(await page.evaluate(domAuditScript)),
    };
    console.log(`✓ Tema escuro salvo em ${darkShotPath}`);
  } catch (err) {
    console.error('Erro no tema escuro:', err.message);
  }

  fs.writeFileSync(path.join(ARTIFACTS_DIR, 'metrics.json'), JSON.stringify(auditResults, null, 2));
  console.log('Auditoria mobile concluída com sucesso!');
  await browser.close();
}

main().catch((e) => {
  console.error('Falha fatal:', e);
  process.exit(1);
});
