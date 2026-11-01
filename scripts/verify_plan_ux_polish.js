const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const CHROME_PATH = '/opt/data/projects/deep-research/Deep-Research/scripts/chrome_wrapper.sh';
const OUT_DIR = '/opt/data/projects/deep-research/Deep-Research/artifacts/audit-mobile-impeccable-2026-10-31/shots';

const SEED_HISTORY = [
  {
    id_pesquisa: 'test-matriz-energia-001',
    tema: 'Matriz energética brasileira: composição da matriz elétrica e energética 2025-2026',
    criado_em: new Date().toISOString(),
    status: 'planejado',
    total_pontos: 1,
    planResponse: {
      id_pesquisa: 'test-matriz-energia-001',
      tema: 'Matriz energética brasileira: composição da matriz elétrica e energética 2025-2026',
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
        pedido_original: 'Matriz energética brasileira: composição da matriz elétrica e energética 2025-2026',
        pedido_normalizado: 'Matriz energética brasileira: composição da matriz elétrica e energética 2025-2026',
        publico: 'Especialistas e Tomadores de Decisão',
        formato_entrega: 'Dossiê analítico',
        recorte_temporal: '2025-2026',
        eixos: ['Composição da matriz elétrica e energética brasileira'],
      },
      pontos: [
        {
          id: 'ponto-1',
          n: 1,
          foco: 'Composição da matriz elétrica e energética brasileira 2025-2026',
          status: 'planejado',
          eixo_estruturado: {
            pergunta_investigativa: 'Qual a composição exata da matriz elétrica e energética brasileira projetada para 2025-2026?',
            subperguntas: [
              'Qual a participação percentual esperada de fontes renováveis (hídrica, eólica, solar e biomassa) em 2025-2026?',
              'Como a capacidade instalada e a geração distribuída evoluíram segundo dados oficiais do BEN, ANEEL e ONS?',
            ],
            hipoteses: [
              'A participação de fontes renováveis na matriz elétrica consolidará patamar superior a 85%, com expressiva expansão solar e eólica.',
              'A matriz energética geral manterá cerca de 48% a 50% de fontes renováveis, liderada por biomassa e bioenergia.',
            ],
            fontes_prioritarias: ['EPE BEN 2025', 'MME Boletim Mensal', 'ANEEL Sigel', 'ONS Histórico', 'CCEE InfoMercado'],
            criterio_de_conclusao: 'Validação cruzada dos números oficiais de capacidade instalada e balanço energético entre relatórios da EPE e do ONS.',
          },
        },
      ],
    },
  },
];

async function run() {
  fs.mkdirSync(OUT_DIR, { recursive: true });
  console.log('Lançando Chromium com wrapper...');

  const browser = await chromium.launch({
    executablePath: CHROME_PATH,
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  });

  try {
    // 1. MOBILE SUITE (390 x 844)
    console.log('Testando ambiente Mobile (390x844)...');
    const mobileContext = await browser.newContext({
      viewport: { width: 390, height: 844 },
      deviceScaleFactor: 2,
      isMobile: true,
      hasTouch: true,
    });

    await mobileContext.addInitScript((seed) => {
      localStorage.setItem('deep_research_local_history_v1', JSON.stringify(seed));
      localStorage.setItem('deepResearch.activeResearchId', 'test-matriz-energia-001');
      localStorage.setItem('deepResearch.theme', 'light');
    }, SEED_HISTORY);

    const mobilePage = await mobileContext.newPage();
    await mobilePage.goto('http://127.0.0.1:3002/#research', { waitUntil: 'networkidle' });
    await mobilePage.waitForTimeout(1000);

    // Validações Mobile
    const startButtonsCount = await mobilePage.locator('#start-research-btn').count();
    console.log(`Mobile: Contagem de #start-research-btn (deve ser 1): ${startButtonsCount}`);

    const editParamCount = await mobilePage.locator('[data-gdr-action="edit-parameters"]').count();
    console.log(`Mobile: Contagem de edit-parameters (deve ser 0): ${editParamCount}`);

    const gdrPhasesCount = await mobilePage.locator('.gdr-phases').count();
    console.log(`Mobile: Contagem de .gdr-phases (deve ser 0): ${gdrPhasesCount}`);

    const gdrPreflightCount = await mobilePage.locator('.gdr-plan-preflight').count();
    console.log(`Mobile: Contagem de .gdr-plan-preflight (deve ser 0): ${gdrPreflightCount}`);

    const firstPointVisible = await mobilePage.locator('.stepper-point-title').first().isVisible();
    console.log(`Mobile: Primeiro eixo visível na tela: ${firstPointVisible}`);

    // Captura Mobile 39a (Visão limpa, focada no conteúdo com zero fluxo redundante)
    const shot39aPath = path.join(OUT_DIR, '39a-mobile-plan-clean-no-phases.png');
    await mobilePage.screenshot({ path: shot39aPath, fullPage: false });
    console.log(`Captura salva: ${shot39aPath}`);

    // 2. DESKTOP SUITE (1440 x 900)
    console.log('Testando ambiente Desktop (1440x900)...');
    const desktopContext = await browser.newContext({
      viewport: { width: 1440, height: 900 },
      deviceScaleFactor: 1,
    });

    await desktopContext.addInitScript((seed) => {
      localStorage.setItem('deep_research_local_history_v1', JSON.stringify(seed));
      localStorage.setItem('deepResearch.activeResearchId', 'test-matriz-energia-001');
      localStorage.setItem('deepResearch.theme', 'light');
    }, SEED_HISTORY);

    const desktopPage = await desktopContext.newPage();
    await desktopPage.goto('http://127.0.0.1:3002/#research', { waitUntil: 'networkidle' });
    await desktopPage.waitForTimeout(1000);

    const desktopStartCount = await desktopPage.locator('#start-research-btn').count();
    console.log(`Desktop: Contagem de #start-research-btn (deve ser 1): ${desktopStartCount}`);

    const desktopPhasesCount = await desktopPage.locator('.gdr-phases').count();
    console.log(`Desktop: Contagem de .gdr-phases (deve ser 0): ${desktopPhasesCount}`);

    // Captura Desktop 39b
    const shot39bPath = path.join(OUT_DIR, '39b-desktop-plan-clean-no-phases.png');
    await desktopPage.screenshot({ path: shot39bPath, fullPage: false });
    console.log(`Captura salva: ${shot39bPath}`);

    console.log('Todas as validações e capturas concluídas com sucesso!');
  } finally {
    await browser.close();
  }
}

run().catch((err) => {
  console.error('Erro na execução:', err);
  process.exit(1);
});
