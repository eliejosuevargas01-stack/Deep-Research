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
import { readFileSync } from 'node:fs';
import React from 'react';
import { renderToString } from 'react-dom/server';
import type { AuditResponse, PlanResponse, SearchResponse } from '../types/api.js';
import type { ReasoningFeedItem } from '../types/stream.js';

const { LinearTimeline, formatarHoraTimelog, extrairQueriesTimelog } = await import(
  '../components/LinearTimeline.js'
);

function contar(html: string, alvo: string): number {
  return html.split(alvo).length - 1;
}

const noop = () => {};

// --- Helpers puros ---
assert.equal(formatarHoraTimelog(''), '', 'timestamp vazio devolve string vazia');
assert.equal(formatarHoraTimelog('nao-e-data'), '', 'timestamp invalido devolve string vazia');

const horaNaive = formatarHoraTimelog('2026-10-28T03:02:00');
assert.match(horaNaive, /^\d{2}:\d{2}:\d{2}$/, 'timestamp ISO vira HH:MM:SS');
assert.equal(
  formatarHoraTimelog('2026-10-28T03:02:00Z'),
  horaNaive,
  'carimbo sem fuso recebe UTC e mantem a mesma hora'
);

const reasoningMulti = [
  '**Ferramenta · SERP** `serie historica agencias 2010-2024` → 10 resultados',
  'texto entre consultas',
  '**Ferramenta · SERP** `fechamento agencias bancarias 2024` → 8 resultados',
  '**Ferramenta · Reader** `bcb.gov.br/agencias` → 3 páginas lidas',
].join('\n');
assert.deepEqual(
  extrairQueriesTimelog(reasoningMulti),
  ['serie historica agencias 2010-2024', 'fechamento agencias bancarias 2024'],
  'extrai TODAS as queries SERP e ignora Reader'
);
assert.deepEqual(extrairQueriesTimelog('sem ferramenta'), [], 'reasoning sem SERP devolve lista vazia');
assert.deepEqual(extrairQueriesTimelog(''), [], 'reasoning vazio devolve lista vazia');
assert.deepEqual(
  extrairQueriesTimelog('Ferramenta · SERP · `consulta com separador` → 4 resultados'),
  ['consulta com separador'],
  'aceita separador extra depois de SERP'
);

// --- Massa SSR ---
const plano: PlanResponse = {
  id_pesquisa: 'timelog-step',
  tema: 'agências bancárias',
  n_pontos: 1,
  criado_em: '2026-10-28T03:00:00',
  pontos: [{ ponto_id: 'p1', ponto_n: 1, ponto: 'Série histórica de agências', status: 'reprovado' }],
};

const busca: SearchResponse = {
  id_pesquisa: 'timelog-step',
  total_pontos_processados: 1,
  status_pesquisa: 'buscando',
  total_falhas_coleta: 0,
  resumo_coletas: [
    {
      ponto_id: 'p1',
      ponto_n: 1,
      status: 'coletado',
      falha_coleta: false,
      total_urls_lidas: 12,
      total_urls_fonte: 30,
      tamanho_conteudo_caracteres: 120000,
      tentativas: 1,
      personas: [
        {
          persona: 'historiador',
          analise: 'Série do BCB mostra redução de 23% nas agências entre 2010 e 2024.',
          urls_fonte: ['https://www.bcb.gov.br/agencias'],
          queries_executadas: 2,
          falha_coleta: false,
          reasoning: reasoningMulti,
        },
        {
          persona: 'cetico',
          analise: 'Fechamento de agência não implica corte proporcional de postos.',
          urls_fonte: ['https://www.dieese.org.br/'],
          queries_executadas: 1,
          falha_coleta: false,
          reasoning: '**Ferramenta · SERP** `custo agencia bancaria dieese` → 5 resultados',
        },
      ],
    },
  ],
};

const auditoria: AuditResponse = {
  id_pesquisa: 'timelog-step',
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
      pontuacao_percentual: 50,
      criterios_aprovados: 6,
      criterios_minimos: 11,
      valido: false,
      criterios: [
        {
          id: 1,
          aprovado: false,
          justificativa: 'tema difuso',
          claim_ids: [],
          source_ids: [],
          correcao: 'delimitar o recorte',
        },
        { id: 2, aprovado: false, justificativa: 'fonte única', claim_ids: [], source_ids: [] },
        { id: 9, aprovado: true, justificativa: 'tom neutro', claim_ids: [], source_ids: [] },
      ],
    },
  ],
};

const eventos: ReasoningFeedItem[] = [
  {
    id: 'r1',
    timestamp: '2026-10-28T03:02:00',
    agentType: 'busca',
    agentName: 'Historiador',
    title: 'Varredura Web',
    reasoning: reasoningMulti,
    details: { ponto_id: 'p1' },
  },
  {
    id: 'r2',
    timestamp: '2026-10-28T03:02:07',
    agentType: 'busca',
    agentName: 'Cético',
    title: 'Varredura Web',
    reasoning: '**Ferramenta · SERP** `custo agencia bancaria dieese` → 5 resultados',
    details: { ponto_id: 'p1' },
  },
  {
    id: 'r3',
    timestamp: '2026-10-28T03:02:15',
    agentType: 'auditor',
    agentName: 'Auditor',
    title: 'Auditoria do ponto 1',
    reasoning: 'Dois critérios reprovados; cobertura regional ausente.',
    status: 'reprovado',
    details: { ponto_id: 'p1' },
  },
];

const html = renderToString(
  React.createElement(LinearTimeline, {
    plan: plano,
    searchResult: busca,
    auditResult: auditoria,
    reasoningItems: eventos,
    onRefazerBuscaPonto: noop,
    onReauditarPonto: noop,
  } as any)
);

// --- Timestamp por entrada ---
/* Contrato r3 (DESIGN.md §6): a hora vive no corpo expandido; a linha fechada
   tem só o rótulo denso. No SSR os corpos vêm com `hidden`, então a hora
   existe no markup mas não é visível. */
assert.ok(html.includes('class="tl-hora"'), 'corpo expandido usa a classe tl-hora');
const horaHistoriador = formatarHoraTimelog('2026-10-28T03:02:00');
const horaCetico = formatarHoraTimelog('2026-10-28T03:02:07');
const horaAuditor = formatarHoraTimelog('2026-10-28T03:02:15');
assert.match(horaHistoriador, /^\d{2}:\d{2}:\d{2}$/, 'hora da persona segue HH:MM:SS');
assert.ok(html.includes(`>${horaHistoriador}</time>`), 'timestamp do Historiador no corpo');
assert.ok(html.includes(`>${horaCetico}</time>`), 'timestamp do Cético no corpo');
assert.ok(html.includes(`>${horaAuditor}</time>`), 'timestamp do Auditor no corpo');
assert.ok(html.includes('dateTime="2026-10-28T03:02:00"'), 'time preserva o carimbo ISO no atributo');
assert.equal(contar(html, 'class="tl-entrada-corpo" hidden=""'), 3, 'todo corpo nasce fechado (3 passos com detalhe)');
assert.equal(contar(html, 'aria-expanded="false"'), 3, 'linha fechada anuncia aria-expanded=false');
assert.equal(contar(html, 'class="tl-pill'), 0, 'linha fechada não tem chip de persona');

// --- Queries inline de TODAS as personas ---
assert.equal(contar(html, 'class="tl-query-line"'), 3, 'todas as queries das duas personas viram linhas');
assert.ok(html.includes('$ serie historica agencias 2010-2024'), 'primeira query do Historiador inline');
assert.ok(html.includes('$ fechamento agencias bancarias 2024'), 'segunda query do Historiador inline');
assert.ok(html.includes('$ custo agencia bancaria dieese'), 'query do Cético inline');
assert.ok(!html.includes('ver query'), 'nao existe mais o toggle de primeira query');

// --- Linha do auditor reprovando ---
/* Contrato r3: persona e frase são nós separados na linha fechada
   (`Persona — frase`), e as ações de recuperação vivem no corpo. */
const fraseAuditor = 'reprovou o ponto número 1 por tema difuso (50% × 6/11) — reenviado';
assert.ok(html.includes(fraseAuditor), 'linha do auditor preserva o formato e o primeiro critério');
assert.ok(
  html.indexOf('>Auditor<') < html.indexOf(fraseAuditor),
  'persona do auditor vem antes da frase na mesma linha'
);
assert.ok(html.includes('<span>refazer busca</span>'), 'botao refazer busca presente no corpo');
assert.ok(html.includes('<span>reauditar</span>'), 'botao reauditar presente no corpo');
assert.ok(
  html.indexOf(fraseAuditor) < html.indexOf('<span>refazer busca</span>'),
  'acoes de recuperação continuam depois da frase do auditor'
);
assert.ok(html.includes('tl-detalhe'), 'criterios reprovados usam tl-detalhe');
assert.ok(html.includes('Critério 1:'), 'detalhe mantem criterio reprovado');
assert.ok(html.includes('— correção: delimitar o recorte'), 'correcao do criterio preservada');

// CSS flat: tl-detalhe sem borda e sem fundo (bloco tracked gdr-refit.css).
const css = readFileSync(new URL('../styles/gdr-refit.css', import.meta.url), 'utf8');
const blocoTimelog = css.slice(css.indexOf('/* --- Timelog flat'));
assert.ok(blocoTimelog.length > 0, 'bloco de timelog acrescentado ao fim do CSS');
assert.match(blocoTimelog, /\.tl-detalhe\s*\{[^}]*border:\s*0/, 'tl-detalhe sem borda');
assert.match(blocoTimelog, /\.tl-detalhe\s*\{[^}]*background:\s*none/, 'tl-detalhe sem fundo');
assert.match(blocoTimelog, /\.tl-query-line\s*\{/, 'linha de query tem estilo mono proprio');

console.log('gdr-timelog-step ok');
