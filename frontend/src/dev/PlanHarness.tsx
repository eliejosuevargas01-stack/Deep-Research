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

  const raciocinioCompleto = JSON.stringify({
    tema: HARNESS_PLAN.tema ?? 'IA generativa no trabalho de TI',
    publico: 'gestores de TI e profissionais acompanhando o mercado',
    formato_entrega: 'Relatório com evidências datadas e distinção entre estudo e relato de mídia',
    pressupostos: ['Trabalho de TI inclui código, dados e segurança'],
    ambiguidades: ['Não está definido se o foco é adoção individual ou agregado'],
  });
  const raciocinioTruncado = raciocinioCompleto.slice(0, Math.floor(raciocinioCompleto.length * 0.55));
  const amostras: Array<[string, string]> = [
    ['json completo', raciocinioCompleto],
    ['json pela metade (streaming)', raciocinioTruncado],
    ['prosa pura', 'O pedido pede comparação entre estudos controlados e relatos de mercado. Vou dividir em quatro pontos.'],
  ];

  return (
    <div className="harness-plan" data-harness="plan">
      <h1 className="harness-plan-titulo">Amostras do planejador</h1>
      {amostras.map(([rotulo, texto], indice) => (
        <section className="harness-planning-sample" key={rotulo} aria-label={`Amostra do planejador: ${rotulo}`}>
          <p className="harness-planning-rotulo">{rotulo}</p>
          <PlanningView
            tema={HARNESS_PLAN.tema ?? 'IA generativa no trabalho de TI'}
            iniciadoEm={Date.now() - 8000}
            raciocinio={texto}
            erro={null}
            onRetry={() => undefined}
            tituloNivel={2}
            tituloId={`amostra-planejador-${indice}`}
          />
        </section>
      ))}
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
