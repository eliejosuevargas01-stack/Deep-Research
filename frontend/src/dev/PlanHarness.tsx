import React, { useState } from 'react';
import { PlanView } from '../components/PlanView';
import { PlanningView } from '../components/PlanningView';
import { HARNESS_PLAN } from './ExecutionHarness';

/**
 * Revisão de plano determinística (card pré-voo) para medir layout e rodar
 * auditorias sem disparar uma pesquisa real. Só existe em DEV: `#plan`.
 */
export const PlanHarness: React.FC = () => {
  const [iniciando, setIniciando] = useState(false);

  const raciocinioJson = JSON.stringify({
    tema: HARNESS_PLAN.tema ?? 'IA generativa no trabalho de TI',
    publico: 'gestores de TI e profissionais acompanhando o mercado',
    formato_entrega: 'Relatório com evidências datadas e distinção entre estudo e relato de mídia',
    pressupostos: ['Trabalho de TI inclui código, dados e segurança'],
    ambiguidades: ['Não está definido se o foco é adoção individual ou agregado'],
  });

  return (
    <div className="harness-plan" data-harness="plan">
      <section className="harness-planning-sample" aria-label="Amostra do planejador em ação">
        <PlanningView
          tema={HARNESS_PLAN.tema ?? 'IA generativa no trabalho de TI'}
          iniciadoEm={Date.now() - 8000}
          raciocinio={raciocinioJson}
          erro={null}
          onRetry={() => undefined}
        />
      </section>
      <PlanView
        plan={HARNESS_PLAN}
        isStarting={iniciando}
        onStartExecution={() => {
          setIniciando(true);
          window.setTimeout(() => setIniciando(false), 1200);
        }}
        onReset={() => undefined}
        onEditTheme={() => undefined}
        onEditParameters={() => undefined}
      />
    </div>
  );
};

export default PlanHarness;
