import React, { useEffect, useMemo, useState } from 'react';
import { ExecutionView, PipelineStage } from '../components/ExecutionView';
import { ContextSidebar } from '../components/ContextSidebar';
import { FonteExplorerItem } from '../components/SourcesExplorer';
import { HARNESS_AUDIT, HARNESS_ITEMS, HARNESS_PLAN, HARNESS_SEARCH } from './ExecutionHarness';
import { ReasoningFeedItem } from '../types/stream';

/**
 * Pesquisa simulada: plano pré-gerado e pipeline que avança sozinho
 * (busca -> auditoria -> redação -> concluído) para auditar as telas de
 * execução sem gastar chamadas reais. Só existe em DEV: `#research-sim`.
 */

const ROTEIRO: Array<{ ate: number; stage: PipelineStage }> = [
  { ate: 10, stage: 'searching' },
  { ate: 20, stage: 'auditing' },
  { ate: 28, stage: 'writing' },
  { ate: Number.POSITIVE_INFINITY, stage: 'completed' },
];

const TODAS_FONTES_SIM: FonteExplorerItem[] = [
  { url: 'https://www.bcb.gov.br/estabilidadefinanceira/relatorios', titulo: 'Banco Central - Relatório de Estabilidade Financeira', dominio: 'bcb.gov.br', status: 'utilizada', ponto_n: 1 },
  { url: 'https://www.dieese.org.br/estudosepesquisas/bancarios', titulo: 'DIEESE - Emprego Bancário 2014-2024', dominio: 'dieese.org.br', status: 'utilizada', ponto_n: 1 },
  { url: 'https://www.contrafcut.org.br/acordos-coletivos', titulo: 'Contraf-CUT - Cláusulas de Requalificação', dominio: 'contrafcut.org.br', status: 'utilizada', ponto_n: 1 },
  { url: 'https://mte.gov.br/rais-caged-2024', titulo: 'Ministério do Trabalho - RAIS/CAGED Setorial', dominio: 'mte.gov.br', status: 'utilizada', ponto_n: 2 },
  { url: 'https://febraban.org.br/dados-setor-2024', titulo: 'FEBRABAN - Relatório de Tecnologia Bancária', dominio: 'febraban.org.br', status: 'lendo', ponto_n: 2 },
  { url: 'https://ibge.gov.br/pesquisa-servicos-financeiros', titulo: 'IBGE - Pesquisa Anual de Serviços', dominio: 'ibge.gov.br', status: 'lendo', ponto_n: 3 },
  { url: 'https://ipea.gov.br/automacao-mercado-trabalho', titulo: 'IPEA - Impactos da Automação no Setor Financeiro', dominio: 'ipea.gov.br', status: 'lendo', ponto_n: 3 },
];

const DELTAS = [
  'Lendo o documento do Banco Central sobre agências desde 2007 (https://www.bcb.gov.br/estabilidadefinanceira/relatorios); a série confirma queda de 23% entre 2010 e 2024.',
  'Cruzando o CAGED com a RAIS (https://mte.gov.br/rais-caged-2024): a mudança de classificação em 2020 quebra a comparação direta de ocupações.',
  'Encontrei 41 cláusulas de requalificação em acordos coletivos (https://www.contrafcut.org.br/acordos-coletivos), sem métrica de conclusão declarada.',
  'O Dieese publica abertura por região (https://www.dieese.org.br/estudosepesquisas/bancarios); capitais concentram 61% das perdas de postos.',
  'Ainda falta fonte primária para a execução dos programas citados nos acordos (https://febraban.org.br/dados-setor-2024).',
];

export const SimulatedResearch: React.FC = () => {
  const [segundos, setSegundos] = useState(0);
  const [isRailOpen, setIsRailOpen] = useState(false);
  const [railMode, setRailMode] = useState<'contexto' | 'fontes'>('contexto');

  useEffect(() => {
    const id = window.setInterval(() => setSegundos((s) => s + 1), 1000);
    return () => window.clearInterval(id);
  }, []);

  const stage = ROTEIRO.find((passo) => segundos < passo.ate)?.stage ?? 'completed';
  const ciclo = stage === 'auditing' || stage === 'writing' || stage === 'completed' ? 2 : 1;

  const reasoningItems: ReasoningFeedItem[] = useMemo(() => {
    const base = HARNESS_ITEMS.filter((i) => i.agentType !== 'auditor');
    if (stage === 'searching') {
      const passos = Math.min(DELTAS.length, Math.floor(segundos / 2) + 1);
      const texto = DELTAS.slice(0, passos).join('\n');
      return [
        ...base,
        {
          id: 'sim-busca',
          timestamp: new Date().toISOString(),
          agentType: 'busca',
          agentName: 'Historiador',
          title: 'Varredura Web — Historiador (ao vivo)',
          reasoning: texto,
          status: 'em_andamento',
          streaming: true,
          details: { stage: 'search', ponto_id: 'p1', started_at: Date.now() - segundos * 1000 },
        },
      ];
    }
    if (stage === 'auditing') {
      return [
        ...base,
        ...HARNESS_ITEMS.filter((i) => i.agentType === 'auditor').slice(0, 1),
        {
          id: 'sim-auditoria',
          timestamp: new Date().toISOString(),
          agentType: 'auditor',
          agentName: 'Auditor',
          title: 'Auditoria do ponto 2 (ao vivo)',
          reasoning:
            'Conferindo os 12 critérios do ponto 2. A cobertura dos programas é declaratória: falta prestação de contas primária.',
          status: 'em_andamento',
          streaming: true,
          details: { stage: 'audit', ponto_id: 'p2', started_at: Date.now() - 4000 },
        },
      ];
    }
    return HARNESS_ITEMS;
  }, [stage, segundos]);

  const tokens = 14_300 + segundos * 1_850;
  const tokensAoVivo = useMemo(
    () => ({
      prompt_tokens: Math.max(0, tokens - 9000),
      completion_tokens: 9000 + Math.floor(segundos * 650),
      total_tokens: tokens + Math.floor(segundos * 650),
    }),
    [tokens, segundos]
  );

  const fontesSimuladas = useMemo(() => {
    // Cresce com o decorrer dos segundos: 2 -> 3 -> 4 -> 5 -> 7 fontes
    const qtd = Math.min(TODAS_FONTES_SIM.length, Math.max(2, Math.floor(segundos / 3) + 2));
    return TODAS_FONTES_SIM.slice(0, qtd).map((f, idx) => ({
      ...f,
      status: stage === 'searching' && idx >= qtd - 2 ? ('lendo' as const) : ('utilizada' as const),
    }));
  }, [segundos, stage]);

  const auditoria = useMemo(() => {
    if (stage === 'searching') return { aprovados: 0, total: 3, ciclo: 1 };
    if (stage === 'auditing') return { aprovados: 1, total: 3, ciclo: 2 };
    return { aprovados: 2, total: 3, ciclo: 2 };
  }, [stage]);

  return (
    <div className="workspace-grid" data-sim="research">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
        <ExecutionView
          stage={stage}
          plan={HARNESS_PLAN}
          searchResult={HARNESS_SEARCH}
          auditResult={stage === 'searching' ? null : HARNESS_AUDIT}
          cycleNumber={ciclo}
          maxCycles={4}
          reasoningItems={reasoningItems}
          elapsedSeconds={segundos}
          tokensAoVivo={tokensAoVivo}
          sourcesCount={fontesSimuladas.length}
          isRailOpen={isRailOpen}
          onToggleRail={(targetTab) => {
            if (targetTab) setRailMode(targetTab);
            setIsRailOpen((prev) => !prev);
          }}
          onReset={() => setSegundos(0)}
          onRetry={() => setSegundos(0)}
          failedStage={null}
        />
      </div>
      <ContextSidebar
        plan={HARNESS_PLAN}
        pipelineStatus={stage}
        cycleNumber={ciclo}
        maxCycles={4}
        collectedPoints={stage === 'searching' ? 1 : 2}
        auditSummary={auditoria}
        isCollapsed={!isRailOpen}
        onToggleCollapse={() => setIsRailOpen(false)}
        initialMode={railMode}
        mode={railMode}
        metadadosModelo={{
          model_used: 'deepseek-v4.1-flash',
          usage_total: { prompt_tokens: tokensAoVivo.prompt_tokens, completion_tokens: tokensAoVivo.completion_tokens, total_tokens: tokensAoVivo.total_tokens },
          usage_complete: true,
        }}
        tokensAoVivo={tokensAoVivo}
        fontes={fontesSimuladas}
        searchResult={HARNESS_SEARCH}
        fontesAtivas={stage === 'searching'}
        reasoningItems={reasoningItems}
      />
    </div>
  );
};
