import { register } from 'node:module';
import { pathToFileURL } from 'node:url';
const cssHook = `
export async function load(url, context, nextLoad) {
  if (url.endsWith('.css')) {
    return { format: 'module', shortCircuit: true, source: 'export default {};' };
  }
  return nextLoad(url, context);
}`;
register('data:text/javascript,' + encodeURIComponent(cssHook), pathToFileURL('./'));

import assert from 'node:assert/strict';
import React from 'react';
import { renderToString } from 'react-dom/server';

const { PlanView } = await import('../components/PlanView.js');

const planoCompleto = {
  id_pesquisa: 'plan-step-1',
  tema: 'energia solar no nordeste',
  n_pontos: 2,
  criado_em: new Date().toISOString(),
  pontos: [],
  preferencias: { personas: ['historiador', 'cetico'], n_pontos: 2 },
  plano_estruturado: {
    pedido_original: 'energia solar',
    pedido_normalizado: 'energia solar no nordeste',
    publico: 'gestores públicos',
    formato_entrega: 'Dossiê analítico executivo',
    eixos: [],
  },
};

const renderPlan = (props: Record<string, unknown>) =>
  renderToString(
    React.createElement(PlanView, {
      plan: planoCompleto,
      onStartExecution: () => {},
      onReset: () => {},
      onEditTheme: () => {},
      isStarting: false,
      ...props,
    } as any)
  );

// --- 1. Eliminação de explicação desnecessária de fluxo (gdr-phases e preflight descartados) ---
const html = renderPlan({});

assert.ok(!html.includes('gdr-plan-preflight'), 'cartão de pré-voo descartado para ganho de espaço vertical');
assert.ok(!html.includes('class="gdr-phases"'), 'faixa de fases redundante eliminada');

// --- 2. Eliminação de botão redundante Editar parâmetros ---
assert.ok(!html.includes('data-gdr-action="edit-parameters"'), 'botão Editar parâmetros eliminado pós-geração');
assert.ok(!html.includes('<span>Editar parâmetros</span>'), 'rótulo Editar parâmetros não existe no DOM');

// --- 3. Botão primário consolidado e único no DOM ---
assert.equal(
  (html.match(/id="start-research-btn"/g) || []).length,
  1,
  'exatamente um #start-research-btn no DOM'
);
assert.equal(
  (html.match(/<span>Iniciar pesquisa<\/span>/g) || []).length,
  1,
  'texto Iniciar pesquisa preservado uma única vez'
);
assert.ok(html.includes('data-gdr-action="approve-and-start"'), 'ação approve-and-start presente no botão primário');

// --- 4. Ordem e foco: botão de início e stepper de eixos imediatos ---
const startBtnIdx = html.indexOf('id="start-research-btn"');
const stepperIdx = html.indexOf('plan-stepper');
assert.ok(startBtnIdx !== -1 && stepperIdx !== -1, 'marcos presentes no DOM');
assert.ok(startBtnIdx < stepperIdx, 'Iniciar pesquisa precede os eixos no topo');

// --- 5. isStarting desabilita o botão de início ---
const htmlStarting = renderPlan({ isStarting: true });
const startTag = htmlStarting.match(/<button[^>]*id="start-research-btn"[^>]*>/)?.[0] || '';
assert.ok(startTag.includes('disabled'), 'Iniciar pesquisa desabilitado durante início');

// --- 6. Metadados essenciais visíveis em chips compactos ---
assert.ok(html.includes('2 pontos analíticos'), 'chip de pontos presente no header');
assert.ok(html.includes('2 personas'), 'chip de personas presente no header');

console.log('GDR plan step ok');
