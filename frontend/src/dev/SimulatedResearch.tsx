import React, { useEffect, useMemo, useState } from 'react';
import { ExecutionView, PipelineStage } from '../components/ExecutionView';
import { ContextSidebar } from '../components/ContextSidebar';
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

const DELTAS = [
  'Lendo o documento do Banco Central sobre agências desde 2007; a série confirma queda de 23% entre 2010 e 2024.',
  'Cruzando o CAGED com a RAIS: a mudança de classificação em 2020 quebra a comparação direta de ocupações.',
  'Encontrei 41 cláusulas de requalificação em acordos coletivos, sem métrica de conclusão declarada.',
  'O Dieese publica abertura por região; capitais concentram 61% das perdas de postos.',
  'Ainda falta fonte primária para a execução dos programas citados nos acordos.',
];

export const SimulatedResearch: React.FC = () => {
  const [segundos, setSegundos] = useState(0);

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
        metadadosModelo={{
          model_used: 'deepseek-v4.1-flash',
          usage_total: { prompt_tokens: tokens - 9000, completion_tokens: 9000, total_tokens: tokens },
          usage_complete: true,
        }}
        searchResult={HARNESS_SEARCH}
        fontesAtivas={stage === 'searching'}
      />
    </div>
  );
};
