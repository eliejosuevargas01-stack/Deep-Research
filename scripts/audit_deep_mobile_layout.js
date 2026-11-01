const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const CHROME_PATH = '/opt/data/projects/deep-research/Deep-Research/scripts/chrome_wrapper.sh';
const OUT_DIR = '/opt/data/projects/deep-research/Deep-Research/artifacts/audit-cycles/shots/pass1-mobile';

const SEED_HISTORY = [
  {
    id_pesquisa: 'audit-deep-mobile-001',
    tema: 'Descarbonização do setor de transportes pesados no Brasil: biocombustíveis avançados vs eletrificação a bateria 2026-2035',
    criado_em: new Date().toISOString(),
    status: 'planejado',
    total_pontos: 3,
    planResponse: {
      id_pesquisa: 'audit-deep-mobile-001',
      tema: 'Descarbonização do setor de transportes pesados no Brasil: biocombustíveis avançados vs eletrificação a bateria 2026-2035',
      n_pontos: 3,
      criado_em: new Date().toISOString(),
      status_pipeline: 'planejado',
      preferencias: {
        n_pontos: 3,
        personas: ['historiador', 'visionario', 'cetico', 'futurista'],
        execution_mode: 'parallel',
        recencia: '24h',
        criterios_minimos: 12,
      },
      plano_estruturado: {
        pedido_original: 'Descarbonização do transporte pesado',
        pedido_normalizado: 'Descarbonização do transporte rodoviário de carga',
        publico: 'Operadores logísticos e montadoras',
        formato_entrega: 'Dossiê técnico-econômico',
        eixos: [
          'Competitividade do HVO e biometano vs diesel fóssil',
          'TCO de caminhões elétricos pesados com recarga megawatt',
          'Gargalos de infraestrutura de abastecimento e rede elétrica',
        ],
      },
      pontos: [
        {
          ponto_id: 'ponto-1',
          ponto_n: 1,
          ponto: 'Competitividade do HVO e biometano vs diesel fóssil nas principais rotas de escoamento agrícola',
          status: 'planejado',
          eixo_estruturado: {
            pergunta_principal: 'Qual a paridade de custo por km rodado entre HVO, biometano e diesel S10?',
            subperguntas: ['Quais incentivos tributários e mandatos de mistura influenciam o preço final na bomba?'],
            hipoteses: ['Biometano comprimido apresenta paridade imediata em rotas com oferta de biogás agroindustrial.'],
            fontes_primarias_desejadas: ['EPE Combustíveis 2025', 'ANP Anuário', 'CNT Boletim Econômico'],
            criterio_de_conclusao: 'Validação da planilha de custo nivelado de transporte (LCOT).',
          },
        },
        {
          ponto_id: 'ponto-2',
          ponto_n: 2,
          ponto: 'TCO de caminhões elétricos pesados com recarga megawatt e autonomia rodoviária',
          status: 'planejado',
          eixo_estruturado: {
            pergunta_principal: 'Em que horizonte temporal o custo total de propriedade (TCO) de cavalos mecânicos elétricos empata com diesel?',
            subperguntas: ['Como o custo de substituição de baterias impacta o valor residual da frota?'],
            hipoteses: ['O empate ocorre entre 2029 e 2031 para frotas rodando mais de 12.000 km/mês.'],
            fontes_primarias_desejadas: ['ICCT Brasil', 'ANFAVEA Relatório', 'BNDES Setorial'],
            criterio_de_conclusao: 'Curva de amortização do custo de aquisição adicional frente à economia de combustível.',
          },
        },
        {
          ponto_id: 'ponto-3',
          ponto_n: 3,
          ponto: 'Gargalos de infraestrutura de abastecimento e capacidade da rede de distribuição para eletropostos pesados',
          status: 'planejado',
          eixo_estruturado: {
            pergunta_principal: 'Quais corredores rodoviários demandam reforço prioritário de subestações para estações MCS?',
            subperguntas: ['Qual a potência simultânea requerida por pátio de triagem logístico?'],
            hipoteses: ['Corredores BR-163 e BR-050 exigem conexão direta em alta tensão (>69 kV) para viabilizar múltiplos carregadores de 1 MW.'],
            fontes_primarias_desejadas: ['ONS Planejamento', 'EPL Logística', 'ABRAPCH'],
            criterio_de_conclusao: 'Mapeamento georreferenciado das subestações com capacidade ociosa.',
          },
        },
      ],
    },
  },
];

async function runPass1Mobile() {
  fs.mkdirSync(OUT_DIR, { recursive: true });
  console.log('=== PASS 1: AUDITORIA PROFUNDA DE LAYOUT E ESPAÇO MOBILE (390x844) ===');

  const browser = await chromium.launch({
    executablePath: CHROME_PATH,
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  });

  const findings = [];

  try {
    const ctx = await browser.newContext({
      viewport: { width: 390, height: 844 },
      deviceScaleFactor: 2,
      isMobile: true,
      hasTouch: true,
    });

    await ctx.addInitScript((seed) => {
      localStorage.setItem('deep_research_local_history_v1', JSON.stringify(seed));
      localStorage.setItem('deepResearch.activeResearchId', 'audit-deep-mobile-001');
      localStorage.setItem('deepResearch.theme', 'light');
    }, SEED_HISTORY);

    const routes = [
      { id: 'home', hash: '#research', title: 'Home / Inicial' },
      { id: 'plan', hash: '#research', title: 'Plano (com pesquisa ativa)' },
      { id: 'writing', hash: '#execution-writing', title: 'Execução / Síntese' },
      { id: 'report', hash: '#report', title: 'Dossiê / Relatório' },
      { id: 'settings', hash: '#settings', title: 'Configurações' },
    ];

    for (const r of routes) {
      console.log(`\nInspecionando rota mobile: ${r.title} (${r.hash})...`);
      const page = await ctx.newPage();
      await page.goto(`http://127.0.0.1:3002/${r.hash}`, { waitUntil: 'networkidle' });
      await page.waitForTimeout(600);

      // Medição geométrica da página
      const metrics = await page.evaluate(() => {
        const docEl = document.documentElement;
        const body = document.body;

        // Elementos que excedem a largura de 390px
        const clippingElements = [];
        document.querySelectorAll('*').forEach((el) => {
          if (el.tagName === 'svg' || el.closest('svg') || el.tagName === 'BODY' || el.tagName === 'HTML') return;
          const rect = el.getBoundingClientRect();
          if (rect.right > 390.5 || rect.left < -0.5) {
            clippingElements.push({
              tag: el.tagName,
              cls: typeof el.className === 'string' ? el.className.slice(0, 35) : '',
              left: Math.round(rect.left),
              right: Math.round(rect.right),
              width: Math.round(rect.width),
            });
          }
        });

        // Espaços verticais vazios excessivos (> 48px entre blocos contíguos)
        const excessiveGaps = [];
        const mainBlocks = Array.from(document.querySelectorAll('.plan-card, .query-banner, .execution-card, .report-card, .composer-box, .hero-container, .settings-card'));
        for (let i = 0; i < mainBlocks.length - 1; i++) {
          const r1 = mainBlocks[i].getBoundingClientRect();
          const r2 = mainBlocks[i + 1].getBoundingClientRect();
          const gap = r2.top - r1.bottom;
          if (gap > 48) {
            excessiveGaps.push({ from: mainBlocks[i].className.slice(0, 25), to: mainBlocks[i + 1].className.slice(0, 25), gap: Math.round(gap) });
          }
        }

        // Padding inferior para não colidir com o dock/tabbar (dock tem ~58px)
        const bottomPadding = parseFloat(window.getComputedStyle(document.querySelector('.workspace-main') || body).paddingBottom) || 0;

        return {
          scrollWidth: docEl.scrollWidth,
          clientWidth: docEl.clientWidth,
          scrollHeight: docEl.scrollHeight,
          clientHeight: docEl.clientHeight,
          clippingCount: clippingElements.length,
          sampleClipping: clippingElements.slice(0, 3),
          excessiveGaps,
          bottomPadding,
        };
      });

      console.log(` • scrollWidth: ${metrics.scrollWidth}px (client: ${metrics.clientWidth}px)`);
      console.log(` • scrollHeight: ${metrics.scrollHeight}px (client: ${metrics.clientHeight}px)`);
      console.log(` • bottomPadding do workspace: ${metrics.bottomPadding}px`);

      if (metrics.clippingCount > 0) {
        console.log(` • AVISO: ${metrics.clippingCount} elementos ultrapassando bordas horizontais!`);
        metrics.sampleClipping.forEach(c => console.log(`   -> ${c.tag}.${c.cls}: left=${c.left}px, right=${c.right}px, w=${c.width}px`));
        findings.push({
          route: r.id,
          type: 'clipping',
          desc: `${metrics.clippingCount} elementos excedendo bordas na rota ${r.title} (ex: ${metrics.sampleClipping[0].tag}.${metrics.sampleClipping[0].cls})`,
        });
      }

      if (metrics.excessiveGaps.length > 0) {
        console.log(` • AVISO: Espaços verticais excessivos detectados:`, metrics.excessiveGaps);
        findings.push({
          route: r.id,
          type: 'empty-space',
          desc: `Espaço ocioso excessivo na rota ${r.title}: gap de ${metrics.excessiveGaps[0].gap}px entre ${metrics.excessiveGaps[0].from} e ${metrics.excessiveGaps[0].to}`,
        });
      }

      // Captura de tela da rota
      const shotPath = path.join(OUT_DIR, `pass1-mobile-${r.id}.png`);
      await page.screenshot({ path: shotPath, fullPage: false });
      console.log(` • Screenshot viewport salva: ${shotPath}`);

      // Scroll para metade da página se for longa
      if (metrics.scrollHeight > 1000) {
        await page.evaluate(() => window.scrollBy(0, 600));
        await page.waitForTimeout(300);
        const shotScrollPath = path.join(OUT_DIR, `pass1-mobile-${r.id}-scroll.png`);
        await page.screenshot({ path: shotScrollPath, fullPage: false });
        console.log(` • Screenshot scroll salva: ${shotScrollPath}`);
      }

      await page.close();
    }

  } finally {
    await browser.close();
  }

  console.log('\n======================================================');
  console.log(`RESUMO AUDITORIA MOBILE (PASS 1): ${findings.length} ACHADOS DE LAYOUT/ESPAÇO`);
  findings.forEach((f, idx) => {
    console.log(` [${idx + 1}] [${f.type.toUpperCase()}] (${f.route}): ${f.desc}`);
  });
  console.log('======================================================\n');
}

runPass1Mobile().catch(e => {
  console.error('Erro no pass 1:', e);
  process.exit(1);
});
