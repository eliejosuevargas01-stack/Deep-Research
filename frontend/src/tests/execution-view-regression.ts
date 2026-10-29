/**
 * Testes de Regressão Focados para ExecutionView, ContextSidebar e Estado de Ciclo de Auditoria.
 * Executa exclusivamente componentes reais de produção via SSR (renderToString) e helpers puros.
 */
import { register } from 'node:module';
import { pathToFileURL } from 'node:url';

// Registra hook leve para ignorar import de folha de estilos CSS durante execução de testes SSR no Node
const cssHook = `
export async function load(url, context, nextLoad) {
  if (url.endsWith('.css')) {
    return { format: 'module', shortCircuit: true, source: 'export default {};' };
  }
  return nextLoad(url, context);
}
`;
register('data:text/javascript,' + encodeURIComponent(cssHook), pathToFileURL('./'));

import assert from 'node:assert/strict';
import React from 'react';
import { renderToString } from 'react-dom/server';
import { PlanResponse, AuditResponse, AuditItem, AuditCriterionDetail } from '../types/api';

function makeCriterion(id: number, aprovado: boolean, lacuna?: string, correcao?: string): AuditCriterionDetail {
  return {
    id,
    aprovado,
    justificativa: `Justificativa analítica para o critério ${id}.`,
    claim_ids: [`clm_${id}_test`],
    source_ids: [`src_${id}_test`],
    lacuna: lacuna ?? (aprovado ? null : `Lacuna observada no critério ${id}.`),
    correcao: correcao ?? (aprovado ? null : `Correção recomendada para o critério ${id}.`),
    personas_pertinentes: aprovado ? [] : ['cetico', 'historiador'],
  };
}

function makeAuditResponse(
  status: 'aprovado' | 'reprovado',
  criteriosAprovados: number,
  failedIds: number[] = []
): AuditResponse {
  const criterios: AuditCriterionDetail[] = Array.from({ length: 12 }, (_, i) => {
    const id = i + 1;
    const isFailed = failedIds.includes(id);
    return makeCriterion(id, !isFailed);
  });

  const auditItem: AuditItem = {
    ponto_id: 'p1',
    ponto_n: 1,
    status,
    pontuacao_percentual: (criteriosAprovados / 12) * 100,
    criterios_aprovados: criteriosAprovados,
    criterios_minimos: 11,
    valido: true,
    criterios,
    pontos_fracos:
      status === 'reprovado'
        ? "- Critério 4 (ausencia_contradicoes) (claims: [clm_historiador_2_fe580774: 'afirmação A']; sources: [src_7406715: https://exemplo.com]): divergência empírica | Correção: reconciliar datas"
        : null,
    diagnostico: status === 'reprovado' ? 'diagnostico_tecnico_interno_chk_567' : null,
    resumo_auditoria:
      status === 'reprovado'
        ? 'Divergência cronológica observada entre as personas Cético e Historiador.'
        : 'Todos os critérios atendidos.',
  };

  return {
    id_pesquisa: 'pesquisa-uuid-test',
    total_pontos: 1,
    aprovados: status === 'aprovado' ? 1 : 0,
    reprovados: status === 'reprovado' ? 1 : 0,
    status_geral: status === 'aprovado' ? 'aprovado' : 'reprovado',
    pronto_para_writer: status === 'aprovado',
    auditorias: [auditItem],
  };
}

const mockPlan: PlanResponse = {
  id_pesquisa: 'pesquisa-uuid-test',
  tema: 'Impacto dos Modelos de Raciocínio na Arquitetura de Software',
  n_pontos: 1,
  criado_em: '2026-10-26T19:00:00Z',
  pontos: [{ ponto_id: 'p1', ponto_n: 1, ponto: 'Eixo 1', status: 'pendente' }],
  preferencias: {
    n_pontos: 1,
    personas: ['historiador', 'cetico'],
  },
};

async function runExecutionViewRegressionTests() {
  console.log('=== Iniciando Testes de Regressão de Produção (ExecutionView & ContextSidebar) ===\n');

  // Carrega componentes de produção dinamicamente após o registro do hook CSS
  const {
    ExecutionView,
    CANONICAL_CRITERIA_NAMES: _unusedCriteria,
    getAuditContextualLabel,
    getSuccinctStatus,
    getCycleBadgeClass,
  } = await import('../components/ExecutionView.js');
  const { ContextSidebar } = await import('../components/ContextSidebar.js');

  // =========================================================================
  // 1. Prior Cycle 1 Audit in Cycle 2 Searching
  // =========================================================================
  console.log('[Teste 1] Auditoria do Ciclo 1 em andamento de busca no Ciclo 2');
  const auditCycle1 = makeAuditResponse('reprovado', 10, [4, 5]);

  const htmlCycle2 = renderToString(
    React.createElement(ExecutionView, {
      stage: 'searching',
      plan: mockPlan,
      searchResult: null,
      auditResult: auditCycle1,
      cycleNumber: 2,
      maxCycles: 4,
      onReset: () => {},
    })
  );

  assert.ok(
    htmlCycle2.includes('tl-linear'),
    'Timeline linear deve renderizar no lugar do breakdown aninhado'
  );
  assert.ok(
    htmlCycle2.includes('Auditor reprovou o ponto #'),
    'Timeline deve usar copy operacional na reprovação'
  );
  // Linha de estágios: texto corrido, sem caixas.
  assert.ok(
    htmlCycle2.includes('stage-line-item ativo') && htmlCycle2.includes('Busca com personas'),
    'Estágio de busca deve estar ativo na linha de estágios'
  );

  // =========================================================================
  // 2. Known Same Cycle during Writing
  // =========================================================================
  console.log('[Teste 2] Auditoria do mesmo ciclo durante a redação (Writing)');
  const auditCycle2Passed = makeAuditResponse('aprovado', 12, []);

  const htmlWriting = renderToString(
    React.createElement(ExecutionView, {
      stage: 'writing',
      plan: mockPlan,
      searchResult: null,
      auditResult: auditCycle2Passed,
      cycleNumber: 2,
      maxCycles: 4,
      onReset: () => {},
    })
  );

  assert.ok(
    htmlWriting.includes('Pesquisa aprovada, Redator está gerando o relatório final'),
    'Timeline deve anunciar a redação após aprovação'
  );
  assert.ok(
    !htmlWriting.includes('audit-breakdown'),
    'Breakdown aninhado não deve mais existir'
  );

  // =========================================================================
  // 3. Unknown / Legacy Audit Cycle (Never fabricate cycleNumber - 1)
  // =========================================================================
  console.log('[Teste 3] Ciclo de auditoria desconhecido/legado (fallback seguro)');
  const htmlUnknownCycle = renderToString(
    React.createElement(ExecutionView, {
      stage: 'searching',
      plan: mockPlan,
      searchResult: null,
      auditResult: auditCycle1, // legado sem captura
      cycleNumber: 3,
      maxCycles: 4,
      onReset: () => {},
    })
  );

  assert.ok(
    htmlUnknownCycle.includes('tl-linear'),
    'Timeline deve renderizar mesmo sem ciclo capturado'
  );
  assert.ok(
    !htmlUnknownCycle.includes('Auditoria do ciclo 2 —'),
    'NUNCA deve assumir cegamente cycleNumber - 1'
  );

  // =========================================================================
  // 4. Failed Search Tracker: Must NOT show done when failedStage === 'searching'
  // =========================================================================
  console.log('[Teste 4] Tracker de busca em falha no estágio searching');
  const htmlFailedSearch = renderToString(
    React.createElement(ExecutionView, {
      stage: 'failed',
      failedStage: 'searching',
      errorMessage: 'Falha HTTP 504 no Jina Web Reader',
      plan: mockPlan,
      searchResult: null,
      auditResult: null,
      cycleNumber: 1,
      maxCycles: 4,
      onReset: () => {},
    })
  );

  assert.ok(
    htmlFailedSearch.includes('stage-line-item falhou') && htmlFailedSearch.includes('Busca com personas'),
    'Busca deve estar marcada como falha na linha de estágios'
  );

  // =========================================================================
  // 5. P1 Structured Criteria & Preserved Full Technical Details
  // =========================================================================
  console.log('[Teste 5] Diagnóstico estruturado canônico e detalhes técnicos preservados');
  const htmlDiagnostics = renderToString(
    React.createElement(ExecutionView, {
      stage: 'auditing',
      plan: mockPlan,
      searchResult: null,
      auditResult: auditCycle1,
      cycleNumber: 1,
      maxCycles: 4,
      onReset: () => {},
    })
  );

  // Critérios reprovados aparecem como linhas na timeline, sem cards aninhados
  assert.ok(
    htmlDiagnostics.includes('tl-criterio'),
    'Timeline deve listar critérios reprovados como linhas'
  );
  assert.ok(
    !htmlDiagnostics.includes('failed-criterion-card'),
    'Cards aninhados de critério não devem mais existir'
  );
  assert.ok(
    !htmlDiagnostics.includes('audit-item-box'),
    'Caixas de ponto aninhadas não devem mais existir'
  );

  // =========================================================================
  // 6. WCAG: Narrow aria-live (No full-card live region)
  // =========================================================================
  console.log('[Teste 6] Acessibilidade: aria-live restrito a status sucinto');
  assert.ok(
    !htmlDiagnostics.includes('<article class="execution-card" aria-live='),
    'Card article principal NÃO deve ter aria-live'
  );
  assert.ok(
    htmlDiagnostics.includes('class="sr-only" aria-live="polite" aria-atomic="true"'),
    'Deve conter região sr-only com aria-live="polite" atômica'
  );

  // =========================================================================
  // 7. Research Theme & Non-Technical Title
  // =========================================================================
  console.log('[Teste 7] Tema da pesquisa visível e título em linguagem de produto');
  assert.ok(
    htmlDiagnostics.includes('execution-theme-inline'),
    'Deve exibir o tema inline no cabeçalho'
  );
  assert.ok(
    htmlDiagnostics.includes('Impacto dos Modelos de Raciocínio na Arquitetura de Software'),
    'Deve exibir o tema real do plano'
  );
  assert.ok(
    htmlDiagnostics.includes('Investigação em andamento'),
    'Título do card deve ser "Investigação em andamento"'
  );
  assert.ok(
    !htmlDiagnostics.includes('Execução Síncrona da Investigação'),
    'NÃO deve conter o título técnico "Execução Síncrona da Investigação"'
  );

  // =========================================================================
  // 8. Singular / Plural Counts in Sidebar & ExecutionView
  // =========================================================================
  console.log('[Teste 8] Concordância gramatical singular ("1 ponto")');
  const htmlSidebarSingular = renderToString(
    React.createElement(ContextSidebar, {
      plan: mockPlan,
      pipelineStatus: 'auditing',
    })
  );
  assert.ok(
    htmlSidebarSingular.includes('1 ponto'),
    'ContextSidebar com 1 ponto deve exibir "1 ponto" e não "1 pontos"'
  );
  assert.ok(
    htmlSidebarSingular.includes('status-badge-chip auditando'),
    'ContextSidebar deve usar a classe "auditando" para o estágio auditing'
  );

  const mockPlanPlural: PlanResponse = {
    ...mockPlan,
    n_pontos: 3,
  };
  const htmlSidebarPlural = renderToString(
    React.createElement(ContextSidebar, {
      plan: mockPlanPlural,
      pipelineStatus: 'writing',
    })
  );
  assert.ok(
    htmlSidebarPlural.includes('3 pontos'),
    'ContextSidebar com 3 pontos deve exibir "3 pontos"'
  );
  assert.ok(
    htmlSidebarPlural.includes('status-badge-chip redigindo'),
    'ContextSidebar deve usar a classe "redigindo" para o estágio writing'
  );

  assert.ok(
    htmlCycle2.includes('0/1') || htmlCycle2.includes('pontos aprovados'),
    'Execução singular de contagem de auditoria'
  );

  // =========================================================================
  // 9. Pure Helper Unit Logic Checks
  // =========================================================================
  console.log('[Teste 9] Lógica determinística dos helpers puros');
  assert.equal(getCycleBadgeClass('searching'), 'buscando');
  assert.equal(getCycleBadgeClass('auditing'), 'auditando');
  assert.equal(getCycleBadgeClass('writing'), 'redigindo');
  assert.equal(getCycleBadgeClass('completed'), 'concluido');
  assert.equal(getCycleBadgeClass('rejected'), 'reprovado');
  assert.equal(getCycleBadgeClass('failed'), 'reprovado');

  const priorLabel = getAuditContextualLabel('searching', 2, 1);
  assert.equal(priorLabel.isPriorCycle, true);
  assert.equal(priorLabel.heading, 'Auditoria do ciclo 1 — revisão em andamento no ciclo 2');

  const sameLabel = getAuditContextualLabel('writing', 2, 2);
  assert.equal(sameLabel.isPriorCycle, false);
  assert.equal(sameLabel.heading, 'Auditoria do ciclo 2 (Aprovada)');

  const unknownLabel = getAuditContextualLabel('searching', 2, null);
  assert.equal(unknownLabel.heading, 'Última auditoria disponível');

  const statusSearching = getSuccinctStatus('searching', 2, 4);
  assert.ok(statusSearching.includes('Ciclo 2 de 4: Coleta e varredura web'));

  console.log('\n--- TODOS OS 9 TESTES DE REGRESSÃO PASSARAM COM SUCESSO! ---');
}

runExecutionViewRegressionTests().catch((err) => {
  console.error('\n❌ Falha nos testes de regressão:', err);
  process.exit(1);
});
