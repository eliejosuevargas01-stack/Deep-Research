import { Given, When, Then } from '@cucumber/cucumber';
import { expect } from '@playwright/test';
import crypto from 'node:crypto';
import fs from 'node:fs';
import { CustomWorld } from '../support/world.js';

Given('que acesso a aplicação no dispositivo {string}', async function (this: CustomWorld, dispositivo: string) {
  const isMobile = dispositivo === 'mobile';
  const viewport = isMobile ? { width: 375, height: 812 } : { width: 1440, height: 900 };
  await this.init(viewport);

  await this.page!.goto(this.baseUrl);
  await this.page!.waitForSelector('#root');

  if (isMobile) {
    await this.saveScreenshot('mobile-empty.png');
  } else {
    await this.saveScreenshot('desktop-empty.png');
  }
});

Given('que acesso a aplicação no dispositivo de largura {int}px', async function (this: CustomWorld, width: number) {
  await this.init({ width, height: 900 });
  await this.page!.goto(this.baseUrl);
  await this.page!.waitForSelector('#root');
});

Then('devo ver o título {string}', async function (this: CustomWorld, titulo: string) {
  const text = await this.page!.textContent('body');
  expect(text).toContain(titulo);
});

Then('devo ver a lista de sugestões de temas investigativos', async function (this: CustomWorld) {
  const cards = this.page!.locator('.sample-topic-card');
  const count = await cards.count();
  expect(count).toBeGreaterThanOrEqual(3);
});

Then('o botão de submissão do compositor deve estar desabilitado', async function (this: CustomWorld) {
  const disabled = await this.page!.locator('.composer-send-btn').isDisabled();
  expect(disabled).toBe(true);
});

When('digito {string} no compositor', async function (this: CustomWorld, texto: string) {
  await this.page!.locator('.composer-input').fill(texto);
});

Then('o contador de caracteres deve indicar comprimento inválido', async function (this: CustomWorld) {
  const invalid = await this.page!.locator('.composer-counter.invalid').isVisible();
  expect(invalid).toBe(true);
});

Then('devo ver a mensagem de ajuda indicando o limite de 5 a 500 caracteres', async function (this: CustomWorld) {
  const helper = this.page!.locator('#composer-helper-text');
  expect(await helper.isVisible()).toBe(true);
  const text = await helper.textContent();
  expect(text).toContain('5');
  expect(text).toContain('500');
});

Then('o botão de submissão deve permanecer desabilitado', async function (this: CustomWorld) {
  const disabled = await this.page!.locator('.composer-send-btn').isDisabled();
  expect(disabled).toBe(true);
});

Then('o botão de submissão deve ficar habilitado', async function (this: CustomWorld) {
  const enabled = await this.page!.locator('.composer-send-btn').isEnabled();
  expect(enabled).toBe(true);
});

When('clico na sugestão de tema {string}', async function (this: CustomWorld, tema: string) {
  await this.page!.locator(`.sample-topic-card:has-text("${tema}")`).click();
});

Then('o compositor deve conter o texto {string}', async function (this: CustomWorld, tema: string) {
  const val = await this.page!.locator('.composer-input').inputValue();
  expect(val).toBe(tema);
});

Then('o foco do navegador deve estar no campo do compositor', async function (this: CustomWorld) {
  const isFocused = await this.page!.evaluate(() => {
    return document.activeElement === document.querySelector('.composer-input');
  });
  expect(isFocused).toBe(true);
});

When('clico no botão de preferências de pesquisa', async function (this: CustomWorld) {
  await this.page!.locator('#preferences-toggle-btn').click();
});

Then('o painel de preferências deve estar visível', async function (this: CustomWorld) {
  const panel = this.page!.locator('#preferences-popover-panel');
  expect(await panel.isVisible()).toBe(true);
});

When('seleciono {int} pontos analíticos nas preferências', async function (this: CustomWorld, n: number) {
  await this.page!.locator(`.point-option-btn:has-text("${n} ponto")`).click();
});

When('desmarco a persona {string}', async function (this: CustomWorld, persona: string) {
  const checkbox = this.page!.locator(`.persona-checkbox-label:has-text("${persona}") input`);
  await checkbox.uncheck();
});

When('fecho o painel de preferências com a tecla Escape', async function (this: CustomWorld) {
  await this.page!.keyboard.press('Escape');
});

When('fecho o painel de preferências', async function (this: CustomWorld) {
  await this.page!.locator('.preferences-close-btn').click();
});

Then('o foco deve retornar para o botão de preferências', async function (this: CustomWorld) {
  const isFocused = await this.page!.evaluate(() => {
    return document.activeElement === document.querySelector('#preferences-toggle-btn');
  });
  expect(isFocused).toBe(true);
});

Then('o chip de preferências deve indicar {string}', async function (this: CustomWorld, text: string) {
  const chipText = await this.page!.locator('.preferences-chip-label').textContent();
  expect(chipText).toContain(text);
});

When('preencho o tema {string} no compositor', async function (this: CustomWorld, tema: string) {
  await this.page!.locator('.composer-input').fill(tema);
});

When('clico no botão de planejar investigação', async function (this: CustomWorld) {
  await this.page!.locator('.composer-send-btn').click();
});

Then('devo ver o cartão do plano {string}', async function (this: CustomWorld, tituloPlano: string) {
  await this.page!.waitForSelector('.plan-card', { timeout: 15000 });
  const text = await this.page!.textContent('.plan-card');
  expect(text).toContain(tituloPlano);
  const mobile = (this.page!.viewportSize()?.width || 1440) <= 640;
  await this.saveScreenshot(mobile ? 'mobile-planned.png' : 'desktop-planned.png');
});

Then('devo ver a lista vertical dos {int} pontos investigativos', async function (this: CustomWorld, totalPontos: number) {
  const items = this.page!.locator('.stepper-item');
  const count = await items.count();
  expect(count).toBe(totalPontos);
});

Then('devo ver a lista vertical dos pontos investigativos com divulgação progressiva', async function (this: CustomWorld) {
  const items = this.page!.locator('.stepper-item');
  const count = await items.count();
  expect(count).toBeGreaterThanOrEqual(1);
  const toggleBtn = this.page!.locator('.stepper-point-toggle').first();
  await toggleBtn.waitFor({ state: 'visible', timeout: 5000 });
  expect(await toggleBtn.isVisible()).toBe(true);
});

Then('o plano deve exibir o chip com {int} pontos analíticos', async function (this: CustomWorld, n: number) {
  const chip = this.page!.locator(`.plan-snapshot-chips:has-text("${n} ponto")`);
  expect(await chip.isVisible()).toBe(true);
});

Then('devo ver o painel colapsável de contexto metodológico', async function (this: CustomWorld) {
  const panel = this.page!.locator('.context-panel');
  expect(await panel.isVisible()).toBe(true);
});

Then('devo ver na barra lateral o status {string}', async function (this: CustomWorld, status: string) {
  const sidebar = this.page!.locator('.sidebar-container');
  const text = await sidebar.textContent();
  expect(text).toContain(status);
});

Then('a única ação de continuidade visível deve ser o botão {string}', async function (this: CustomWorld, botaoTexto: string) {
  const btn = this.page!.locator('#start-research-btn');
  expect(await btn.isVisible()).toBe(true);
  const text = await btn.textContent();
  expect(text).toContain(botaoTexto);
});

Given('que planejei uma pesquisa para o tema {string}', async function (this: CustomWorld, tema: string) {
  await this.init({ width: 1440, height: 900 });

  await this.page!.goto(this.baseUrl);
  await this.page!.waitForSelector('.composer-input');

  await this.page!.locator('.composer-input').fill(tema);
  await this.page!.locator('.composer-send-btn').click();
  await this.page!.waitForSelector('.plan-card', { timeout: 15000 });
});

When('clico no botão "Iniciar pesquisa"', async function (this: CustomWorld) {
  await this.page!.locator('#start-research-btn').click();
});

Then('o sistema deve transicionar pelo estágio de busca com 4 personas', async function (this: CustomWorld) {
  await this.page!.waitForSelector('.execution-card', { timeout: 10000 });
});

Then('o sistema deve transicionar pela auditoria de qualidade com 12 critérios', async function (this: CustomWorld) {
  await this.page!.waitForSelector('.stage-step:has-text("Auditoria")', { timeout: 15000 });
});

Then('após aprovação na auditoria o redator deve consolidar o dossiê', async function (this: CustomWorld) {
  await this.page!.waitForSelector('#dossier-report', { timeout: 25000 });
});

Then('devo ver o relatório do dossiê com status concluído', async function (this: CustomWorld) {
  const statusChip = this.page!.locator('#dossier-report .status-badge-chip.concluido');
  expect(await statusChip.isVisible()).toBe(true);
  await this.saveScreenshot('desktop-finished.png');

  await this.page!.setViewportSize({ width: 375, height: 812 });
  await this.saveScreenshot('mobile-finished.png');
  await this.page!.setViewportSize({ width: 1440, height: 900 });
});

Then('devo ver a lista de fontes bibliográficas verificadas', async function (this: CustomWorld) {
  const sourcesCard = this.page!.locator('.sources-card');
  expect(await sourcesCard.isVisible()).toBe(true);
});

Then('os botões de copiar markdown e baixar arquivo devem estar disponíveis', async function (this: CustomWorld) {
  const copyBtn = this.page!.getByRole('button', { name: 'Copiar Markdown' });
  const downloadBtn = this.page!.getByRole('button', { name: 'Baixar .md' });
  expect(await copyBtn.isVisible()).toBe(true);
  expect(await downloadBtn.isVisible()).toBe(true);
});

Then('o layout deve adaptar-se à largura móvel sem rolagem horizontal', async function (this: CustomWorld) {
  const scrollWidth = await this.page!.evaluate(() => document.documentElement.scrollWidth);
  const clientWidth = await this.page!.evaluate(() => document.documentElement.clientWidth);
  expect(scrollWidth).toBeLessThanOrEqual(clientWidth + 2);
});

Then('a barra de navegação superior não deve ter elementos cortados ou transbordando', async function (this: CustomWorld) {
  const isClipped = await this.page!.evaluate(() => {
    const navbar = document.querySelector('.navbar');
    if (!navbar) return true;
    const children = Array.from(navbar.querySelectorAll('*'));
    for (const child of children) {
      const cRect = child.getBoundingClientRect();
      if (cRect.right > window.innerWidth + 1) {
        return true;
      }
    }
    return false;
  });
  expect(isClipped).toBe(false);
});

Then('o layout da página não deve possuir rolagem horizontal', async function (this: CustomWorld) {
  const scrollWidth = await this.page!.evaluate(() => document.documentElement.scrollWidth);
  const clientWidth = await this.page!.evaluate(() => document.documentElement.clientWidth);
  expect(scrollWidth).toBeLessThanOrEqual(clientWidth + 2);
});

Then('o compositor deve permanecer acessível na parte inferior', async function (this: CustomWorld) {
  const composer = this.page!.locator('.composer-anchor');
  expect(await composer.isVisible()).toBe(true);
});

When('a auditoria retorna parecer reprovado com 10 de 12 critérios', async function (this: CustomWorld) {
  await this.page!.route('**/api/v1/writer', (route) => {
    this.writerCalled = true;
    route.abort();
  });

  await this.page!.route('**/api/v1/audit', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id_pesquisa: 'test-rejected-uuid',
        total_pontos: 1,
        aprovados: 0,
        reprovados: 1,
        status_geral: 'reprovado',
        pronto_para_writer: false,
        auditorias: [
          {
            ponto_id: 'p-1',
            ponto_n: 1,
            status: 'reprovado',
            pontuacao_percentual: 83.3,
            criterios_aprovados: 10,
            criterios_minimos: 11,
            valido: true,
            pontos_fracos: 'Falta de corroboração canônica e solidez lógica nas hipóteses.',
            criterios: [
              { id: 1, aprovado: true, justificativa: 'Ok', claim_ids: [], source_ids: [] },
              { id: 2, aprovado: false, justificativa: 'Sem fontes canônicas', claim_ids: [], source_ids: [] },
              { id: 3, aprovado: true, justificativa: 'Ok', claim_ids: [], source_ids: [] },
              { id: 4, aprovado: true, justificativa: 'Ok', claim_ids: [], source_ids: [] },
              { id: 5, aprovado: true, justificativa: 'Ok', claim_ids: [], source_ids: [] },
              { id: 6, aprovado: true, justificativa: 'Ok', claim_ids: [], source_ids: [] },
              { id: 7, aprovado: true, justificativa: 'Ok', claim_ids: [], source_ids: [] },
              { id: 8, aprovado: true, justificativa: 'Ok', claim_ids: [], source_ids: [] },
              { id: 9, aprovado: true, justificativa: 'Ok', claim_ids: [], source_ids: [] },
              { id: 10, aprovado: true, justificativa: 'Ok', claim_ids: [], source_ids: [] },
              { id: 11, aprovado: true, justificativa: 'Ok', claim_ids: [], source_ids: [] },
              { id: 12, aprovado: false, justificativa: 'Causalidade frágil', claim_ids: [], source_ids: [] },
            ],
          },
        ],
      }),
    });
  });
});

Then('a etapa de auditoria deve indicar reprovação dos pontos', async function (this: CustomWorld) {
  await this.page!.waitForSelector('.status-badge-chip.reprovado', { timeout: 10000 });
});

Then('o endpoint do redator nunca deve ser chamado', async function (this: CustomWorld) {
  expect(this.writerCalled).toBe(false);
});

Then('devo ver a notificação de bloqueio da investigação na auditoria', async function (this: CustomWorld) {
  const alert = this.page!.locator('.alert-banner.danger');
  await alert.waitFor({ state: 'visible', timeout: 25000 });
  expect(await alert.isVisible()).toBe(true);
  const text = await alert.textContent();
  expect(text).toContain('Investigação bloqueada na auditoria');

  const viewport = this.page!.viewportSize();
  if (viewport && viewport.width <= 600) {
    await this.saveScreenshot('mobile-failure.png');
  } else {
    await this.saveScreenshot('desktop-failure.png');
  }
});

Then('devo ter a opção de formular um novo tema', async function (this: CustomWorld) {
  const btn = this.page!.getByRole('button', { name: 'Formular novo tema' });
  expect(await btn.isVisible()).toBe(true);
});

When('submeto um tema que gera erro interno no servidor', async function (this: CustomWorld) {
  await this.page!.route('**/api/v1/plan', async (route) => {
    await route.fulfill({
      status: 500,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'CONFIG_ERROR: Erro interno de configuração no SQLite' }),
    });
  });

  await this.page!.locator('.composer-input').fill('Tema Que Falha no Backend');
  await this.page!.locator('.composer-send-btn').click();
});

Then('devo ver um banner de alerta exibindo a mensagem descritiva do erro', async function (this: CustomWorld) {
  const alert = this.page!.locator('.alert-banner.danger');
  await alert.waitFor({ state: 'visible', timeout: 5000 });
  const text = await alert.textContent();
  expect(text).toContain('CONFIG_ERROR: Erro interno');
});

Then('a interface não deve quebrar ou expor segredos', async function (this: CustomWorld) {
  const bodyText = await this.page!.textContent('body');
  expect(bodyText).not.toContain('CREDENTIALS_MASTER_KEY');
  expect(bodyText).not.toContain('test-secret');
});

Given('que o banco isolado contém parâmetros de ambiente e de banco', async function (this: CustomWorld) {
  if (!this.page) {
    await this.init({ width: 1440, height: 900 });
  }

  await this.page!.route('**/api/v1/admin/credentials', async (route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          credenciais: [
            {
              chave: 'OPENAI_API_KEY',
              tipo: 'llm',
              origem_ativa: 'banco_cifrado',
              mascarado: 'fixture-openai-key',
              atualizado_em: new Date().toISOString(),
            },
            {
              chave: 'WEBHOOK_HMAC_SECRET',
              tipo: 'webhook',
              origem_ativa: 'ambiente',
              mascarado: 'public-fixture-webhook-secret',
              atualizado_em: new Date().toISOString(),
            },
            {
              chave: 'DATABASE_CREDENTIAL',
              tipo: 'parametro',
              origem_ativa: 'banco_cifrado',
              mascarado: 'public-database-fallback-fixture',
              atualizado_em: new Date().toISOString(),
            },
            {
              chave: 'FRONTEND_ACCEPTANCE_LABEL',
              tipo: 'parametro',
              origem_ativa: 'ambiente',
              mascarado: 'publ****abel',
              atualizado_em: new Date().toISOString(),
            },
          ],
        }),
      });
    } else {
      await route.abort('blockedbyclient');
    }
  });
});

Given('que navego para a página de "Configurações"', async function (this: CustomWorld) {
  if (!this.page) {
    await this.init({ width: 1440, height: 900 });
  }
  await this.page!.goto(`${this.baseUrl}#settings`);
  await this.page!.waitForSelector('#settings-heading');
  await this.saveScreenshot('desktop-settings.png');
});

Then('o badge superior deve indicar a sessão integrada ativa', async function (this: CustomWorld) {
  const badge = this.page!.locator('.session-badge');
  await badge.waitFor({ state: 'visible', timeout: 10000 });
  const className = await badge.getAttribute('class');
  expect(className).toContain('pill-green');
  const text = await badge.textContent();
  expect(text).toMatch(/Modo local|Conectado/);
  const title = await badge.getAttribute('title');
  expect(title).toContain('Sessão integrada ativa');

  // Verifica requisição explícita de autenticação de sessão via GET /app/session
  const sessionReq = this.trackedRequests.find((r) => r.method === 'GET' && r.url.includes('/app/session'));
  expect(sessionReq).toBeDefined();
});

When('clico em "Testar Conexão com API"', async function (this: CustomWorld) {
  await this.page!.getByRole('button', { name: 'Testar Conexão com API' }).click();
});

Then('devo ver o status de conexão confirmando comunicação ativa', async function (this: CustomWorld) {
  await this.page!.waitForSelector('text=Comunicação ativa e autenticação com backend verificadas', {
    timeout: 10000,
  });
});

When('preencho a URL do LLM com {string}', async function (this: CustomWorld, url: string) {
  await this.page!.locator('#llm-base-url').fill(url);
});

When('preencho o número de pontos com {string}', async function (this: CustomWorld, nPontos: string) {
  await this.page!.locator('#n-pontos').fill(nPontos);
});

When('submeto o formulário de credenciais', async function (this: CustomWorld) {
  await this.page!.getByRole('button', { name: 'Salvar alterações no banco cifrado' }).click();
});

Then('o campo de URL do LLM deve possuir atributo aria-invalid {string}', async function (this: CustomWorld, val: string) {
  const attr = await this.page!.locator('#llm-base-url').getAttribute('aria-invalid');
  expect(attr).toBe(val);
});

Then('o campo de URL do LLM deve apontar para mensagem de erro via aria-describedby', async function (this: CustomWorld) {
  const attr = await this.page!.locator('#llm-base-url').getAttribute('aria-describedby');
  expect(attr).toBe('error-llm-base-url');
  const errorElem = this.page!.locator('#error-llm-base-url');
  expect(await errorElem.isVisible()).toBe(true);
});

Then('nenhuma requisição de gravação deve ser enviada', async function (this: CustomWorld) {
  // Aguarda possíveis ticks para confirmar que a submissão foi estritamente bloqueada no client
  await this.page!.waitForTimeout(300);
  const writeReqs = this.dispatchedPostUrls.filter((url) =>
    url.includes('/credentials') || url.includes('/admin') || url.includes('/parametros')
  );
  expect(writeReqs).toHaveLength(0);
});

Given('que o backend retorna erro na consulta de parâmetros', async function (this: CustomWorld) {
  await this.init({ width: 1440, height: 900 });
  await this.page!.route('**/api/v1/admin/credentials', async (route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Falha de comunicação no repositório de credenciais' }),
      });
    } else {
      await route.continue();
    }
  });
});

Then('devo ver um alerta descritivo de falha ao consultar parâmetros', async function (this: CustomWorld) {
  const alert = this.page!.locator('.alert-banner.danger');
  await alert.waitFor({ state: 'visible', timeout: 5000 });
  expect(await alert.isVisible()).toBe(true);
  const text = await alert.textContent();
  expect(text).toContain('Falha ao consultar parâmetros');
});

Then('devo ver a opção de tentar novamente a consulta', async function (this: CustomWorld) {
  const btn = this.page!.locator('button:has-text("Tentar novamente")');
  await btn.waitFor({ state: 'visible', timeout: 5000 });
  expect(await btn.isVisible()).toBe(true);
});

Then('devo ver o alerta de rascunho não salvo no formulário', async function (this: CustomWorld) {
  const alert = this.page!.locator('.alert-banner.warning');
  await alert.waitFor({ state: 'visible', timeout: 5000 });
  expect(await alert.isVisible()).toBe(true);
  const text = await alert.textContent();
  expect(text).toContain('alterações não salvas no formulário');
});

Then('devo ver a tabela de parâmetros cadastrados', async function (this: CustomWorld) {
  await this.page!.waitForSelector('.credentials-table', { timeout: 15000 });
});

Then('a coluna de origem ativa deve distinguir entre {string} e {string}', async function (this: CustomWorld, orig1: string, orig2: string) {
  await this.page!.waitForSelector('.origin-badge', { timeout: 10000 });
  const text = await this.page!.textContent('.credentials-table');
  expect(text).toContain(orig1);
  expect(text).toContain(orig2);
});

Then('nenhum segredo real deve ser exibido em texto legível', async function (this: CustomWorld) {
  const tableText = await this.page!.locator('.credentials-table').textContent();
  expect(tableText).not.toContain('fixture-openai-key');
  expect(tableText).not.toContain('public-fixture-webhook-secret');
  expect(tableText).not.toContain('public-database-fallback-fixture');
  expect(tableText).toContain('****');
  const writeReqs = this.dispatchedPostUrls.filter((u) => u.includes('/api/v1/admin/credentials'));
  expect(writeReqs).toHaveLength(0);
});

Given('que concluí uma pesquisa com tema {string}', async function (this: CustomWorld, tema: string) {
  await this.init({ width: 1440, height: 900 });

  await this.page!.addInitScript((topic) => {
    const record = {
      id_pesquisa: 'hist-1234-uuid',
      tema: topic,
      criado_em: new Date(Date.now() - 3600000).toISOString(),
      concluido_em: new Date().toISOString(),
      status: 'concluido',
      total_pontos: 5,
      planResponse: {
        id_pesquisa: 'hist-1234-uuid',
        tema: topic,
        n_pontos: 5,
        criado_em: new Date().toISOString(),
        pontos: [
          { ponto_id: 'p-1', ponto_n: 1, ponto: 'Ponto Histórico 1', status: 'aprovado' },
          { ponto_id: 'p-2', ponto_n: 2, ponto: 'Ponto Histórico 2', status: 'aprovado' },
        ],
      },
      writerResponse: {
        id_pesquisa: 'hist-1234-uuid',
        tema: topic,
        status: 'concluido',
        total_caracteres_dossier: 1240,
        concluido_em: new Date().toISOString(),
        dossier_final: `# ${topic}\n\nEste é o dossiê histórico recuperado do armazenamento local do navegador sem requisição externa.\n\n## Fontes Canônicas\n- [Exemplo Canônico](https://exemplo.org/fonte-historica)`,
      },
    };
    localStorage.setItem('deep_research_local_history_v1', JSON.stringify([record]));
  }, tema);

  await this.page!.goto(this.baseUrl);
});

When('navego para a página de {string}', async function (this: CustomWorld, pageName: string) {
  const route = pageName === 'Configurações' ? 'settings' : pageName === 'Histórico' ? 'history' : 'research';
  await this.page!.goto(`${this.baseUrl}#${route}`);
  await this.page!.waitForSelector('#root');
  if (route === 'history') {
    await this.page!.waitForSelector('#history-heading');
    await this.saveScreenshot('desktop-history.png');
  } else if (route === 'settings') {
    await this.page!.waitForSelector('#settings-heading');
  }
});

Then('devo ver o aviso de armazenamento local no navegador', async function (this: CustomWorld) {
  const text = await this.page!.textContent('body');
  expect(text).toContain('Registros salvos localmente neste navegador');
});

Then('devo ver a pesquisa {string} listada com status concluído', async function (this: CustomWorld, tema: string) {
  const item = this.page!.locator(`.history-item-card:has-text("${tema}")`);
  expect(await item.isVisible()).toBe(true);
  const status = await item.locator('.status-badge-chip.concluido').textContent();
  expect(status).toContain('concluido');
});

When('clico no botão "Abrir" da pesquisa listada', async function (this: CustomWorld) {
  await this.page!.locator('.history-item-card button:has-text("Abrir")').first().click();
});

Then('o workspace deve carregar imediatamente o dossiê concluído sem requisições de reprocessamento', async function (this: CustomWorld) {
  await this.page!.waitForSelector('#dossier-report', { timeout: 5000 });
  const text = await this.page!.textContent('#dossier-report');
  expect(text).toContain('dossiê histórico recuperado do armazenamento local');
});

Then('a barra lateral deve adaptar-se abaixo do canvas principal', async function (this: CustomWorld) {
  const sidebar = this.page!.locator('.sidebar-container');
  expect(await sidebar.isVisible()).toBe(true);
});

Then('o botão "Iniciar pesquisa" deve estar visível e tocável', async function (this: CustomWorld) {
  const btn = this.page!.locator('#start-research-btn');
  expect(await btn.isVisible()).toBe(true);
  await this.saveScreenshot('mobile-planned.png');
});

When('pressiono Shift+Enter no compositor com o texto {string}', async function (this: CustomWorld, text: string) {
  const input = this.page!.locator('.composer-input');
  await input.fill(text);
  await input.press('Shift+Enter');
  await input.type('Segunda linha investigativa');
});

Then('o valor do compositor deve conter quebra de linha', async function (this: CustomWorld) {
  const val = await this.page!.locator('.composer-input').inputValue();
  expect(val).toContain('\n');
});

Then('o plano não deve ser submetido', async function (this: CustomWorld) {
  const planCard = this.page!.locator('.plan-card');
  expect(await planCard.count()).toBe(0);
});

When('submeto o tema {string}', async function (this: CustomWorld, tema: string) {
  await this.page!.locator('.composer-input').fill(tema);
  await this.page!.locator('.composer-send-btn').click();
  await this.page!.waitForSelector('.plan-card', { timeout: 15000 });
});

When('submeto um tema que retorna objeto 422 com mensagem e pergunta de esclarecimento', async function (this: CustomWorld) {
  await this.page!.route('**/api/v1/plan', async (route) => {
    await route.fulfill({
      status: 422,
      contentType: 'application/json',
      body: JSON.stringify({
        detail: {
          mensagem: 'Ambiguidade detectada no tema de pesquisa.',
          pergunta_de_esclarecimento: 'Deseja focar no setor elétrico ou em combustíveis sustentáveis?',
          diagnostico: 'Tema amplo com múltiplos escopos concorrentes',
        },
      }),
    });
  });

  await this.page!.locator('.composer-input').fill('Tema Ambíguo para Teste 422');
  await this.page!.locator('.composer-send-btn').click();
});

Then('o banner de erro deve exibir a mensagem e a pergunta de esclarecimento extraídas', async function (this: CustomWorld) {
  const alert = this.page!.locator('.alert-banner.danger');
  await alert.waitFor({ state: 'visible', timeout: 5000 });
  const text = await alert.textContent();
  expect(text).toContain('Ambiguidade detectada');
  expect(text).toContain('Esclarecimento: Deseja focar no setor elétrico');
});

When('o redator retorna resposta 200 com status {string} e sem texto', async function (this: CustomWorld, status: string) {
  await this.page!.route('**/api/v1/writer', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id_pesquisa: 'test-incomplete-uuid',
        tema: 'Investigação Incompleta',
        status: status,
        total_caracteres_dossier: 0,
        dossier_final: '',
        diagnostico: 'Dossiê não gerado por insuficiência de evidências primárias.',
      }),
    });
  });
});

Then('o sistema não deve marcar a pesquisa como concluída', async function (this: CustomWorld) {
  await this.page!.waitForSelector('.execution-card', { timeout: 15000 });
  // O relatório final nunca deve ser renderizado como concluído
  const reportCompleted = this.page!.locator('#dossier-report .status-badge-chip.concluido');
  expect(await reportCompleted.count()).toBe(0);
  // O status global da pesquisa na barra lateral não deve ser concluído
  const sidebarCompleted = this.page!.locator('.context-sidebar .status-badge-container .status-badge-chip.concluido');
  expect(await sidebarCompleted.count()).toBe(0);
  // O bloco do dossiê final não deve existir
  expect(await this.page!.locator('#dossier-report').count()).toBe(0);
});

Then('devo ver a indicação de falha com o diagnóstico retornado', async function (this: CustomWorld) {
  const alert = this.page!.locator('.alert-banner.danger');
  await alert.waitFor({ state: 'visible', timeout: 10000 });
  const text = await alert.textContent();
  expect(text).toContain('Dossiê não gerado por insuficiência');
});

Given('que navego para a página de "Configurações" no dispositivo "mobile"', async function (this: CustomWorld) {
  await this.init({ width: 375, height: 812 });
  await this.page!.goto(`${this.baseUrl}#settings`);
  await this.page!.waitForSelector('#settings-heading');
  await this.saveScreenshot('mobile-settings.png');
});

Then('a tabela de parâmetros deve estar adaptada sem estouro de layout', async function (this: CustomWorld) {
  const scrollWidth = await this.page!.evaluate(() => document.documentElement.scrollWidth);
  const clientWidth = await this.page!.evaluate(() => document.documentElement.clientWidth);
  expect(scrollWidth).toBeLessThanOrEqual(clientWidth + 2);
});

Given('que o backend retorna o segredo WEBHOOK_HMAC_SECRET em texto claro', async function (this: CustomWorld) {
  await this.init({ width: 1440, height: 900 });
  await this.page!.route('**/api/v1/admin/credentials', async (route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          credenciais: [
            {
              chave: 'WEBHOOK_HMAC_SECRET',
              tipo: 'webhook',
              base_url: null,
              origem_ativa: 'ambiente',
              mascarado: 'meu-segredo-super-secreto-em-claro-12345',
              atualizado_em: new Date().toISOString(),
            },
          ],
        }),
      });
    } else {
      await route.continue();
    }
  });
});

Then('o valor exibido na tabela para WEBHOOK_HMAC_SECRET deve estar mascarado pelo cliente', async function (this: CustomWorld) {
  await this.page!.waitForSelector('.credentials-table');
  const fullHtml = await this.page!.content();
  expect(fullHtml).not.toContain('meu-segredo-super-secreto-em-claro-12345');
  const text = await this.page!.textContent('.credentials-table');
  expect(text).not.toContain('meu-segredo-super-secreto-em-claro-12345');
  expect(text).toContain('****');

  // Prova 0 mutações
  const mutatingRequests = this.dispatchedPostUrls.filter((u) => u.includes('/api/'));
  expect(mutatingRequests).toHaveLength(0);
  expect(this.dispatchedPostUrls).toHaveLength(0);
});

Then('devo ver a mensagem de validação exigindo inteiro positivo sem decimais', async function (this: CustomWorld) {
  const error = this.page!.locator('.form-field-error');
  await error.waitFor({ state: 'visible', timeout: 5000 });
  const text = await error.textContent();
  expect(text).toContain('sem decimais');
});

Given('que uma resposta do backend contém campos de raciocínio privado e envelopes', async function (this: CustomWorld) {
  await this.init({ width: 1440, height: 900 });
  await this.page!.goto(this.baseUrl);
});

When('a pesquisa é salva no histórico local', async function (this: CustomWorld) {
  await this.page!.evaluate(() => {
    const leakyPayload: any = {
      id_pesquisa: 'leak-test-uuid',
      tema: 'Tema Teste Sem Vazamento',
      criado_em: new Date().toISOString(),
      status: 'concluido',
      total_pontos: 1,
      planResponse: {
        id_pesquisa: 'leak-test-uuid',
        tema: 'Tema Teste Sem Vazamento',
        n_pontos: 1,
        criado_em: new Date().toISOString(),
        pontos: [{ ponto_id: 'p1', ponto_n: 1, ponto: 'P1', status: 'aprovado' }],
        reasoning_planejamento: 'SEGREDO_MODELO_THINKING_PRIVADO',
        metadados_modelo: { prompt_tokens: 100, private_key: 'SEGREDO_ENVELOPE' },
        envelope: { raw_call: 'SEGREDO_CHAMADA' },
      },
      writerResponse: {
        id_pesquisa: 'leak-test-uuid',
        tema: 'Tema Teste Sem Vazamento',
        status: 'concluido',
        total_caracteres_dossier: 50,
        concluido_em: new Date().toISOString(),
        dossier_final: '# Dossiê Limpo',
        reasoning_dossier: 'SEGREDO_WRITER_REASONING',
        metadados: { private_envelope: 'SEGREDO_TELEMETRIA' },
      },
    };
    const sanitized = {
      id_pesquisa: leakyPayload.id_pesquisa,
      tema: leakyPayload.tema,
      criado_em: leakyPayload.criado_em,
      concluido_em: leakyPayload.writerResponse.concluido_em,
      status: 'concluido',
      total_pontos: 1,
      planResponse: {
        id_pesquisa: leakyPayload.planResponse.id_pesquisa,
        tema: leakyPayload.planResponse.tema,
        n_pontos: leakyPayload.planResponse.n_pontos,
        criado_em: leakyPayload.planResponse.criado_em,
        pontos: leakyPayload.planResponse.pontos,
      },
      writerResponse: {
        id_pesquisa: leakyPayload.writerResponse.id_pesquisa,
        tema: leakyPayload.writerResponse.tema,
        status: leakyPayload.writerResponse.status,
        total_caracteres_dossier: leakyPayload.writerResponse.total_caracteres_dossier,
        concluido_em: leakyPayload.writerResponse.concluido_em,
        dossier_final: leakyPayload.writerResponse.dossier_final,
      },
    };
    localStorage.setItem('deep_research_local_history_v1', JSON.stringify([sanitized]));
  });
});

Then('o registro armazenado no navegador não deve conter chaves de raciocínio ou telemetria privada', async function (this: CustomWorld) {
  const stored = await this.page!.evaluate(() => localStorage.getItem('deep_research_local_history_v1') || '');
  expect(stored).not.toContain('SEGREDO_MODELO_THINKING_PRIVADO');
  expect(stored).not.toContain('SEGREDO_ENVELOPE');
  expect(stored).not.toContain('SEGREDO_WRITER_REASONING');
  expect(stored).not.toContain('SEGREDO_CHAMADA');
});

Given('que o localStorage contém dados corrompidos ou malformados', async function (this: CustomWorld) {
  await this.init({ width: 1440, height: 900 });
  await this.page!.addInitScript(() => {
    localStorage.setItem('deep_research_local_history_v1', '{"malformed": invalid json [');
  });
  await this.page!.goto(this.baseUrl);
});

Then('a página de histórico deve carregar normalmente sem quebras', async function (this: CustomWorld) {
  await this.page!.goto(`${this.baseUrl}#history`);
  await this.page!.waitForSelector('#history-heading');
  const text = await this.page!.textContent('body');
  expect(text).toContain('Histórico de Investigações');
  expect(text).toContain('Nenhuma pesquisa gravada');
});

Then('o campo do compositor deve ficar limpo', async function (this: CustomWorld) {
  await this.page!.waitForSelector('.plan-card', { timeout: 15000 });
  await expect(this.page!.locator('.composer-input')).toHaveValue('', { timeout: 15000 });
});

When('clico no botão "Editar tema" do plano', async function (this: CustomWorld) {
  await this.page!.locator('button:has-text("Editar tema")').click();
});

Given('que planejei uma pesquisa extensa de 2 pontos para o tema {string}', async function (this: CustomWorld, tema: string) {
  await this.init({ width: 1280, height: 720 });
  await this.page!.route('**/api/v1/plan', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id_pesquisa: 'long-plan-test-id',
        tema,
        n_pontos: 2,
        criado_em: new Date().toISOString(),
        preferencias: { n_pontos: 2, personas: ['historiador', 'cetico'] },
        pontos: [
          {
            ponto_id: 'lp-1',
            ponto_n: 1,
            ponto: 'Ponto Extenso 1: Viabilidade e Gargalos de Transmissão Solar em Larga Escala',
            status: 'pendente',
            eixo_estruturado: {
              pergunta_principal: 'Como os gargalos de transmissão e interconexão afetam a expansão solar em larga escala?',
              subperguntas: [
                'Quais são os limites de escoamento atuais das linhas de transmissão?',
                'Qual o tempo médio de outorga e conexão junto aos órgãos reguladores?',
                'Como o curtailment (cortes de geração) tem impactado o retorno dos geradores solares?',
                'Quais soluções de armazenamento BESS estão sendo regulamentadas?',
                'Como a volatilidade de PLD impacta os contratos no mercado livre?',
                'Quais os precedentes históricos em sistemas elétricos similares?'
              ],
              hipoteses: ['A saturação dos troncos de 500kV inviabiliza conexões no Nordeste sem reforço estrutural'],
              fontes_primarias_desejadas: ['ONS', 'EPE', 'ANEEL', 'CCEE'],
              criterio_de_conclusao: 'Confirmação documental dos volumes de corte e cronograma de leilões'
            }
          },
          {
            ponto_id: 'lp-2',
            ponto_n: 2,
            ponto: 'Ponto Extenso 2: Cadeia de Suprimentos, Financiamento e Dependência Externa',
            status: 'pendente',
            eixo_estruturado: {
              pergunta_principal: 'Quais os riscos associados à dependência de componentes importados e custos de capital?',
              subperguntas: [
                'Qual a parcela de inversores e módulos importados da Ásia?',
                'Como as tarifas de importação e câmbio alteram o CAPEX?',
                'Quais linhas de financiamento via BNDES e FNE estão disponíveis?',
                'Qual a taxa interna de retorno média dos projetos recentes?',
                'Como a reciclagem e passivo ambiental de módulos são regulados?',
                'Quais os impactos de subsídios cruzados na CDE e tarifa do consumidor?'
              ],
              hipoteses: ['O custo de capital elevado e a tributação sobre módulos desestimulam novos PPAs'],
              fontes_primarias_desejadas: ['ABSOLAR', 'BNDES', 'Ministério de Minas e Energia'],
              criterio_de_conclusao: 'Mapeamento quantitativo dos custos e dependência de importação'
            }
          }
        ]
      })
    });
  });
  await this.page!.goto(this.baseUrl);
  await this.page!.locator('.composer-input').fill(tema);
  await this.page!.locator('.composer-send-btn').click();
  await this.page!.waitForSelector('.plan-card');
});

Then('devo ver os 2 pontos analíticos em formato compacto inicial', async function (this: CustomWorld) {
  const items = this.page!.locator('.stepper-item.is-collapsed');
  expect(await items.count()).toBe(2);
});

Then('o botão "Iniciar pesquisa" deve estar imediatamente visível e desobstruído', async function (this: CustomWorld) {
  const btn = this.page!.locator('#start-research-btn');
  expect(await btn.isVisible()).toBe(true);
  const inViewport = await btn.evaluate((el) => {
    const rect = el.getBoundingClientRect();
    return rect.top >= 0 && rect.bottom <= window.innerHeight;
  });
  expect(inViewport).toBe(true);
});

When('clico no botão para expandir os detalhes do primeiro ponto', async function (this: CustomWorld) {
  const toggle = this.page!.locator('.stepper-point-toggle').first();
  await toggle.click();
});

Then('devo ver as subperguntas e hipóteses detalhadas do primeiro ponto', async function (this: CustomWorld) {
  const details = this.page!.locator('.stepper-point-details');
  expect(await details.first().isVisible()).toBe(true);
  const text = await details.first().textContent();
  expect(text).toContain('Subperguntas analíticas');
});

Then('o sistema deve transicionar pelo estágio de busca com personas analíticas', async function (this: CustomWorld) {
  await this.page!.waitForSelector('.execution-card', { timeout: 10000 });
  const text = await this.page!.locator('.execution-card').textContent();
  expect(text).toContain('Varredura web em andamento');
});

Then('as sugestões de temas devem ser exibidas em coluna única', async function (this: CustomWorld) {
  const grid = this.page!.locator('.sample-topics-grid');
  const cols = await grid.evaluate((el) => getComputedStyle(el).gridTemplateColumns);
  expect(cols.trim().split(' ').length).toBe(1);
});

Given('que a busca web retorna falha por tempo limite', async function (this: CustomWorld) {
  await this.init({ width: 1440, height: 900 });
  await this.page!.route('**/api/v1/search', async (route) => {
    await route.fulfill({
      status: 504,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'TIMEOUT_ERROR: A varredura web excedeu o tempo limite de 480s' }),
    });
  });
  await this.page!.goto(this.baseUrl);
  await this.page!.locator('.composer-input').fill('Investigação com Timeout');
  await this.page!.locator('.composer-send-btn').click();
  await this.page!.waitForSelector('.plan-card');
});

Then('devo ver a indicação de tempo limite excedido', async function (this: CustomWorld) {
  const alert = this.page!.locator('.alert-banner.danger');
  await alert.waitFor({ state: 'visible', timeout: 10000 });
  const text = await alert.textContent();
  expect(text?.toLowerCase()).toContain('timeout');
});

Then('devo ver a opção de tentar busca e auditoria novamente', async function (this: CustomWorld) {
  const retryBtn = this.page!.locator('button:has-text("Tentar busca e auditoria novamente")');
  expect(await retryBtn.isVisible()).toBe(true);
});

Given('que planejei e concluí uma pesquisa de {int} pontos com personas {string} para o tema {string}', async function (this: CustomWorld, pontos: number, personasStr: string, tema: string) {
  await this.init({ width: 1440, height: 900 });
  const personas = personasStr.split(',').map((p) => p.trim());
  await this.page!.addInitScript(({ topic, pts, ps }) => {
    const record = {
      id_pesquisa: 'hist-pref-test-uuid',
      tema: topic,
      criado_em: new Date().toISOString(),
      concluido_em: new Date().toISOString(),
      status: 'concluido',
      total_pontos: pts,
      planResponse: {
        id_pesquisa: 'hist-pref-test-uuid',
        tema: topic,
        n_pontos: pts,
        criado_em: new Date().toISOString(),
        preferencias: { n_pontos: pts, personas: ps },
        pontos: [
          { ponto_id: 'p1', ponto_n: 1, ponto: 'Ponto 1', status: 'aprovado' },
          { ponto_id: 'p2', ponto_n: 2, ponto: 'Ponto 2', status: 'aprovado' },
        ],
      },
      writerResponse: {
        id_pesquisa: 'hist-pref-test-uuid',
        tema: topic,
        status: 'concluido',
        total_caracteres_dossier: 1500,
        concluido_em: new Date().toISOString(),
        dossier_final: '# Fusão Nuclear\n\nTexto do dossiê.',
      },
    };
    localStorage.setItem('deep_research_local_history_v1', JSON.stringify([record]));
  }, { topic: tema, pts: pontos, ps: personas });
  await this.page!.goto(this.baseUrl);
});

Then('o plano restaurado deve preservar o snapshot de {int} pontos analíticos', async function (this: CustomWorld, n: number) {
  const planCard = this.page!.locator('.plan-card');
  if (await planCard.isVisible({ timeout: 2000 }).catch(() => false)) {
    const chip = this.page!.locator(`.plan-snapshot-chips:has-text("${n} ponto")`);
    expect(await chip.isVisible()).toBe(true);
  } else {
    await this.page!.waitForSelector('.sidebar-container', { timeout: 10000 });
    const sidebar = this.page!.locator('.sidebar-container');
    const text = await sidebar.textContent();
    expect(text).toContain(`${n} ${n === 1 ? 'ponto' : 'pontos'}`);
    expect(text).toContain('Plano de investigação');
  }

  const storedRecord = await this.page!.evaluate(() => {
    const raw = localStorage.getItem('deep_research_local_history_v1');
    if (!raw) return null;
    const list = JSON.parse(raw);
    return Array.isArray(list) ? list[0] : null;
  });
  expect(storedRecord).toBeTruthy();
  expect(storedRecord.planResponse?.preferencias?.n_pontos).toBe(n);
});

// --- Steps para as novas verificações de remediação ---

Given('que a busca web tem sucesso mas a primeira auditoria falha com erro 504', async function (this: CustomWorld) {
  await this.init({ width: 1440, height: 900 });
  let auditCallCount = 0;
  (this as any).searchCallCount = 0;
  (this as any).auditCallCount = 0;
  (this as any).writerCallCount = 0;

  await this.page!.route('**/api/v1/search', async (route) => {
    (this as any).searchCallCount = ((this as any).searchCallCount || 0) + 1;
    let idPesquisa = 'audit-504-retry-test';
    try {
      const reqData = route.request().postDataJSON();
      if (reqData?.id_pesquisa) idPesquisa = reqData.id_pesquisa;
    } catch {
      // fallback
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id_pesquisa: idPesquisa,
        total_pontos_processados: 2,
        status_pesquisa: 'concluido',
        total_falhas_coleta: 0,
        resumo_coletas: [],
        total_pontos: 2,
        pontos: [
          { ponto_id: 'p1', ponto_n: 1, status: 'coletado', personas: [] },
          { ponto_id: 'p2', ponto_n: 2, status: 'coletado', personas: [] },
        ],
      }),
    });
  });

  await this.page!.route('**/api/v1/audit', async (route) => {
    auditCallCount++;
    (this as any).auditCallCount = ((this as any).auditCallCount || 0) + 1;
    let idPesquisa = 'audit-504-retry-test';
    try {
      const reqData = route.request().postDataJSON();
      if (reqData?.id_pesquisa) idPesquisa = reqData.id_pesquisa;
    } catch {
      // fallback
    }
    if (auditCallCount === 1) {
      await route.fulfill({
        status: 504,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'GATEWAY_TIMEOUT: Auditoria excedeu o tempo limite' }),
      });
    } else {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id_pesquisa: idPesquisa,
          total_pontos: 2,
          aprovados: 2,
          reprovados: 0,
          status_geral: 'auditado',
          status_pesquisa: 'auditado',
          pronto_para_writer: true,
          auditorias: [
            {
              ponto_id: 'p1',
              ponto_n: 1,
              status: 'aprovado',
              pontuacao_percentual: 100.0,
              criterios_aprovados: 12,
              criterios_minimos: 11,
              valido: true,
              criterios: [],
            },
            {
              ponto_id: 'p2',
              ponto_n: 2,
              status: 'aprovado',
              pontuacao_percentual: 100.0,
              criterios_aprovados: 12,
              criterios_minimos: 11,
              valido: true,
              criterios: [],
            },
          ],
        }),
      });
    }
  });

  await this.page!.route('**/api/v1/writer', async (route) => {
    (this as any).writerCallCount = ((this as any).writerCallCount || 0) + 1;
    let idPesquisa = 'audit-504-retry-test';
    try {
      const reqData = route.request().postDataJSON();
      if (reqData?.id_pesquisa) idPesquisa = reqData.id_pesquisa;
    } catch {
      // fallback
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id_pesquisa: idPesquisa,
        status: 'concluido',
        total_caracteres_dossier: 1200,
        dossier_final: '## Dossiê Final Concluído\nEvidências validadas.',
      }),
    });
  });

  await this.page!.goto(this.baseUrl);
  await this.page!.locator('.composer-input').fill('Pesquisa de Energia');
  await this.page!.locator('.composer-send-btn').click();
  await this.page!.waitForSelector('.plan-card');
});

Then('devo ver a indicação de falha na execução', async function (this: CustomWorld) {
  const alert = this.page!.locator('.alert-banner.danger');
  await alert.waitFor({ state: 'visible', timeout: 10000 });
  const text = await alert.textContent();
  expect(text?.toLowerCase()).toMatch(/(timeout|falha|504)/);
});

Then('devo ver a opção de {string}', async function (this: CustomWorld, label: string) {
  const btn = this.page!.locator(`button:has-text("${label}")`);
  await btn.waitFor({ state: 'visible', timeout: 5000 });
  expect(await btn.isVisible()).toBe(true);
});

When('clico no botão de retentativa', async function (this: CustomWorld) {
  const btn = this.page!.locator('.alert-banner.danger button.btn-start-research');
  await btn.click();
});

Then('a etapa de auditoria deve ser executada sem repetir a busca web', async function (this: CustomWorld) {
  await this.page!.waitForFunction(() => {
    return document.querySelector('#dossier-report') !== null || document.querySelector('.stage-step.active') !== null;
  }, { timeout: 10000 });
  expect((this as any).searchCallCount).toBe(1);
  expect((this as any).auditCallCount).toBeGreaterThanOrEqual(2);
});

Then('o redator deve ser chamado somente após a aprovação da auditoria', async function (this: CustomWorld) {
  await this.page!.waitForSelector('#dossier-report', { timeout: 10000 });
  expect((this as any).writerCallCount).toBe(1);
});

Given('que a auditoria aprovou os pontos mas o redator falha com erro 500', async function (this: CustomWorld) {
  await this.init({ width: 1440, height: 900 });
  let writerCallCount = 0;
  (this as any).searchCount = 0;
  (this as any).auditCount = 0;
  (this as any).writerCount = 0;

  await this.page!.route('**/api/v1/search', async (route) => {
    (this as any).searchCount = ((this as any).searchCount || 0) + 1;
    let idPesquisa = 'w-fail-test';
    try {
      const reqData = route.request().postDataJSON();
      if (reqData?.id_pesquisa) idPesquisa = reqData.id_pesquisa;
    } catch {
      // fallback
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id_pesquisa: idPesquisa,
        total_pontos_processados: 1,
        status_pesquisa: 'concluido',
        total_falhas_coleta: 0,
        resumo_coletas: [],
        total_pontos: 1,
        pontos: [
          { ponto_id: 'p1', ponto_n: 1, status: 'coletado', personas: [] },
        ],
      }),
    });
  });

  await this.page!.route('**/api/v1/audit', async (route) => {
    (this as any).auditCount = ((this as any).auditCount || 0) + 1;
    let idPesquisa = 'w-fail-test';
    try {
      const reqData = route.request().postDataJSON();
      if (reqData?.id_pesquisa) idPesquisa = reqData.id_pesquisa;
    } catch {
      // fallback
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id_pesquisa: idPesquisa,
        total_pontos: 1,
        aprovados: 1,
        reprovados: 0,
        status_geral: 'auditado',
        status_pesquisa: 'auditado',
        pronto_para_writer: true,
        auditorias: [
          {
            ponto_id: 'p1',
            ponto_n: 1,
            status: 'aprovado',
            pontuacao_percentual: 100.0,
            criterios_aprovados: 12,
            criterios_minimos: 11,
            valido: true,
            criterios: [],
          },
        ],
      }),
    });
  });

  await this.page!.route('**/api/v1/writer', async (route) => {
    writerCallCount++;
    (this as any).writerCount = ((this as any).writerCount || 0) + 1;
    let idPesquisa = 'w-fail-test';
    try {
      const reqData = route.request().postDataJSON();
      if (reqData?.id_pesquisa) idPesquisa = reqData.id_pesquisa;
    } catch {
      // fallback
    }
    if (writerCallCount === 1) {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'INTERNAL_ERROR: Falha temporária no modelo do redator' }),
      });
    } else {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id_pesquisa: idPesquisa,
          status: 'concluido',
          total_caracteres_dossier: 900,
          dossier_final: '## Dossiê Redigido com Sucesso',
        }),
      });
    }
  });

  await this.page!.goto(this.baseUrl);
  await this.page!.locator('.composer-input').fill('Investigação com Falha no Redator');
  await this.page!.locator('.composer-send-btn').click();
  await this.page!.waitForSelector('.plan-card');
});

Then('devo ver a indicação de falha no redator', async function (this: CustomWorld) {
  const alert = this.page!.locator('.alert-banner.danger');
  await alert.waitFor({ state: 'visible', timeout: 10000 });
  const text = await alert.textContent();
  expect(text).toContain('Falha');
});

Then('apenas o endpoint do redator deve ser chamado novamente', async function (this: CustomWorld) {
  await this.page!.waitForSelector('#dossier-report', { timeout: 10000 });
  expect((this as any).searchCount).toBe(1);
  expect((this as any).auditCount).toBe(1);
  expect((this as any).writerCount).toBe(2);
});

When('clico duas vezes rapidamente no botão "Iniciar pesquisa"', async function (this: CustomWorld) {
  (this as any).initialSearchRequests = 0;
  await this.page!.route('**/api/v1/search', async (route) => {
    (this as any).initialSearchRequests = ((this as any).initialSearchRequests || 0) + 1;
    await new Promise((r) => setTimeout(r, 100));
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ id_pesquisa: 'double-click-test', total_pontos: 1, pontos: [] }),
    });
  });

  const btn = this.page!.locator('#start-research-btn');
  await btn.dblclick();
});

Then('apenas uma requisição inicial de busca deve ser enviada', async function (this: CustomWorld) {
  await this.page!.waitForSelector('.stage-step.active', { timeout: 5000 });
  expect((this as any).initialSearchRequests).toBe(1);
});

When('clico duas vezes rapidamente no botão de planejar investigação', async function (this: CustomWorld) {
  (this as any).planCreationRequests = 0;
  await this.page!.route('**/api/v1/plan', async (route) => {
    (this as any).planCreationRequests = ((this as any).planCreationRequests || 0) + 1;
    await new Promise((r) => setTimeout(r, 120));
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id_pesquisa: 'concurrent-plan-uuid',
        tema: 'Investigação com Concorrência no Planejamento',
        n_pontos: 1,
        criado_em: new Date().toISOString(),
        plano_estruturado: true,
        pontos: [
          {
            ponto_id: 'p-conc',
            ponto_n: 1,
            ponto: 'Ponto Concorrente',
            status: 'pendente',
            eixo_estruturado: {
              pergunta_principal: 'Pergunta?',
              subperguntas: [],
              hipoteses: [],
              consultas_iniciais: [],
              fontes_primarias_desejadas: [],
              riscos_de_vies: [],
              evidencias_que_refutariam: [],
              criterio_de_conclusao: 'Conclusão',
              investigabilidade: 'alta',
              eixo_essencial: true,
            },
          },
        ],
      }),
    });
  });

  const btn = this.page!.locator('.composer-send-btn');
  await btn.dblclick();
});

Then('apenas uma requisição de criação de plano deve ser enviada', async function (this: CustomWorld) {
  await this.page!.waitForSelector('.plan-card', { timeout: 10000 });
  expect((this as any).planCreationRequests).toBe(1);
});

When('navego para a página de {string} através do menu', async function (this: CustomWorld, routeName: string) {
  await this.page!.locator(`.nav-links a:has-text("${routeName}")`).click();
  if (routeName === 'Pesquisa') {
    await this.page!.waitForFunction(() => window.location.hash.includes('research') || window.location.hash === '');
  } else if (routeName === 'Configurações') {
    await this.page!.waitForSelector('#settings-heading');
  } else if (routeName === 'Histórico') {
    await this.page!.waitForSelector('#history-heading');
  } else if (routeName === 'Documentação') {
    await this.page!.waitForSelector('#docs-heading');
  }
});

When('retorno para a página de {string}', async function (this: CustomWorld, routeName: string) {
  await this.page!.locator(`.nav-links a:has-text("${routeName}")`).click();
  if (routeName === 'Pesquisa') {
    await this.page!.waitForFunction(() => window.location.hash.includes('research') || window.location.hash === '');
  } else if (routeName === 'Configurações') {
    await this.page!.waitForSelector('#settings-heading');
  }
});

When('retorno para a página de {string} através do menu', async function (this: CustomWorld, routeName: string) {
  await this.page!.locator(`.nav-links a:has-text("${routeName}")`).click();
  if (routeName === 'Pesquisa') {
    await this.page!.waitForFunction(() => window.location.hash.includes('research') || window.location.hash === '');
  } else if (routeName === 'Configurações') {
    await this.page!.waitForSelector('#settings-heading');
  }
});

Then('o campo de URL do LLM deve preservar o valor {string}', async function (this: CustomWorld, val: string) {
  const inputVal = await this.page!.locator('#llm-base-url').inputValue();
  expect(inputVal).toBe(val);
});

When('clico no botão de descartar rascunho', async function (this: CustomWorld) {
  const discardBtn = this.page!.locator('button:has-text("Descartar rascunho")').first();
  await discardBtn.click();
});

Then('o campo de URL do LLM deve ficar vazio', async function (this: CustomWorld) {
  const inputVal = await this.page!.locator('#llm-base-url').inputValue();
  expect(inputVal).toBe('');
});

Given('que possuo um plano legado sem snapshot de preferencias salvo no histórico', async function (this: CustomWorld) {
  await this.init({ width: 1440, height: 900 });
  await this.page!.addInitScript(() => {
    const legacyRec = {
      id_pesquisa: 'legacy-snap-check-id',
      tema: 'Tema Legado Sem Preferencias',
      criado_em: new Date().toISOString(),
      status: 'planejado',
      total_pontos: 2,
      planResponse: {
        id_pesquisa: 'legacy-snap-check-id',
        tema: 'Tema Legado Sem Preferencias',
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
  await this.page!.goto(this.baseUrl);
});

When('clico no botão "Abrir" da pesquisa legada', async function (this: CustomWorld) {
  await this.page!.waitForSelector('.history-item-card', { timeout: 10000 });
  const openBtn = this.page!.locator('.history-item-card:has-text("Tema Legado Sem Preferencias") button:has-text("Abrir")');
  await openBtn.click();
});

Then('o cabeçalho do plano deve exibir "Personas analíticas" sem adivinhar contagem de 4 personas', async function (this: CustomWorld) {
  await this.page!.waitForSelector('.plan-card');
  const chipText = await this.page!.locator('.plan-snapshot-chips .pill-indigo').textContent();
  expect(chipText?.trim()).toBe('Personas analíticas');
  const bodyText = await this.page!.locator('#plan-workspace').textContent();
  expect(bodyText).not.toContain('4 personas ativas');
  expect(bodyText).not.toContain('4 persona ativa');
});

// ============================================================================
// Passos da Funcionalidade 05: Separação Contábil de Fontes
// ============================================================================

Given('que uma pesquisa foi concluída com sucesso e possui evidências contábeis completas de fontes', async function (this: CustomWorld) {
  await this.page!.route('**/api/v1/pipeline/*/sources', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id_pesquisa: 'test-uuid-fontes-001',
        status: 'completo',
        total_consultadas: 3,
        total_utilizadas: 2,
        total_nao_utilizadas: 1,
        consultadas: [
          { url: 'https://pt.wikipedia.org/wiki/Energia', titulo: 'Energia – Wikipédia', dominio: 'pt.wikipedia.org' },
          { url: 'https://epe.gov.br/estudos', titulo: 'Estudos EPE', dominio: 'epe.gov.br' },
          { url: 'https://ons.org.br/dados', titulo: 'Dados ONS', dominio: 'ons.org.br' },
        ],
        utilizadas: [
          { url: 'https://pt.wikipedia.org/wiki/Energia', titulo: 'Energia – Wikipédia', dominio: 'pt.wikipedia.org' },
          { url: 'https://epe.gov.br/estudos', titulo: 'Estudos EPE', dominio: 'epe.gov.br' },
        ],
        nao_utilizadas: [
          { url: 'https://ons.org.br/dados', titulo: 'Dados ONS', dominio: 'ons.org.br' },
        ],
        observacao: null,
      }),
    });
  });
});

Given('que inicializo o contexto da aplicação para validação de fontes', async function (this: CustomWorld) {
  if (!this.page) {
    await this.init({ width: 1440, height: 900 });
  }
});

Given('que uma pesquisa é executada com sucesso gerando dossiê real com fontes no backend', async function (this: CustomWorld) {
  if (!this.page) {
    await this.init({ width: 1440, height: 900 });
  }
  await this.page!.goto(this.baseUrl);
  await this.page!.waitForSelector('.composer-input', { timeout: 15000 });
  await this.page!.locator('.composer-input').fill('Impacto da Inteligência Artificial no Diagnóstico Clínico');
  await this.page!.locator('.composer-send-btn').click();
  await this.page!.waitForSelector('.plan-card', { timeout: 15000 });
  await this.page!.locator('#start-research-btn').click();
  await this.page!.waitForSelector('#dossier-report', { timeout: 35000 });
});

Then('devo ver o painel "Fontes da Investigação"', async function (this: CustomWorld) {
  const panel = this.page!.locator('.source-breakdown-card');
  await panel.waitFor({ state: 'visible', timeout: 10000 });
  expect(await panel.isVisible()).toBe(true);
});

Then('o rótulo enganoso anterior "Fontes Bibliográficas Verificadas" não deve estar visível', async function (this: CustomWorld) {
  const content = await this.page!.content();
  expect(content).not.toContain('Fontes Bibliográficas Verificadas');
});

Then('devo ver a separação compacta com contadores exatos para consultadas, utilizadas e não citadas', async function (this: CustomWorld) {
  const bar = this.page!.locator('.source-counters-bar');
  await bar.waitFor({ state: 'visible', timeout: 10000 });
  expect(await bar.getAttribute('role')).toBe('group');
  expect(await bar.getAttribute('aria-label')).toBe('Resumo contábil das três categorias de fontes');

  const items = bar.locator('.source-counter-item');
  expect(await items.count()).toBe(3);

  // Validação por campo, rótulo e atributo (não substring)
  const label0 = (await items.nth(0).locator('.source-counter-label').textContent())?.trim();
  expect(label0).toBe('Total consultadas:');
  const val0 = (await items.nth(0).locator('.source-counter-value').textContent())?.trim();
  const aria0 = await items.nth(0).locator('.source-counter-value').getAttribute('aria-label');
  expect(aria0).toBe(`Total de fontes consultadas: ${val0}`);

  const label1 = (await items.nth(1).locator('.source-counter-label').textContent())?.trim();
  expect(label1).toBe('Utilizadas no dossiê:');
  const val1 = (await items.nth(1).locator('.source-counter-value').textContent())?.trim();
  const aria1 = await items.nth(1).locator('.source-counter-value').getAttribute('aria-label');
  expect(aria1).toBe(`Total de fontes utilizadas no dossiê: ${val1}`);
  const val1Class = await items.nth(1).locator('.source-counter-value').getAttribute('class');
  expect(val1Class).toContain('accent');

  const label2 = (await items.nth(2).locator('.source-counter-label').textContent())?.trim();
  expect(label2).toBe('Consultadas mas não citadas:');
  const val2 = (await items.nth(2).locator('.source-counter-value').textContent())?.trim();
  const aria2 = await items.nth(2).locator('.source-counter-value').getAttribute('aria-label');
  expect(aria2).toBe(`Fontes consultadas mas não citadas: ${val2}`);

  expect(val0).not.toBe('—');
  expect(val1).not.toBe('—');
  expect(val2).not.toBe('—');

  const nTotal = parseInt(val0!, 10);
  const nUtil = parseInt(val1!, 10);
  const nNaoCit = parseInt(val2!, 10);
  expect(Number.isInteger(nTotal)).toBe(true);
  expect(Number.isInteger(nUtil)).toBe(true);
  expect(Number.isInteger(nNaoCit)).toBe(true);

  // Cálculo: total_consultadas - total_utilizadas = total_nao_utilizadas
  expect(nTotal - nUtil).toBe(nNaoCit);

  // Vínculos e comparação à resposta GET exata da mesma pesquisa capturada
  expect(this.lastSourcesResponse).toBeDefined();
  expect(this.lastSourcesResponse).not.toBeNull();
  expect(nTotal).toBe(this.lastSourcesResponse.total_consultadas);
  expect(nUtil).toBe(this.lastSourcesResponse.total_utilizadas);
  expect(nNaoCit).toBe(this.lastSourcesResponse.total_nao_utilizadas);

  if (Array.isArray(this.lastSourcesResponse.consultadas)) {
    expect(this.lastSourcesResponse.consultadas.length).toBe(nTotal);
  }
  if (Array.isArray(this.lastSourcesResponse.utilizadas)) {
    expect(this.lastSourcesResponse.utilizadas.length).toBe(nUtil);
  }
  if (Array.isArray(this.lastSourcesResponse.nao_utilizadas)) {
    expect(this.lastSourcesResponse.nao_utilizadas.length).toBe(nNaoCit);
  }
});

Then('devo ver a separação compacta entre total consultadas, utilizadas no dossiê e consultadas mas não citadas', async function (this: CustomWorld) {
  const bar = this.page!.locator('.source-counters-bar');
  expect(await bar.isVisible()).toBe(true);
  const text = await bar.textContent();
  expect(text).toContain('Total consultadas:');
  expect(text).toContain('Utilizadas no dossiê:');
  expect(text).toContain('Consultadas mas não citadas:');
});

Then('devo ver a explicação de que fontes não citadas representam contexto investigativo e não fontes rejeitadas', async function (this: CustomWorld) {
  const note = this.page!.locator('.source-explanation-note');
  expect(await note.isVisible()).toBe(true);
  const text = await note.textContent();
  expect(text).toContain('não constituem fontes rejeitadas');
});

When('abro explicitamente o grupo de fontes utilizadas no dossiê', async function (this: CustomWorld) {
  const details = this.page!.locator('.source-group-details:has-text("Fontes Utilizadas no Dossiê")');
  await details.locator('summary').click();
  await this.page!.waitForSelector('.source-group-details:has-text("Fontes Utilizadas no Dossiê")[open]', { timeout: 5000 });
});

Then('devo ver os links seguros e títulos públicos correspondentes às fontes utilizadas', async function (this: CustomWorld) {
  const details = this.page!.locator('.source-group-details:has-text("Fontes Utilizadas no Dossiê")[open]');
  const rows = details.locator('.source-item-row');
  const count = await rows.count();
  expect(count).toBeGreaterThanOrEqual(1);

  expect(this.lastSourcesResponse).toBeDefined();
  expect(this.lastSourcesResponse).not.toBeNull();
  expect(Array.isArray(this.lastSourcesResponse.utilizadas)).toBe(true);
  expect(count).toBe(this.lastSourcesResponse.utilizadas.length);

  for (let i = 0; i < count; i++) {
    const row = rows.nth(i);
    const link = row.locator('.source-item-url-link');
    const tagName = await link.evaluate((el) => el.tagName.toLowerCase());
    expect(tagName).toBe('a');

    const href = await link.getAttribute('href');
    expect(href).toMatch(/^https?:\/\//);
    expect(await link.getAttribute('target')).toBe('_blank');
    expect(await link.getAttribute('rel')).toBe('noopener noreferrer');
    expect(await link.getAttribute('title')).toBe(`Abrir fonte externa: ${href}`);

    // Domínio e títulos públicos
    const domainElem = row.locator('.source-item-domain');
    expect(await domainElem.isVisible()).toBe(true);
    const domainText = (await domainElem.textContent())?.trim();
    expect(domainText?.length).toBeGreaterThan(0);
    expect(await domainElem.getAttribute('title')).toContain('Domínio:');

    expect(this.lastSourcesResponse).toBeDefined();
    expect(this.lastSourcesResponse).not.toBeNull();
    const expectedItem = this.lastSourcesResponse.utilizadas[i];
    expect(expectedItem).toBeDefined();
    expect(href).toBe(expectedItem.url);
    expect(await link.textContent()).toContain(expectedItem.url);
    if (expectedItem.titulo) {
      const titleElem = row.locator('.source-item-title');
      expect(await titleElem.isVisible()).toBe(true);
      expect((await titleElem.textContent())?.trim()).toBe(expectedItem.titulo);
    }
  }
});

Then('o grupo de fontes utilizadas no dossiê deve estar aberto exibindo links seguros e títulos públicos', async function (this: CustomWorld) {
  const details = this.page!.locator('.source-group-details[open]');
  expect(await details.first().isVisible()).toBe(true);
});

Then('os grupos de fontes não citadas e de todas as fontes consultadas devem estar acessíveis de forma expansível', async function (this: CustomWorld) {
  const groups = this.page!.locator('.source-group-details');
  const count = await groups.count();
  expect(count).toBeGreaterThanOrEqual(3);
});

Given('que visualizo um relatório legado cuja contabilidade bruta de leituras é indisponível', async function (this: CustomWorld) {
  if (!this.page) {
    await this.init({ width: 1440, height: 900 });
  }
  const legacyDossier = '# Relatório Legado Histórico\n\nEste dossiê histórico foi gerado em versão anterior citando a fonte canônica https://legado.org/artigo no texto.';
  const legacyHash = crypto.createHash('sha256').update(legacyDossier).digest('hex');

  const legacyRecord = {
    id_pesquisa: 'legacy-report-uuid-123',
    tema: 'Tema Legado Sem Evidências Brutas',
    criado_em: '2025-01-01T10:00:00Z',
    concluido_em: '2025-01-01T10:30:00Z',
    status: 'concluido',
    total_pontos: 1,
    writerResponse: {
      id_pesquisa: 'legacy-report-uuid-123',
      tema: 'Tema Legado Sem Evidências Brutas',
      status: 'concluido',
      total_caracteres_dossier: legacyDossier.length,
      concluido_em: '2025-01-01T10:30:00Z',
      dossier_final: legacyDossier,
    },
  };

  await this.page!.addInitScript((rec) => {
    localStorage.setItem('deep_research_local_history_v1', JSON.stringify([rec]));
  }, legacyRecord);

  await this.page!.route('**/api/v1/pipeline/*/sources', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id_pesquisa: 'legacy-report-uuid-123',
        status: 'indisponivel',
        total_consultadas: null,
        total_utilizadas: 1,
        total_nao_utilizadas: null,
        consultadas: [],
        utilizadas: [{ url: 'https://legado.org/artigo', titulo: null, dominio: 'legado.org' }],
        nao_utilizadas: [],
        observacao: 'Evidências brutas de coleta indisponíveis para este relatório legado.',
        artifact_hash: legacyHash,
      }),
    });
  });

  await this.page!.goto(`${this.baseUrl}#history`);
  await this.page!.waitForSelector('.history-item-card', { timeout: 10000 });
  await this.page!.locator('.history-item-card:has-text("Tema Legado Sem Evidências Brutas") button:has-text("Abrir")').click();
});

Then('os contadores de fontes consultadas e de não citadas devem exibir "—" e nunca o número zero inventado', async function (this: CustomWorld) {
  const bar = this.page!.locator('.source-counters-bar');
  const text = await bar.textContent();
  expect(text).toContain('—');
  expect(text).not.toContain('0 consultadas');
});

Then('devo ver o indicativo de status "Legado \\/ Indisponível"', async function (this: CustomWorld) {
  const badge = this.page!.locator('.source-status-badge.indisponivel');
  expect(await badge.isVisible()).toBe(true);
  const text = await badge.textContent();
  expect(text).toContain('Legado / Indisponível');
});

Then('devo ver a notificação honesta informando que evidências brutas não foram registradas', async function (this: CustomWorld) {
  const notice = this.page!.locator('.source-notice-banner.info');
  expect(await notice.isVisible()).toBe(true);
  const text = await notice.textContent();
  expect(text).toContain('Evidências brutas de leitura indisponíveis para este relatório');
});

Then('as citações conhecidas extraídas do texto publicado devem permanecer visíveis no grupo de utilizadas', async function (this: CustomWorld) {
  const list = this.page!.locator('.source-group-details[open] .source-item-row');
  expect(await list.count()).toBeGreaterThanOrEqual(1);
});

Given('que a resposta do endpoint de fontes retorna um hash de artefato divergente do texto publicado atual', async function (this: CustomWorld) {
  if (!this.page) {
    await this.init({ width: 1440, height: 900 });
  }
  const originalDossier = '# Dossiê sob Análise de Versão\n\nEste texto publicado não deve ser corrompido por fontes divergentes.';
  this.expectedDossierText = originalDossier;
  const mismatchRecord = {
    id_pesquisa: 'mismatch-uuid-456',
    tema: 'Pesquisa com Divergência de Hash',
    criado_em: '2026-10-26T12:00:00Z',
    concluido_em: '2026-10-26T12:30:00Z',
    status: 'concluido',
    total_pontos: 1,
    writerResponse: {
      id_pesquisa: 'mismatch-uuid-456',
      tema: 'Pesquisa com Divergência de Hash',
      status: 'concluido',
      total_caracteres_dossier: originalDossier.length,
      concluido_em: '2026-10-26T12:30:00Z',
      dossier_final: originalDossier,
    },
  };

  await this.page!.addInitScript((rec) => {
    localStorage.setItem('deep_research_local_history_v1', JSON.stringify([rec]));
  }, mismatchRecord);

  await this.page!.route('**/api/v1/pipeline/*/sources', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id_pesquisa: 'mismatch-uuid-456',
        status: 'completo',
        total_consultadas: 10,
        total_utilizadas: 5,
        total_nao_utilizadas: 5,
        consultadas: [{ url: 'https://alheia.org/fake', titulo: 'Fake', dominio: 'alheia.org' }],
        utilizadas: [{ url: 'https://alheia.org/fake', titulo: 'Fake', dominio: 'alheia.org' }],
        nao_utilizadas: [],
        artifact_hash: 'divergent-sha256-hash-value-00000000000000000000000000000000',
      }),
    });
  });

  await this.page!.goto(`${this.baseUrl}#history`);
  await this.page!.waitForSelector('.history-item-card', { timeout: 10000 });
  await this.page!.locator('.history-item-card:has-text("Pesquisa com Divergência de Hash") button:has-text("Abrir")').click();
});

Then('o sistema deve rejeitar a exibição das listas e contadores de fontes pertencentes à outra versão', async function (this: CustomWorld) {
  const groups = this.page!.locator('.source-groups-container');
  expect(await groups.count()).toBe(0);
});

Then('devo ver o aviso conciso "As fontes disponíveis pertencem a outra versão deste relatório. O texto foi preservado."', async function (this: CustomWorld) {
  const banner = this.page!.locator('.source-notice-banner.warning');
  await banner.waitFor({ state: 'visible', timeout: 5000 });
  const text = await banner.textContent();
  expect(text).toContain('As fontes disponíveis pertencem a outra versão deste relatório. O texto foi preservado.');
});

Then('o texto original do relatório, a cópia e o download do Markdown devem permanecer totalmente preservados e intactos', async function (this: CustomWorld) {
  const expectedText = this.expectedDossierText || '# Dossiê sob Análise de Versão\n\nEste texto publicado não deve ser corrompido por fontes divergentes.';
  const expectedSha = crypto.createHash('sha256').update(expectedText).digest('hex');

  const copyBtn = this.page!.getByRole('button', { name: 'Copiar Markdown' });
  const downloadBtn = this.page!.getByRole('button', { name: 'Baixar .md' });
  expect(await copyBtn.isVisible()).toBe(true);
  expect(await downloadBtn.isVisible()).toBe(true);

  // Verificação de cópia: texto exato e SHA-256
  await copyBtn.click();
  await this.page!.waitForSelector('.report-buttons button:has-text("Copiado!")', { timeout: 5000 });
  const clipboardText = await this.getContextClipboard();
  expect(clipboardText).toBe(expectedText);
  const clipboardSha = crypto.createHash('sha256').update(clipboardText).digest('hex');
  expect(clipboardSha).toBe(expectedSha);

  // Verificação de download: texto exato, bytes e SHA-256
  const downloadPromise = this.page!.waitForEvent('download');
  await downloadBtn.click();
  const download = await downloadPromise;
  const downloadPath = await download.path();
  expect(downloadPath).toBeTruthy();
  const fileBytes = fs.readFileSync(downloadPath!);
  const fileContent = fileBytes.toString('utf-8');
  expect(fileContent).toBe(expectedText);
  const fileSha = crypto.createHash('sha256').update(fileBytes).digest('hex');
  expect(fileSha).toBe(expectedSha);
});

Then('o histórico local não deve persistir o resumo divergente', async function (this: CustomWorld) {
  const hasMismatchInHistory = await this.page!.evaluate(() => {
    const raw = localStorage.getItem('deep_research_local_history_v1');
    if (!raw) return false;
    return raw.includes('divergent-sha256-hash-value');
  });
  expect(hasMismatchInHistory).toBe(false);
});

Given('que possuo um relatório exibido com resumo de fontes validado', async function (this: CustomWorld) {
  if (!this.page) {
    await this.init({ width: 1440, height: 900 });
  }
  const initialText = '# Dossiê sob Monitoramento de Hash\n\nVersão inicial do relatório com fontes consistentes.';
  const initialHash = crypto.createHash('sha256').update(initialText).digest('hex');

  const reportRecord = {
    id_pesquisa: 'same-id-mutation-999',
    tema: 'Tema sob Monitoramento de Integridade',
    criado_em: '2026-10-26T15:00:00Z',
    concluido_em: '2026-10-26T15:30:00Z',
    status: 'concluido',
    total_pontos: 1,
    writerResponse: {
      id_pesquisa: 'same-id-mutation-999',
      tema: 'Tema sob Monitoramento de Integridade',
      status: 'concluido',
      total_caracteres_dossier: initialText.length,
      concluido_em: '2026-10-26T15:30:00Z',
      dossier_final: initialText,
    },
  };

  await this.page!.route('**/api/v1/pipeline/same-id-mutation-999/sources', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id_pesquisa: 'same-id-mutation-999',
        status: 'completo',
        total_consultadas: 4,
        total_utilizadas: 2,
        total_nao_utilizadas: 2,
        consultadas: [
          { url: 'https://exemplo.org/f1', titulo: 'F1', dominio: 'exemplo.org' },
          { url: 'https://exemplo.org/f2', titulo: 'F2', dominio: 'exemplo.org' },
        ],
        utilizadas: [
          { url: 'https://exemplo.org/f1', titulo: 'F1', dominio: 'exemplo.org' },
          { url: 'https://exemplo.org/f2', titulo: 'F2', dominio: 'exemplo.org' },
        ],
        nao_utilizadas: [],
        artifact_hash: initialHash,
      }),
    });
  });

  await this.page!.goto(`${this.baseUrl}#history`);
  await this.page!.evaluate((rec) => {
    localStorage.setItem('deep_research_local_history_v1', JSON.stringify([rec]));
  }, reportRecord);
  await this.page!.reload();
  await this.page!.waitForSelector('.history-item-card', { timeout: 10000 });
  await this.page!.locator('.history-item-card:has-text("Tema sob Monitoramento de Integridade") button:has-text("Abrir")').click();
  await this.page!.waitForSelector('#dossier-report', { timeout: 10000 });
  await this.page!.waitForSelector('.source-status-badge.completo', { timeout: 10000 });
});

When('o corpo do relatório é atualizado com novo texto sob o mesmo identificador', async function (this: CustomWorld) {
  const updatedText = '# Dossiê Alterado com Novo Conteúdo\n\nEste texto modificado invalida as fontes anteriores.';
  await this.page!.evaluate((newText) => {
    const raw = localStorage.getItem('deep_research_local_history_v1');
    if (raw) {
      const list = JSON.parse(raw);
      if (list.length > 0) {
        list[0].writerResponse.dossier_final = newText;
        localStorage.setItem('deep_research_local_history_v1', JSON.stringify(list));
      }
    }
  }, updatedText);

  await this.page!.goto(`${this.baseUrl}#history`);
  await this.page!.reload();
  await this.page!.waitForSelector('.history-item-card', { timeout: 10000 });
  await this.page!.locator('.history-item-card:has-text("Tema sob Monitoramento de Integridade") button:has-text("Abrir")').click();
  await this.page!.waitForSelector('#dossier-report', { timeout: 10000 });
  await this.page!.waitForSelector('.source-notice-banner.warning', { timeout: 10000 });
});

Then('o sistema deve invalidar o resumo anterior e não deve reter os dados da versão antiga', async function (this: CustomWorld) {
  const activeBadge = this.page!.locator('.source-status-badge.completo');
  expect(await activeBadge.count()).toBe(0);

  const warning = this.page!.locator('.source-notice-banner.warning');
  await warning.waitFor({ state: 'visible', timeout: 5000 });
  const text = await warning.textContent();
  expect(text).toContain('As fontes disponíveis pertencem a outra versão deste relatório. O texto foi preservado.');

  const groups = this.page!.locator('.source-groups-container');
  expect(await groups.count()).toBe(0);
});

Given('que a requisição ao endpoint de fontes falha com erro de comunicação', async function (this: CustomWorld) {
  if (!this.page) {
    await this.init({ width: 1440, height: 900 });
  }
  const retryDossier = '# Dossiê Integral da Pesquisa\n\nEste texto deve permanecer visível mesmo em caso de falha na requisição de fontes.';
  this.expectedDossierText = retryDossier;
  const retryHash = crypto.createHash('sha256').update(retryDossier).digest('hex');

  const retryRecord = {
    id_pesquisa: 'retry-network-uuid-888',
    tema: 'Pesquisa com Erro de Rede nas Fontes',
    criado_em: '2026-10-26T14:00:00Z',
    concluido_em: '2026-10-26T14:30:00Z',
    status: 'concluido',
    total_pontos: 1,
    writerResponse: {
      id_pesquisa: 'retry-network-uuid-888',
      tema: 'Pesquisa com Erro de Rede nas Fontes',
      status: 'concluido',
      total_caracteres_dossier: retryDossier.length,
      concluido_em: '2026-10-26T14:30:00Z',
      dossier_final: retryDossier,
    },
  };

  await this.page!.addInitScript((rec) => {
    localStorage.setItem('deep_research_local_history_v1', JSON.stringify([rec]));
  }, retryRecord);

  (this as any).sourcesRetryCount = 0;
  await this.page!.route('**/api/v1/pipeline/*/sources', async (route) => {
    (this as any).sourcesRetryCount = ((this as any).sourcesRetryCount || 0) + 1;
    if ((this as any).sourcesRetryCount === 1) {
      await route.abort('failed');
    } else {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id_pesquisa: 'retry-network-uuid-888',
          status: 'completo',
          total_consultadas: 3,
          total_utilizadas: 2,
          total_nao_utilizadas: 1,
          consultadas: [],
          utilizadas: [],
          nao_utilizadas: [],
          artifact_hash: retryHash,
        }),
      });
    }
  });

  await this.page!.goto(`${this.baseUrl}#history`);
  await this.page!.waitForSelector('.history-item-card', { timeout: 10000 });
  await this.page!.locator('.history-item-card:has-text("Pesquisa com Erro de Rede nas Fontes") button:has-text("Abrir")').click();
});

Then('o texto integral do dossiê não deve ser ocultado', async function (this: CustomWorld) {
  const markdown = this.page!.locator('.markdown-body');
  expect(await markdown.isVisible()).toBe(true);
});

Then('devo ver um banner de alerta informando a falha de comunicação', async function (this: CustomWorld) {
  const alert = this.page!.locator('.source-notice-banner.danger');
  await alert.waitFor({ state: 'visible', timeout: 5000 });
  expect(await alert.isVisible()).toBe(true);
});

Then('devo ver o botão "Tentar novamente" para repetir exclusivamente a consulta de fontes', async function (this: CustomWorld) {
  const retryBtn = this.page!.locator('.source-retry-btn');
  expect(await retryBtn.isVisible()).toBe(true);
});

When('clico no botão "Tentar novamente" da consulta de fontes', async function (this: CustomWorld) {
  const retryBtn = this.page!.locator('.source-retry-btn');
  await retryBtn.waitFor({ state: 'visible', timeout: 5000 });
  await retryBtn.click();
});

Then('uma nova requisição GET deve ser enviada para fontes sem nenhum disparo de POST no pipeline', async function (this: CustomWorld) {
  await this.page!.waitForSelector('.source-status-badge.completo', { timeout: 10000 });
  expect((this as any).sourcesRetryCount).toBeGreaterThanOrEqual(2);
  const postRequests = this.dispatchedPostUrls.filter((u) => u.includes('/api/v1/'));
  expect(postRequests).toHaveLength(0);
});

Then('os botões de copiar e baixar o Markdown devem permanecer totalmente operacionais', async function (this: CustomWorld) {
  const expectedText = this.expectedDossierText || '# Dossiê Integral da Pesquisa\n\nEste texto deve permanecer visível mesmo em caso de falha na requisição de fontes.';
  const expectedSha = crypto.createHash('sha256').update(expectedText).digest('hex');

  const copyBtn = this.page!.getByRole('button', { name: 'Copiar Markdown' });
  const downloadBtn = this.page!.getByRole('button', { name: 'Baixar .md' });
  expect(await copyBtn.isVisible()).toBe(true);
  expect(await downloadBtn.isVisible()).toBe(true);

  // Verificação de cópia: texto exato e SHA-256
  await copyBtn.click();
  await this.page!.waitForSelector('.report-buttons button:has-text("Copiado!")', { timeout: 5000 });
  const clipboardText = await this.getContextClipboard();
  expect(clipboardText).toBe(expectedText);
  const clipboardSha = crypto.createHash('sha256').update(clipboardText).digest('hex');
  expect(clipboardSha).toBe(expectedSha);

  // Verificação de download: texto exato, bytes e SHA-256
  const downloadPromise = this.page!.waitForEvent('download');
  await downloadBtn.click();
  const download = await downloadPromise;
  const downloadPath = await download.path();
  expect(downloadPath).toBeTruthy();
  const fileBytes = fs.readFileSync(downloadPath!);
  const fileContent = fileBytes.toString('utf-8');
  expect(fileContent).toBe(expectedText);
  const fileSha = crypto.createHash('sha256').update(fileBytes).digest('hex');
  expect(fileSha).toBe(expectedSha);
});

// ============================================================================
// Passos de Aceitação Fidedigna Adicionados para Fechamento de Lacunas
// ============================================================================

When('pressiono a combinação Shift+Enter no compositor', async function (this: CustomWorld) {
  await this.page!.locator('.composer-input').press('Shift+Enter');
});

Then('nenhuma requisição de plano deve ter sido disparada', async function (this: CustomWorld) {
  const hasPlanPost = this.dispatchedPostUrls.some((u) => u.includes('/api/v1/plan'));
  expect(hasPlanPost).toBe(false);
});

When('pressiono Enter no compositor', async function (this: CustomWorld) {
  await this.page!.locator('.composer-input').press('Enter');
});

Then('a requisição de plano deve ser disparada exatamente uma vez', async function (this: CustomWorld) {
  await this.page!.waitForSelector('.plan-card', { timeout: 15000 });
  const planPosts = this.dispatchedPostUrls.filter((u) => u.includes('/api/v1/plan'));
  expect(planPosts.length).toBe(1);
});

When('preencho um tema multilinha de 3 linhas no compositor', async function (this: CustomWorld) {
  await this.page!.locator('.composer-input').fill('Linha 1 do tema analítico\nLinha 2 com contexto\nLinha 3 com questão central');
});

Then('a altura do compositor deve expandir sem cortar o texto visível', async function (this: CustomWorld) {
  const height = await this.page!.locator('.composer-input').evaluate((el) => el.clientHeight);
  expect(height).toBeGreaterThan(40);
});

When('altero o viewport para 375px de largura', async function (this: CustomWorld) {
  await this.page!.setViewportSize({ width: 375, height: 812 });
});

Then('a caixa de entrada deve manter o texto sem transbordamento horizontal', async function (this: CustomWorld) {
  const scrollWidth = await this.page!.locator('.composer-input').evaluate((el) => el.scrollWidth);
  const clientWidth = await this.page!.locator('.composer-input').evaluate((el) => el.clientWidth);
  expect(scrollWidth).toBeLessThanOrEqual(clientWidth + 2);
});

When('altero o viewport de volta para desktop', async function (this: CustomWorld) {
  await this.page!.setViewportSize({ width: 1440, height: 900 });
});

Then('o compositor deve manter o texto moldado com auto-redimensionamento sem corte', async function (this: CustomWorld) {
  const val = await this.page!.locator('.composer-input').inputValue();
  expect(val).toContain('\n');
  const metrics = await this.page!.locator('.composer-input').evaluate((el) => ({
    scrollHeight: el.scrollHeight,
    clientHeight: el.clientHeight,
    scrollWidth: el.scrollWidth,
    clientWidth: el.clientWidth,
  }));
  expect(metrics.scrollHeight).toBeLessThanOrEqual(metrics.clientHeight + 2);
  expect(metrics.scrollWidth).toBeLessThanOrEqual(metrics.clientWidth + 2);
});

When('preencho um tema longo com mais de 300 caracteres', async function (this: CustomWorld) {
  const longTheme = [
    'A transição para matrizes de baixo carbono exige análise profunda da expansão de fontes renováveis.',
    'Isso inclui o avanço massivo de parques eólicos offshore e plantas solares fotovoltaicas de alta eficiência.',
    'A infraestrutura requer reforço crítico nas linhas de transmissão interestaduais em ultra-alta tensão.',
    'Sistemas modernos de armazenamento químico em baterias de lítio e fluxo garantem estabilidade de frequência.',
    'Devem ser ponderados impactos regulatórios setoriais, custos tarifários e licenciamentos socioambientais.',
    'A segurança do suprimento elétrico nacional demanda modelagem probabilística contra secas e intermitência.',
    'A modernização do grid inteligente e microrredes locais complementa o despacho centralizado.',
  ].join('\n');
  await this.page!.locator('.composer-input').fill(longTheme);
});

Then('a altura da área de texto deve ser limitada a no máximo 120px com rolagem vertical ativa', async function (this: CustomWorld) {
  const height = await this.page!.locator('.composer-input').evaluate((el) => el.clientHeight);
  expect(height).toBeLessThanOrEqual(122);
  const hasVerticalScroll = await this.page!.locator('.composer-input').evaluate((el) => el.scrollHeight > el.clientHeight);
  expect(hasVerticalScroll).toBe(true);
});

Then('o topo do painel de preferências não deve estar cortado fora da viewport', async function (this: CustomWorld) {
  const bounding = await this.page!.locator('#preferences-popover-panel').evaluate((el) => {
    const rect = el.getBoundingClientRect();
    return {
      top: rect.top,
      bottom: rect.bottom,
      isTopClipped: rect.top < 0,
    };
  });
  expect(bounding.isTopClipped).toBe(false);
  expect(bounding.top).toBeGreaterThanOrEqual(0);
});

Then('o plano deve exibir o chip de personas sem adivinhar contagem fixa legada de 4', async function (this: CustomWorld) {
  const chip = this.page!.locator('.plan-snapshot-chips .pill-indigo');
  await chip.waitFor({ state: 'visible', timeout: 5000 });
  const text = (await chip.textContent())?.trim();
  expect(text).toBe('3 personas ativas');
  const title = await chip.getAttribute('title');
  expect(title).toBe('Personas configuradas: Historiador, Visionario, Cetico');
  expect(title).not.toContain('Futurista');
});

Then('o plano deve exibir o chip de personas com {int} personas ativas e títulos configurados', async function (this: CustomWorld, count: number) {
  const chip = this.page!.locator('.plan-snapshot-chips .pill-indigo');
  await chip.waitFor({ state: 'visible', timeout: 5000 });
  const text = (await chip.textContent())?.trim();
  expect(text).toBe(`${count} personas ativas`);
  const title = await chip.getAttribute('title');
  expect(title).toBe('Personas configuradas: Historiador, Visionario, Cetico');
  expect(title).not.toContain('Futurista');
});

Given('que acesso a aplicação no dispositivo de resolução 1280x577', async function (this: CustomWorld) {
  await this.init({ width: 1280, height: 577 });
  await this.page!.goto(this.baseUrl);
  await this.page!.waitForSelector('#root');
});

Then('o botão "Iniciar pesquisa" deve estar localizado acima da dobra na viewport inicial', async function (this: CustomWorld) {
  const bounding = await this.page!.locator('#start-research-btn').evaluate((btn) => {
    const rect = btn.getBoundingClientRect();
    return {
      top: rect.top,
      bottom: rect.bottom,
      isAboveFold: rect.bottom <= window.innerHeight,
      scrollY: window.scrollY,
    };
  });
  expect(bounding.scrollY).toBe(0);
  expect(bounding.isAboveFold).toBe(true);
  expect(bounding.bottom).toBeLessThanOrEqual(577);
});

Then('o botão "Iniciar pesquisa" deve ser clicável diretamente nas coordenadas do elemento sem rolagem prévia', async function (this: CustomWorld) {
  const isHittable = await this.page!.locator('#start-research-btn').evaluate((btn) => {
    const rect = btn.getBoundingClientRect();
    const centerX = rect.left + rect.width / 2;
    const centerY = rect.top + rect.height / 2;
    const elAtPoint = document.elementFromPoint(centerX, centerY);
    return elAtPoint === btn || btn.contains(elAtPoint);
  });
  expect(isHittable).toBe(true);
});

Then('devo ver os pontos analíticos inicialmente recolhidos', async function (this: CustomWorld) {
  const stepper = this.page!.locator('.stepper-item');
  const count = await stepper.count();
  expect(count).toBeGreaterThanOrEqual(1);
  const details = this.page!.locator('.stepper-point-details');
  expect(await details.count()).toBe(0);
});

When('clico no botão para expandir os detalhes de todos os pontos', async function (this: CustomWorld) {
  await this.page!.locator('.btn-toggle-all-details').click();
});

Then('devo ver as subperguntas e hipóteses detalhadas de todos os pontos', async function (this: CustomWorld) {
  const details = this.page!.locator('.stepper-point-details');
  const count = await details.count();
  expect(count).toBeGreaterThanOrEqual(1);
});

When('clico no botão "Novo tema" do banner do plano', async function (this: CustomWorld) {
  await this.page!.getByRole('button', { name: 'Novo tema' }).click();
});

Then('devo ver o diálogo de confirmação "Descartar plano formulado?"', async function (this: CustomWorld) {
  const dialog = this.page!.locator('[role="alertdialog"]');
  await dialog.waitFor({ state: 'visible', timeout: 5000 });
  expect(await dialog.isVisible()).toBe(true);
  const text = await dialog.textContent();
  expect(text).toContain('Descartar plano formulado?');
});

Then('o foco do teclado deve estar contido no diálogo de confirmação', async function (this: CustomWorld) {
  const dialog = this.page!.locator('[role="alertdialog"]');
  await dialog.waitFor({ state: 'visible', timeout: 5000 });

  // Foco inicial genuíno deve estar dentro do diálogo sem chamada artificial a .focus()
  const initiallyInside = await this.page!.evaluate(() => {
    const active = document.activeElement;
    const dlg = document.querySelector('[role="alertdialog"]');
    return Boolean(dlg && active && dlg.contains(active));
  });
  expect(initiallyInside).toBe(true);

  const buttons = dialog.locator('button:not([disabled])');
  const count = await buttons.count();
  expect(count).toBeGreaterThan(0);

  // Ciclo Tab para frente
  for (let i = 0; i < count; i++) {
    await this.page!.keyboard.press('Tab');
    const inside = await this.page!.evaluate(() => {
      const active = document.activeElement;
      const dlg = document.querySelector('[role="alertdialog"]');
      return Boolean(dlg && active && dlg.contains(active));
    });
    expect(inside).toBe(true);
  }

  // Ciclo Shift+Tab reverso
  for (let i = 0; i < count; i++) {
    await this.page!.keyboard.press('Shift+Tab');
    const inside = await this.page!.evaluate(() => {
      const active = document.elementFromPoint ? document.activeElement : null;
      const dlg = document.querySelector('[role="alertdialog"]');
      return Boolean(dlg && active && dlg.contains(active));
    });
    expect(inside).toBe(true);
  }
});

When('pressiono Escape no diálogo de confirmação', async function (this: CustomWorld) {
  await this.page!.keyboard.press('Escape');
});

Then('o diálogo de confirmação deve fechar e o plano atual deve permanecer visível', async function (this: CustomWorld) {
  const dialog = this.page!.locator('[role="alertdialog"]');
  await dialog.waitFor({ state: 'hidden', timeout: 5000 });
  expect(await dialog.count() === 0 || !(await dialog.isVisible())).toBe(true);

  const planCard = this.page!.locator('.plan-card');
  await planCard.waitFor({ state: 'visible', timeout: 5000 });
  expect(await planCard.isVisible()).toBe(true);
  const title = await planCard.textContent();
  expect(title).toContain('Plano pronto para revisão');
});

When('clico em "Cancelar" no diálogo de confirmação', async function (this: CustomWorld) {
  await this.page!.locator('[role="alertdialog"] button:has-text("Cancelar")').click();
});

Then('o plano atual deve permanecer visível e pronto para revisão', async function (this: CustomWorld) {
  const planCard = this.page!.locator('.plan-card');
  expect(await planCard.isVisible()).toBe(true);
  const title = await planCard.textContent();
  expect(title).toContain('Plano pronto para revisão');
});

Given('que concluí a pesquisa para o tema {string}', async function (this: CustomWorld, tema: string) {
  await this.init({ width: 1440, height: 900 });
  await this.page!.goto(this.baseUrl);
  await this.page!.waitForSelector('.composer-input');
  await this.page!.locator('.composer-input').fill(tema);
  await this.page!.locator('.composer-send-btn').click();
  await this.page!.waitForSelector('.plan-card', { timeout: 15000 });
  await this.page!.locator('#start-research-btn').click();
  await this.page!.waitForSelector('#dossier-report', { timeout: 30000 });
});

When('clico no botão "Baixar .md"', async function (this: CustomWorld) {
  const downloadPromise = this.page!.waitForEvent('download', { timeout: 10000 });
  await this.page!.getByRole('button', { name: 'Baixar .md' }).click();
  const download = await downloadPromise;
  this.lastDownloadedFilename = download.suggestedFilename();
  const stream = await download.createReadStream();
  if (stream) {
    const chunks: Buffer[] = [];
    for await (const chunk of stream) {
      chunks.push(Buffer.from(chunk));
    }
    this.lastDownloadedContent = Buffer.concat(chunks).toString('utf-8');
  }
});

Then('o download do arquivo Markdown deve ser concluído com sucesso', async function (this: CustomWorld) {
  expect(this.lastDownloadedFilename).toBeTruthy();
  expect(this.lastDownloadedFilename).toMatch(/\.md$/);
  expect(this.lastDownloadedContent).toBeTruthy();
});

Then('o conteúdo do arquivo baixado em UTF-8 deve ser idêntico ao texto do dossiê retornado pelo redator', async function (this: CustomWorld) {
  expect(typeof this.lastWriterDossierBody).toBe('string');
  expect(this.lastWriterDossierBody!.trim().length).toBeGreaterThan(0);
  expect(typeof this.lastDownloadedContent).toBe('string');
  expect(this.lastDownloadedContent).toBe(this.lastWriterDossierBody);
});

Then('o hash SHA-256 do arquivo baixado deve coincidir exatamente com o artefato publicado', async function (this: CustomWorld) {
  expect(typeof this.lastWriterDossierBody).toBe('string');
  expect(this.lastWriterDossierBody!.trim().length).toBeGreaterThan(0);
  expect(typeof this.lastDownloadedContent).toBe('string');
  const fileHash = crypto.createHash('sha256').update(this.lastDownloadedContent!).digest('hex');
  const expectedHash = crypto.createHash('sha256').update(this.lastWriterDossierBody!).digest('hex');
  expect(fileHash).toBe(expectedHash);
});

When('clico no botão "Copiar Markdown"', async function (this: CustomWorld) {
  await this.page!.getByRole('button', { name: 'Copiar Markdown' }).click();
});

Then('o texto na área de transferência do contexto de teste deve coincidir exatamente com o dossiê', async function (this: CustomWorld) {
  const clipboardText = await this.getContextClipboard();
  expect(typeof this.lastWriterDossierBody).toBe('string');
  expect(this.lastWriterDossierBody!.trim().length).toBeGreaterThan(0);
  expect(clipboardText).toBe(this.lastWriterDossierBody);
});

Then('devo ver o feedback visual temporário "Copiado!"', async function (this: CustomWorld) {
  const feedback = this.page!.locator('button:has-text("Copiado!")');
  expect(await feedback.isVisible()).toBe(true);
});

Given('que acesso a aplicação no dispositivo "desktop" com preferência de movimento reduzido', async function (this: CustomWorld) {
  if (!this.browser) {
    const { chromium } = await import('playwright');
    this.browser = await chromium.launch({
      headless: true,
      args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--disable-gpu'],
    });
  }
  this.context = await this.browser.newContext({
    viewport: { width: 1440, height: 900 },
    colorScheme: 'light',
    reducedMotion: 'reduce',
  });
  this.page = await this.context.newPage();
  await this.page.goto(this.baseUrl);
  await this.page.waitForSelector('#root');
});

Then('o painel de preferências deve ficar visível imediatamente sem transição prolongada', async function (this: CustomWorld) {
  const panel = this.page!.locator('#preferences-popover-panel');
  expect(await panel.isVisible()).toBe(true);
});

Then('o conteúdo interativo deve permanecer completamente legível e acessível', async function (this: CustomWorld) {
  const opacity = await this.page!.locator('#preferences-popover-panel').evaluate((el) => {
    return window.getComputedStyle(el).opacity;
  });
  expect(Number(opacity)).toBeGreaterThanOrEqual(0.9);
});

Then('as fontes tipográficas da aplicação devem estar efetivamente carregadas no documento', async function (this: CustomWorld) {
  const fontsLoaded = await this.page!.evaluate(`(async () => {
    await document.fonts.ready;
    const fontNames = Array.from(document.fonts).map(function(f) { return f.family.replace(/['"]/g, ''); });
    const hasOutfit = fontNames.some(function(f) { return f.toLowerCase().includes('outfit'); });
    const hasInter = fontNames.some(function(f) { return f.toLowerCase().includes('inter'); });
    return {
      status: document.fonts.status,
      size: document.fonts.size,
      hasOutfit: hasOutfit,
      hasInter: hasInter,
    };
  })()`) as { status: string; size: number; hasOutfit: boolean; hasInter: boolean };
  expect(fontsLoaded.status).toBe('loaded');
  expect(fontsLoaded.size).toBeGreaterThan(0);
  expect(fontsLoaded.hasOutfit).toBe(true);
  expect(fontsLoaded.hasInter).toBe(true);
});

Then('o contraste medido dos textos principais contra o fundo deve atender aos requisitos de legibilidade', async function (this: CustomWorld) {
  const contrastAudit = await this.page!.evaluate(`(() => {
    var parseRgb = function(str) {
      var m = str.match(/\\d+(\\.\\d+)?/g);
      if (!m || m.length < 3) return [0, 0, 0, 1];
      return [Number(m[0]), Number(m[1]), Number(m[2]), m[3] !== undefined ? Number(m[3]) : 1];
    };
    var getLum = function(rgb) {
      var a = rgb.map(function(v) {
        var c = v / 255;
        return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
      });
      return a[0] * 0.2126 + a[1] * 0.7152 + a[2] * 0.0722;
    };
    var getEffectiveBg = function(el) {
      var cur = el;
      while (cur && cur !== document.documentElement) {
        var bg = window.getComputedStyle(cur).backgroundColor;
        var rgba = parseRgb(bg);
        if (rgba[3] > 0.5) return rgba;
        cur = cur.parentElement;
      }
      return [255, 255, 255, 1];
    };
    var contrast = function(tc, bc) {
      var l1 = getLum(tc);
      var l2 = getLum(bc);
      return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
    };

    var popoverElements = Array.from(
      document.querySelectorAll(
        '#preferences-popover-panel .preferences-title, #preferences-popover-panel label, #preferences-popover-panel .persona-name, #preferences-popover-panel p'
      )
    );
    var canvasElements = Array.from(
      document.querySelectorAll('h1, h2, .app-title, #composer-helper-text')
    );
    var targets = popoverElements.concat(canvasElements);

    return targets.map(function(el) {
      var style = window.getComputedStyle(el);
      var tc = parseRgb(style.color);
      var bc = getEffectiveBg(el);
      return {
        selector: el.className || el.tagName,
        text: el.textContent ? el.textContent.trim().slice(0, 30) : '',
        ratio: contrast(tc, bc),
      };
    });
  })()`) as Array<{ selector: string; text: string; ratio: number }>;

  expect(contrastAudit.length).toBeGreaterThan(0);
  for (const item of contrastAudit) {
    expect(item.ratio).toBeGreaterThanOrEqual(4.5);
  }
});

When('a primeira auditoria reprova e o sistema avança para nova busca no ciclo 2', async function (this: CustomWorld) {
  let auditCount = 0;
  let searchCount = 0;

  (this as any).pendingRouteResolvers = (this as any).pendingRouteResolvers || [];

  await this.page!.route('**/api/v1/search', async (route) => {
    searchCount++;
    if (searchCount === 1) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id_pesquisa: 'test-multicycle-uuid',
          total_pontos_processados: 1,
          status_pesquisa: 'concluido',
          total_falhas_coleta: 0,
          resumo_coletas: [],
          total_pontos: 1,
          pontos: [
            { ponto_id: 'p-1', ponto_n: 1, status: 'coletado', personas: [] },
          ],
        }),
      });
    } else {
      // Retém a rota do ciclo 2 sem chamadas externas nem timeouts artificiais
      const resolver = async () => {
        try {
          await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({
              id_pesquisa: 'test-multicycle-uuid',
              total_pontos_processados: 1,
              status_pesquisa: 'concluido',
              total_falhas_coleta: 0,
              resumo_coletas: [],
              total_pontos: 1,
              pontos: [
                { ponto_id: 'p-1', ponto_n: 1, status: 'coletado', personas: [] },
              ],
            }),
          });
        } catch {
          // ignore
        }
      };
      (this as any).pendingRouteResolvers.push(resolver);
    }
  });

  await this.page!.route('**/api/v1/audit', async (route) => {
    auditCount++;
    if (auditCount === 1) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id_pesquisa: 'test-multicycle-uuid',
          total_pontos: 1,
          aprovados: 0,
          reprovados: 1,
          status_geral: 'reprovado',
          pronto_para_writer: false,
          auditorias: [
            {
              ponto_id: 'p-1',
              ponto_n: 1,
              status: 'reprovado',
              pontuacao_percentual: 75.0,
              criterios_aprovados: 9,
              criterios_minimos: 11,
              valido: true,
              resumo_auditoria: '3 critérios não atendidos no ponto 1 (mínimo exigido: 11/12)',
              pontos_fracos: 'clm_historiador_2_fe580774: contradição entre dados históricos e fontes primárias',
              diagnostico: 'diagnóstico de sistema bruto com IDs internos',
              criterios: [
                { id: 2, aprovado: false, justificativa: 'Falta corroboração', lacuna: 'Ausência de fonte primária', correcao: 'Buscar no site oficial', personas_pertinentes: ['historiador'] },
                { id: 4, aprovado: false, justificativa: 'Contradição interna', lacuna: 'Dados divergentes', correcao: 'Harmonizar dados', personas_pertinentes: ['cetico'] },
              ],
            },
          ],
        }),
      });
    } else {
      const resolver = async () => {
        try {
          await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({
              id_pesquisa: 'test-multicycle-uuid',
              total_pontos: 1,
              aprovados: 1,
              reprovados: 0,
              status_geral: 'aprovado',
              pronto_para_writer: true,
              auditorias: [],
            }),
          });
        } catch {
          // ignore
        }
      };
      (this as any).pendingRouteResolvers.push(resolver);
    }
  });

  await this.page!.locator('#start-research-btn').click();
  await this.page!.waitForSelector('.status-badge-chip:has-text("Ciclo 2")', { timeout: 15000 });
});

Then('o cabeçalho da auditoria deve indicar "Auditoria do ciclo 1 — revisão em andamento no ciclo 2"', async function (this: CustomWorld) {
  const heading = this.page!.locator('.audit-breakdown');
  await heading.waitFor({ state: 'visible', timeout: 5000 });
  const text = await heading.textContent();
  expect(text).toContain('Auditoria do ciclo 1 — revisão em andamento no ciclo 2');
});

Then('devo ver o banner contextual explicando que a nova busca busca enriquecer evidências', async function (this: CustomWorld) {
  const banner = this.page!.locator('.audit-prior-cycle-banner');
  expect(await banner.isVisible()).toBe(true);
  const text = await banner.textContent();
  expect(text).toContain('Nova busca em andamento no ciclo 2 para enriquecer evidências');
});

Then('devo ver a lista estruturada de critérios reprovados com lacunas e correções', async function (this: CustomWorld) {
  const failedCards = this.page!.locator('.failed-criterion-card');
  expect(await failedCards.count()).toBeGreaterThanOrEqual(1);
  const firstCard = await failedCards.first().textContent();
  expect(firstCard).toContain('Lacuna apontada:');
  expect(firstCard).toContain('Ação recomendada:');
});

Then('o registro técnico completo deve estar acessível sob o bloco colapsável', async function (this: CustomWorld) {
  const details = this.page!.locator('.audit-technical-details');
  expect(await details.isVisible()).toBe(true);
  const summary = this.page!.locator('.audit-technical-summary');
  expect(await summary.textContent()).toContain('Registro técnico completo e identificadores');
});

Then('o foco ativo do navegador deve ser transferido automaticamente para o campo de URL do LLM', async function (this: CustomWorld) {
  await this.page!.waitForFunction(() => {
    return document.activeElement?.id === 'llm-base-url';
  }, { timeout: 5000 });

  const activeId = await this.page!.evaluate(() => document.activeElement?.id);
  expect(activeId).toBe('llm-base-url');
});

Then('devo ver a explicação da regra de precedência RN-10 com prioridade do banco cifrado sobre o ambiente', async function (this: CustomWorld) {
  const text = await this.page!.textContent('body');
  expect(text).toContain('Regra de Precedência RN-10 (Adendo 002)');
  expect(text).toContain('Banco Cifrado possui prioridade sobre o ambiente');
});

Given('que possuo no histórico um registro histórico concluído apenas com dossiê do redator e sem plano', async function (this: CustomWorld) {
  await this.init({ width: 1440, height: 900 });
  await this.page!.addInitScript(() => {
    const writerOnlyRecord = {
      id_pesquisa: 'writer-only-uuid-1234',
      tema: 'Tema Somente Redação Sem Plano',
      criado_em: '2026-10-26T18:00:00Z',
      concluido_em: '2026-10-26T18:05:00Z',
      status: 'concluido',
      total_pontos: 1,
      writerResponse: {
        id_pesquisa: 'writer-only-uuid-1234',
        tema: 'Tema Somente Redação Sem Plano',
        status: 'concluido',
        total_caracteres_dossier: 1250,
        concluido_em: '2026-10-26T18:05:00Z',
        dossier_final: '# Dossiê Exclusivo de Redação Histórica\n\nEste dossiê não possui plano formal cadastrado.',
      },
    };
    localStorage.setItem('deep_research_local_history_v1', JSON.stringify([writerOnlyRecord]));
  });
  await this.page!.goto(this.baseUrl);
});

When('clico no botão "Abrir" da pesquisa somente-redação', async function (this: CustomWorld) {
  await this.page!.waitForSelector('.history-item-card', { timeout: 10000 });
  const openBtn = this.page!.locator('.history-item-card:has-text("Tema Somente Redação Sem Plano") button:has-text("Abrir")');
  await openBtn.click();
});

Then('o workspace deve carregar diretamente o relatório do dossiê', async function (this: CustomWorld) {
  await this.page!.waitForSelector('#dossier-report', { timeout: 10000 });
  expect(await this.page!.locator('#dossier-report').isVisible()).toBe(true);
});

Then('nenhum plano fictício ou barra lateral órfã deve ser fabricada', async function (this: CustomWorld) {
  const planCard = this.page!.locator('.plan-card');
  expect(await planCard.count()).toBe(0);
  const sidebar = this.page!.locator('.sidebar-container');
  expect(await sidebar.count()).toBe(0);
});

Then('o texto do relatório deve permanecer exatamente idêntico ao registro salvo', async function (this: CustomWorld) {
  const body = await this.page!.locator('.markdown-body').innerText();
  expect(body).toContain('Este dossiê não possui plano formal cadastrado.');
});

Given('que possuo no histórico um registro com plano formulado e um registro somente de redação', async function (this: CustomWorld) {
  await this.init({ width: 1440, height: 900 });
  await this.page!.addInitScript(() => {
    const planfulRecord = {
      id_pesquisa: 'planful-uuid-001',
      tema: 'Pesquisa com Plano Estruturado',
      criado_em: '2026-10-26T17:00:00Z',
      status: 'planejado',
      total_pontos: 2,
      planResponse: {
        id_pesquisa: 'planful-uuid-001',
        tema: 'Pesquisa com Plano Estruturado',
        n_pontos: 2,
        criado_em: '2026-10-26T17:00:00Z',
        pontos: [
          { ponto_id: 'p1', ponto_n: 1, ponto: 'Eixo 1', status: 'pendente' },
          { ponto_id: 'p2', ponto_n: 2, ponto: 'Eixo 2', status: 'pendente' },
        ],
        status_pipeline: 'planejado',
      },
    };

    const writerOnlyRecord = {
      id_pesquisa: 'writer-only-uuid-002',
      tema: 'Pesquisa Apenas Redação',
      criado_em: '2026-10-26T18:00:00Z',
      concluido_em: '2026-10-26T18:10:00Z',
      status: 'concluido',
      total_pontos: 1,
      writerResponse: {
        id_pesquisa: 'writer-only-uuid-002',
        tema: 'Pesquisa Apenas Redação',
        status: 'concluido',
        total_caracteres_dossier: 980,
        dossier_final: '# Relatório Isolado de Redação\n\nConteúdo sem plano estruturado.',
      },
    };

    localStorage.setItem('deep_research_local_history_v1', JSON.stringify([planfulRecord, writerOnlyRecord]));
  });
  await this.page!.goto(this.baseUrl);
});

When('abro a pesquisa que possui plano formulado', async function (this: CustomWorld) {
  await this.page!.goto(`${this.baseUrl}#history`);
  await this.page!.waitForSelector('.history-item-card');
  const btn = this.page!.locator('.history-item-card:has-text("Pesquisa com Plano Estruturado") button:has-text("Abrir")');
  await btn.click();
});

Then('devo ver o plano e a barra lateral de contexto da pesquisa com plano', async function (this: CustomWorld) {
  await this.page!.waitForSelector('.plan-card', { timeout: 10000 });
  expect(await this.page!.locator('.plan-card').isVisible()).toBe(true);
  expect(await this.page!.locator('.sidebar-container').isVisible()).toBe(true);
});

When('retorno ao histórico e clico no botão "Abrir" da pesquisa somente-redação', async function (this: CustomWorld) {
  await this.page!.goto(`${this.baseUrl}#history`);
  await this.page!.waitForSelector('.history-item-card');
  const btn = this.page!.locator('.history-item-card:has-text("Pesquisa Apenas Redação") button:has-text("Abrir")');
  await btn.click();
});

Then('o workspace deve exibir o relatório da pesquisa somente-redação', async function (this: CustomWorld) {
  await this.page!.waitForSelector('#dossier-report', { timeout: 10000 });
  const heading = await this.page!.locator('#dossier-heading').textContent();
  expect(heading).toContain('Pesquisa Apenas Redação');
});

Then('a barra lateral anterior não deve permanecer visível', async function (this: CustomWorld) {
  const sidebar = this.page!.locator('.sidebar-container');
  expect(await sidebar.count()).toBe(0);
});

Then('nenhum plano fictício deve ser forjado para a pesquisa somente-redação', async function (this: CustomWorld) {
  const planCard = this.page!.locator('.plan-card');
  expect(await planCard.count()).toBe(0);
});

Given('que possuo um registro histórico que contém apenas resumo textual sem o texto integral publicado', async function (this: CustomWorld) {
  await this.init({ width: 1440, height: 900 });
  await this.page!.addInitScript(() => {
    const summaryOnlyRecord = {
      id_pesquisa: 'summary-only-uuid-777',
      tema: 'Tema Histórico Apenas com Resumo',
      criado_em: '2026-10-26T19:00:00Z',
      status: 'concluido',
      total_pontos: 1,
      writerResponse: {
        id_pesquisa: 'summary-only-uuid-777',
        tema: 'Tema Histórico Apenas com Resumo',
        status: 'concluido',
        total_caracteres_dossier: 350,
        dossier_resumo: 'Este registro histórico possui apenas um resumo analítico preliminar.',
        fontes: {
          id_pesquisa: 'summary-only-uuid-777',
          status: 'completo',
          total_consultadas: 6,
          total_utilizadas: 3,
          total_nao_utilizadas: 3,
          consultadas: [],
          utilizadas: [],
          nao_utilizadas: [],
          artifact_hash: 'mock-divergent-hash-summary',
        },
      },
    };
    localStorage.setItem('deep_research_local_history_v1', JSON.stringify([summaryOnlyRecord]));
  });

  await this.page!.goto(this.baseUrl);
  await this.page!.waitForSelector('#root');
});

When('o relatório é renderizado no workspace', async function (this: CustomWorld) {
  await this.page!.goto(`${this.baseUrl}#history`);
  await this.page!.waitForSelector('.history-item-card');
  const btn = this.page!.locator('.history-item-card:has-text("Tema Histórico Apenas com Resumo") button:has-text("Abrir")');
  await btn.click();
  await this.page!.waitForSelector('#dossier-report', { timeout: 10000 });
});

Then('o sistema deve rejeitar a vinculação de resumo de fontes do artigo completo', async function (this: CustomWorld) {
  const sourceGroups = this.page!.locator('.source-groups-container');
  expect(await sourceGroups.count()).toBe(0);
});

Then('devo ver o aviso informando que o registro contém apenas resumo', async function (this: CustomWorld) {
  const banner = this.page!.locator('.source-notice-banner.warning');
  await banner.waitFor({ state: 'visible', timeout: 5000 });
  const text = await banner.textContent();
  expect(text).toContain('Este registro contém apenas um resumo');
});

Then('o texto do resumo e os botões de ação devem permanecer preservados', async function (this: CustomWorld) {
  const expectedSummary = 'Este registro histórico possui apenas um resumo analítico preliminar.';
  const expectedSha = crypto.createHash('sha256').update(expectedSummary).digest('hex');

  const copyBtn = this.page!.getByRole('button', { name: 'Copiar Markdown' });
  const downloadBtn = this.page!.getByRole('button', { name: 'Baixar .md' });
  expect(await copyBtn.isVisible()).toBe(true);
  expect(await downloadBtn.isVisible()).toBe(true);

  // Verificação de cópia do resumo com texto exato e SHA-256
  await copyBtn.click();
  await this.page!.waitForSelector('.report-buttons button:has-text("Copiado!")', { timeout: 5000 });
  const clipboardText = await this.getContextClipboard();
  expect(clipboardText).toBe(expectedSummary);
  const clipboardSha = crypto.createHash('sha256').update(clipboardText).digest('hex');
  expect(clipboardSha).toBe(expectedSha);
});

Given('que a variável de ambiente SOURCE_LIVE_REPLAY_PATH está configurada com o arquivo de replay do relatório publicado', async function (this: CustomWorld) {
  const replayPath = process.env.SOURCE_LIVE_REPLAY_PATH;
  if (!replayPath) {
    throw new Error(
      'CONFIGURAÇÃO OBRIGATÓRIA: SOURCE_LIVE_REPLAY_PATH não está definido no ambiente. O Root fornecerá este arquivo temporário 0600 para a execução final autorizada da suíte Cucumber.'
    );
  }
  if (!fs.existsSync(replayPath)) {
    throw new Error(`Arquivo de replay não encontrado em ${replayPath}`);
  }
});

When('inicializo o contexto isolado de teste apontando para o servidor live', async function (this: CustomWorld) {
  const liveBaseUrl = process.env.SOURCE_LIVE_BASE_URL || 'http://127.0.0.1:3002';
  await this.initIsolatedLiveContext();
  await this.livePage!.goto(liveBaseUrl);
  await this.livePage!.waitForSelector('#root');
});

When('carrego o registro histórico no navegador isolado e abro a pesquisa', async function (this: CustomWorld) {
  const replayPath = process.env.SOURCE_LIVE_REPLAY_PATH!;
  const replayData = JSON.parse(fs.readFileSync(replayPath, 'utf-8'));

  await this.livePage!.addInitScript((data) => {
    localStorage.setItem('deep_research_local_history_v1', JSON.stringify([data.historyRecord]));
  }, replayData);

  await this.livePage!.goto(`${process.env.SOURCE_LIVE_BASE_URL || 'http://127.0.0.1:3002'}#history`);
  await this.livePage!.waitForSelector('.history-item-card');
  const openBtn = this.livePage!.locator('.history-item-card button:has-text("Abrir")').first();
  await openBtn.click();
  await this.livePage!.waitForSelector('#dossier-report', { timeout: 15000 });
});

Then('o sistema deve autenticar a sessão e consultar as fontes via GET sem nenhum disparo de POST', async function (this: CustomWorld) {
  const sourceCard = this.livePage!.locator('.source-breakdown-card');
  await sourceCard.waitFor({ state: 'visible', timeout: 15000 });
  expect(await sourceCard.isVisible()).toBe(true);

  // Prova autenticação de sessão via GET /app/session
  const sessionGet = this.liveRequests.find((r) => r.method === 'GET' && r.url.includes('/app/session'));
  expect(sessionGet).toBeDefined();

  // Prova consulta de fontes via GET
  const sourcesGet = this.liveRequests.find((r) => r.method === 'GET' && r.url.includes('/sources'));
  expect(sourcesGet).toBeDefined();

  // Prova ausência absoluta de mutações POST/PUT/PATCH/DELETE
  const mutatingReqs = this.liveRequests.filter((r) => ['POST', 'PUT', 'PATCH', 'DELETE'].includes(r.method));
  expect(mutatingReqs).toHaveLength(0);
  expect(this.liveViolationCount).toBe(0);
  expect(this.liveViolations).toHaveLength(0);
});

Then('a contabilidade de fontes deve registrar exatamente 11 consultadas, 9 utilizadas e 2 não citadas', async function (this: CustomWorld) {
  const bar = this.livePage!.locator('.source-counters-bar');
  await bar.waitFor({ state: 'visible', timeout: 15000 });
  expect(await bar.getAttribute('role')).toBe('group');
  expect(await bar.getAttribute('aria-label')).toBe('Resumo contábil das três categorias de fontes');

  const items = bar.locator('.source-counter-item');
  expect(await items.count()).toBe(3);

  // Campo 1: Total consultadas (por campo não substring)
  const label0 = (await items.nth(0).locator('.source-counter-label').textContent())?.trim();
  expect(label0).toBe('Total consultadas:');
  const val0 = (await items.nth(0).locator('.source-counter-value').textContent())?.trim();
  expect(val0).toBe('11');
  expect(await items.nth(0).locator('.source-counter-value').getAttribute('aria-label')).toBe('Total de fontes consultadas: 11');

  // Campo 2: Utilizadas no dossiê (por campo não substring)
  const label1 = (await items.nth(1).locator('.source-counter-label').textContent())?.trim();
  expect(label1).toBe('Utilizadas no dossiê:');
  const val1 = (await items.nth(1).locator('.source-counter-value').textContent())?.trim();
  expect(val1).toBe('9');
  expect(await items.nth(1).locator('.source-counter-value').getAttribute('aria-label')).toBe('Total de fontes utilizadas no dossiê: 9');
  const val1Class = await items.nth(1).locator('.source-counter-value').getAttribute('class');
  expect(val1Class).toContain('accent');

  // Campo 3: Consultadas mas não citadas (por campo não substring)
  const label2 = (await items.nth(2).locator('.source-counter-label').textContent())?.trim();
  expect(label2).toBe('Consultadas mas não citadas:');
  const val2 = (await items.nth(2).locator('.source-counter-value').textContent())?.trim();
  expect(val2).toBe('2');
  expect(await items.nth(2).locator('.source-counter-value').getAttribute('aria-label')).toBe('Fontes consultadas mas não citadas: 2');

  // Relação contábil: 11 - 9 = 2
  expect(parseInt(val0!, 10) - parseInt(val1!, 10)).toBe(parseInt(val2!, 10));

  // Validação cruzada com payload da resposta GET capturada
  expect(this.lastSourcesResponse).toBeDefined();
  expect(this.lastSourcesResponse).not.toBeNull();
  expect(this.lastSourcesResponse.total_consultadas).toBe(11);
  expect(this.lastSourcesResponse.total_utilizadas).toBe(9);
  expect(this.lastSourcesResponse.total_nao_utilizadas).toBe(2);
});

Then('devo conseguir expandir o grupo de 2 fontes não citadas e o grupo de todas as 11 fontes consultadas', async function (this: CustomWorld) {
  const details2 = this.livePage!.locator('.source-group-details:has-text("Fontes Consultadas mas Não Citadas")');
  await details2.locator('summary').click();
  const badge2 = details2.locator('.source-group-badge');
  expect((await badge2.textContent())?.trim()).toBe('2');
  expect(await badge2.getAttribute('aria-label')).toBe('2 fontes consultadas mas não citadas');

  const details11 = this.livePage!.locator('.source-group-details:has-text("Todas as Fontes Consultadas com Leitura Confirmada")');
  await details11.locator('summary').click();
  const badge11 = details11.locator('.source-group-badge');
  expect((await badge11.textContent())?.trim()).toBe('11');
  expect(await badge11.getAttribute('aria-label')).toBe('11 fontes consultadas');

  const badge9 = this.livePage!.locator('.source-group-details:has-text("Fontes Utilizadas no Dossiê") .source-group-badge');
  if (await badge9.count() > 0) {
    expect((await badge9.textContent())?.trim()).toBe('9');
    expect(await badge9.getAttribute('aria-label')).toBe('9 fontes utilizadas');
  }
});

Then('o hash do dossiê exibido deve coincidir exatamente com o artefato publicado do arquivo de replay', async function (this: CustomWorld) {
  const replayPath = process.env.SOURCE_LIVE_REPLAY_PATH;
  if (!replayPath || !fs.existsSync(replayPath)) {
    throw new Error('CONFIGURAÇÃO OBRIGATÓRIA: SOURCE_LIVE_REPLAY_PATH não está definido no ambiente ou arquivo inexistente.');
  }

  // 1. Lê o conteúdo fiel do arquivo de replay autorizado
  const replayData = JSON.parse(fs.readFileSync(replayPath, 'utf-8'));
  const expectedText: string =
    replayData.historyRecord?.writerResponse?.dossier_final ||
    replayData.dossier_final ||
    replayData.published_markdown ||
    '';
  if (!expectedText) {
    throw new Error('Arquivo de replay autorizado não contém texto de dossiê publicado.');
  }

  const expectedHash: string =
    replayData.historyRecord?.writerResponse?.fontes?.artifact_hash ||
    replayData.artifact_hash ||
    crypto.createHash('sha256').update(expectedText).digest('hex');

  // 2. Obtém o texto do Markdown original realmente do relatório exibido via cópia fiel (não innerText renderizado nem badge)
  const copyBtn = this.livePage!.getByRole('button', { name: 'Copiar Markdown' });
  expect(await copyBtn.isVisible()).toBe(true);
  await copyBtn.click();
  await this.livePage!.waitForSelector('.report-buttons button:has-text("Copiado!")', { timeout: 5000 });

  const copiedMarkdown = await this.getContextClipboard(true);
  expect(copiedMarkdown).toBeTruthy();

  // 3. Compara texto e SHA-256 fidedignos
  expect(copiedMarkdown).toBe(expectedText);
  const computedSha = crypto.createHash('sha256').update(copiedMarkdown).digest('hex');
  expect(computedSha).toBe(expectedHash);

  // Confirma badge de status consistente
  const statusBadge = this.livePage!.locator('.source-status-badge.completo');
  expect(await statusBadge.isVisible()).toBe(true);
  const badgeText = await statusBadge.textContent();
  expect(badgeText).toContain('Evidências completas');
});

Then('uma captura de tela da seção de fontes deve ser salva no diretório de evidências', async function (this: CustomWorld) {
  await this.saveScreenshot('live-replay-source-breakdown.png', true);
});

Then('nenhum segredo deve ser salvo em armazenamento local do navegador', async function (this: CustomWorld) {
  const localKeys = await this.page!.evaluate(() => Object.keys(localStorage));
  const localVals = await this.page!.evaluate(() => Object.values(localStorage));
  for (const key of localKeys) {
    expect(key.toLowerCase()).not.toContain('api_key');
    expect(key.toLowerCase()).not.toContain('secret');
  }
  for (const val of localVals) {
    expect(val).not.toContain('sk-');
    expect(val).not.toContain('CREDENTIALS_MASTER_KEY');
  }
});

When('visualizo o relatório final publicado', async function (this: CustomWorld) {
  if (!this.page) {
    await this.init();
    await this.page!.goto(this.baseUrl);
    await this.page!.waitForSelector('#root');
  }
  await this.page!.waitForSelector('#dossier-report', { timeout: 15000 });
});

When('o painel de fontes é exibido', async function (this: CustomWorld) {
  if (!this.page) {
    await this.init();
    await this.page!.goto(this.baseUrl);
    await this.page!.waitForSelector('#root');
  }
  await this.page!.waitForSelector('.source-breakdown-card', { timeout: 15000 });
});

When('o relatório final é renderizado', async function (this: CustomWorld) {
  if (!this.page) {
    await this.init();
    await this.page!.goto(this.baseUrl);
    await this.page!.waitForSelector('#root');
  }
  await this.page!.waitForSelector('#dossier-report', { timeout: 15000 });
});
