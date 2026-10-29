/**
 * Testes Focados de Produção para Remediação de Docs e HistoryView
 * Valida componentes reais de produção via renderToString (SSR) sem simulações espelhadas:
 * 1. HistoryView: concordância gramatical singular ("1 ponto")
 * 2. HistoryView: concordância gramatical plural ("N pontos")
 * 3. DocsView: precedência RN-10 Adendo 002 (Banco Cifrado > Ambiente), CREDENTIALS_MASTER_KEY bootstrap,
 *    subconjunto selecionável de personas no plano, e nova seção de contabilidade de fontes.
 */
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

import assert from 'node:assert/strict';
import React from 'react';
import { renderToString } from 'react-dom/server';
import { ResearchHistoryRecord } from '../types/api';

async function runRemediationTests() {
  console.log('--- Executando Testes de Produção: DocsView e HistoryView SSR ---');

  const { HistoryView } = await import('../components/HistoryView.js');
  const { DocsView } = await import('../components/DocsView.js');

  // =========================================================================
  // 1. HistoryView: Singular "1 ponto" vs Plural "N pontos"
  // =========================================================================
  console.log('\n[Teste 1] HistoryView: Singular 1 ponto');
  const recordSingular: ResearchHistoryRecord = {
    id_pesquisa: 'test-singular-uuid-1',
    tema: 'Investigação Singular de Teste',
    criado_em: '2026-10-26T12:00:00Z',
    status: 'concluido',
    total_pontos: 1,
    writerResponse: {
      id_pesquisa: 'test-singular-uuid-1',
      tema: 'Investigação Singular de Teste',
      status: 'concluido',
      total_caracteres_dossier: 500,
      dossier_final: '# Dossiê 1 Ponto',
    },
  };

  const htmlSingular = renderToString(
    React.createElement(HistoryView, {
      records: [recordSingular],
      onSelectRecord: () => {},
      onDeleteRecord: () => {},
      onClearAll: () => {},
    })
  );

  assert.ok(htmlSingular.includes('1 ponto'), 'Deve exibir "1 ponto" para total_pontos === 1');
  assert.ok(!htmlSingular.includes('1 pontos'), 'NÃO deve exibir "1 pontos" para total_pontos === 1');
  console.log('  ✓ Singular "1 ponto" verificado com sucesso');

  console.log('\n[Teste 2] HistoryView: Plural N pontos');
  const recordPlural: ResearchHistoryRecord = {
    id_pesquisa: 'test-plural-uuid-2',
    tema: 'Investigação Plural de Teste',
    criado_em: '2026-10-26T12:00:00Z',
    status: 'concluido',
    total_pontos: 4,
    writerResponse: {
      id_pesquisa: 'test-plural-uuid-2',
      tema: 'Investigação Plural de Teste',
      status: 'concluido',
      total_caracteres_dossier: 2000,
      dossier_final: '# Dossiê 4 Pontos',
    },
  };

  const htmlPlural = renderToString(
    React.createElement(HistoryView, {
      records: [recordPlural],
      onSelectRecord: () => {},
      onDeleteRecord: () => {},
      onClearAll: () => {},
    })
  );

  assert.ok(htmlPlural.includes('4 pontos'), 'Deve exibir "4 pontos" para total_pontos === 4');
  console.log('  ✓ Plural "4 pontos" verificado com sucesso');

  // =========================================================================
  // 2. DocsView: RN-10 Adendo 002, CREDENTIALS_MASTER_KEY e Categorias de Fontes
  // =========================================================================
  console.log('\n[Teste 3] DocsView: RN-10 Adendo 002 (Banco Cifrado > Ambiente) e Bootstrap');
  const htmlDocs = renderToString(React.createElement(DocsView));

  // Precedência RN-10
  assert.ok(
    htmlDocs.includes('Banco de Dados Relacional Cifrado (tabela <code>credenciais</code>) possui prioridade primária sobre as variáveis de ambiente'),
    'DocsView Seção 5 deve documentar precedência estrita do Banco Cifrado sobre variáveis de ambiente'
  );
  assert.ok(
    !htmlDocs.includes('Variáveis de ambiente definidas no servidor (.env ou host) possuem precedência absoluta sobre o banco cifrado'),
    'DocsView NÃO deve conter a regra legada invertida contraditória'
  );

  // Chave de bootstrap
  assert.ok(
    htmlDocs.includes('CREDENTIALS_MASTER_KEY') && htmlDocs.includes('obrigatoriamente restrita ao ambiente do sistema operacional'),
    'DocsView Seção 5 deve documentar que CREDENTIALS_MASTER_KEY é restrita ao ambiente'
  );

  // Personas selecionáveis
  assert.ok(
    htmlDocs.includes('subconjunto selecionável de até 4 personas analíticas') ||
      htmlDocs.includes('subconjunto selecionável de até quatro personas analíticas'),
    'DocsView deve clarificar que as 4 personas são um subconjunto selecionável capturado no plano'
  );

  // Nova seção de fontes públicas
  assert.ok(
    htmlDocs.includes('Contabilidade e Categorias de Fontes'),
    'DocsView deve conter o título da seção de contabilidade e categorias de fontes'
  );
  assert.ok(
    htmlDocs.includes('status <code>read_ok</code>'),
    'DocsView deve definir fontes consultadas com base em leitura confirmada / read_ok'
  );
  assert.ok(
    htmlDocs.includes('explicitamente citadas no dossiê final publicado'),
    'DocsView deve definir fontes utilizadas como citadas no dossiê'
  );
  assert.ok(
    htmlDocs.includes('consultadas - utilizadas'),
    'DocsView deve definir fontes não utilizadas como consultadas menos utilizadas'
  );
  assert.ok(
    htmlDocs.includes('nunca apresentando zero (<code>0</code>) fictício'),
    'DocsView deve esclarecer que contabilidade desconhecida não é apresentada como zero'
  );
  assert.ok(
    htmlDocs.includes('Carregar fontes não executa novamente a pesquisa nem gera novos custos'),
    'DocsView deve orientar que o carregamento de fontes não reprocessa a pesquisa'
  );
  console.log('  ✓ Conteúdo normativo do DocsView verificado integralmente');

  console.log('\n--- Todos os 3 testes de renderização de componentes reais passaram com sucesso! ---');
}

runRemediationTests().catch((err) => {
  console.error('Falha nos testes de remediação:', err);
  process.exit(1);
});
