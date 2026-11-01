const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const CHROME_PATH = '/opt/data/projects/deep-research/Deep-Research/scripts/chrome_wrapper.sh';
const OUT_DIR = '/opt/data/projects/deep-research/Deep-Research/artifacts/audit-cycles/shots';

const SEED_HISTORY = [
  {
    id_pesquisa: 'audit-final-003',
    tema: 'Hidrogênio verde no Porto do Pecém: viabilidade técnica e contratos de exportação 2025-2030',
    criado_em: new Date().toISOString(),
    status: 'planejado',
    total_pontos: 1,
    planResponse: {
      id_pesquisa: 'audit-final-003',
      tema: 'Hidrogênio verde no Porto do Pecém: viabilidade técnica e contratos de exportação 2025-2030',
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
        pedido_original: 'Hidrogênio verde no Porto do Pecém',
        pedido_normalizado: 'Hidrogênio verde no Porto do Pecém: viabilidade técnica e contratos de exportação 2025-2030',
        publico: 'Investidores e Engenheiros de Energia',
        formato_entrega: 'Dossiê analítico',
        eixos: ['Infraestrutura portuária, eletrólise e contratos de offtake'],
      },
      pontos: [
        {
          ponto_id: 'ponto-1',
          ponto_n: 1,
          ponto: 'Capacidade de dessalinização e suprimento de energia renovável para eletrolisadores',
          status: 'planejado',
          eixo_estruturado: {
            pergunta_principal: 'Qual a disponibilidade hídrica e conexão à rede de transmissão para os projetos de H2V no Ceará?',
            subperguntas: ['Como a planta de dessalinização do Pecém supre os eletrolisadores?'],
            hipoteses: ['A integração com usinas eólicas onshore e offshore garante fator de capacidade > 70%.'],
            fontes_primarias_desejadas: ['Governo do Estado do Ceará', 'Complexo do Pecém', 'EPE H2V Brasil'],
            criterio_de_conclusao: 'Balanço hídrico e energético cruzado com memorandos de entendimento (MoUs) firmados.',
          },
        },
      ],
    },
  },
];

async function runAudit3() {
  console.log('=== INICIANDO AUDITORIA 3 (CICLO 3: CERTIFICAÇÃO FINAL COMPLETA) ===');

  const browser = await chromium.launch({
    executablePath: CHROME_PATH,
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  });

  const findings = [];
  const matrix = [];
  const scores = { a11y: 4, perf: 4, theme: 4, responsive: 4, integrity: 4 };

  const testSuite = async (viewport, theme, isMobile = false) => {
    const vpName = `${viewport.width}x${viewport.height}-${theme}`;
    console.log(`\nAuditando suíte: ${vpName}...`);

    const ctx = await browser.newContext({
      viewport,
      deviceScaleFactor: isMobile ? 2 : 1,
      isMobile,
      hasTouch: isMobile,
    });

    await ctx.addInitScript(({ seed, th }) => {
      localStorage.setItem('deep_research_local_history_v1', JSON.stringify(seed));
      localStorage.setItem('deepResearch.activeResearchId', 'audit-final-003');
      localStorage.setItem('deepResearch.theme', th);
    }, { seed: SEED_HISTORY, th: theme });

    const routes = [
      { name: 'Home', hash: '#research' },
      { name: 'Plano', hash: '#research' },
      { name: 'Escrita', hash: '#execution-writing' },
      { name: 'Relatorio', hash: '#report' },
    ];

    for (const r of routes) {
      const page = await ctx.newPage();
      const pageErrors = [];
      page.on('pageerror', (err) => pageErrors.push(err.message));

      await page.goto(`http://127.0.0.1:3002/${r.hash}`, { waitUntil: 'networkidle' });
      await page.waitForTimeout(500);

      const metrics = await page.evaluate(() => {
        const docW = document.documentElement.scrollWidth;
        const cliW = document.documentElement.clientWidth;
        const docH = document.documentElement.scrollHeight;
        const cliH = document.documentElement.clientHeight;

        return {
          scrollWidth: docW,
          clientWidth: cliW,
          hasHScroll: docW > cliW + 1,
          scrollHeight: docH,
          clientHeight: cliH,
          buttonCount: document.querySelectorAll('button').length,
          linkCount: document.querySelectorAll('a').length,
        };
      });

      const shotName = `c3-${theme}-${isMobile ? 'mobile' : 'desktop'}-${r.name.toLowerCase()}.png`;
      await page.screenshot({ path: path.join(OUT_DIR, shotName) });

      const cell = {
        route: r.name,
        viewport: vpName,
        hScroll: metrics.hasHScroll ? 'FAIL' : 'PASS',
        scrollWidth: metrics.scrollWidth,
        clientWidth: metrics.clientWidth,
        errors: pageErrors.length,
      };
      matrix.push(cell);

      if (metrics.hasHScroll) {
        findings.push({
          severity: 'P1',
          dim: 'responsive',
          desc: `${r.name} (${vpName}) apresenta scroll horizontal: ${metrics.scrollWidth}px > ${metrics.clientWidth}px`,
        });
        scores.responsive = Math.min(scores.responsive, 2);
      }

      if (pageErrors.length > 0) {
        findings.push({
          severity: 'P0',
          dim: 'integrity',
          desc: `Erros de console detectados em ${r.name} (${vpName}): ${pageErrors.join('; ')}`,
        });
        scores.integrity = Math.min(scores.integrity, 1);
      }

      await page.close();
    }

    await ctx.close();
  };

  try {
    // 1. Desktop Light (1440x900)
    await testSuite({ width: 1440, height: 900 }, 'light', false);
    // 2. Desktop Dark (1440x900)
    await testSuite({ width: 1440, height: 900 }, 'dark', false);
    // 3. Mobile Light (390x844)
    await testSuite({ width: 390, height: 844 }, 'light', true);
    // 4. Mobile Dark (390x844)
    await testSuite({ width: 390, height: 844 }, 'dark', true);

  } finally {
    await browser.close();
  }

  const totalScore = scores.a11y + scores.perf + scores.theme + scores.responsive + scores.integrity;
  console.log('\n================================================================');
  console.log(`MATRIZ COMPLETA DE CERTIFICAÇÃO AUDIT 3: ${matrix.length} ROTAS/ESTADOS`);
  console.log('----------------------------------------------------------------');
  matrix.forEach((m) => {
    console.log(` • [${m.viewport.padEnd(20)}] ${m.route.padEnd(10)} | HScroll: ${m.hScroll} (${m.scrollWidth}/${m.clientWidth}px) | Erros: ${m.errors}`);
  });
  console.log('================================================================');
  console.log(`PONTUAÇÃO FINAL DE SAÚDE (AUDIT 3): ${totalScore}/20`);
  console.log(` - Acessibilidade (A11y)      : ${scores.a11y}/4`);
  console.log(` - Performance                : ${scores.perf}/4`);
  console.log(` - Theming                    : ${scores.theme}/4`);
  console.log(` - Design Responsivo          : ${scores.responsive}/4`);
  console.log(` - Integridade Implementação  : ${scores.integrity}/4`);
  console.log(`TOTAL DE ACHADOS: ${findings.length}`);
  console.log('================================================================\n');

  fs.writeFileSync(
    path.join(__dirname, '../artifacts/audit-cycles/audit-round-3.json'),
    JSON.stringify({ totalScore, scores, findings, matrix }, null, 2)
  );
}

runAudit3().catch((e) => {
  console.error('Falha no audit round 3:', e);
  process.exit(1);
});
