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

// --- 1. Cartão de pré-voo + faixa numerada de quatro fases ---
const html = renderPlan({ onEditParameters: () => {} });

assert.ok(html.includes('gdr-plan-preflight'), 'cartão de pré-voo renderizado');
assert.ok(html.includes('class="gdr-phases"'), 'faixa de fases usa classe gdr-phases');
assert.equal(
  (html.match(/class="gdr-phase"/g) || []).length,
  4,
  'faixa lista exatamente quatro fases'
);

const fasesEsperadas = ['Mapeamento', 'Busca', 'Auditoria', 'Dossiê'];
let cursorFase = -1;
for (const nome of fasesEsperadas) {
  const idx = html.indexOf(nome, cursorFase + 1);
  assert.ok(idx > cursorFase, `fase "${nome}" presente e na ordem canônica`);
  cursorFase = idx;
}

const numerosEsperados = ['01', '02', '03', '04'];
let cursorNum = -1;
for (const num of numerosEsperados) {
  const idx = html.indexOf(`gdr-phase-num">${num}`, cursorNum + 1);
  assert.ok(idx > cursorNum, `fase ${num} numerada em sequência`);
  cursorNum = idx;
}

assert.ok(html.includes('2 personas'), 'fase Busca reflete personas do plano');
assert.ok(html.includes('Dossiê'), 'fase Dossiê presente');

// --- 2. Ações primárias do pré-voo ---
assert.ok(html.includes('data-gdr-action="edit-parameters"'), 'ação Editar parâmetros presente');
assert.ok(html.includes('data-gdr-action="approve-and-start"'), 'ação Aprovar e iniciar presente');
assert.ok(html.includes('<span>Editar parâmetros</span>'), 'rótulo Editar parâmetros exato');

// --- 3. Botão atual preservado e único para E2E ---
assert.equal(
  (html.match(/id="start-research-btn"/g) || []).length,
  1,
  'exatamente um #start-research-btn'
);
assert.equal(
  (html.match(/<span>Iniciar pesquisa<\/span>/g) || []).length,
  1,
  'texto Iniciar pesquisa preservado uma única vez'
);

// --- 4. Ordem: pré-voo e botão de início antes do stepper ---
const preflightIdx = html.indexOf('gdr-plan-preflight');
const startBtnIdx = html.indexOf('id="start-research-btn"');
const stepperIdx = html.indexOf('plan-stepper');
assert.ok(preflightIdx !== -1 && startBtnIdx !== -1 && stepperIdx !== -1, 'marcos presentes no DOM');
assert.ok(startBtnIdx < stepperIdx, 'Iniciar pesquisa precede os eixos (acima da dobra)');
assert.ok(preflightIdx < stepperIdx, 'pré-voo precede os eixos investigativos');

// --- 5. isStarting desabilita as duas ações novas, sem quebrar o botão atual ---
const htmlStarting = renderPlan({ isStarting: true });
const editTag = htmlStarting.match(/<button[^>]*data-gdr-action="edit-parameters"[^>]*>/)?.[0] || '';
const approveTag = htmlStarting.match(/<button[^>]*data-gdr-action="approve-and-start"[^>]*>/)?.[0] || '';
const startTag = htmlStarting.match(/<button[^>]*id="start-research-btn"[^>]*>/)?.[0] || '';
assert.ok(editTag.includes('disabled'), 'Editar parâmetros desabilita durante início');
assert.ok(approveTag.includes('disabled'), 'Aprovar e iniciar desabilita durante início');
assert.ok(startTag.includes('disabled'), 'Iniciar pesquisa segue desabilitando durante início');

// --- 6. Props atuais intactas + fallback de parâmetros para onEditTheme ---
const htmlSemPropNova = renderPlan({});
assert.ok(htmlSemPropNova.includes('data-gdr-action="edit-parameters"'), 'ação renderiza sem prop nova');
assert.ok(htmlSemPropNova.includes('gdr-phases'), 'faixa de fases independe de props opcionais');

// --- 7. Plano mínimo mantém faixa e fallbacks de metadados ---
const htmlMinimo = renderToString(
  React.createElement(PlanView, {
    plan: {
      id_pesquisa: 'plan-step-2',
      tema: 'tema mínimo',
      n_pontos: 1,
      criado_em: new Date().toISOString(),
      pontos: [],
    },
    onStartExecution: () => {},
    onReset: () => {},
    isStarting: false,
  } as any)
);
assert.equal((htmlMinimo.match(/class="gdr-phase"/g) || []).length, 4, 'plano mínimo mantém quatro fases');
assert.ok(htmlMinimo.includes('1 eixo'), 'fase Mapeamento usa singular para 1 ponto');
assert.ok(htmlMinimo.includes('Personas'), 'fase Busca cai no rótulo Personas sem snapshot');

console.log('GDR plan step ok');
