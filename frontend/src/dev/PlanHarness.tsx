import React, { useState } from 'react';
import { PlanView } from '../components/PlanView';
import { HARNESS_PLAN } from './ExecutionHarness';

/**
 * Revisão de plano determinística (card pré-voo) para medir layout e rodar
 * auditorias sem disparar uma pesquisa real. Só existe em DEV: `#plan`.
 */
export const PlanHarness: React.FC = () => {
  const [iniciando, setIniciando] = useState(false);

  return (
    <div className="harness-plan" data-harness="plan">
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
