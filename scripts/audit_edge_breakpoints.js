const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const CHROME_PATH = '/opt/data/projects/deep-research/Deep-Research/scripts/chrome_wrapper.sh';
const OUT_DIR = '/opt/data/projects/deep-research/Deep-Research/artifacts/audit-cycles/shots/pass3-edge';

const LONG_TITLE_SEED = [
  {
    id_pesquisa: 'audit-edge-001',
    tema: 'Avaliação socioeconômica e geoespacial da infraestrutura de transmissão de ultra-alta tensão (UAT) corrente contínua (HVDC ±800 kV) no bioma Amazônia-Cerrado 2026-2035: licenciamento, comunidades tradicionais e perdas técnicas',
    criado_em: new Date().toISOString(),
    status: 'planejado',
    total_pontos: 1,
    planResponse: {
      id_pesquisa: 'audit-edge-001',
      tema: 'Avaliação socioeconômica e geoespacial da infraestrutura de transmissão de ultra-alta tensão (UAT) corrente contínua (HVDC ±800 kV) no bioma Amazônia-Cerrado 2026-2035: licenciamento, comunidades tradicionais e perdas técnicas',
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
        pedido_original: 'Transmissão UAT HVDC no Brasil',
        pedido_normalizado: 'Transmissão HVDC ±800 kV Amazônia-Cerrado',
        publico: 'Engenheiros e Reguladores de Energia',
        formato_entrega: 'Dossiê analítico',
        eixos: ['Impactos de licenciamento socioambiental e estabilidade eletromecânica'],
      },
      pontos: [
        {
          ponto_id: 'ponto-1',
          ponto_n: 1,
          ponto: 'Impactos de licenciamento socioambiental em terras indígenas e unidades de conservação cruzadas pelas linhas de transmissão de corrente contínua',
          status: 'planejado',
          eixo_estruturado: {
            pergunta_principal: 'Quais os passivos jurídicos e condicionantes do IBAMA para a concessão da Licença de Instalação dos bipolos HVDC?',
            subperguntas: ['Qual o tempo médio de tramitação dos estudos de componente indígena (ECI) junto à FUNAI?'],
            hipoteses: ['A adoção de traçados alternativos periféricos mitiga embargos judiciais e reduz o custo de servidão.'],
            fontes_primarias_desejadas: ['IBAMA Sislic', 'FUNAI Pareceres', 'EPE R1/R2 Planejamento da Transmissão'],
            criterio_de_conclusao: 'Quadro comparativo de prazos de licenciamento e áreas interceptadas.',
          },
        },
      ],
    },
  },
];

async function runPass3Edge() {
  fs.mkdirSync(OUT_DIR, { recursive: true });
  console.log('=== PASS 3: AUDITORIA EM BREAKPOINTS EXTREMOS E TÍTULOS LONGOS ===');

  const browser = await chromium.launch({
    executablePath: CHROME_PATH,
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  });

  const findings = [];

  const viewports = [
    { name: 'android-360x740', width: 360, height: 740, isMobile: true, dpr: 2 },
    { name: 'iphone-390x844', width: 390, height: 844, isMobile: true, dpr: 2 },
    { name: 'laptop-1280x720', width: 1280, height: 720, isMobile: false, dpr: 1 },
    { name: 'desktop-1440x900', width: 1440, height: 900, isMobile: false, dpr: 1 },
  ];

  try {
    for (const vp of viewports) {
      console.log(`\nTestando viewport ${vp.name} (${vp.width}x${vp.height})...`);
      const ctx = await browser.newContext({
        viewport: { width: vp.width, height: vp.height },
        deviceScaleFactor: vp.dpr,
        isMobile: vp.isMobile,
        hasTouch: vp.isMobile,
      });

      await ctx.addInitScript((seed) => {
        localStorage.setItem('deep_research_local_history_v1', JSON.stringify(seed));
        localStorage.setItem('deepResearch.activeResearchId', 'audit-edge-001');
        localStorage.setItem('deepResearch.theme', 'light');
      }, LONG_TITLE_SEED);

      const page = await ctx.newPage();
      await page.goto('http://127.0.0.1:3002/#research', { waitUntil: 'networkidle' });
      await page.waitForTimeout(600);

      const metrics = await page.evaluate((vpWidth) => {
        const docW = document.documentElement.scrollWidth;
        const cliW = document.documentElement.clientWidth;

        // Medição do banner com título longo
        const queryBanner = document.querySelector('.query-banner');
        const bannerRect = queryBanner ? queryBanner.getBoundingClientRect() : null;

        // Quebra e legibilidade do primeiro ponto
        const pointTitle = document.querySelector('.stepper-point-title');
        const pointRect = pointTitle ? pointTitle.getBoundingClientRect() : null;

        return {
          scrollWidth: docW,
          clientWidth: cliW,
          hasHScroll: docW > cliW + 0.5,
          bannerW: bannerRect ? Math.round(bannerRect.width) : 0,
          pointTitleW: pointRect ? Math.round(pointRect.width) : 0,
        };
      }, vp.width);

      console.log(` • [${vp.name}] scrollWidth: ${metrics.scrollWidth}px (client: ${metrics.clientWidth}px) | HScroll: ${metrics.hasHScroll ? 'FAIL' : 'PASS'}`);
      console.log(` • [${vp.name}] bannerWidth: ${metrics.bannerW}px, pointTitleWidth: ${metrics.pointTitleW}px`);

      if (metrics.hasHScroll) {
        findings.push({
          vp: vp.name,
          issue: `Scroll horizontal ativado com título longo: scrollWidth=${metrics.scrollWidth}px > clientWidth=${metrics.clientWidth}px`,
        });
      }

      const shotPath = path.join(OUT_DIR, `pass3-${vp.name}-plan.png`);
      await page.screenshot({ path: shotPath, fullPage: false });

      // Testar também relatório em 1280x720 para checar legibilidade de medida de linha
      if (vp.name === 'laptop-1280x720') {
        await page.goto('http://127.0.0.1:3002/#report', { waitUntil: 'networkidle' });
        await page.waitForTimeout(500);
        const reportMeasure = await page.evaluate(() => {
          const body = document.querySelector('.report-card');
          return body ? Math.round(body.getBoundingClientRect().width) : 0;
        });
        console.log(` • [laptop-1280x720] Largura do Report Card: ${reportMeasure}px`);
        await page.screenshot({ path: path.join(OUT_DIR, `pass3-laptop-1280x720-report.png`), fullPage: false });
      }

      await page.close();
      await ctx.close();
    }

  } finally {
    await browser.close();
  }

  console.log('\n======================================================');
  console.log(`RESUMO AUDITORIA EDGE BREAKPOINTS (PASS 3): ${findings.length} ACHADOS`);
  findings.forEach((f, idx) => {
    console.log(` [${idx + 1}] [${f.vp}]: ${f.issue}`);
  });
  console.log('======================================================\n');
}

runPass3Edge().catch(e => {
  console.error('Erro no pass 3:', e);
  process.exit(1);
});
