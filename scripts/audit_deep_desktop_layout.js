const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const CHROME_PATH = '/opt/data/projects/deep-research/Deep-Research/scripts/chrome_wrapper.sh';
const OUT_DIR = '/opt/data/projects/deep-research/Deep-Research/artifacts/audit-cycles/shots/pass2-desktop';

const SEED_HISTORY = [
  {
    id_pesquisa: 'audit-deep-desktop-001',
    tema: 'Semicondutores de banda larga (SiC e GaN) no Brasil: fabricação e integração em eletrônica de potência 2026',
    criado_em: new Date().toISOString(),
    status: 'planejado',
    total_pontos: 2,
    planResponse: {
      id_pesquisa: 'audit-deep-desktop-001',
      tema: 'Semicondutores de banda larga (SiC e GaN) no Brasil: fabricação e integração em eletrônica de potência 2026',
      n_pontos: 2,
      criado_em: new Date().toISOString(),
      status_pipeline: 'planejado',
      preferencias: {
        n_pontos: 2,
        personas: ['historiador', 'visionario', 'cetico', 'futurista'],
        execution_mode: 'parallel',
        recencia: '24h',
        criterios_minimos: 12,
      },
      plano_estruturado: {
        pedido_original: 'Semicondutores SiC e GaN no Brasil',
        pedido_normalizado: 'Semicondutores de banda larga (SiC e GaN) no Brasil: fabricação e integração em eletrônica de potência 2026',
        publico: 'Engenheiros de Sistemas e Especialistas em Microeletrônica',
        formato_entrega: 'Dossiê analítico',
        eixos: [
          'Capacidade instalada de encapsulamento e testes (back-end)',
          'Incentivos do PADIS e atração de fundições internacionais',
        ],
      },
      pontos: [
        {
          ponto_id: 'ponto-1',
          ponto_n: 1,
          ponto: 'Capacidade instalada de encapsulamento e testes (back-end) no polo de semicondutores de São Paulo e RS',
          status: 'planejado',
          eixo_estruturado: {
            pergunta_principal: 'Quais indústrias nacionais operam linhas de montagem para módulos de potência baseados em SiC?',
            subperguntas: ['Qual o gap tecnológico frente aos centros de Taiwan e EUA?'],
            hipoteses: ['O Brasil possui linhas de encapsulamento consolidadas para inversores solares e tração automotiva.'],
            fontes_primarias_desejadas: ['ABISEMI', 'MCTI Relatório', 'Eldorado Pesquisa'],
            criterio_de_conclusao: 'Mapeamento de capacidade de produção por empresa instalada.',
          },
        },
        {
          ponto_id: 'ponto-2',
          ponto_n: 2,
          ponto: 'Evolução dos incentivos do PADIS para dispositivos de banda ultralarga (WBG)',
          status: 'planejado',
          eixo_estruturado: {
            pergunta_principal: 'Como a renovação do PADIS contempla crédito financeiro para P&D de componentes GaN?',
            subperguntas: ['Quais montadoras demandam módulos SiC locais?'],
            hipoteses: ['Os benefícios fiscais equilibram o custo de importação de wafers brutos.'],
            fontes_primarias_desejadas: ['Receita Federal IN PADIS', 'MDIC Brasil', 'BNDES Inovação'],
            criterio_de_conclusao: 'Análise cruzada dos relatórios de renúncia fiscal e investimentos declarados.',
          },
        },
      ],
    },
  },
];

async function runPass2Desktop() {
  fs.mkdirSync(OUT_DIR, { recursive: true });
  console.log('=== PASS 2: AUDITORIA PROFUNDA DE LAYOUT E DENSIDADE DESKTOP (1440x900) ===');

  const browser = await chromium.launch({
    executablePath: CHROME_PATH,
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  });

  const findings = [];

  try {
    const ctx = await browser.newContext({
      viewport: { width: 1440, height: 900 },
      deviceScaleFactor: 1,
    });

    await ctx.addInitScript((seed) => {
      localStorage.setItem('deep_research_local_history_v1', JSON.stringify(seed));
      localStorage.setItem('deepResearch.activeResearchId', 'audit-deep-desktop-001');
      localStorage.setItem('deepResearch.theme', 'light');
    }, SEED_HISTORY);

    const routes = [
      { id: 'home', hash: '#research', title: 'Home / Inicial' },
      { id: 'plan', hash: '#research', title: 'Plano (com eixos gerados)' },
      { id: 'writing', hash: '#execution-writing', title: 'Execução / Síntese' },
      { id: 'report', hash: '#report', title: 'Dossiê / Relatório Final' },
      { id: 'settings', hash: '#settings', title: 'Configurações' },
    ];

    for (const r of routes) {
      console.log(`\nInspecionando rota desktop: ${r.title} (${r.hash})...`);
      const page = await ctx.newPage();
      await page.goto(`http://127.0.0.1:3002/${r.hash}`, { waitUntil: 'networkidle' });
      await page.waitForTimeout(600);

      const metrics = await page.evaluate(() => {
        const docW = document.documentElement.scrollWidth;
        const cliW = document.documentElement.clientWidth;

        // Medição das colunas desktop
        const sidebar = document.querySelector('.app-sidebar');
        const main = document.querySelector('.workspace-main');
        const rail = document.querySelector('.context-sidebar, .rr-rail');
        const reportBody = document.querySelector('.report-body, .prose, .report-card');

        const sidebarW = sidebar ? Math.round(sidebar.getBoundingClientRect().width) : 0;
        const mainW = main ? Math.round(main.getBoundingClientRect().width) : 0;
        const railW = rail ? Math.round(rail.getBoundingClientRect().width) : 0;
        const reportBodyW = reportBody ? Math.round(reportBody.getBoundingClientRect().width) : 0;

        // Checar gaps vazios gigantes entre elementos principais (> 60px)
        const emptyGaps = [];
        const blocks = Array.from(document.querySelectorAll('.query-banner, .plan-card, .execution-heading-row, .report-card, .composer-box'));
        for (let i = 0; i < blocks.length - 1; i++) {
          const r1 = blocks[i].getBoundingClientRect();
          const r2 = blocks[i + 1].getBoundingClientRect();
          const gap = r2.top - r1.bottom;
          if (gap > 60) {
            emptyGaps.push({ from: blocks[i].className.slice(0, 25), to: blocks[i + 1].className.slice(0, 25), gap: Math.round(gap) });
          }
        }

        // Elementos que ultrapassam a largura de 1440px
        const overflows = [];
        document.querySelectorAll('*').forEach(el => {
          if (el.tagName === 'svg' || el.closest('svg') || el.tagName === 'BODY' || el.tagName === 'HTML' || el.classList.contains('ambient-blob')) return;
          const rect = el.getBoundingClientRect();
          if (rect.right > 1440.5) {
            overflows.push({ tag: el.tagName, cls: typeof el.className === 'string' ? el.className.slice(0, 30) : '', r: Math.round(rect.right) });
          }
        });

        return {
          scrollWidth: docW,
          clientWidth: cliW,
          sidebarW,
          mainW,
          railW,
          reportBodyW,
          emptyGaps,
          overflowCount: overflows.length,
          sampleOverflow: overflows.slice(0, 2),
        };
      });

      console.log(` • Larguras no layout: Sidebar=${metrics.sidebarW}px, Main=${metrics.mainW}px, Rail=${metrics.railW}px, ReportBody=${metrics.reportBodyW}px`);
      console.log(` • scrollWidth: ${metrics.scrollWidth}px (client: ${metrics.clientWidth}px)`);

      if (metrics.overflowCount > 0) {
        findings.push({
          route: r.id,
          type: 'overflow',
          desc: `${metrics.overflowCount} elementos ultrapassando a viewport desktop em ${r.title} (ex: ${metrics.sampleOverflow[0].tag}.${metrics.sampleOverflow[0].cls})`,
        });
      }

      if (metrics.emptyGaps.length > 0) {
        findings.push({
          route: r.id,
          type: 'empty-space',
          desc: `Espaço ocioso detectado em ${r.title}: gap de ${metrics.emptyGaps[0].gap}px entre ${metrics.emptyGaps[0].from} e ${metrics.emptyGaps[0].to}`,
        });
      }

      const shotPath = path.join(OUT_DIR, `pass2-desktop-${r.id}.png`);
      await page.screenshot({ path: shotPath, fullPage: false });
      console.log(` • Screenshot desktop salva: ${shotPath}`);

      await page.close();
    }

  } finally {
    await browser.close();
  }

  console.log('\n======================================================');
  console.log(`RESUMO AUDITORIA DESKTOP (PASS 2): ${findings.length} ACHADOS`);
  findings.forEach((f, idx) => {
    console.log(` [${idx + 1}] [${f.type.toUpperCase()}] (${f.route}): ${f.desc}`);
  });
  console.log('======================================================\n');
}

runPass2Desktop().catch(e => {
  console.error('Erro no pass 2:', e);
  process.exit(1);
});
