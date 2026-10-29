import { Given, When, Then, After } from '@cucumber/cucumber';
import { expect } from '@playwright/test';
import http from 'node:http';
import { CustomWorld } from '../support/world.js';

interface SSEServerInstance {
  server: http.Server;
  port: number;
  activeResponses: http.ServerResponse[];
  sendEvent: (event: string, data: any) => void;
  close: () => void;
}

function createSSEServer(): Promise<SSEServerInstance> {
  return new Promise((resolve, reject) => {
    const activeResponses: http.ServerResponse[] = [];
    const server = http.createServer((req, res) => {
      res.writeHead(200, {
        'Content-Type': 'text/event-stream; charset=utf-8',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Credentials': 'true',
      });
      activeResponses.push(res);
      req.on('close', () => {
        const idx = activeResponses.indexOf(res);
        if (idx !== -1) {
          activeResponses.splice(idx, 1);
        }
      });
    });

    server.on('error', reject);

    server.listen(0, '127.0.0.1', () => {
      const port = (server.address() as any).port;
      const sendEvent = (event: string, data: any) => {
        const payload = `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
        for (const res of [...activeResponses]) {
          try {
            res.write(payload);
          } catch {
            // ignore broken connection
          }
        }
      };

      const close = () => {
        for (const res of activeResponses) {
          try {
            res.end();
          } catch {
            // ignore
          }
        }
        activeResponses.length = 0;
        try {
          server.close();
        } catch {
          // ignore
        }
      };

      resolve({
        server,
        port,
        activeResponses,
        sendEvent,
        close,
      });
    });
  });
}

// Fechamento de segurança do servidor SSE em caso de interrupção
After(async function (this: CustomWorld) {
  const sseInstance = (this as any).__sseServer as SSEServerInstance | undefined;
  if (sseInstance) {
    sseInstance.close();
    (this as any).__sseServer = null;
  }
});

// Helper para inicializar e manter sessão ativa de streaming determinístico
async function setupAndStartStreaming(world: CustomWorld, tema: string) {
  if (!world.page) {
    await world.init({ width: 1440, height: 900 });
  }

  // Se já não estiver na página, acessa a home
  const currentUrl = world.page!.url();
  if (!currentUrl || !currentUrl.includes(world.baseUrl)) {
    await world.page!.goto(world.baseUrl);
    await world.page!.waitForSelector('.composer-input');
  }

  // Verifica se o plano já está visível
  const planVisible = await world.page!.locator('.plan-card').isVisible().catch(() => false);
  if (!planVisible) {
    await world.page!.locator('.composer-input').fill(tema);
    await world.page!.locator('.composer-send-btn').click();
    await world.page!.waitForSelector('.plan-card', { timeout: 15000 });
  }

  // Inicializa servidor SSE controlado se ainda não existir
  let sseInstance = (world as any).__sseServer as SSEServerInstance | undefined;
  if (!sseInstance) {
    sseInstance = await createSSEServer();
    (world as any).__sseServer = sseInstance;

    // Roteia requisições SSE para o servidor local mock
    await world.page!.route('**/api/v1/pipeline/*/stream', async (route) => {
      await route.continue({ url: `http://127.0.0.1:${sseInstance!.port}/stream` });
    });

    // Intercepta rotas de mutação síncrona para que o stream assuma o controle do pipeline
    let resolveSearch: () => void;
    const searchPromise = new Promise<void>((r) => {
      resolveSearch = r;
    });

    (world as any).pendingRouteResolvers = (world as any).pendingRouteResolvers || [];
    (world as any).pendingRouteResolvers.push(() => {
      resolveSearch?.();
    });

    await world.page!.route('**/api/v1/search', async (route) => {
      await searchPromise;
      await route.fulfill({
        status: 200,
        headers: { 'Content-Type': 'application/json' },
        json: { resumo_coletas: [] },
      });
    });
  }

  // Inicia a pesquisa se o botão ainda estiver na tela
  const startBtn = world.page!.locator('#start-research-btn');
  if (await startBtn.isVisible()) {
    await startBtn.click();
  }

  // Envia status inicial de busca via SSE para garantir sincronização
  sseInstance.sendEvent('pipeline.status', {
    status_pipeline: 'buscando',
  });

  // Aguarda montagem do indicador pulsante
  await world.page!.waitForSelector('.live-pulse-dot', { timeout: 10000 });
}

// Helper para emitir deliberações de teste (busca e auditoria)
async function emitSampleDeliberations(world: CustomWorld) {
  const sseInstance = (world as any).__sseServer as SSEServerInstance;
  if (!sseInstance) {
    throw new Error('Servidor SSE não inicializado.');
  }

  // 1. Persona Cético
  sseInstance.sendEvent('search.progress', {
    ponto_id: 'ponto-1',
    persona: 'cetico',
    queries_executadas: 4,
    urls_lidas: 7,
    falha_coleta: false,
    reasoning_coleta:
      '### Deliberação da Persona Cética\n\nAvaliando ceticamente as projeções de consumo de data centers para IA. Identificadas discrepâncias metodológicas entre relatórios setoriais e consumo real medido em redes elétricas regionais.',
  });

  // 2. Persona Historiador
  sseInstance.sendEvent('search.progress', {
    ponto_id: 'ponto-1',
    persona: 'historiador',
    queries_executadas: 3,
    urls_lidas: 5,
    falha_coleta: false,
    reasoning_coleta:
      '### Perspectiva Histórica\n\nComparação direta com o salto de demanda de infraestrutura durante a eletrificação das indústrias na década de 1920. Padrões de transição tecnológica indicam curva S de adoção.',
  });

  // 3. Auditor Analítico
  sseInstance.sendEvent('audit.result', {
    ponto_id: 'ponto-1',
    status: 'aprovado',
    pontuacao_percentual: 91.6,
    ponto_n: 1,
    criterios_aprovados: 11,
    pontos_fracos: [],
    reasoning_auditoria:
      '### Parecer da Auditoria Técnica (11/12 Critérios)\n\nEvidências canônicas verificadas. Triangulação de fontes confiáveis, ausência de alucinações factuais e rigor metodológico validado para o Ponto 1.',
  });

  // Aguarda os 4 cartões serem renderizados na tela (1 do planejador + 2 buscas + 1 auditoria)
  await world.page!.waitForFunction(() => {
    return document.querySelectorAll('.reasoning-card').length >= 4;
  }, { timeout: 10000 });
}

// -----------------------------------------------------------------------------
// STEP DEFINITIONS: Cenário 1 — Conexão SSE e indicador pulsante (.live-pulse-dot)
// -----------------------------------------------------------------------------

Given('planejo uma pesquisa para o tema {string}', async function (this: CustomWorld, tema: string) {
  await this.page!.locator('.composer-input').fill(tema);
  await this.page!.locator('.composer-send-btn').click();
  await this.page!.waitForSelector('.plan-card', { timeout: 15000 });
});

When('o canal de streaming SSE é iniciado para a pesquisa ativa', async function (this: CustomWorld) {
  await setupAndStartStreaming(this, 'Impacto da Inteligência Artificial na Matriz Energética');
});

Then('devo ver o indicador pulsante em tempo real ativo com a classe pulse-violet', async function (this: CustomWorld) {
  const pulseDot = this.page!.locator('.live-pulse-dot');
  await expect(pulseDot).toBeVisible();
  await expect(pulseDot).toHaveClass(/pulse-violet/);
});

Then('o indicador pulsante deve indicar atividade dos agentes em tempo real', async function (this: CustomWorld) {
  const pulseDot = this.page!.locator('.live-pulse-dot');
  const title = await pulseDot.getAttribute('title');
  expect(title).toBe('Agentes raciocinando em tempo real');
});

Then('uma captura de tela do indicador pulsante ativo deve ser salva no diretório de evidências', async function (this: CustomWorld) {
  await this.saveScreenshot('streaming-01-live-pulse.png');
});

// -----------------------------------------------------------------------------
// STEP DEFINITIONS: Cenário 2 — Raciocínios e cards expansíveis (.reasoning-card)
// -----------------------------------------------------------------------------

Given('que a conexão de streaming está ativa para a pesquisa em andamento', async function (this: CustomWorld) {
  await setupAndStartStreaming(this, 'Impacto da Inteligência Artificial na Matriz Energética');
});

When('o pipeline transmite raciocínios de busca e parecer da auditoria', async function (this: CustomWorld) {
  await emitSampleDeliberations(this);
});

Then('devo ver os cartões de raciocínio renderizados no feed', async function (this: CustomWorld) {
  const cards = this.page!.locator('.reasoning-card');
  const count = await cards.count();
  expect(count).toBeGreaterThanOrEqual(4);
});

Then('cada cartão deve exibir o crachá do agente e o título da deliberação', async function (this: CustomWorld) {
  const badges = this.page!.locator('.reasoning-card .reasoning-agent-badge');
  const titles = this.page!.locator('.reasoning-card .reasoning-card-title');

  expect(await badges.count()).toBeGreaterThanOrEqual(4);
  expect(await titles.count()).toBeGreaterThanOrEqual(4);

  const firstBadgeText = await badges.first().textContent();
  expect(firstBadgeText?.trim().length).toBeGreaterThan(0);

  const firstTitleText = await titles.first().textContent();
  expect(firstTitleText?.trim().length).toBeGreaterThan(0);
});

Then('devo conseguir recolher e expandir o conteúdo de um cartão de raciocínio ao clicar no cabeçalho', async function (this: CustomWorld) {
  const targetCard = this.page!.locator('.reasoning-card').first();
  const targetHeader = targetCard.locator('.reasoning-card-header');
  const targetBody = targetCard.locator('.reasoning-card-body');

  // Inicialmente expandido
  await expect(targetHeader).toHaveAttribute('aria-expanded', 'true');
  await expect(targetBody).toBeVisible();

  // Clica no cabeçalho para recolher
  await targetHeader.click();
  await expect(targetHeader).toHaveAttribute('aria-expanded', 'false');
  await expect(targetBody).toHaveCount(0);

  // Clica novamente para reexpandir
  await targetHeader.click();
  await expect(targetHeader).toHaveAttribute('aria-expanded', 'true');
  await expect(targetBody).toBeVisible();
});

Then('uma captura de tela dos cartões de raciocínio expansíveis deve ser salva no diretório de evidências', async function (this: CustomWorld) {
  await this.saveScreenshot('streaming-02-cards-expandable.png');
});

// -----------------------------------------------------------------------------
// STEP DEFINITIONS: Cenário 3 — Filtro de cartões de raciocínio por chips
// -----------------------------------------------------------------------------

Given('que o feed de raciocínio possui deliberações de busca e auditoria registradas', async function (this: CustomWorld) {
  await setupAndStartStreaming(this, 'Impacto da Inteligência Artificial na Matriz Energética');
  const count = await this.page!.locator('.reasoning-card').count();
  if (count < 4) {
    await emitSampleDeliberations(this);
  }
});

When('seleciono o chip de filtro de "Personas de Busca"', async function (this: CustomWorld) {
  const chipBusca = this.page!.locator('.reasoning-chip:has-text("Personas de Busca")');
  await chipBusca.click();
  await expect(chipBusca).toHaveClass(/selected/);
});

Then('apenas os cartões das personas de busca devem estar visíveis no feed', async function (this: CustomWorld) {
  const cards = this.page!.locator('.reasoning-card');
  const count = await cards.count();
  expect(count).toBe(2);

  const badges = this.page!.locator('.reasoning-agent-badge');
  const badgeCounts = await badges.count();
  for (let i = 0; i < badgeCounts; i++) {
    await expect(badges.nth(i)).toHaveClass(/agent-badge-busca/);
  }
});

When('seleciono o chip de filtro de "Auditor"', async function (this: CustomWorld) {
  const chipAuditor = this.page!.locator('.reasoning-chip:has-text("Auditor")');
  await chipAuditor.click();
  await expect(chipAuditor).toHaveClass(/selected/);
});

Then('apenas os pareceres do auditor analítico devem estar visíveis no feed', async function (this: CustomWorld) {
  const cards = this.page!.locator('.reasoning-card');
  const count = await cards.count();
  expect(count).toBe(1);

  const badge = this.page!.locator('.reasoning-agent-badge').first();
  await expect(badge).toHaveClass(/agent-badge-auditor/);
});

When('seleciono o chip de filtro "Todos"', async function (this: CustomWorld) {
  const chipTodos = this.page!.locator('.reasoning-chip:has-text("Todos")');
  await chipTodos.click();
  await expect(chipTodos).toHaveClass(/selected/);
});

Then('todos os cartões de raciocínio devem voltar a ficar visíveis', async function (this: CustomWorld) {
  const cards = this.page!.locator('.reasoning-card');
  const count = await cards.count();
  expect(count).toBeGreaterThanOrEqual(4);
});

Then('os contadores dos chips devem corresponder ao total de deliberações por agente', async function (this: CustomWorld) {
  const chipTodos = this.page!.locator('.reasoning-chip:has-text("Todos")');
  const chipBusca = this.page!.locator('.reasoning-chip:has-text("Personas de Busca")');
  const chipAuditor = this.page!.locator('.reasoning-chip:has-text("Auditor")');

  expect(await chipTodos.textContent()).toContain('(4)');
  expect(await chipBusca.textContent()).toContain('(2)');
  expect(await chipAuditor.textContent()).toContain('(1)');
});

Then('uma captura de tela do filtro por chips deve ser salva no diretório de evidências', async function (this: CustomWorld) {
  await this.saveScreenshot('streaming-03-filtering-chips.png');
});

// -----------------------------------------------------------------------------
// STEP DEFINITIONS: Cenário 4 — Controles de rolagem e cópia para clipboard
// -----------------------------------------------------------------------------

Given('que o feed de raciocínio possui deliberações analíticas detalhadas', async function (this: CustomWorld) {
  await setupAndStartStreaming(this, 'Impacto da Inteligência Artificial na Matriz Energética');
  const count = await this.page!.locator('.reasoning-card').count();
  if (count < 4) {
    await emitSampleDeliberations(this);
  }
});

When('clico no botão de auto-rolagem do feed', async function (this: CustomWorld) {
  const autoScrollBtn = this.page!.locator('.reasoning-feed-btn[title*="rolagem automática"]');
  await autoScrollBtn.click();
});

Then('o botão de auto-rolagem deve indicar o estado pausado', async function (this: CustomWorld) {
  const autoScrollBtn = this.page!.locator('.reasoning-feed-btn[title*="rolagem automática"]');
  await expect(autoScrollBtn).toHaveText(/Pausado/);
  await expect(autoScrollBtn).not.toHaveClass(/active/);
  await expect(autoScrollBtn).toHaveAttribute('aria-pressed', 'false');
});

When('clico novamente no botão de auto-rolagem do feed', async function (this: CustomWorld) {
  const autoScrollBtn = this.page!.locator('.reasoning-feed-btn[title*="rolagem automática"]');
  await autoScrollBtn.click();
});

Then('o botão de auto-rolagem deve retornar ao estado ativo', async function (this: CustomWorld) {
  const autoScrollBtn = this.page!.locator('.reasoning-feed-btn[title*="rolagem automática"]');
  await expect(autoScrollBtn).toHaveText(/Auto-scroll On/);
  await expect(autoScrollBtn).toHaveClass(/active/);
  await expect(autoScrollBtn).toHaveAttribute('aria-pressed', 'true');
});

When('clico no botão de copiar o raciocínio de um cartão', async function (this: CustomWorld) {
  // Clica no botão de cópia do primeiro cartão de busca (Cético)
  const ceticoCard = this.page!.locator('.reasoning-card:has-text("Cético")');
  const copyBtn = ceticoCard.locator('button[title="Copiar cadeia de raciocínio"]');
  await copyBtn.click();
});

Then('o texto da deliberação analítica deve ser gravado na área de transferência', async function (this: CustomWorld) {
  const clipboardText = await this.getContextClipboard();
  expect(clipboardText.length).toBeGreaterThan(20);
  expect(clipboardText).toContain('Deliberação da Persona Cética');
});

Then('o botão de cópia deve exibir a confirmação visual', async function (this: CustomWorld) {
  const ceticoCard = this.page!.locator('.reasoning-card:has-text("Cético")');
  const copyBtn = ceticoCard.locator('button[title="Copiar cadeia de raciocínio"]');
  // Verifica se o ícone Check substituiu o Copy com a cor de sucesso esmeralda DominusLabs
  await expect(copyBtn.locator('svg')).toBeVisible();
  const innerHtml = await copyBtn.innerHTML();
  expect(innerHtml).toContain('#047857');
});

Then('uma captura de tela dos controles de rolagem e cópia deve ser salva no diretório de evidências', async function (this: CustomWorld) {
  await this.saveScreenshot('streaming-04-scroll-and-copy.png');
});

// -----------------------------------------------------------------------------
// STEP DEFINITIONS: Cenário 5 — Conclusão com entrega do dossiê e feed preservado
// -----------------------------------------------------------------------------

Given('que a conexão de streaming está ativa com deliberações analíticas registradas', async function (this: CustomWorld) {
  await setupAndStartStreaming(this, 'Impacto da Inteligência Artificial na Matriz Energética');
  const count = await this.page!.locator('.reasoning-card').count();
  if (count < 4) {
    await emitSampleDeliberations(this);
  }
});

When('o pipeline transmite o relatório final concluído com o dossiê completo', async function (this: CustomWorld) {
  const sseInstance = (this as any).__sseServer as SSEServerInstance;
  if (!sseInstance) {
    throw new Error('Servidor SSE não inicializado.');
  }

  // 1. Emite progresso de redação
  sseInstance.sendEvent('writer.progress', {
    status: 'concluido',
    total_caracteres: 2480,
    reasoning_dossier:
      '### Deliberação da Redação Final\n\nConsolidação das análises cética e histórica em síntese executiva contínua com fontes canônicas auditadas.',
  });

  // 2. Emite o relatório final concluído
  sseInstance.sendEvent('report.final', {
    id_pesquisa: 'pesquisa-streaming-e2e',
    tema: 'Impacto da Inteligência Artificial na Matriz Energética',
    status: 'concluido',
    total_caracteres: 2480,
    concluido_em: new Date().toISOString(),
    dossier_final:
      '# Dossiê Analítico: Impacto da Inteligência Artificial na Matriz Energética\n\n## 1. Sumário Executivo\nA expansão contínua da capacidade computacional para modelos de linguagem exige redimensionamento das subestações e geração renovável dedicada.\n\n## 2. Evidências Empíricas\nDados canônicos auditados confirmam avanço na eficiência de PUE dos data centers modernos.',
  });

  // 3. Emite atualização final de status do pipeline
  sseInstance.sendEvent('pipeline.status', {
    status_pipeline: 'concluido',
  });

  // Aguarda montagem do relatório na página
  await this.page!.waitForSelector('#dossier-report', { timeout: 15000 });
});

Then('devo ver o relatório do dossiê analítico entregue com sucesso', async function (this: CustomWorld) {
  const reportContainer = this.page!.locator('#dossier-report');
  await expect(reportContainer).toBeVisible();

  const statusBadge = reportContainer.locator('.status-badge-chip.concluido');
  await expect(statusBadge).toBeVisible();
  expect(await statusBadge.textContent()).toContain('Dossiê Concluído');
});

Then('o feed de raciocínio com todos os cartões anteriores deve permanecer preservado e acessível', async function (this: CustomWorld) {
  const feedContainer = this.page!.locator('.reasoning-feed-container');
  await expect(feedContainer).toBeVisible();

  const cards = this.page!.locator('.reasoning-card');
  const count = await cards.count();
  // 1 planejador + 2 buscas + 1 auditoria + 1 redação = 5
  expect(count).toBeGreaterThanOrEqual(5);
});

Then('o indicador pulsante deve transicionar para o estado ocioso', async function (this: CustomWorld) {
  const pulseDot = this.page!.locator('.live-pulse-dot');
  await expect(pulseDot).toBeVisible();
  await expect(pulseDot).toHaveClass(/idle/);
  await expect(pulseDot).not.toHaveClass(/pulse-violet/);
});

Then('uma captura de tela da conclusão do streaming com dossiê e feed preservado deve ser salva no diretório de evidências', async function (this: CustomWorld) {
  await this.saveScreenshot('streaming-05-dossier-delivered-feed-preserved.png');
});

// -----------------------------------------------------------------------------
// STEP DEFINITIONS: Cenário 6 — Erro terminal e encerramento seguro da conexão
// -----------------------------------------------------------------------------

When('o pipeline transmite um evento de erro fatal no stream', async function (this: CustomWorld) {
  const sseInstance = (this as any).__sseServer as SSEServerInstance;
  if (!sseInstance) {
    throw new Error('Servidor SSE não inicializado.');
  }

  // Emite erro terminal no stream
  sseInstance.sendEvent('pipeline.error', {
    erro: 'Falha terminal irrecuperável: indisponibilidade dos provedores externos e cancelamento seguro',
  });

  sseInstance.sendEvent('pipeline.status', {
    status_pipeline: 'falha',
  });

  // Aguarda montagem do alerta de perigo
  await this.page!.waitForSelector('.alert-banner.danger', { timeout: 10000 });
});

Then('devo ver o banner de alerta exibindo a mensagem descritiva do erro terminal', async function (this: CustomWorld) {
  const banner = this.page!.locator('.alert-banner.danger');
  await expect(banner).toBeVisible();
  const text = await banner.textContent();
  expect(text).toContain('Falha terminal irrecuperável');
});

Then('o indicador pulsante deve estar em estado ocioso', async function (this: CustomWorld) {
  const pulseDot = this.page!.locator('.live-pulse-dot');
  await expect(pulseDot).toBeVisible();
  await expect(pulseDot).toHaveClass(/idle/);
  await expect(pulseDot).not.toHaveClass(/pulse-violet/);
});

Then('as opções de reinício e recuperação devem estar acessíveis', async function (this: CustomWorld) {
  const resetBtn = this.page!.locator('.alert-banner.danger button:has-text("Formular novo tema")');
  await expect(resetBtn).toBeVisible();
  expect(await resetBtn.textContent()).toContain('Formular novo tema');
});

Then('uma captura de tela do tratamento de erro terminal deve ser salva no diretório de evidências', async function (this: CustomWorld) {
  await this.saveScreenshot('streaming-06-terminal-error-safe-closure.png');
});
