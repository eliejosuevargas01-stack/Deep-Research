/**
 * Testes Reais E2E no Navegador: Concorrência, Bootstrap e Posse de Execução
 *
 * Exercita o código de produção real do App no navegador via Playwright com
 * isolamento total (todas as rotas de mutação interceptadas com fixtures sintéticas):
 * 1. Submissão de tema durante bootstrap com resolução assíncrona de sessão (/app/session com barreira)
 * 2. Bloqueio de planejamento sob falha de bootstrap e recuperação após retry
 * 3. Prevenção de reentrância / duplo clique no envio de tema (lock síncrono atômico)
 * 4. Posse de execução por token e bloqueio mútuo entre planejamento e execução
 * 5. Proteção de posse de execução: finalização antiga nunca rouba lock de nova execução
 */
import { chromium, Browser } from 'playwright';
import assert from 'node:assert/strict';

const BASE_URL = process.env.BASE_URL || 'http://localhost:8011';

function createSyntheticSession() {
  return {
    authenticated: true,
    mode: 'local',
    preferences: {
      n_pontos: 1,
      personas: ['historiador'],
    },
  };
}

function createSyntheticPlan(id: string, tema: string) {
  return {
    id_pesquisa: id,
    tema,
    n_pontos: 1,
    criado_em: new Date().toISOString(),
    pontos: [
      {
        ponto_id: `pt-${id}-1`,
        ponto_n: 1,
        ponto: `Ponto investigativo: ${tema}`,
        status: 'pendente',
        eixo_estruturado: {
          pergunta_principal: `Questão investigativa de ${tema}?`,
          subperguntas: ['Subpergunta 1'],
          hipoteses: ['Hipótese 1'],
          consultas_iniciais: ['consulta 1'],
          fontes_primarias_desejadas: ['fonte 1'],
          riscos_de_vies: ['viés 1'],
          evidencias_que_refutariam: ['evidência 1'],
          criterio_de_conclusao: 'Critério de conclusão',
          investigabilidade: 'alta',
          eixo_essencial: true,
        },
      },
    ],
    preferencias: {
      n_pontos: 1,
      personas: ['historiador'],
    },
  };
}

function createSyntheticSearch(id: string) {
  return {
    id_pesquisa: id,
    total_pontos_processados: 1,
    status_pesquisa: 'concluido',
    total_falhas_coleta: 0,
    resumo_coletas: [
      {
        ponto_id: `pt-${id}-1`,
        ponto_n: 1,
        status: 'sucesso',
        falha_coleta: false,
        total_urls_lidas: 2,
        total_urls_fonte: 2,
        tamanho_conteudo_caracteres: 800,
        tentativas: 1,
        personas: [
          {
            persona: 'historiador',
            analise: `Análise factual para ${id}`,
            urls_fonte: ['https://exemplo.org/fonte-a'],
            queries_executadas: 1,
            falha_coleta: false,
          },
        ],
      },
    ],
  };
}

function createSyntheticAudit(id: string) {
  return {
    id_pesquisa: id,
    total_pontos: 1,
    aprovados: 1,
    reprovados: 0,
    status_geral: 'aprovado',
    pronto_para_writer: true,
    auditorias: [
      {
        ponto_id: `pt-${id}-1`,
        ponto_n: 1,
        status: 'aprovado',
        pontuacao_percentual: 100,
        criterios_aprovados: 11,
        criterios_minimos: 11,
        valido: true,
        criterios: [],
      },
    ],
  };
}

function createSyntheticWriter(id: string, tema: string) {
  return {
    id_pesquisa: id,
    tema,
    status: 'concluido',
    total_caracteres_dossier: 950,
    concluido_em: new Date().toISOString(),
    dossier_final: `# Dossiê de Pesquisa: ${tema}\n\nEvidências robustas apuradas sinteticamente.`,
    dossier_resumo: `Resumo executivo de ${tema}`,
    fontes: {
      status: 'completo',
      total_consultadas: 2,
      total_utilizadas: 2,
      total_nao_utilizadas: 0,
      consultadas: [{ url: 'https://exemplo.org/fonte-a', titulo: 'Fonte A', dominio: 'exemplo.org' }],
      utilizadas: [{ url: 'https://exemplo.org/fonte-a', titulo: 'Fonte A', dominio: 'exemplo.org' }],
      nao_utilizadas: [],
    },
  };
}

async function runRealConcurrencyTests() {
  console.log('--- Iniciando Testes Reais de Concorrência e Bootstrap no Navegador ---');

  const browser: Browser = await chromium.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
  });

  try {
    // =======================================================================
    // Teste 1: Submissão de tema ANTES da resolução de /app/session
    // =======================================================================
    console.log('\n[Teste 1] Submissão durante bootstrap: await de sessão não deve bloquear incorretamente');
    {
      const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
      const page = await context.newPage();

      let resolveSessionRoute!: () => void;
      const sessionGatePromise = new Promise<void>((resolve) => {
        resolveSessionRoute = resolve;
      });

      let planApiCalls = 0;

      // Bloqueia qualquer rota de API não prevista para garantir isolamento absoluto
      await page.route('**/api/**', (route) => {
        throw new Error(`Requisição de API não isolada detectada: ${route.request().method()} ${route.request().url()}`);
      });

      // Intercepta /app/session segurando a resolução até liberação explícita
      await page.route('**/app/session', async (route) => {
        await sessionGatePromise;
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(createSyntheticSession()),
        });
      });

      // Intercepta rota de mutação de plano com fixture sintética isolada
      await page.route('**/api/v1/plan', async (route) => {
        planApiCalls++;
        const postData = route.request().postDataJSON();
        const tema = postData?.tema || 'Investigação com Bootstrap Concorrente no Navegador';
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(createSyntheticPlan('test-1-plan', tema)),
        });
      });

      await page.goto(BASE_URL);

      // Compositor deve permitir inserção durante bootstrap pendente
      const composerInput = page.locator('.composer-input');
      await composerInput.waitFor({ state: 'attached', timeout: 5000 });

      // Preenche o tema enquanto o bootstrap está pendente
      await composerInput.fill('Investigação com Bootstrap Concorrente no Navegador');

      // Clica em Enviar antes da resolução da sessão
      const sendBtn = page.locator('.composer-send-btn');
      await sendBtn.click();

      // Verifica que o plano ainda não foi disparado ao backend (aguardando bootstrap)
      assert.equal(planApiCalls, 0, 'Plano não deve ser enviado antes da sessão inicial responder');

      // Agora libera a resolução da sessão
      resolveSessionRoute();

      // Aguarda a renderização do card de plano formulado
      await page.waitForSelector('.plan-card', { timeout: 15000 });

      // Verifica que exatamente UMA chamada à API de plano foi executada
      assert.equal(planApiCalls, 1, 'Exatamente uma chamada ao endpoint de plano deve ocorrer');

      // Nenhum erro falso de sessão não estabelecida deve existir
      const dangerAlert = page.locator('.alert-banner.danger');
      assert.equal(await dangerAlert.count(), 0, 'Não deve exibir alerta de erro de sessão stale');

      await context.close();
      console.log('✓ Teste 1 concluído com sucesso: plano gerado após resolução sem erro stale');
    }

    // =======================================================================
    // Teste 2: Falha no bootstrap, bloqueio e recuperação via Retry
    // =======================================================================
    console.log('\n[Teste 2] Falha de bootstrap: bloqueio seguro e recuperação com botão "Tentar novamente"');
    {
      const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
      const page = await context.newPage();

      let sessionShouldFail = true;
      let planCalls = 0;

      // Bloqueia qualquer rota de API não prevista para garantir isolamento absoluto
      await page.route('**/api/**', (route) => {
        throw new Error(`Requisição de API não isolada detectada: ${route.request().method()} ${route.request().url()}`);
      });

      await page.route('**/app/session', async (route) => {
        if (sessionShouldFail) {
          await route.fulfill({
            status: 500,
            contentType: 'application/json',
            body: JSON.stringify({ detail: 'Falha transitória de comunicação com o backend' }),
          });
        } else {
          await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify(createSyntheticSession()),
          });
        }
      });

      await page.route('**/api/v1/plan', async (route) => {
        planCalls++;
        const postData = route.request().postDataJSON();
        const tema = postData?.tema || 'Investigação Pós-Recuperação de Sessão';
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(createSyntheticPlan('test-2-plan', tema)),
        });
      });

      await page.goto(BASE_URL);

      // Deve exibir o banner de falha de sincronização de sessão
      const warningAlert = page.locator('.alert-banner.warning');
      await warningAlert.waitFor({ state: 'visible', timeout: 10000 });
      const warningText = await warningAlert.textContent();
      assert.ok(
        warningText?.includes('Sessão inicial não sincronizada com o backend'),
        'Deve exibir aviso explícito de falha na sincronização inicial'
      );

      // O compositor deve estar bloqueado para evitar planos fantasmas
      const composerBox = page.locator('.composer-box');
      assert.ok(
        (await composerBox.getAttribute('class'))?.includes('disabled'),
        'Compositor deve estar desabilitado enquanto houver erro de bootstrap'
      );

      // Tentativa de submissão via evento com bootstrap falhado não deve disparar POST
      await page.locator('.composer-send-btn').dispatchEvent('click');
      assert.equal(planCalls, 0, 'Nenhum POST de plano deve ser emitido sob falha de bootstrap');

      // Agora o backend se recupera: atualizamos flag para a rota responder 200
      sessionShouldFail = false;

      // Clica no botão "Tentar novamente" do banner
      const retryBtn = warningAlert.locator('button.btn-secondary');
      await retryBtn.click();

      // Aguarda o banner de aviso desaparecer
      await warningAlert.waitFor({ state: 'detached', timeout: 10000 });

      // Compositor não deve mais ter classe disabled
      assert.ok(
        !(await composerBox.getAttribute('class'))?.includes('disabled'),
        'Compositor deve ser reabilitado após retry bem-sucedido'
      );

      // Agora que a sessão está autenticada, submete um tema
      const composerInput = page.locator('.composer-input');
      await composerInput.fill('Investigação Pós-Recuperação de Sessão');
      await page.locator('.composer-send-btn').click();

      // Plano deve ser formulado normalmente
      await page.waitForSelector('.plan-card', { timeout: 15000 });
      assert.equal(planCalls, 1, 'Deve disparar a criação do plano após a recuperação da sessão');

      await context.close();
      console.log('✓ Teste 2 concluído com sucesso: recuperação de bootstrap via retry');
    }

    // =======================================================================
    // Teste 3: Prevenção de reentrância / duplo clique no formulário de plano
    // =======================================================================
    console.log('\n[Teste 3] Prevenção de reentrância / duplo clique na submissão de plano');
    {
      const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
      const page = await context.newPage();

      let planRequestsCount = 0;
      let resolvePlanGate!: () => void;
      const planGatePromise = new Promise<void>((r) => {
        resolvePlanGate = r;
      });

      // Bloqueia qualquer rota de API não prevista para garantir isolamento absoluto
      await page.route('**/api/**', (route) => {
        throw new Error(`Requisição de API não isolada detectada: ${route.request().method()} ${route.request().url()}`);
      });

      await page.route('**/app/session', async (route) => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(createSyntheticSession()),
        });
      });

      // Intercepta /api/v1/plan segurando a resposta para simular latência de rede determinística
      await page.route('**/api/v1/plan', async (route) => {
        planRequestsCount++;
        await planGatePromise;
        const postData = route.request().postDataJSON();
        const tema = postData?.tema || 'Investigação para Teste de Barreira Reentrante';
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(createSyntheticPlan('test-3-plan', tema)),
        });
      });

      await page.goto(BASE_URL);
      await page.waitForSelector('.composer-input');

      await page.locator('.composer-input').fill('Investigação para Teste de Barreira Reentrante');

      const sendBtn = page.locator('.composer-send-btn');

      // Primeiro clique inicia a submissão e trava o lock síncrono isPlanningRef
      await sendBtn.click();

      // Dispara cliques adicionais concorrentes enquanto a primeira requisição está suspensa na barreira.
      // Usa dispatchEvent para testar reentrância direta no DOM sem catches que mascarem falhas reais.
      await sendBtn.dispatchEvent('click');
      await sendBtn.dispatchEvent('click');

      // Libera a resposta do plano
      resolvePlanGate();

      await page.waitForSelector('.plan-card', { timeout: 15000 });

      assert.equal(
        planRequestsCount,
        1,
        'Apenas uma requisição à API deve ser realizada apesar de múltiplos cliques concorrentes'
      );

      await context.close();
      console.log('✓ Teste 3 concluído com sucesso: lock síncrono previne requisições duplicadas');
    }

    // =======================================================================
    // Teste 4: Posse de execução (Token) e bloqueio mútuo
    // =======================================================================
    console.log('\n[Teste 4] Posse de execução por token e bloqueio mútuo entre planejamento e execução');
    {
      const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
      const page = await context.newPage();

      let planCalls = 0;
      let searchCalls = 0;
      let auditCalls = 0;
      let writerCalls = 0;

      let holdSearch!: () => void;
      const searchGate = new Promise<void>((r) => {
        holdSearch = r;
      });

      // Bloqueia qualquer rota de API não prevista para garantir isolamento absoluto
      await page.route('**/api/**', (route) => {
        throw new Error(`Requisição de API não isolada detectada: ${route.request().method()} ${route.request().url()}`);
      });

      await page.route('**/api/v1/pipeline/*/stream', async (route) => {
        await route.fulfill({
          status: 200,
          contentType: 'text/event-stream',
          headers: {
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
          },
          body: ': keep-alive\n\n',
        });
      });

      await page.route('**/app/session', async (route) => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(createSyntheticSession()),
        });
      });

      await page.route('**/api/v1/plan', async (route) => {
        planCalls++;
        const postData = route.request().postDataJSON();
        const tema = postData?.tema || 'Investigação para Teste de Posse de Execução';
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(createSyntheticPlan('test-4-plan', tema)),
        });
      });

      await page.route('**/api/v1/search', async (route) => {
        searchCalls++;
        await searchGate;
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(createSyntheticSearch('test-4-plan')),
        });
      });

      await page.route('**/api/v1/audit', async (route) => {
        auditCalls++;
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(createSyntheticAudit('test-4-plan')),
        });
      });

      await page.route('**/api/v1/writer', async (route) => {
        writerCalls++;
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(createSyntheticWriter('test-4-plan', 'Investigação para Teste de Posse de Execução')),
        });
      });

      await page.goto(BASE_URL);
      await page.waitForSelector('.composer-input');

      await page.locator('.composer-input').fill('Investigação para Teste de Posse de Execução');
      await page.locator('.composer-send-btn').click();
      await page.waitForSelector('#start-research-btn', { timeout: 15000 });

      // Inicia execução com duplo acionamento concorrente (dblclick) para verificar bloqueio de reentrância
      const startBtn = page.locator('#start-research-btn');
      await startBtn.dblclick();

      await page.waitForSelector('.execution-card', { timeout: 10000 });

      // Durante a execução ativa com busca suspensa:
      // 1. Apenas 1 chamada de busca deve ter sido emitida
      assert.equal(searchCalls, 1, 'Duplo clique no início de execução não deve disparar POST duplicado');

      // 2. O compositor deve estar bloqueado (exclusão mútua)
      const composerBox = page.locator('.composer-box');
      assert.ok(
        (await composerBox.getAttribute('class'))?.includes('disabled'),
        'Compositor deve estar bloqueado durante a execução ativa do pipeline'
      );

      // 3. Tentativa de submissão no compositor não deve gerar nova chamada de plano
      await page.locator('.composer-send-btn').dispatchEvent('click');
      assert.equal(planCalls, 1, 'Compositor travado não deve emitir requisição POST de plano');

      // Libera a busca para prosseguir com auditoria e redação
      holdSearch();

      // Aguarda o pipeline terminar na exibição do dossiê final
      await page.waitForSelector('.report-card', { timeout: 15000 });
      assert.equal(await page.locator('#dossier-heading').count(), 1, 'Dossiê deve exibir cabeçalho');

      assert.equal(searchCalls, 1, 'Exatamente uma chamada de busca executada');
      assert.equal(auditCalls, 1, 'Exatamente uma chamada de auditoria executada');
      assert.equal(writerCalls, 1, 'Exatamente uma chamada do redator executada');

      await context.close();
      console.log('✓ Teste 4 concluído com sucesso: posse de execução e bloqueio mútuo respeitados');
    }

    // =======================================================================
    // Teste 5: Proteção de posse de execução: finalização antiga nunca rouba lock de nova execução
    // =======================================================================
    console.log('\n[Teste 5] Proteção de posse: finally retardado de execução anterior não limpa lock ativo');
    {
      const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
      const page = await context.newPage();

      // Auto-aceita confirmações de descarte de pesquisa (window.confirm)
      page.on('dialog', async (dialog) => {
        await dialog.accept();
      });

      let resolveSearchA!: () => void;
      const searchAGate = new Promise<void>((r) => {
        resolveSearchA = r;
      });

      let resolveSearchB!: () => void;
      const searchBGate = new Promise<void>((r) => {
        resolveSearchB = r;
      });

      const planRequests: string[] = [];
      const searchRequests: string[] = [];
      const auditRequests: string[] = [];
      const writerRequests: string[] = [];

      // Bloqueia qualquer rota de API não prevista para garantir isolamento absoluto
      await page.route('**/api/**', (route) => {
        throw new Error(`Requisição de API não isolada detectada: ${route.request().method()} ${route.request().url()}`);
      });

      await page.route('**/api/v1/pipeline/*/stream', async (route) => {
        await route.fulfill({
          status: 200,
          contentType: 'text/event-stream',
          headers: {
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
          },
          body: ': keep-alive\n\n',
        });
      });

      await page.route('**/app/session', async (route) => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(createSyntheticSession()),
        });
      });

      await page.route('**/api/v1/plan', async (route) => {
        const postData = route.request().postDataJSON();
        const tema = postData?.tema || '';
        planRequests.push(tema);

        const id = tema.includes('Alpha') ? 'pesquisa-alpha-id' : 'pesquisa-beta-id';
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(createSyntheticPlan(id, tema)),
        });
      });

      await page.route('**/api/v1/search', async (route) => {
        const postData = route.request().postDataJSON();
        const id = postData?.id_pesquisa;
        searchRequests.push(id);

        if (id === 'pesquisa-alpha-id') {
          await searchAGate;
          await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify(createSyntheticSearch('pesquisa-alpha-id')),
          });
        } else if (id === 'pesquisa-beta-id') {
          await searchBGate;
          await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify(createSyntheticSearch('pesquisa-beta-id')),
          });
        } else {
          await route.fulfill({
            status: 400,
            contentType: 'application/json',
            body: JSON.stringify({ detail: `Pesquisa desconhecida: ${id}` }),
          });
        }
      });

      await page.route('**/api/v1/audit', async (route) => {
        const postData = route.request().postDataJSON();
        const id = postData?.id_pesquisa;
        auditRequests.push(id);
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(createSyntheticAudit(id)),
        });
      });

      await page.route('**/api/v1/writer', async (route) => {
        const postData = route.request().postDataJSON();
        const id = postData?.id_pesquisa;
        writerRequests.push(id);
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(createSyntheticWriter(id, 'Dossiê Beta Final')),
        });
      });

      // Passo 1: Iniciar pesquisa A e suspender POST search A
      await page.goto(BASE_URL);
      await page.waitForSelector('.composer-input');

      await page.locator('.composer-input').fill('Investigação Alpha (Pesquisa A)');
      await page.locator('.composer-send-btn').click();
      await page.waitForSelector('#start-research-btn', { timeout: 15000 });

      await page.locator('#start-research-btn').click();
      await page.waitForSelector('.execution-card', { timeout: 10000 });

      assert.equal(searchRequests.length, 1, 'Pesquisa A deve disparar exatamente uma busca inicial');
      assert.equal(searchRequests[0], 'pesquisa-alpha-id', 'Busca A deve pertencer a pesquisa-alpha-id');

      // Passo 2: Alterar posse por ação suportada da aplicação (Reset via botão "Nova pesquisa")
      const newResearchBtn = page.locator('.btn-new-research');
      await newResearchBtn.click();

      // Confirmação via dialog é aceita e workspace retorna ao compositor limpo
      const composerInput = page.locator('.composer-input');
      await composerInput.waitFor({ state: 'visible', timeout: 10000 });
      assert.equal(await page.locator('.execution-card').count(), 0, 'Execução A desacoplada do workspace');

      // Passo 3: Iniciar pesquisa B e suspender POST search B
      await composerInput.fill('Investigação Beta (Pesquisa B)');
      await page.locator('.composer-send-btn').click();
      await page.waitForSelector('#start-research-btn', { timeout: 15000 });

      await page.locator('#start-research-btn').click();
      await page.waitForSelector('.execution-card', { timeout: 10000 });

      assert.equal(searchRequests.length, 2, 'Pesquisa B deve disparar segunda busca');
      assert.equal(searchRequests[1], 'pesquisa-beta-id', 'Busca B deve pertencer a pesquisa-beta-id');

      // Verifica que o lock de B está ativo antes de liberar A
      const composerBox = page.locator('.composer-box');
      assert.ok(
        (await composerBox.getAttribute('class'))?.includes('disabled'),
        'Compositor deve estar travado sob a posse ativa de B'
      );

      // Passo 4: Liberar A enquanto B continua pendente na busca
      resolveSearchA();

      // Aguarda resolução da promise de A e execução do seu bloco finally no navegador
      await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => setTimeout(resolve, 50))));

      // Passo 5: Comprovar que lock B continua ativo e tentativa extra NÃO gera POST
      const isComposerStillDisabled = (await composerBox.getAttribute('class'))?.includes('disabled');
      assert.ok(
        isComposerStillDisabled,
        'Lock B deve permanecer estritamente ativo após resolução defasada de A'
      );
      assert.equal(
        await page.locator('.execution-card').count(),
        1,
        'Card de execução de B deve permanecer ativo e visível'
      );

      // Tentativa espúria de disparar plano via evento no compositor travado
      await page.locator('.composer-send-btn').dispatchEvent('click');

      // Comprova por contagem de rede que nenhuma chamada extra foi disparada
      assert.equal(planRequests.length, 2, 'Tentativa extra sob lock de B não deve gerar POST de plano');
      assert.equal(searchRequests.length, 2, 'Nenhuma busca adicional deve ser disparada');

      // Passo 6: Liberar B e comprovar término conforme contrato
      resolveSearchB();

      // Aguarda finalização da pesquisa B com exibição do relatório
      await page.waitForSelector('.report-card', { timeout: 15000 });
      const reportTitle = await page.locator('#dossier-heading').textContent();
      assert.ok(
        reportTitle?.includes('Investigação Beta') || reportTitle?.includes('Dossiê Beta Final'),
        'Relatório exibido deve ser o dossiê legítimo da pesquisa B'
      );

      // Comprova contabilidade estrita de rede: Alpha nunca avançou para auditoria/redação
      assert.deepEqual(planRequests, [
        'Investigação Alpha (Pesquisa A)',
        'Investigação Beta (Pesquisa B)',
      ]);
      assert.deepEqual(searchRequests, ['pesquisa-alpha-id', 'pesquisa-beta-id']);
      assert.deepEqual(auditRequests, ['pesquisa-beta-id'], 'Apenas B deve ter sido submetido à auditoria');
      assert.deepEqual(writerRequests, ['pesquisa-beta-id'], 'Apenas B deve ter sido submetido à redação final');

      // Nenhum erro perigoso de sessão corrompida
      const dangerBanners = await page.locator('.alert-banner.danger').count();
      assert.equal(dangerBanners, 0, 'Nenhum erro de estado corrompido deve ser gerado');

      await context.close();
      console.log('✓ Teste 5 concluído com sucesso: token de posse previne corrupção de lock');
    }

    console.log('\n============================================================');
    console.log('Todos os testes reais E2E no navegador passaram com sucesso!');
    console.log('============================================================');
  } finally {
    await browser.close();
  }
}

runRealConcurrencyTests().catch((err) => {
  console.error('Falha nos testes reais de concorrência:', err);
  process.exit(1);
});
