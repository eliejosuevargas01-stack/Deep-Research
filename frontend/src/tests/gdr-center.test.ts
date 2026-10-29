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
const { ExecutionView } = await import('../components/ExecutionView.js');
const { ReasoningCardItem } = await import('../components/ReasoningCardItem.js');

// --- T4: faixa de fases ---
const htmlPlan = renderToString(
  React.createElement(PlanView, {
    plan: { id_pesquisa: 'x', tema: 'energia', n_pontos: 2, criado_em: new Date().toISOString(), pontos: [], preferencias: { personas: ['historiador'] }, plano_estruturado: { pedido_original: 'e', pedido_normalizado: 'e', publico: 'p', formato_entrega: 'Dossiê analítico', eixos: [] } },
    onStartExecution: () => {}, onReset: () => {}, isStarting: false,
  } as any)
);
assert.ok(htmlPlan.includes('gdr-phases'), 'plano exibe faixa de fases');
assert.ok(htmlPlan.includes('Mapeamento'), 'fase 01 presente');
assert.ok(htmlPlan.includes('Iniciar pesquisa'), 'acao primaria preservada');

// --- T6: pilulas de criterios reprovados ---
const htmlExec = renderToString(
  React.createElement(ExecutionView, {
    stage: 'rejected',
    plan: null,
    searchResult: null,
    auditResult: {
      id_pesquisa: 'x', total_pontos: 1, aprovados: 0, reprovados: 1,
      status_geral: 'reprovado', pronto_para_writer: false,
      auditorias: [{
        ponto_id: 'p1', ponto_n: 1, status: 'reprovado', pontuacao_percentual: 50,
        criterios_aprovados: 6, criterios_minimos: 11, valido: false,
        criterios: [{ id: 3, aprovado: false, justificativa: 'desatualizado', claim_ids: [], source_ids: [] }],
      }],
    },
    cycleNumber: 1, maxCycles: 4, errorMessage: null, failedStage: null,
    onReset: () => {},
  } as any)
);
assert.ok(htmlExec.includes('gdr-criteria-pill'), 'auditoria exibe pilula de criterio');
assert.ok(htmlExec.includes('Atualidade'), 'pilula usa nome canonico do criterio 3');

// --- T5: takeaway com pontos_fracos, ausente sem ---
const noop = () => {};
const reg = () => {};
const itemComTakeaway = {
  id: 't1', timestamp: new Date().toISOString(), agentType: 'auditor', agentName: 'Auditor',
  title: 'Auditoria', reasoning: 'Análise geral do ponto.\nConclusão: evidências insuficientes para aprovar.',
  status: 'reprovado',
};
const htmlTake = renderToString(
  React.createElement(ReasoningCardItem, {
    item: itemComTakeaway, aberto: true, copiado: false, onToggle: noop, onCopy: noop, registrarToggle: reg,
  } as any)
);
assert.ok(htmlTake.includes('reasoning-takeaway'), 'takeaway renderizado com Conclusao');
assert.ok(htmlTake.includes('evidências insuficientes'), 'texto do takeaway preservado');

const itemSemTakeaway = {
  id: 't2', timestamp: new Date().toISOString(), agentType: 'busca', agentName: 'Historiador',
  title: 'Varredura', reasoning: 'Buscando fontes sobre o tema sem marcador final.',
  status: 'concluido',
};
const htmlSem = renderToString(
  React.createElement(ReasoningCardItem, {
    item: itemSemTakeaway, aberto: true, copiado: false, onToggle: noop, onCopy: noop, registrarToggle: reg,
  } as any)
);
assert.ok(!htmlSem.includes('reasoning-takeaway'), 'sem marcador nao fabrica takeaway');

console.log('GDR center ok');
