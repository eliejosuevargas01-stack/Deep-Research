/**
 * Testes focados de regressão para os componentes isolados das Ondas 3 e 4:
 * B-04, B-10 (SourcesExplorer), B-03 (ContextSidebar), B-17 (ReportView).
 */

import { register } from 'node:module';
import { pathToFileURL } from 'node:url';

// Registra hook para ignorar imports de CSS durante execução de testes SSR no Node
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
import { FontesResumo, SearchResponse } from '../types/api';

async function runTests() {
  const {
    derivarFontesParaExplorer,
    converterFontesResumoParaExplorer,
  } = await import('../components/SourcesExplorer');
  const { ContextSidebar } = await import('../components/ContextSidebar');
  const { verifySourcesBinding } = await import('../components/ReportView');

  console.log('=== Iniciando Testes Unitários Ondas 3 e 4 (B-03, B-04, B-10, B-17) ===\n');

  // ---------------------------------------------------------------------------
  // 1. B-10: Preservação de URL original com deduplicação normalizada
  // ---------------------------------------------------------------------------
  console.log('[Teste 1] B-10: Preservação da URL original intacta no href (deduplicação via Set normalizado)');

  const mockSearch: SearchResponse = {
    id_pesquisa: 'p-1',
    total_pontos_processados: 1,
    status_pesquisa: 'concluido',
    total_falhas_coleta: 0,
    resumo_coletas: [
      {
        ponto_id: 'p1',
        ponto_n: 1,
        status: 'concluido',
        falha_coleta: false,
        total_urls_lidas: 2,
        total_urls_fonte: 3,
        tamanho_conteudo_caracteres: 1000,
        tentativas: 1,
        personas: [
          {
            persona: 'historiador',
            analise: 'Análise teste',
            queries_executadas: 1,
            falha_coleta: false,
            urls_fonte: [
              'http://exemplo-http.com/artigo?foo=bar',
              'https://exemplo-http.com/artigo?foo=bar', // duplicata com esquema diferente
              'http://outro-site.org/docs',
            ],
          },
        ],
      },
    ],
  };

  const itensDerivados = derivarFontesParaExplorer(mockSearch);
  assert.equal(itensDerivados.length, 2, 'Deve deduplicar http e https equivalentes');
  // O primeiro item adicionado foi com http://
  assert.equal(
    itensDerivados[0].url,
    'http://exemplo-http.com/artigo?foo=bar',
    'B-10: item.url deve preservar a URL original com protocolo http intacto'
  );
  assert.equal(
    itensDerivados[1].url,
    'http://outro-site.org/docs',
    'B-10: segunda URL deve manter o protocolo original'
  );

  // ---------------------------------------------------------------------------
  // 2. B-04: leituras de apoio (nao_utilizadas) não podem ser marcadas como erro
  // ---------------------------------------------------------------------------
  console.log('[Teste 2] B-04: Classificação por uso real (utilizada/lida_nao_utilizada)');

  const mockResumo: FontesResumo = {
    id_pesquisa: 'test-pesquisa-123',
    status: 'completo',
    total_consultadas: 2,
    total_utilizadas: 1,
    total_nao_utilizadas: 1,
    utilizadas: [
      {
        url: 'http://usada.org/estudo',
        titulo: 'Estudo Principal',
        dominio: 'usada.org',
      },
    ],
    consultadas: [
      {
        url: 'http://apoio.org/referencia',
        titulo: 'Referência de Apoio',
        dominio: 'apoio.org',
      },
    ],
    nao_utilizadas: [
      {
        url: 'http://apoio.org/referencia',
        titulo: 'Referência de Apoio',
        dominio: 'apoio.org',
      },
    ],
  };

  const itensExplorer = converterFontesResumoParaExplorer(mockResumo);


  const itemUsado = itensExplorer.find((i) => i.url === 'http://usada.org/estudo');
  assert.ok(itemUsado);
  assert.equal(itemUsado?.status, 'utilizada');

  const itemApoio = itensExplorer.find((i) => i.url === 'http://apoio.org/referencia');
  assert.ok(itemApoio);
  assert.equal(itemApoio?.status, 'lida_nao_utilizada');
  assert.equal(itemApoio?.url, 'http://apoio.org/referencia', 'B-10: url original preservada');

  // ---------------------------------------------------------------------------
  // 3. B-03: ContextSidebar e SourcesExplorer exibem metadados enriquecidos (ponto_n, status)
  // ---------------------------------------------------------------------------
  console.log('[Teste 3] B-03: ContextSidebar exibe fontes enriquecidas com ponto_n e status');

  const htmlSidebar = renderToString(
    React.createElement(ContextSidebar, {
      fontes: [
        {
          url: 'https://exemplo.com/doc1',
          titulo: 'Doc 1',
          dominio: 'exemplo.com',
          status: 'lendo',
          ponto_n: 1,
        },
        {
          url: 'https://exemplo.com/doc2',
          titulo: 'Doc 2',
          dominio: 'exemplo.com',
          status: 'lida_nao_utilizada',
          ponto_n: 2,
        },
      ],
      initialMode: 'fontes',
      mode: 'fontes',
    })
  );

  assert.ok(htmlSidebar.includes('Ponto 1'), 'Deve renderizar o grupo Ponto 1');
  assert.ok(htmlSidebar.includes('Ponto 2'), 'Deve renderizar o grupo Ponto 2');
  assert.ok(htmlSidebar.includes('is-lendo'), 'Deve exibir badge is-lendo');
  assert.ok(htmlSidebar.includes('is-lida_nao_utilizada'), 'Deve exibir badge is-lida_nao_utilizada');
  assert.ok(htmlSidebar.includes('Lendo'), 'Texto do badge Lendo presente');
  assert.ok(htmlSidebar.includes('Consultada'), 'Texto do badge Consultada presente');

  // ---------------------------------------------------------------------------
  // 4. B-17: verifySourcesBinding sem falso alerta para artifact_hash nulo/vazio
  // ---------------------------------------------------------------------------
  console.log('[Teste 4] B-17: verifySourcesBinding tolera artifact_hash nulo/indefinido sem falso alerta');

  const baseSources: FontesResumo = {
    id_pesquisa: 'pesquisa-b17',
    status: 'completo',
    total_consultadas: 5,
    total_utilizadas: 3,
    total_nao_utilizadas: 2,
    consultadas: [],
    utilizadas: [],
    nao_utilizadas: [],
  };

  // Caso 4.1: artifact_hash nulo
  const resNullHash = verifySourcesBinding(
    'pesquisa-b17',
    'Texto do relatório publicado',
    'localhash123',
    { ...baseSources, artifact_hash: null }
  );
  assert.equal(resNullHash.isValid, true, 'artifact_hash nulo deve ser aprovado sem falso alerta');

  // Caso 4.2: artifact_hash indefinido
  const resUndefHash = verifySourcesBinding(
    'pesquisa-b17',
    'Texto do relatório publicado',
    'localhash123',
    { ...baseSources, artifact_hash: undefined }
  );
  assert.equal(resUndefHash.isValid, true, 'artifact_hash indefinido deve ser aprovado sem falso alerta');

  // Caso 4.3: artifact_hash vazio
  const resEmptyHash = verifySourcesBinding(
    'pesquisa-b17',
    'Texto do relatório publicado',
    'localhash123',
    { ...baseSources, artifact_hash: '   ' }
  );
  assert.equal(resEmptyHash.isValid, true, 'artifact_hash vazio deve ser aprovado sem falso alerta');

  // Caso 4.4: hashes presentes e coincidentes
  const resMatch = verifySourcesBinding(
    'pesquisa-b17',
    'Texto do relatório publicado',
    'HASH-ABC-123',
    { ...baseSources, artifact_hash: 'hash-abc-123' }
  );
  assert.equal(resMatch.isValid, true, 'hashes coincidentes (case-insensitive) devem ser aprovados');

  // Caso 4.5: hashes presentes e diferentes
  const resMismatch = verifySourcesBinding(
    'pesquisa-b17',
    'Texto do relatório publicado',
    'hash-local-novo',
    { ...baseSources, artifact_hash: 'hash-servidor-antigo' }
  );
  assert.equal(resMismatch.isValid, false, 'hashes diferentes devem acusar versão divergente');
  assert.ok(resMismatch.reason?.includes('outra versão deste relatório'));

  console.log('\n--- Todos os testes unitários das Ondas 3 e 4 passaram com sucesso! ---');
}

runTests().catch((err) => {
  console.error('❌ Falha nos testes:', err);
  process.exit(1);
});