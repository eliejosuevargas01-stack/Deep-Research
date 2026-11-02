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
import type { SearchResponse } from '../types/api.js';

const { derivarFontesParaExplorer } = await import('../components/SourcesExplorer.js');

const search: SearchResponse = {
  id_pesquisa: 'abc',
  total_pontos_processados: 1,
  status_pesquisa: 'ok',
  total_falhas_coleta: 0,
  resumo_coletas: [{
    ponto_id: 'p1', ponto_n: 1, status: 'coletado', falha_coleta: false,
    total_urls_lidas: 3, total_urls_fonte: 3, tamanho_conteudo_caracteres: 100,
    tentativas: 1,
    personas: [
      { persona: 'historiador', analise: 'a', urls_fonte: ['https://example.com/a', 'ftp://inseguro-test.invalid/x'], queries_executadas: 1, falha_coleta: false },
      { persona: 'cetico', analise: 'b', urls_fonte: ['https://example.com/a', 'javascript:alert(1)'], queries_executadas: 1, falha_coleta: false },
    ],
  }],
};

const itens = derivarFontesParaExplorer(search, { emColeta: true });
assert.equal(itens.length, 1, 'dedupe por URL, descarta non-http(s)');
assert.equal(itens[0].url, 'https://example.com/a');
assert.equal(itens[0].status, 'lendo');
assert.equal(itens[0].ponto_n, 1);

const itens2 = derivarFontesParaExplorer(search, { emColeta: false });
assert.equal(itens2[0].status, 'utilizada');

import React from 'react';
import { renderToString } from 'react-dom/server';
const { ContextSidebar } = await import('../components/ContextSidebar.js');
const html = renderToString(
  React.createElement(ContextSidebar, {
    plan: { id_pesquisa: '773ceba0-0000-0000-0000-000000000000', tema: 't', n_pontos: 1, criado_em: new Date().toISOString(), pontos: [], metadados_modelo: { usage_total: { prompt_tokens: 1000, completion_tokens: 500, total_tokens: 1500 } } } as any,
    metadadosModelo: { usage_total: { prompt_tokens: 1000, completion_tokens: 500, total_tokens: 1500 } } as any,
    fontes: [{ url: 'https://example.com/a', titulo: 'Artigo A', dominio: 'example.com', status: 'utilizada', ponto_n: 1 }],
  })
);
assert.ok(html.includes('tokens'), 'rail exibe medidor de tokens');
/* Contrato r3 (DESIGN.md §7): painel único com abas, contagem na aba
   "Fontes" e lista de fontes com favicon/título/domínio/estado. */
assert.ok(html.includes('Contexto') && html.includes('Fontes'), 'rail tem as duas abas');
assert.ok(/rr-rail__tab-count">1</.test(html), 'contagem de fontes = 1 na aba');
assert.ok(html.includes('aria-label="Fontes exploradas"'), 'lista de fontes mantém o rótulo acessível');
assert.ok(html.includes('example.com'), 'chip referencia o domínio da fonte');
assert.ok(html.includes('Artigo A'), 'chip exibe o título truncado');

console.log('T1 ok');
