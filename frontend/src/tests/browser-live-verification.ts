/**
 * Browser Live Verification Script on Fixture (http://localhost:8011)
 * Uses real Playwright with edge fault injection (first audit 504, subsequent forward).
 * Captures real screenshots and measures exact viewport geometry.
 */
import { chromium } from 'playwright';
import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';
import assert from 'node:assert/strict';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const EVIDENCE_DIR = path.resolve(__dirname, '../../../frontend-recovery-browser-evidence');
const BASE_URL = 'http://localhost:8011';

async function runBrowserVerification() {
  if (!fs.existsSync(EVIDENCE_DIR)) {
    fs.mkdirSync(EVIDENCE_DIR, { recursive: true });
  }

  console.log('--- Iniciando Verificação no Navegador com App Real e Injeção de Falha ---');

  const browser = await chromium.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
  });

  try {
    // =======================================================================
    // PARTE 1: Geometria do Painel de Preferências em 3 Viewports
    // =======================================================================
    console.log('\n[Etapa 1] Testando geometria do painel em 1280x578 (Desktop Baixo)...');
    const ctxDesktop = await browser.newContext({ viewport: { width: 1280, height: 578 } });
    const pageDesktop = await ctxDesktop.newPage();
    await pageDesktop.goto(BASE_URL);
    await pageDesktop.waitForSelector('#root');
    await pageDesktop.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await pageDesktop.locator('#preferences-toggle-btn').click();
    await pageDesktop.waitForSelector('#preferences-popover-panel');

    const geom1280 = await pageDesktop.evaluate(() => {
      const panel = document.querySelector('#preferences-popover-panel')!;
      const header = panel.querySelector('.preferences-header')!;
      const r = panel.getBoundingClientRect();
      const hr = header.getBoundingClientRect();
      return {
        windowH: window.innerHeight,
        panelTop: r.top,
        panelBottom: r.bottom,
        panelHeight: r.height,
        headerTop: hr.top,
        headerBottom: hr.bottom,
        isTopClipped: r.top < 0,
        isHeaderClipped: hr.top < 0,
      };
    });
    console.log('Geometria 1280x578:', geom1280);
    assert.equal(geom1280.isTopClipped, false, 'Painel não deve estar cortado no topo em 1280x578');
    assert.equal(geom1280.isHeaderClipped, false, 'Cabeçalho não deve estar cortado no topo em 1280x578');
    await pageDesktop.screenshot({ path: path.join(EVIDENCE_DIR, '01-preferences-bounded-1280x578.png'), fullPage: true });
    await ctxDesktop.close();

    console.log('\n[Etapa 2] Testando geometria do painel em 375x667 (Mobile Retrato)...');
    const ctxMobile = await browser.newContext({ viewport: { width: 375, height: 667 } });
    const pageMobile = await ctxMobile.newPage();
    await pageMobile.goto(BASE_URL);
    await pageMobile.waitForSelector('#root');
    await pageMobile.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await pageMobile.locator('#preferences-toggle-btn').click();
    await pageMobile.waitForSelector('#preferences-popover-panel');

    const geom375 = await pageMobile.evaluate(() => {
      const panel = document.querySelector('#preferences-popover-panel')!;
      const header = panel.querySelector('.preferences-header')!;
      const r = panel.getBoundingClientRect();
      const hr = header.getBoundingClientRect();
      return {
        windowH: window.innerHeight,
        panelTop: r.top,
        panelBottom: r.bottom,
        panelHeight: r.height,
        headerTop: hr.top,
        isTopClipped: r.top < 0,
        isHeaderClipped: hr.top < 0,
      };
    });
    console.log('Geometria 375x667:', geom375);
    assert.equal(geom375.isTopClipped, false, 'Painel não deve estar cortado no topo em 375x667');
    assert.equal(geom375.isHeaderClipped, false, 'Cabeçalho não deve estar cortado no topo em 375x667');
    await pageMobile.screenshot({ path: path.join(EVIDENCE_DIR, '02-preferences-bounded-375x667.png'), fullPage: true });
    await ctxMobile.close();

    console.log('\n[Etapa 3] Testando geometria do painel em 667x375 (Mobile Paisagem)...');
    const ctxLandscape = await browser.newContext({ viewport: { width: 667, height: 375 } });
    const pageLandscape = await ctxLandscape.newPage();
    await pageLandscape.goto(BASE_URL);
    await pageLandscape.waitForSelector('#root');
    await pageLandscape.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await pageLandscape.locator('#preferences-toggle-btn').click();
    await pageLandscape.waitForSelector('#preferences-popover-panel');

    const geom667 = await pageLandscape.evaluate(() => {
      const panel = document.querySelector('#preferences-popover-panel')!;
      const header = panel.querySelector('.preferences-header')!;
      const r = panel.getBoundingClientRect();
      const hr = header.getBoundingClientRect();
      return {
        windowH: window.innerHeight,
        panelTop: r.top,
        panelBottom: r.bottom,
        panelHeight: r.height,
        headerTop: hr.top,
        isTopClipped: r.top < 0,
        isHeaderClipped: hr.top < 0,
      };
    });
    console.log('Geometria 667x375:', geom667);
    assert.equal(geom667.isTopClipped, false, 'Painel não deve estar cortado no topo em 667x375');
    assert.equal(geom667.isHeaderClipped, false, 'Cabeçalho não deve estar cortado no topo em 667x375');
    await pageLandscape.screenshot({ path: path.join(EVIDENCE_DIR, '03-preferences-bounded-667x375.png'), fullPage: true });
    await ctxLandscape.close();

    // =======================================================================
    // PARTE 2: Preservação de Rascunho em Memória em Configurações
    // =======================================================================
    console.log('\n[Etapa 4] Verificando rascunho em memória através de navegação por hash...');
    const ctxSettings = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const pageSettings = await ctxSettings.newPage();
    await pageSettings.goto(`${BASE_URL}#settings`);
    await pageSettings.waitForSelector('#settings-heading');

    // Digita URL segura pública
    await pageSettings.locator('#llm-base-url').fill('https://api.openai.com/v1');

    // Navega para #research (desmontando SettingsView)
    await pageSettings.locator('.nav-links a:has-text("Pesquisa")').click();
    await pageSettings.waitForFunction(() => window.location.hash.includes('research') || window.location.hash === '');

    // Retorna para #settings (remontando SettingsView com draft)
    await pageSettings.locator('.nav-links a:has-text("Configurações")').click();
    await pageSettings.waitForSelector('#settings-heading');

    const preservedValue = await pageSettings.locator('#llm-base-url').inputValue();
    console.log('Valor recuperado da memória em #llm-base-url:', preservedValue);
    assert.equal(preservedValue, 'https://api.openai.com/v1', 'Valor digitado deve ser preservado em memória');

    const alertVisible = await pageSettings.locator('.alert-banner.warning:has-text("preservadas em memória")').isVisible();
    assert.equal(alertVisible, true, 'Banner de rascunho ativo deve estar visível');

    await pageSettings.screenshot({ path: path.join(EVIDENCE_DIR, '04-settings-inmemory-draft-preserved.png'), fullPage: true });

    // Clica em descartar rascunho
    await pageSettings.locator('button:has-text("Descartar rascunho")').first().click();
    const discardedValue = await pageSettings.locator('#llm-base-url').inputValue();
    assert.equal(discardedValue, '', 'Campo esvaziado após descarte explícito');
    await ctxSettings.close();

    // =======================================================================
    // PARTE 3: Plano Legado sem Preferências (Sem Adivinhar 4)
    // =======================================================================
    console.log('\n[Etapa 5] Verificando abertura de plano legado sem snapshot no workspace...');
    const ctxLegacy = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const pageLegacy = await ctxLegacy.newPage();
    await pageLegacy.addInitScript(() => {
      const legacyRec = {
        id_pesquisa: 'legacy-browser-uuid',
        tema: 'Pesquisa Histórica Legada (Sem Snapshot)',
        criado_em: new Date().toISOString(),
        status: 'planejado',
        total_pontos: 2,
        planResponse: {
          id_pesquisa: 'legacy-browser-uuid',
          tema: 'Pesquisa Histórica Legada (Sem Snapshot)',
          n_pontos: 2,
          criado_em: new Date().toISOString(),
          pontos: [
            { ponto_id: 'p1', ponto_n: 1, ponto: 'Ponto 1', status: 'pendente' },
            { ponto_id: 'p2', ponto_n: 2, ponto: 'Ponto 2', status: 'pendente' },
          ],
        },
      };
      localStorage.setItem('deep_research_local_history_v1', JSON.stringify([legacyRec]));
    });

    await pageLegacy.goto(`${BASE_URL}#history`);
    await pageLegacy.waitForSelector('.history-item-card');
    await pageLegacy.locator('.history-item-card button:has-text("Abrir")').click();
    await pageLegacy.waitForSelector('.plan-card');

    const chipText = await pageLegacy.locator('.plan-snapshot-chips .pill-indigo').textContent();
    console.log('Texto do chip de snapshot de personas:', chipText?.trim());
    assert.equal(chipText?.trim(), 'Personas analíticas', 'Plano legado deve exibir "Personas analíticas"');

    const fullPlanText = await pageLegacy.locator('#plan-workspace').textContent();
    assert.equal(fullPlanText?.includes('4 personas ativas'), false, 'Não deve inventar 4 personas');
    await pageLegacy.screenshot({ path: path.join(EVIDENCE_DIR, '05-legacy-plan-no-guess4.png'), fullPage: true });
    await ctxLegacy.close();

    // =======================================================================
    // PARTE 4: Injeção de Falha Real de Borda: 1ª Auditoria 504 -> Retry Só Audita
    // =======================================================================
    console.log('\n[Etapa 6] Execução integrada com injeção de falha de borda (504 na 1ª auditoria)...');
    const ctxFault = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const pageFault = await ctxFault.newPage();

    let searchRequests = 0;
    let auditRequests = 0;
    let writerRequests = 0;

    await pageFault.route('**/api/v1/search', async (route) => {
      searchRequests++;
      console.log(`[HTTP Intercept] POST /api/v1/search disparado (chamada #${searchRequests})`);
      // Encaminha requisição real ao backend fixture
      await route.continue();
    });

    await pageFault.route('**/api/v1/audit', async (route) => {
      auditRequests++;
      console.log(`[HTTP Intercept] POST /api/v1/audit disparado (chamada #${auditRequests})`);
      if (auditRequests === 1) {
        console.log('[Injeção de Falha] Injetando 504 Gateway Timeout na 1ª auditoria');
        await route.fulfill({
          status: 504,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'GATEWAY_TIMEOUT: Tempo limite de resposta excedido' }),
        });
      } else {
        console.log('[Encaminhamento Real] Encaminhando 2ª chamada de auditoria ao backend fixture');
        await route.continue();
      }
    });

    await pageFault.route('**/api/v1/writer', async (route) => {
      writerRequests++;
      console.log(`[HTTP Intercept] POST /api/v1/writer disparado (chamada #${writerRequests})`);
      await route.continue();
    });

    await pageFault.goto(BASE_URL);
    await pageFault.waitForSelector('#root');

    // Submete tema de pesquisa
    await pageFault.locator('.composer-input').fill('Investigação de Falha de Auditoria com Recuperação');
    await pageFault.locator('.composer-send-btn').click();
    await pageFault.waitForSelector('.plan-card');

    // Inicia pesquisa
    await pageFault.locator('.btn-start-research:has-text("Iniciar pesquisa")').click();

    // Aguarda a falha injetada no estágio de auditoria
    await pageFault.waitForSelector('.alert-banner.danger', { timeout: 15000 });
    const retryBtnText = await pageFault.locator('.alert-banner.danger .btn-start-research').textContent();
    console.log('Botão de retentativa exibido:', retryBtnText?.trim());
    assert.equal(retryBtnText?.trim(), 'Tentar auditoria novamente', 'Botão deve indicar "Tentar auditoria novamente"');
    assert.equal(searchRequests, 1, 'Busca foi executada com sucesso exatamente 1 vez');
    assert.equal(auditRequests, 1, 'Auditoria falhou com 504 exatamente 1 vez');
    assert.equal(writerRequests, 0, 'Writer NÃO foi chamado');

    await pageFault.screenshot({ path: path.join(EVIDENCE_DIR, '06-audit-504-failed-stage.png'), fullPage: true });

    // Aciona a retentativa ("Tentar auditoria novamente")
    console.log('\n[Etapa 7] Acionando botão "Tentar auditoria novamente"...');
    await pageFault.locator('.alert-banner.danger .btn-start-research:has-text("Tentar auditoria novamente")').click();

    // Aguarda conclusão ou próximo estágio
    await pageFault.waitForFunction(() => {
      return (
        document.querySelector('.report-article') !== null ||
        document.querySelector('.execution-card') !== null
      );
    }, { timeout: 20000 });

    console.log(`Totais após retry: Busca=${searchRequests}, Auditoria=${auditRequests}, Redator=${writerRequests}`);
    assert.equal(searchRequests, 1, 'Busca NÃO FOI REPETIDA! Permaneceu com exatamente 1 requisição');
    assert.equal(auditRequests, 2, 'Auditoria foi chamada uma segunda vez na retentativa');

    await pageFault.screenshot({ path: path.join(EVIDENCE_DIR, '07-audit-retry-no-search-repeat.png'), fullPage: true });
    await ctxFault.close();

    console.log('\n--- Todas as 7 verificações no navegador passaram com sucesso e evidências gravadas! ---');
  } finally {
    await browser.close();
  }
}

runBrowserVerification().catch((err) => {
  console.error('Falha na verificação do navegador:', err);
  process.exit(1);
});
