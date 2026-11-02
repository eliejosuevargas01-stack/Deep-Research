import { register } from 'node:module';
import { pathToFileURL } from 'node:url';

const cssHook = `
export async function load(url, context, nextLoad) {
  if (url.endsWith('.css')) {
    return { format: 'module', shortCircuit: true, source: 'export default {};' };
  }
  return nextLoad(url, context);
}
`;
register('data:text/javascript,' + encodeURIComponent(cssHook), pathToFileURL('./'));

import assert from 'node:assert';
import React from 'react';
import { renderToString } from 'react-dom/server';
import type { PlanResponse } from '../types/api';

async function run() {
  const { ExecutionView } = await import('../components/ExecutionView.js');

  const mockPlan: PlanResponse = {
    id_pesquisa: 'chat-scroll-test-id',
    tema: 'OWASP Top 10:2025 Teste Chat Scroll',
    n_pontos: 1,
    pontos: [
      {
        ponto_id: 'p1',
        ponto_n: 1,
        ponto: 'Vulnerabilidades emergentes',
        status: 'pendente',
      },
    ],
    criado_em: '2026-11-01T20:00:00.000Z',
    preferencias: { criterios_minimos: 11 },
  };

  console.log('=== Iniciando Teste de Layout e Rolagem Chat (Bottom-pinned) ===\n');

  // 1. Renderizar ExecutionView e validar estrutura de concha de chat
  const html = renderToString(
    React.createElement(ExecutionView, {
      stage: 'searching',
      plan: mockPlan,
      searchResult: null,
      auditResult: null,
      cycleNumber: 1,
      maxCycles: 4,
      sourcesCount: 10,
      onReset: () => {},
    })
  );

  console.log('[Teste 1] Card com classe execution-card--chat-layout');
  assert.ok(
    html.includes('execution-card--chat-layout'),
    'ExecutionView deve carregar classe modificadora de chat execution-card--chat-layout'
  );

  console.log('[Teste 2] Topo estático e fixo presente (execution-card-static-top)');
  assert.ok(
    html.includes('execution-card-static-top'),
    'Deve conter contêiner fixo para título, progresso e telemetria'
  );
  assert.ok(
    html.includes('exec-progress'),
    'Barra de progresso deve estar presente no topo estático'
  );
  assert.ok(
    html.includes('exec-telemetry-bar'),
    'Telemetria de tokens e fontes deve estar no topo estático'
  );

  console.log('[Teste 3] Feed de rolagem presente (execution-feed-scroll)');
  assert.ok(
    html.includes('execution-feed-scroll'),
    'Feed de rolagem deve encapsular a timeline'
  );
  assert.ok(
    html.includes('tl-linear'),
    'Timeline deve estar dentro do feed de rolagem'
  );

  console.log('[Teste 4] Âncora da base presente para rolagem bottom-pinned');
  assert.ok(
    html.includes('execution-chat-anchor'),
    'Âncora invisível da base deve existir para manter o chat ancorado no fim'
  );

  console.log('\n--- TODOS OS 4 TESTES DE LAYOUT CHAT PASSARAM COM SUCESSO! ---');
}

run().catch((err) => {
  console.error('Falha no teste:', err);
  process.exit(1);
});
