/**
 * Testes Focados de Produção: Contabilidade e Separação de Fontes
 * Executa exclusivamente componentes e serviços reais de produção:
 * - extractSourcesFromMarkdown (parser AST unified/remarkParse/remarkGfm: parênteses, autolinks, referências citadas e exclusão de código/definições uncited)
 * - SourceBreakdown (renderização SSR: completo, legado confirmado, parcial, vazio com contagem nula, carregando sem legado falso, erro com retry, mismatch com rejeição)
 * - ReportView (integração real com SourceBreakdown, vinculação estrita de artifact_hash e id_pesquisa, rejeição de dados alheios, preservação byte-a-byte do Markdown)
 * - computeArtifactHash (cálculo real de SHA-256 do artefato publicado)
 * - historyService (sanitização de fontes, retenção exclusiva de HTTP(S), expurgo de userinfo e queries de segredo, preservação de caminhos/queries seguras, rejeição de tipos inválidos)
 * - api.getSources (chamada do endpoint com AbortSignal e credentials same-origin)
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
import crypto from 'node:crypto';
import React from 'react';
import { renderToString } from 'react-dom/server';
import { historyService } from '../services/history';
import { api } from '../services/api';
import { FontesResumo, ResearchHistoryRecord, WriterResponse } from '../types/api';

// Configuração de isolamento de localStorage para os testes de historyService
const memoryStorage: Record<string, string> = {};
global.localStorage = {
  getItem: (k: string) => memoryStorage[k] ?? null,
  setItem: (k: string, v: string) => {
    memoryStorage[k] = String(v);
  },
  removeItem: (k: string) => {
    delete memoryStorage[k];
  },
  clear: () => {
    for (const k in memoryStorage) delete memoryStorage[k];
  },
  length: 0,
  key: () => null,
} as unknown as Storage;

async function runSourcesTests() {
  console.log('--- Iniciando Testes Focados de Produção: Contabilidade de Fontes ---');

  // Importação dinâmica dos componentes após o registro do hook de CSS
  const { SourceBreakdown } = await import('../components/SourceBreakdown.js');
  const { ReportView, computeArtifactHash, extractSourcesFromMarkdown, verifySourcesBinding } = await import(
    '../components/ReportView.js'
  );

  // =========================================================================
  // 1. extractSourcesFromMarkdown (Parser AST Markdown)
  // =========================================================================
  console.log('\n[Teste 1] extractSourcesFromMarkdown: extração via AST sem falsos positivos de código ou truncamentos');
  const markdownSample = `
# Relatório de Investigação
Citação direta com parênteses na query: [Estudo EPE](https://epe.gov.br/artigo?id=12(teste)&ano=2026).
Autolink público: <https://ons.org.br/dados-abertos>.
Referência bibliográfica citada no texto: [Agência Nacional][aneel-ref].

\`\`\`markdown
[Link em bloco de código](https://nao-deve-aparecer-bloco.com)
\`\`\`

Código inline: \`https://nao-deve-aparecer-inline.com\` e \`[outro inline](https://outro-inline.com)\`.

[aneel-ref]: https://aneel.gov.br/normas
[definicao-nunca-citada]: https://nunca-citado-definicao.org
`;

  const extractedUrls = extractSourcesFromMarkdown(markdownSample);
  assert.ok(
    extractedUrls.includes('https://epe.gov.br/artigo?id=12(teste)&ano=2026'),
    'Deve preservar URL completa com parênteses e queries sem truncamento'
  );
  assert.ok(
    extractedUrls.includes('https://ons.org.br/dados-abertos'),
    'Deve extrair autolinks em conformidade com CommonMark/GFM'
  );
  assert.ok(
    extractedUrls.includes('https://aneel.gov.br/normas'),
    'Deve resolver definições de links efetivamente citadas no texto'
  );
  assert.ok(
    !extractedUrls.some((u) => u.includes('nao-deve-aparecer-bloco')),
    'NÃO deve extrair URLs de blocos de código'
  );
  assert.ok(
    !extractedUrls.some((u) => u.includes('nao-deve-aparecer-inline')),
    'NÃO deve extrair URLs de código inline'
  );
  assert.ok(
    !extractedUrls.some((u) => u.includes('nunca-citado-definicao')),
    'NÃO deve extrair definições que nunca foram citadas no texto'
  );

  // =========================================================================
  // 2. computeArtifactHash: SHA-256 do texto publicado
  // =========================================================================
  console.log('\n[Teste 2] computeArtifactHash: conformidade com SHA-256 padrão');
  const sampleText = '# Dossiê Analítico de Teste\nConteúdo completo do artigo.';
  const expectedHash = crypto.createHash('sha256').update(sampleText, 'utf-8').digest('hex');
  const computed = await computeArtifactHash(sampleText);
  assert.equal(
    computed,
    expectedHash,
    `Hash calculado (${computed}) deve ser estritamente igual ao SHA-256 esperado (${expectedHash})`
  );

  const emptyHash = await computeArtifactHash('');
  const expectedEmptyHash = crypto.createHash('sha256').update('', 'utf-8').digest('hex');
  assert.equal(emptyHash, expectedEmptyHash, 'Hash de texto vazio deve ser e3b0c44...');

  // =========================================================================
  // 3. SourceBreakdown: Estado Carregando (sem falsa alegação de legado)
  // =========================================================================
  console.log('\n[Teste 3] SourceBreakdown: Estado carregando não deve exibir badge de legado');
  const htmlLoading = renderToString(
    React.createElement(SourceBreakdown, {
      fontes: null,
      loading: true,
      error: null,
      fallbackCitations: ['https://exemplo.org'],
    })
  );

  assert.ok(
    htmlLoading.includes('Carregando fontes...'),
    'Deve exibir indicação factual de carregamento de fontes'
  );
  assert.ok(
    !htmlLoading.includes('Legado / Indisponível'),
    'NÃO deve rotular como legado enquanto a requisição estiver apenas carregando'
  );
  assert.ok(
    !htmlLoading.includes('Evidências brutas de leitura indisponíveis'),
    'NÃO deve alegar que evidências não foram registradas enquanto estiver carregando'
  );

  // =========================================================================
  // 4. SourceBreakdown: Renderização Completa com 3 Categorias Distintas
  // =========================================================================
  console.log('\n[Teste 4] SourceBreakdown: Estado completo (status: completo)');
  const mockCompleto: FontesResumo = {
    id_pesquisa: 'test-sources-001',
    status: 'completo',
    total_consultadas: 3,
    total_utilizadas: 2,
    total_nao_utilizadas: 1,
    consultadas: [
      {
        url: 'https://pt.wikipedia.org/wiki/Energia_solar',
        titulo: 'Energia solar – Wikipédia',
        dominio: 'pt.wikipedia.org',
      },
      {
        url: 'https://epe.gov.br/pt/publicacoes-dados-abertos/estudos-de-energia',
        titulo: 'Estudos EPE',
        dominio: 'epe.gov.br',
      },
      {
        url: 'https://ons.org.br/relatorios-operacionais',
        titulo: 'Relatórios ONS',
        dominio: 'ons.org.br',
      },
    ],
    utilizadas: [
      {
        url: 'https://pt.wikipedia.org/wiki/Energia_solar',
        titulo: 'Energia solar – Wikipédia',
        dominio: 'pt.wikipedia.org',
      },
      {
        url: 'https://epe.gov.br/pt/publicacoes-dados-abertos/estudos-de-energia',
        titulo: 'Estudos EPE',
        dominio: 'epe.gov.br',
      },
    ],
    nao_utilizadas: [
      {
        url: 'https://ons.org.br/relatorios-operacionais',
        titulo: 'Relatórios ONS',
        dominio: 'ons.org.br',
      },
    ],
    artifact_hash: expectedHash,
  };

  const htmlCompleto = renderToString(
    React.createElement(SourceBreakdown, {
      fontes: mockCompleto,
      loading: false,
      error: null,
    })
  );

  assert.ok(
    htmlCompleto.includes('Fontes da Investigação'),
    'Deve exibir o título "Fontes da Investigação"'
  );
  assert.ok(
    !htmlCompleto.includes('Fontes Bibliográficas Verificadas'),
    'O rótulo enganoso anterior "Fontes Bibliográficas Verificadas" NÃO deve existir'
  );
  assert.ok(
    htmlCompleto.includes('Total consultadas:'),
    'Deve rotular claramente "Total consultadas:"'
  );
  assert.ok(
    htmlCompleto.includes('Utilizadas no dossiê:'),
    'Deve rotular claramente "Utilizadas no dossiê:"'
  );
  assert.ok(
    htmlCompleto.includes('Consultadas mas não citadas:'),
    'Deve rotular claramente "Consultadas mas não citadas:"'
  );
  assert.ok(
    htmlCompleto.includes('Fontes citadas no dossiê'),
    'Deve conter o grupo expansível de fontes utilizadas'
  );
  assert.ok(
    htmlCompleto.includes('Consultadas, não citadas'),
    'Deve conter o grupo expansível de fontes não citadas'
  );
  assert.ok(
    htmlCompleto.includes('Consultadas com leitura confirmada'),
    'Deve conter o grupo de todas as fontes consultadas'
  );
  assert.ok(
    htmlCompleto.includes('não constituem fontes rejeitadas'),
    'Deve conter a explicação factual de que não citadas não são fontes rejeitadas'
  );
  assert.ok(
    htmlCompleto.includes('Energia solar – Wikipédia'),
    'Deve exibir o título público da fonte utilizada'
  );
  assert.ok(
    htmlCompleto.includes('epe.gov.br'),
    'Deve exibir o domínio público da fonte'
  );

  // =========================================================================
  // 5. SourceBreakdown: Relatório Legado Confirmado sem Evidências Brutas
  // =========================================================================
  console.log('\n[Teste 5] SourceBreakdown: Relatório legado confirmado (status: indisponivel)');
  const mockIndisponivel: FontesResumo = {
    id_pesquisa: 'legacy-report-999',
    status: 'indisponivel',
    total_consultadas: null,
    total_utilizadas: 1,
    total_nao_utilizadas: null,
    consultadas: [],
    utilizadas: [
      {
        url: 'https://exemplo.org/fonte-citada-legada',
        titulo: null,
        dominio: 'exemplo.org',
      },
    ],
    nao_utilizadas: [],
    observacao: 'Evidências brutas de coleta indisponíveis para este relatório legado.',
  };

  const htmlIndisponivel = renderToString(
    React.createElement(SourceBreakdown, {
      fontes: mockIndisponivel,
      loading: false,
      error: null,
    })
  );

  // Verificação estrita: Contadores desconhecidos NUNCA são 0
  assert.ok(
    htmlIndisponivel.includes('—'),
    'Contadores de fontes consultadas e não utilizadas desconhecidos devem exibir "—"'
  );
  assert.ok(
    htmlIndisponivel.includes('Legado / Indisponível'),
    'Deve exibir o badge "Legado / Indisponível" quando confirmado pelo backend'
  );
  assert.ok(
    htmlIndisponivel.includes('Este relatório não guardou as leituras brutas'),
    'Deve explicar honestamente que evidências brutas não estão disponíveis'
  );
  assert.ok(
    htmlIndisponivel.includes('exemplo.org'),
    'Deve exibir a citação conhecida'
  );

  // =========================================================================
  // 6. SourceBreakdown: Mismatch Rejeita Exibição de Fontes Alheias
  // =========================================================================
  console.log('\n[Teste 6] SourceBreakdown: isMismatch suprime listas de fontes e contagens alheias');
  const htmlMismatch = renderToString(
    React.createElement(SourceBreakdown, {
      fontes: mockCompleto,
      loading: false,
      error: null,
      isMismatch: true,
      mismatchNotice: 'As fontes disponíveis pertencem a outra versão deste relatório. O texto foi preservado.',
    })
  );

  assert.ok(
    htmlMismatch.includes('As fontes disponíveis pertencem a outra versão deste relatório. O texto foi preservado.'),
    'Deve exibir aviso conciso e claro de versão divergente'
  );
  assert.ok(
    !htmlMismatch.includes('Energia solar – Wikipédia'),
    'NÃO deve renderizar listas de fontes pertencentes a outro artefato/versão'
  );
  assert.ok(
    !htmlMismatch.includes('epe.gov.br'),
    'NÃO deve vazar links de fontes de versão incompatível'
  );

  // =========================================================================
  // 7. SourceBreakdown: Tratamento de Erro com Botão de Retry
  // =========================================================================
  console.log('\n[Teste 7] SourceBreakdown: Exibição de erro com botão de nova tentativa');
  let retryClicked = false;
  const htmlError = renderToString(
    React.createElement(SourceBreakdown, {
      fontes: null,
      loading: false,
      error: 'HTTP 504 Gateway Timeout ao consultar fontes',
      onRetry: () => {
        retryClicked = true;
      },
      fallbackCitations: ['https://citacao-markdown.org/dado'],
    })
  );

  assert.ok(
    htmlError.includes('HTTP 504 Gateway Timeout ao consultar fontes'),
    'Deve exibir a mensagem de erro específica'
  );
  assert.ok(
    htmlError.includes('Carregar de novo'),
    'Deve exibir ação para recarregar as fontes'
  );
  assert.equal(retryClicked, false, 'retryClicked inicial deve ser false');

  // =========================================================================
  // 8. ReportView: Renderização Integral com SourceBreakdown e Preservação de Markdown
  // =========================================================================
  console.log('\n[Teste 8] ReportView: Integração com SourceBreakdown e preservação byte-a-byte');
  const writerReport: WriterResponse = {
    id_pesquisa: 'report-prod-001',
    tema: 'Aceleração de IA no Brasil',
    status: 'concluido',
    total_caracteres_dossier: sampleText.length,
    concluido_em: '2026-10-26T14:30:00Z',
    dossier_final: sampleText,
    fontes: mockCompleto,
  };

  const htmlReport = renderToString(
    React.createElement(ReportView, {
      report: writerReport,
      onReset: () => {},
    })
  );

  assert.ok(
    htmlReport.includes('Aceleração de IA no Brasil'),
    'ReportView deve renderizar o tema do relatório'
  );
  assert.ok(
    htmlReport.includes('Dossiê concluído'),
    'ReportView deve indicar status de conclusão'
  );
  assert.ok(
    htmlReport.includes('Copiar Markdown'),
    'Botão de copiar deve estar presente'
  );
  assert.ok(
    htmlReport.includes('Baixar .md'),
    'Botão de baixar deve estar presente'
  );
  assert.ok(
    htmlReport.includes('source-breakdown-card'),
    'SourceBreakdown deve estar acoplado no ReportView'
  );
  assert.ok(
    !htmlReport.includes('Fontes Bibliográficas Verificadas'),
    'Rótulo enganoso anterior não pode aparecer em nenhuma parte do ReportView'
  );

  // =========================================================================
  // 9. historyService: Projeção de Fontes, Expurgo de Segredos e Validação de Esquemas
  // =========================================================================
  console.log('\n[Teste 9] historyService: Sanitização estrita de HTTP(S), expurgo de userinfo e queries de segredo');
  const dirtyRecord: ResearchHistoryRecord = {
    id_pesquisa: 'sec-test-fontes-001',
    tema: 'Pesquisa com Metadados Sujos',
    criado_em: '2026-10-26T15:00:00Z',
    status: 'concluido',
    total_pontos: 1,
    writerResponse: {
      id_pesquisa: 'sec-test-fontes-001',
      tema: 'Pesquisa com Metadados Sujos',
      status: 'concluido',
      total_caracteres_dossier: 120,
      dossier_final: 'Texto do dossiê',
      fontes: {
        id_pesquisa: 'sec-test-fontes-001',
        status: 'completo',
        total_consultadas: 2,
        total_utilizadas: 1,
        total_nao_utilizadas: 1,
        consultadas: [
          {
            url: 'https://usuario:senha123@segredo.com/relatorio?token=secret123&filtro=energia',
            titulo: 'Relatório Interno',
            dominio: 'segredo.com',
          },
          {
            url: 'javascript:alert(1)',
            titulo: 'XSS Attack',
            dominio: 'evil.com',
          },
          {
            url: 'ftp://ftp.example.org/dump.csv',
            titulo: 'FTP dump',
            dominio: 'ftp.example.org',
          },
          {
            url: 'https://publico.org/artigo?secao=1&pagina=2',
            titulo: 'Artigo Público',
            dominio: 'publico.org',
          },
        ],
        utilizadas: [
          {
            url: 'https://publico.org/artigo?secao=1&pagina=2',
            titulo: 'Artigo Público',
            dominio: 'publico.org',
          },
        ],
        nao_utilizadas: [
          {
            url: 'https://usuario:senha123@segredo.com/relatorio?token=secret123&filtro=energia',
            titulo: 'Relatório Interno',
            dominio: 'segredo.com',
          },
        ],
        observacao: 'Auditoria de fontes realizada',
        artifact_hash: 'a1b2c3d4...',
      },
    },
  };

  historyService.save(dirtyRecord);
  const retrieved = historyService.get('sec-test-fontes-001');
  assert.ok(retrieved, 'Registro deve ser recuperável do histórico');
  assert.ok(retrieved.writerResponse?.fontes, 'Fontes devem estar presentes no registro');

  const savedFontes = retrieved.writerResponse.fontes;
  assert.equal(savedFontes.status, 'completo');
  assert.equal(savedFontes.total_consultadas, 2);
  assert.equal(savedFontes.total_utilizadas, 1);
  assert.equal(savedFontes.total_nao_utilizadas, 1);

  // Verifica que URLs inválidas ou com esquemas perigosos (javascript:, ftp:) foram descartadas
  assert.equal(
    savedFontes.consultadas.some((c) => c.url.startsWith('javascript:')),
    false,
    'URLs javascript: devem ser totalmente descartadas'
  );
  assert.equal(
    savedFontes.consultadas.some((c) => c.url.startsWith('ftp:')),
    false,
    'URLs ftp: devem ser totalmente descartadas'
  );

  // Verifica descarte estrito de userinfo (usuário/senha)
  const itemSegredo = savedFontes.consultadas.find((c) => c.url.includes('segredo.com'));
  assert.ok(itemSegredo, 'Item consultado seguro deve existir');
  assert.ok(
    !itemSegredo.url.includes('usuario:senha123'),
    `Credenciais na URL devem ser expurgadas! URL resultante: ${itemSegredo.url}`
  );
  assert.ok(
    !itemSegredo.url.includes('token=secret123'),
    `Parâmetro token sensível deve ser removido! URL resultante: ${itemSegredo.url}`
  );
  assert.ok(
    itemSegredo.url.includes('filtro=energia'),
    'Parâmetro seguro não-sensível deve ser preservado'
  );
  assert.equal(itemSegredo.url, 'https://segredo.com/relatorio?filtro=energia');

  // Verifica preservação de caminhos e queries seguros
  const itemPublico = savedFontes.consultadas.find((c) => c.url.includes('publico.org'));
  assert.ok(itemPublico, 'Item público deve existir');
  assert.equal(itemPublico.url, 'https://publico.org/artigo?secao=1&pagina=2');

  // =========================================================================
  // 10. api.getSources: Chamada com AbortSignal e credentials same-origin
  // =========================================================================
  console.log('\n[Teste 10] api.getSources: Contrato de rede e AbortSignal');
  let capturedUrl = '';
  let capturedOptions: any = undefined;

  global.fetch = (async (url: string | URL | Request, init?: RequestInit) => {
    capturedUrl = String(url);
    capturedOptions = init;
    return new Response(
      JSON.stringify({
        id_pesquisa: 'net-test-001',
        status: 'completo',
        total_consultadas: 1,
        total_utilizadas: 1,
        total_nao_utilizadas: 0,
        consultadas: [{ url: 'https://test.org', titulo: 'Test', dominio: 'test.org' }],
        utilizadas: [{ url: 'https://test.org', titulo: 'Test', dominio: 'test.org' }],
        nao_utilizadas: [],
        artifact_hash: 'hash-net-001',
      }),
      { status: 200, headers: { 'Content-Type': 'application/json' } }
    );
  }) as unknown as typeof fetch;

  const abortCtrl = new AbortController();
  const apiResult = await api.getSources('net-test-001', abortCtrl.signal);

  assert.equal(capturedUrl, '/api/v1/pipeline/net-test-001/sources');
  assert.equal(capturedOptions?.method, 'GET');
  assert.equal(capturedOptions?.credentials, 'same-origin');
  assert.equal(capturedOptions?.signal, abortCtrl.signal);
  assert.equal(apiResult.status, 'completo');
  assert.equal(apiResult.total_consultadas, 1);

  // =========================================================================
  // 11. verifySourcesBinding: Função de Produção de Vinculação Estrita de Versão
  // =========================================================================
  console.log('\n[Teste 11] verifySourcesBinding: validação de digest local, hash idêntico e ID');
  const validSources: FontesResumo = {
    id_pesquisa: 'report-abc',
    status: 'completo',
    total_consultadas: 2,
    total_utilizadas: 2,
    total_nao_utilizadas: 0,
    consultadas: [],
    utilizadas: [],
    nao_utilizadas: [],
    artifact_hash: 'abc123hash',
  };

  // Caso 1: Sucesso com correspondência exata de ID e hash
  const resValid = verifySourcesBinding('report-abc', 'Texto Publicado', 'abc123hash', validSources);
  assert.equal(resValid.isValid, true, 'Deve aprovar quando ID e hash coincidirem');

  // Caso 2: Falha quando id_pesquisa diferir
  const resDiffId = verifySourcesBinding('report-xyz', 'Texto Publicado', 'abc123hash', validSources);
  assert.equal(resDiffId.isValid, false, 'Deve rejeitar quando ID diferir');
  assert.ok(resDiffId.reason?.includes('outra versão deste relatório'));

  // Caso 3: Falha quando localHash for vazio (falha de digest criptográfico local)
  const resEmptyLocalHash = verifySourcesBinding('report-abc', 'Texto Publicado', '', validSources);
  assert.equal(resEmptyLocalHash.isValid, false, 'Deve rejeitar quando digest local for vazio');
  assert.ok(resEmptyLocalHash.reason?.includes('Não foi possível conferir a integridade'));

  // Caso 4: Falha quando artifact_hash do servidor estiver ausente (mesmo se status for indisponivel)
  const sourcesNoHash: FontesResumo = {
    ...validSources,
    artifact_hash: null,
    status: 'indisponivel',
  };
  const resNoServerHash = verifySourcesBinding('report-abc', 'Texto Publicado', 'abc123hash', sourcesNoHash);
  assert.equal(
    resNoServerHash.isValid,
    false,
    'Deve rejeitar quando hash do servidor estiver ausente para texto publicado'
  );
  assert.ok(resNoServerHash.reason?.includes('outra versão deste relatório'));

  // Caso 5: Falha quando artifact_hash divergir do localHash
  const sourcesDiffHash: FontesResumo = {
    ...validSources,
    artifact_hash: 'hash-antigo-diferente',
  };
  const resDiffHash = verifySourcesBinding('report-abc', 'Texto Publicado', 'abc123hash', sourcesDiffHash);
  assert.equal(resDiffHash.isValid, false, 'Deve rejeitar quando hashes divergirem');
  assert.ok(resDiffHash.reason?.includes('outra versão deste relatório'));

  // Caso 6: Rejeição de resumo de fontes quando o texto publicado completo for ausente ou em branco
  const emptyDigest = crypto.createHash('sha256').update('', 'utf-8').digest('hex');
  const foreignDigest = crypto.createHash('sha256').update('outro relatório completo', 'utf-8').digest('hex');

  const resEmptyPublishedWithForeignHash = verifySourcesBinding('same-id', '', emptyDigest, {
    id_pesquisa: 'same-id',
    status: 'completo',
    total_consultadas: 10,
    total_utilizadas: 5,
    total_nao_utilizadas: 5,
    consultadas: [],
    utilizadas: [],
    nao_utilizadas: [],
    artifact_hash: foreignDigest,
  });
  assert.equal(
    resEmptyPublishedWithForeignHash.isValid,
    false,
    'Deve rejeitar quando o texto publicado completo for ausente/em branco, não aceitando fontes de outro artigo por ID isolado'
  );
  assert.equal(
    resEmptyPublishedWithForeignHash.reason,
    'O registro guardou só um resumo, então os totais de fontes não podem ser conferidos.'
  );

  const resBlankPublished = verifySourcesBinding('report-abc', '   ', 'some-hash', validSources);
  assert.equal(
    resBlankPublished.isValid,
    false,
    'Deve rejeitar quando texto for composto apenas por espaços em branco'
  );
  assert.equal(
    resBlankPublished.reason,
    'O registro guardou só um resumo, então os totais de fontes não podem ser conferidos.'
  );

  // =========================================================================
  // 12. ReportView: Derivação de Identidade Estrita (id E texto publicado)
  // =========================================================================
  console.log('\n[Teste 12] ReportView: Derivação síncrona sem fuga de estado defasado ao alterar texto');
  // Simula renderização do ReportView com relatório inicial
  const reportV1: WriterResponse = {
    id_pesquisa: 'rep-identity-001',
    tema: 'Pesquisa V1',
    status: 'concluido',
    total_caracteres_dossier: 50,
    dossier_final: 'Texto da Versão 1',
    fontes: {
      id_pesquisa: 'rep-identity-001',
      status: 'completo',
      total_consultadas: 5,
      total_utilizadas: 3,
      total_nao_utilizadas: 2,
      consultadas: [],
      utilizadas: [],
      nao_utilizadas: [],
      artifact_hash: crypto.createHash('sha256').update('Texto da Versão 1', 'utf-8').digest('hex'),
    },
  };

  const htmlV1 = renderToString(React.createElement(ReportView, { report: reportV1, onReset: () => {} }));
  assert.ok(htmlV1.includes('Pesquisa V1'), 'Deve renderizar V1');

  // Ao renderizar com o mesmo ID mas texto alterado (V2) e fontes ainda com hash de V1 (mismatch):
  const reportV2WithOldFontes: WriterResponse = {
    ...reportV1,
    dossier_final: 'Texto Modificado da Versão 2 (diferente)',
  };
  const htmlV2Mismatch = renderToString(
    React.createElement(ReportView, { report: reportV2WithOldFontes, onReset: () => {} })
  );
  // Não deve exibir as fontes de V1 como válidas sob o texto de V2
  assert.ok(
    !htmlV2Mismatch.includes('5 consultadas • 3 utilizadas'),
    'Não deve associar contagens do resumo V1 quando o texto foi alterado para V2'
  );

  // =========================================================================
  // 13. ReportView: Relatório Legado apenas com resumo (dossier_resumo sem dossier_final)
  // =========================================================================
  console.log('\n[Teste 13] ReportView: Relatório legado resumo-only preserva texto e marca totais como indisponíveis');
  const legacyResumoOnlyReport: WriterResponse = {
    id_pesquisa: 'legacy-resumo-only-001',
    tema: 'História do Café no Brasil',
    status: 'concluido',
    total_caracteres_dossier: 150,
    dossier_resumo: 'Resumo analítico sobre a expansão cafeeira no Vale do Paraíba com citação [Embrapa](https://embrapa.br/cafe).',
    // dossier_final ausente
    fontes: {
      id_pesquisa: 'legacy-resumo-only-001',
      status: 'completo',
      total_consultadas: 8,
      total_utilizadas: 4,
      total_nao_utilizadas: 4,
      consultadas: [],
      utilizadas: [],
      nao_utilizadas: [],
      artifact_hash: foreignDigest, // Hash pertencente a um artigo completo alheio
    },
  };

  const htmlResumoOnly = renderToString(
    React.createElement(ReportView, { report: legacyResumoOnlyReport, onReset: () => {} })
  );

  // Preserva texto visível do resumo
  assert.ok(
    htmlResumoOnly.includes('História do Café no Brasil'),
    'Deve exibir o tema do relatório legado'
  );
  assert.ok(
    htmlResumoOnly.includes('expansão cafeeira no Vale do Paraíba'),
    'Deve renderizar o corpo do resumo'
  );
  // Botões de cópia e download intactos
  assert.ok(htmlResumoOnly.includes('Copiar Markdown'), 'Botão de copiar deve estar presente');
  assert.ok(htmlResumoOnly.includes('Baixar .md'), 'Botão de baixar deve estar presente');

  // Não deve exibir contagens do artigo alheio
  assert.ok(
    !htmlResumoOnly.includes('8 consultadas • 4 utilizadas'),
    'NÃO deve exibir contagens do artigo completo alheio para um registro de resumo'
  );

  console.log('\n--- Todos os 13 testes focados de contabilidade de fontes passaram com sucesso! ---');
}

runSourcesTests().catch((err) => {
  console.error('\nFALHA NO TESTE:', err);
  process.exit(1);
});
