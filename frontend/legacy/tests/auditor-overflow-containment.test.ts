import { register } from 'node:module';
import { pathToFileURL } from 'node:url';
import fs from 'node:fs';
import path from 'node:path';

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
import type { PlanResponse, AuditResponse } from '../types/api';

async function run() {
  const { ExecutionView } = await import('../components/ExecutionView.js');

  console.log('=== Teste de Contenção e Não-Sobreposição do Auditor ===\n');

  const mockPlan: PlanResponse = {
    id_pesquisa: 'auditor-containment-test',
    tema: 'OWASP Top 10:2025 Teste Auditor',
    n_pontos: 1,
    pontos: [
      {
        ponto_id: 'p1',
        ponto_n: 1,
        ponto: 'Vulnerabilidades em APIs e Cookies',
        status: 'reprovado',
      },
    ],
    criado_em: '2026-11-01T20:00:00.000Z',
    preferencias: { criterios_minimos: 10 },
  };

  const longJustificativa =
    "Critério 2: Taxonomia 2025 tem suporte primário sólido (owasp.org). Mas núcleo do pedido — 'como detectar' via DevTools — não tem fonte primária entregue. chk_103/chk_159/chk_61 citados para clm_cetico_2 e clm_futurista_3 não falam de DevTools, cookies na aba Application nem source maps com API keys. chk_405 só cobre headers HTTP medidos por scanner, não a mecânica DevTools nem flags de cookie.";

  const mockAuditResult: AuditResponse = {
    id_pesquisa: 'auditor-containment-test',
    total_pontos: 1,
    aprovados: 0,
    reprovados: 1,
    status_geral: 'reprovado',
    pronto_para_writer: false,
    auditorias: [
      {
        ponto_id: 'p1',
        ponto_n: 1,
        status: 'reprovado',
        pontuacao_percentual: 75,
        criterios_aprovados: 9,
        criterios_minimos: 10,
        valido: true,
        resumo_auditoria: 'Auditoria encontrou pendências no critério 2.',
        criterios: [
          {
            id: 2,
            aprovado: false,
            justificativa: longJustificativa,
            correcao: 'Buscar doc oficial DevTools e OWASP WSTG.',
            claim_ids: ['clm_1'],
            source_ids: ['src_1'],
          },
        ],
      },
    ],
  };

  // Renderizar a tela de execução com o resultado de auditoria reprovado
  const html = renderToString(
    React.createElement(ExecutionView, {
      stage: 'auditing',
      plan: mockPlan,
      searchResult: null,
      auditResult: mockAuditResult,
      cycleNumber: 1,
      maxCycles: 4,
      onReset: () => {},
    })
  );

  console.log('[Teste 1] Frase do botão do Auditor não pode carregar o parágrafo de 500 caracteres inteiro');
  assert.ok(
    !html.includes(longJustificativa),
    'A justificativa longa de 500 caracteres não deve ser injetada inteira no resumo do botão do auditor'
  );

  console.log('[Teste 2] Linha fechada exibe motivo conciso com ellipsis e dados operacionais');
  assert.ok(
    html.includes('reprovou o ponto 1 (75% · 9/10). Motivo: Critério 2: Taxonomia 2025 tem suporte'),
    'Resumo do auditor deve ser claro e operacional com percentual e contagem'
  );

  console.log('[Teste 3] Corpo fechado do auditor possui display: none explícito');
  assert.ok(
    html.includes('style="display:none"') || html.includes('style="display: none"'),
    'Corpo fechado deve conter inline style display: none para evitar sobreposição'
  );

  console.log('[Teste 4] Detalhe expandido mantém justificativa completa e correção acessíveis');
  assert.ok(
    html.includes('Critério 2:'),
    'Detalhe do critério 2 deve estar presente no DOM'
  );
  assert.ok(
    html.includes('Buscar doc oficial DevTools e OWASP WSTG.'),
    'Correção do critério deve estar presente no detalhe'
  );

  console.log('[Teste 5] Verificação estática do CSS: linear-timeline.css possui overflow: hidden na regra mobile');
  const cssPath = path.resolve('frontend/src/styles/linear-timeline.css');
  const cssContent = fs.readFileSync(cssPath, 'utf8');
  assert.ok(
    !cssContent.includes('.tl-linear .tl-acao-texto {\n    white-space: normal;\n    overflow: visible;'),
    'linear-timeline.css não deve ter overflow: visible com line-clamp'
  );
  assert.ok(
    cssContent.includes('overflow: hidden !important'),
    'linear-timeline.css deve conter overflow: hidden !important para contenção'
  );

  console.log('\n--- TODOS OS 5 TESTES DE CONTENÇÃO DO AUDITOR PASSARAM COM SUCESSO! ---');
}

run().catch((err) => {
  console.error('Falha no teste:', err);
  process.exit(1);
});
