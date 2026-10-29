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
import type { AuditResponse, PlanResponse } from '../types/api.js';

const { ExecutionView } = await import('../components/ExecutionView.js');

const noop = () => {};

/** Conta ocorrências literais no HTML SSR (sem depender de parser DOM). */
function contar(html: string, alvo: string): number {
  return html.split(alvo).length - 1;
}

const plano: PlanResponse = {
  id_pesquisa: 'exec-step',
  tema: 'energia',
  n_pontos: 2,
  criado_em: new Date().toISOString(),
  pontos: [
    { ponto_id: 'p1', ponto_n: 1, ponto: 'Matriz elétrica', status: 'reprovado' },
    { ponto_id: 'p2', ponto_n: 2, ponto: 'Armazenamento', status: 'reprovado' },
    { ponto_id: 'p3', ponto_n: 3, ponto: 'Rede de transmissão', status: 'reprovado' },
  ],
};

const auditoria: AuditResponse = {
  id_pesquisa: 'exec-step',
  total_pontos: 2,
  aprovados: 0,
  reprovados: 2,
  status_geral: 'reprovado',
  pronto_para_writer: false,
  auditorias: [
    {
      ponto_id: 'p1',
      ponto_n: 1,
      status: 'reprovado',
      pontuacao_percentual: 50,
      criterios_aprovados: 6,
      criterios_minimos: 11,
      valido: false,
      criterios: [
        { id: 1, aprovado: false, justificativa: 'tema difuso', claim_ids: [], source_ids: [] },
        { id: 2, aprovado: false, justificativa: 'fonte única', claim_ids: [], source_ids: [] },
        { id: 3, aprovado: false, justificativa: 'desatualizado', claim_ids: [], source_ids: [] },
        { id: 4, aprovado: false, justificativa: 'contradição', claim_ids: [], source_ids: [] },
        { id: 5, aprovado: false, justificativa: 'sem lastro', claim_ids: [], source_ids: [] },
        { id: 6, aprovado: false, justificativa: 'fora do escopo', claim_ids: [], source_ids: [] },
      ],
    },
    {
      ponto_id: 'p2',
      ponto_n: 2,
      status: 'reprovado',
      pontuacao_percentual: 83,
      criterios_aprovados: 10,
      criterios_minimos: 11,
      valido: false,
      criterios: [
        { id: 3, aprovado: false, justificativa: 'dados de 2019', claim_ids: [], source_ids: [] },
        { id: 9, aprovado: true, justificativa: 'tom neutro', claim_ids: [], source_ids: [] },
      ],
    },
  ],
};

// --- T1: estado rejected — banner, pílulas limitadas por ponto e ações ---
const htmlRejected = renderToString(
  React.createElement(ExecutionView, {
    stage: 'rejected',
    plan: null,
    searchResult: null,
    auditResult: auditoria,
    cycleNumber: 1,
    maxCycles: 4,
    errorMessage: null,
    failedStage: null,
    onReset: noop,
    onRefazerBuscaPonto: noop,
    onReauditarPonto: noop,
  } as any)
);
assert.ok(htmlRejected.includes('exec-error-card'), 'rejected usa exec-error-card');
assert.ok(htmlRejected.includes('Investigação bloqueada na auditoria de qualidade'), 'rejected preserva titulo do banner');
assert.ok(
  htmlRejected.includes('Nem todos os pontos atingiram o limiar mínimo de 11/12 critérios'),
  'rejected preserva texto explicativo'
);
assert.ok(htmlRejected.includes('gdr-criteria-pills'), 'rejected usa lista de pilulas existente');
assert.equal(contar(htmlRejected, 'class="gdr-criteria-pill"'), 5, 'pilulas limitadas a 4 por ponto (4 + 1)');
assert.ok(htmlRejected.includes('Clareza Temática'), 'pilula usa nome canonico do criterio 1');
assert.ok(htmlRejected.includes('Atualidade'), 'pilula usa nome canonico do criterio 3');
assert.match(htmlRejected, /\+<!-- -->2<!-- --> .*critérios não cumpridos/, 'excedente de criterios sinalizado');
assert.ok(!htmlRejected.includes('Precisão de Dados'), 'criterio fora do limite nao renderiza');
assert.ok(htmlRejected.includes('data-ponto-id="p1"'), 'pendencia agrupada por ponto p1');
assert.ok(htmlRejected.includes('data-ponto-id="p2"'), 'pendencia agrupada por ponto p2');
assert.equal(contar(htmlRejected, '<span>Refazer busca</span>'), 2, 'um Refazer busca por ponto');
assert.equal(contar(htmlRejected, '<span>Reauditar por ponto</span>'), 2, 'um Reauditar por ponto por ponto');
assert.equal(contar(htmlRejected, '<span>Formular novo tema</span>'), 1, 'acao secundaria unica preservada');

// --- T2: estado failed com parecer — erro + pilulas + botoes primarios ---
const htmlFailed = renderToString(
  React.createElement(ExecutionView, {
    stage: 'failed',
    plan: plano,
    searchResult: null,
    auditResult: auditoria,
    cycleNumber: 2,
    maxCycles: 4,
    errorMessage: 'Timeout ao consultar provedor (504)',
    failedStage: 'searching',
    isRetrying: false,
    onRetry: noop,
    onReset: noop,
    onRefazerBuscaPonto: noop,
    onReauditarPonto: noop,
    pontoEmReprocesso: 'p1',
  } as any)
);
assert.ok(htmlFailed.includes('exec-error-card'), 'failed usa exec-error-card');
assert.ok(htmlFailed.includes('Tempo limite de execução excedido (Timeout):'), 'failed preserva titulo de timeout');
assert.ok(htmlFailed.includes('Timeout ao consultar provedor (504)'), 'failed preserva mensagem do erro');
assert.ok(htmlFailed.includes('gdr-criteria-pills'), 'failed exibe pilulas de criterios');
assert.equal(contar(htmlFailed, 'class="gdr-criteria-pill"'), 5, 'failed aplica mesmo limite por ponto');
assert.equal(contar(htmlFailed, '<span>Refazer busca</span>'), 2, 'failed exibe Refazer busca por ponto');
assert.equal(contar(htmlFailed, '<span>Reauditar por ponto</span>'), 2, 'failed exibe Reauditar por ponto');
assert.equal(contar(htmlFailed, '<span>Formular novo tema</span>'), 1, 'failed mantem acao secundaria');
assert.ok(htmlFailed.includes('Tentar busca e auditoria novamente'), 'failed preserva texto do retry atual');
assert.ok(htmlFailed.includes('disabled=""'), 'ponto em reprocesso desabilita os botoes');

// --- T3: failed sem parecer — pontos do plano como alvo, sem pilulas ---
const htmlFailedSemAuditoria = renderToString(
  React.createElement(ExecutionView, {
    stage: 'failed',
    plan: plano,
    searchResult: null,
    auditResult: null,
    cycleNumber: 1,
    maxCycles: 4,
    errorMessage: 'Falha inesperada',
    failedStage: 'auditing',
    onRetry: noop,
    onReset: noop,
    onRefazerBuscaPonto: noop,
    onReauditarPonto: noop,
  } as any)
);
assert.ok(htmlFailedSemAuditoria.includes('exec-error-card'), 'falha sem parecer mantem banner');
assert.ok(!htmlFailedSemAuditoria.includes('gdr-criteria-pills'), 'sem parecer nao inventa pilulas');
assert.equal(
  contar(htmlFailedSemAuditoria, '<span>Refazer busca</span>'),
  3,
  'sem parecer lista os pontos do plano (limitados a 4)'
);
assert.equal(contar(htmlFailedSemAuditoria, '<span>Reauditar por ponto</span>'), 3, 'reauditoria por ponto disponivel');
assert.equal(contar(htmlFailedSemAuditoria, '<span>Formular novo tema</span>'), 1, 'acao secundaria preservada');
assert.ok(htmlFailedSemAuditoria.includes('Tentar auditoria novamente'), 'retry preserva texto por estagio');

console.log('gdr-exec-step ok');
