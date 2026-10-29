import React from 'react';
import { PlanView } from '../components/PlanView';
import type { PlanResponse } from '../types/api';

const mockPlan: PlanResponse = {
  id_pesquisa: 'dev-plan',
  tema: 'teste de pré-voo',
  n_pontos: 4,
  criado_em: new Date().toISOString(),
  pontos: [
    { ponto_id: 'p1', ponto_n: 1, ponto: 'Ponto 1', status: 'pendente' },
    { ponto_id: 'p2', ponto_n: 2, ponto: 'Ponto 2', status: 'pendente' },
    { ponto_id: 'p3', ponto_n: 3, ponto: 'Ponto 3', status: 'pendente' },
    { ponto_id: 'p4', ponto_n: 4, ponto: 'Ponto 4', status: 'pendente' },
  ],
  preferencias: { n_pontos: 4, personas: ['historiador', 'cetico', 'visionario', 'futurista'] },
};

export const PlanHarness: React.FC = () => {
  return (
    <PlanView
      plan={mockPlan}
      onStartExecution={() => {}}
      onReset={() => {}}
      onEditParameters={() => {}}
      isStarting={false}
    />
  );
};

export default PlanHarness;
