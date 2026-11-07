import React from 'react';
import { ExecutionView, PipelineStage } from '../components/ExecutionView';
import { ContextSidebar } from '../components/ContextSidebar';
import { AuditResponse, PlanResponse, SearchResponse, WriterResponse } from '../types/api';
import { ReasoningFeedItem } from '../types/stream';

/**
 * Estado determinístico da tela de investigação em andamento (busca e
 * auditoria) para medir layout e rodar auditorias sem depender de uma pesquisa
 * real. Só existe em DEV: `#execution/searching` e `#execution/auditing`.
 */

export const HARNESS_PLAN: PlanResponse = {
  id_pesquisa: 'harness-0001',
  tema: 'Automação bancária no Brasil: impactos no emprego e na requalificação profissional entre 2010 e 2026',
  n_pontos: 3,
  criado_em: '2026-10-28T02:10:00',
  status_pipeline: 'buscando',
  preferencias: { n_pontos: 3, personas: ['historiador', 'visionario', 'cetico', 'futurista'] },
  plano_estruturado: {
    pedido_original: 'Automação bancária no Brasil e seus efeitos no emprego',
    pedido_normalizado: 'automação bancária brasil emprego requalificação 2010-2026',
    publico: 'gestores de RH e formuladores de política pública',
    formato_entrega: 'dossiê analítico com evidências e incertezas',
    recorte_temporal: '2010-2026',
    eixos: [
      {
        pergunta_principal: 'Qual o efeito líquido da automação bancária no emprego formal?',
        subperguntas: ['Quantos postos foram fechados?', 'Quais funções cresceram?'],
        hipoteses: ['Fechamento de caixas foi parcialmente compensado por funções digitais'],
        consultas_iniciais: ['automação bancária emprego brasil'],
        fontes_primarias_desejadas: ['Banco Central', 'Dieese'],
        riscos_de_vies: ['contabilidade agregada esconde efeito por região'],
        evidencias_que_refutariam: ['crescimento líquido de vagas no setor'],
        criterio_de_conclusao: 'série temporal com abertura por função',
        investigabilidade: 'alta',
        eixo_essencial: true,
      },
    ],
  },
  pontos: [
    {
      ponto_id: 'p1',
      ponto_n: 1,
      ponto: 'Evolução do número de agências e postos de trabalho no setor bancário brasileiro entre 2010 e 2026',
      status: 'coletado',
      eixo_estruturado: {
        pergunta_principal: 'Qual a composição da matriz energética brasileira e da matriz elétrica brasileira em 2025–2026, como evoluiu e quais fontes oficiais sustentam os números?',
        subperguntas: [
          'Qual a participação percentual das fontes renováveis (hídrica, eólica, solar, biomassa e biogás) na matriz energética total versus matriz elétrica em 2025 e projeções 2026?',
          'Qual a capacidade instalada total do Sistema Interligado Nacional (SIN) segundo dados de BEN/EPE, ANEEL e ONS?',
          'Como evoluiu a expansão da geração distribuída (GD) solar fotovoltaica no período?'
        ],
        hipoteses: [
          'A matriz energética brasileira mantém participação renovável superior a 45–48%, enquanto a matriz elétrica ultrapassa 85–88% de fontes renováveis, impulsionada pelo crescimento acelerado da GD solar e eólica onshore.'
        ],
        consultas_iniciais: ['EPE BEN 2025 balanco energetico nacional'],
        fontes_primarias_desejadas: ['EPE BEN 2025', 'ONS boletim diário', 'ANEEL SIGA'],
        riscos_de_vies: ['confundir matriz elétrica com matriz energética'],
        evidencias_que_refutariam: ['queda da participação de renováveis'],
        criterio_de_conclusao: 'Identificação de dados oficiais consolidados da EPE/MME e ONS para 2025 e estimativas 2026 com desagregação por fonte.',
        investigabilidade: 'alta',
        eixo_essencial: true,
      }
    },
    {
      ponto_id: 'p2',
      ponto_n: 2,
      ponto: 'Programas de requalificação profissional promovidos por bancos e sindicatos: cobertura e resultados',
      status: 'em_andamento',
    },
    {
      ponto_id: 'p3',
      ponto_n: 3,
      ponto: 'Efeitos regionais da automação: concentração de perdas em capitais versus interior',
      status: 'pendente',
    },
  ],
  metadados_modelo: {
    model_used: 'deepseek-v4.1-flash',
    usage_total: {
      prompt_tokens: 12345,
      completion_tokens: 6789,
      total_tokens: 19134,
    },
    usage_complete: true,
  },
};

export const HARNESS_SEARCH: SearchResponse = {
  id_pesquisa: 'harness-0001',
  total_pontos_processados: 2,
  status_pesquisa: 'buscando',
  total_falhas_coleta: 0,
  resumo_coletas: [
    {
      ponto_id: 'p1',
      ponto_n: 1,
      status: 'coletado',
      falha_coleta: false,
      total_urls_lidas: 12,
      total_urls_fonte: 34,
      tamanho_conteudo_caracteres: 184320,
      tentativas: 1,
      personas: [
        {
          persona: 'historiador',
          analise: 'Série histórica do BCB mostra redução de 23% nas agências entre 2010 e 2024, com aceleração após 2018.',
          urls_fonte: ['https://www.bcb.gov.br/estabilidadefinanceira/agencias'],
          queries_executadas: 3,
          falha_coleta: false,
          reasoning: '**Ferramenta · SERP** `banco central serie historica agencias 2010-2024` → 10 resultados',
        },
        {
          persona: 'cetico',
          analise: 'A redução de agências não implica redução proporcional de postos: parte migrou para funções digitais.',
          urls_fonte: ['https://www.dieese.org.br/analisecestabasica/'],
          queries_executadas: 4,
          falha_coleta: false,
        },
        {
          persona: 'visionario',
          analise: 'Programas de requalificação aparecem em acordos coletivos.',
          urls_fonte: ['https://www.ipea.gov.br/portal/'],
          queries_executadas: 2,
          falha_coleta: false,
        },
        {
          persona: 'futurista',
          analise: 'Dados governamentais sobre automação.',
          urls_fonte: ['https://www.gov.br/'],
          queries_executadas: 2,
          falha_coleta: false,
        },
      ],
    },
    {
      ponto_id: 'p2',
      ponto_n: 2,
      status: 'em_andamento',
      falha_coleta: false,
      total_urls_lidas: 5,
      total_urls_fonte: 18,
      tamanho_conteudo_caracteres: 76300,
      tentativas: 2,
      personas: [
        {
          persona: 'visionario',
          analise: 'Programas de requalificação aparecem em acordos coletivos, mas a cobertura declarada não é auditada.',
          urls_fonte: ['https://www.contrafcut.com.br/'],
          queries_executadas: 2,
          falha_coleta: false,
        },
        {
          persona: 'historiador',
          analise: 'Análises sobre requalificação profissional.',
          urls_fonte: ['https://medium.com/'],
          queries_executadas: 2,
          falha_coleta: false,
        },
      ],
    },
  ],
};

const CRITERIOS = [
  { id: 1, aprovado: true, justificativa: 'O ponto delimita o setor bancário e a janela 2010–2026 sem ambiguidade.', claim_ids: ['c1'], source_ids: ['s1'] },
  { id: 2, aprovado: true, justificativa: 'Série do BCB e do Dieese convergem nos totais de agências.', claim_ids: ['c2'], source_ids: ['s1', 's2'] },
  { id: 3, aprovado: true, justificativa: 'Dados de 2025 presentes em duas fontes independentes.', claim_ids: ['c3'], source_ids: ['s2'] },
  { id: 4, aprovado: false, justificativa: 'A queda de agências é usada como proxy de emprego sem ajuste por função.', claim_ids: ['c4'], source_ids: ['s1'], lacuna: 'Falta abertura por função', correcao: 'Cruzar com CAGED por ocupação bancária.' },
  { id: 5, aprovado: true, justificativa: 'Cada afirmação numérica tem URL de origem rastreável.', claim_ids: ['c5'], source_ids: ['s1', 's2', 's3'] },
  { id: 6, aprovado: true, justificativa: 'O escopo pedido é emprego e requalificação; o texto não desvia para crédito.', claim_ids: ['c6'], source_ids: ['s3'] },
  { id: 7, aprovado: false, justificativa: 'O efeito regional é citado, mas não analisado.', claim_ids: ['c7'], source_ids: ['s3'], lacuna: 'Sem recorte regional', correcao: 'Adicionar dados por UF.' },
  { id: 8, aprovado: true, justificativa: 'Números conferem com a fonte original em três checagens.', claim_ids: ['c8'], source_ids: ['s1'] },
  { id: 9, aprovado: true, justificativa: 'Não há linguagem valorativa sobre bancos ou sindicatos.', claim_ids: ['c9'], source_ids: ['s2'] },
  { id: 10, aprovado: true, justificativa: '11 trechos citados para 3 afirmações centrais.', claim_ids: ['c10'], source_ids: ['s1', 's2'] },
  { id: 11, aprovado: true, justificativa: 'Incerteza sobre cobertura sindical declarada está explícita.', claim_ids: ['c11'], source_ids: ['s2'] },
  { id: 12, aprovado: true, justificativa: 'A conclusão decorre das premissas apresentadas, sem salto lógico.', claim_ids: ['c12'], source_ids: ['s1', 's2'] },
];

export const HARNESS_AUDIT: AuditResponse = {
  id_pesquisa: 'harness-0001',
  total_pontos: 2,
  aprovados: 1,
  reprovados: 1,
  status_geral: 'reprovado',
  status_pesquisa: 'auditando',
  pronto_para_writer: false,
  auditorias: [
    {
      ponto_id: 'p1',
      ponto_n: 1,
      status: 'aprovado',
      pontuacao_percentual: 83.3,
      criterios_aprovados: 10,
      criterios_minimos: 12,
      valido: true,
      criterios: CRITERIOS,
      resumo_auditoria: 'Evidência suficiente para sustentar a série histórica, com duas ressalvas metodológicas.',
      reasoning_auditoria: 'Comparei os totais de agências do BCB com a série do Dieese e com o CAGED.',
    },
    {
      ponto_id: 'p2',
      ponto_n: 2,
      status: 'reprovado',
      pontuacao_percentual: 50,
      criterios_aprovados: 6,
      criterios_minimos: 12,
      valido: false,
      criterios: CRITERIOS.map((c) => ({ ...c, aprovado: c.id % 2 === 0 })),
      pontos_fracos: 'Cobertura dos programas de requalificação é declaratória e não verificada em fonte primária.',
      diagnostico: 'Lacuna de evidência primária sobre execução dos programas.',
      resumo_auditoria: 'Reprovado por ausência de fonte primária para a cobertura declarada.',
    },
  ],
};

function item(
  id: string,
  agentType: ReasoningFeedItem['agentType'],
  agentName: string,
  title: string,
  reasoning: string,
  extra: Partial<ReasoningFeedItem> = {}
): ReasoningFeedItem {
  return {
    id,
    timestamp: '2026-10-28T03:02:00',
    agentType,
    agentName,
    title,
    reasoning,
    status: 'concluido',
    ...extra,
  };
}

export const HARNESS_ITEMS: ReasoningFeedItem[] = [
  item('r1', 'planejador', 'Planejador', 'Decomposição do tema', 'Dividi o pedido em três pontos: série histórica de agências e postos, programas de requalificação e efeito regional. Cada ponto exige fonte primária distinta.', { details: { stage: 'plan', ponto_id: 'p1', duration_ms: 9400 } }),
  item('r2', 'busca', 'Historiador', 'Varredura Web', '**Ferramenta · SERP** `banco central serie historica agencias 2010-2024`\nO Banco Central publica a série de agências desde 2007. Encontrei a redução de 23% entre 2010 e 2024 e o corte mais forte em 2019-2021, coincidindo com o fechamento de agências físicas em capitais.\n**Ferramenta · Reader** `bcb.gov.br/estabilidadefinanceira/agencias` → 12 páginas lidas', { details: { stage: 'search', ponto_id: 'p1', duration_ms: 41200 } }),
  item('r3', 'busca', 'Cético', 'Varredura Web', 'A redução de agências não prova redução de postos: parte dos trabalhadores migrou para funções digitais. O CAGED mostra crescimento de ocupações de TI no setor, mas a série muda de classificação em 2020.', { details: { stage: 'search', ponto_id: 'p1', duration_ms: 38700 } }),
  item('r4', 'busca', 'Visionário', 'Varredura Web', 'Acordos coletivos entre 2018 e 2025 mencionam requalificação em 41 cláusulas, porém sem métrica de conclusão. A cobertura declarada é de 62 mil trabalhadores, número que não consegui verificar em fonte independente.', { details: { stage: 'search', ponto_id: 'p1', duration_ms: 52100 } }),
  item('r5', 'busca', 'Futurista', 'Varredura Web', 'Lendo documento do Banco Central sobre explicabilidade de modelos; trecho relevante identificado na seção 4.2, que projeta automação de 30% das tarefas de retaguarda até 2030.', { details: { stage: 'search', ponto_id: 'p2', started_at: Date.now() - 47000 }, streaming: true, status: 'em_andamento' }),
  item('r6', 'auditor', 'Auditor', 'Auditoria do ponto 1', 'Onze critérios avaliados; dois reprovados por proxy de emprego e ausência de recorte regional. A evidência sustenta a série histórica, mas não a inferência sobre postos.', { status: 'aprovado', details: { stage: 'audit', ponto_id: 'p1', duration_ms: 107600 } }),
  item('r7', 'auditor', 'Auditor', 'Auditoria do ponto 2', 'Ponto reprovado: a cobertura dos programas é declaratória e não há fonte primária de execução. Faltam documentos de prestação de contas dos programas citados nos acordos.', { status: 'reprovado', details: { stage: 'audit', ponto_id: 'p2', duration_ms: 96400 } }),
];

interface Props {
  stage: PipelineStage;
}

export const HARNESS_DOSSIER = `# Dossiê Analítico: Automação Bancária no Brasil (2010-2026)

## Sumário Executivo
Entre 2010 e 2026, o setor bancário brasileiro passou pela mais profunda reestruturação operacional da sua história. A consolidação dos canais digitais e a implementação do Pix aceleraram o fechamento de 23% das agências físicas, transformando as remanescentes em postos de consultoria de crédito e investimentos.

## 1. Evolução de Agências e Postos de Atendimento
- **Fechamento de unidades físicas:** Segundo séries estatísticas do Banco Central do Brasil, a rede de agências reduziu de 23.192 unidades em 2014 para 17.840 no encerramento de 2024.
- **Transição de funções operacionais:** Os postos tradicionais de escriturários e caixas foram descontinuados em ritmo superior a 7% ao ano.
- **Compensação setorial:** Houve expansão contínua em áreas de segurança da informação, análise de dados e suporte a plataformas remotas.

## 2. Requalificação e Cláusulas Coletivas
As negociações entre a Fenaban e entidades representativas estabeleceram 41 cláusulas direcionadas à requalificação. Registros apontam que apenas 34% dos trabalhadores migraram internamente com êxito comprovado.

## 3. Disparidades Regionais
A retração concentrou-se inicialmente em capitais e eixos metropolitanos (61% do volume total de fechamentos). No interior, a expansão de correspondentes bancários supriu a presença física com custos operacionais reduzidos.

## Conclusões
A transição tecnológica bancária estabeleceu ganho expressivo de eficiência com forte pressão sobre postos analógicos e migração para unidades de retaguarda técnica.`;

export const HARNESS_REPORT: WriterResponse = {
  id_pesquisa: 'harness-0001',
  tema: 'Automação bancária no Brasil: impactos no emprego e na requalificação profissional entre 2010 e 2026',
  status: 'concluido',
  total_caracteres_dossier: HARNESS_DOSSIER.length,
  concluido_em: '2026-10-31T15:00:00Z',
  dossier_final: HARNESS_DOSSIER,
  dossier_resumo: 'Dossiê analítico sobre o impacto da automação e do fechamento de agências no setor bancário entre 2010 e 2026.',
  fontes: {
    id_pesquisa: 'harness-0001',
    status: 'completo',
    total_consultadas: 5,
    total_utilizadas: 3,
    total_nao_utilizadas: 2,
    artifact_hash: '186a8b3809849332d3fe5c5dd247de4eedcdb0b2ec69375ef1bd3ff82f22123d',
    consultadas: [
      { url: 'https://www.bcb.gov.br/estabilidadefinanceira/agencias', titulo: 'Banco Central - Séries de Agências', dominio: 'bcb.gov.br' },
      { url: 'https://www.dieese.org.br/estudosepesquisas/bancarios', titulo: 'DIEESE - Emprego Bancário 2014-2024', dominio: 'dieese.org.br' },
      { url: 'https://www.contrafcut.org.br/acordos-coletivos', titulo: 'Contraf-CUT - Cláusulas de Requalificação', dominio: 'contrafcut.org.br' },
      { url: 'https://noticias.exemplo.com/mercado-financeiro', titulo: 'Notícia de mercado', dominio: 'noticias.exemplo.com' },
      { url: 'https://blog.exemplo.com/opiniao-financas', titulo: 'Opinião de analista', dominio: 'blog.exemplo.com' },
    ],
    utilizadas: [
      { url: 'https://www.bcb.gov.br/estabilidadefinanceira/agencias', titulo: 'Banco Central - Séries de Agências', dominio: 'bcb.gov.br' },
      { url: 'https://www.dieese.org.br/estudosepesquisas/bancarios', titulo: 'DIEESE - Emprego Bancário 2014-2024', dominio: 'dieese.org.br' },
      { url: 'https://www.contrafcut.org.br/acordos-coletivos', titulo: 'Contraf-CUT - Cláusulas de Requalificação', dominio: 'contrafcut.org.br' },
    ],
    nao_utilizadas: [
      { url: 'https://noticias.exemplo.com/mercado-financeiro', titulo: 'Notícia de mercado', dominio: 'noticias.exemplo.com' },
      { url: 'https://blog.exemplo.com/opiniao-financas', titulo: 'Opinião de analista', dominio: 'blog.exemplo.com' },
    ],
  },
};

export const ExecutionHarness: React.FC<Props> = ({ stage }) => (
  <div className="workspace-grid">
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
        <ExecutionView
          stage={stage}
          plan={HARNESS_PLAN}
          searchResult={HARNESS_SEARCH}
          auditResult={HARNESS_AUDIT}
          cycleNumber={stage === 'auditing' ? 2 : 1}
          maxCycles={4}
          reasoningItems={HARNESS_ITEMS}
          failedStage={stage === 'failed' ? 'writing' : null}
          errorMessage={stage === 'failed' ? 'O provedor derrubou a conexão durante a redação (HTTP 502).' : null}
          onRetry={stage === 'failed' ? () => undefined : undefined}
          onReset={() => undefined}
        />
      </div>
    <ContextSidebar
      plan={HARNESS_PLAN}
      pipelineStatus={stage}
      cycleNumber={stage === 'auditing' ? 2 : 1}
      maxCycles={4}
      collectedPoints={2}
      auditSummary={{ aprovados: HARNESS_AUDIT.aprovados, total: HARNESS_AUDIT.total_pontos, ciclo: 1 }}
      metadadosModelo={HARNESS_PLAN.metadados_modelo}
      tokensAoVivo={{
        prompt_tokens: 12345,
        completion_tokens: 6789,
        total_tokens: 19134,
      }}
      searchResult={HARNESS_SEARCH}
      fontesAtivas={stage === 'searching'}
      reasoningItems={HARNESS_ITEMS}
    />
  </div>
);
