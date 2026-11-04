import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ExecutionView } from '../components/ExecutionView';
import type { PlanResponse } from '../types/api';

const plano = {
  id_pesquisa: 'plan-1791234567890-a9f4c21b',
  tema: 'Matriz energética Brasil',
  n_pontos: 2,
  criado_em: '2026-11-03T10:00:00Z',
  pontos: [
    { ponto_id: 'p1', ponto_n: 1, ponto: 'P1', status: 'aprovado' },
    { ponto_id: 'p2', ponto_n: 2, ponto: 'P2', status: 'pendente' },
  ],
} as unknown as PlanResponse;

describe('ExecutionView — bússola de execução', () => {
  it('test_execution_view_exibe_rodada_atual_turnos_restantes_e_progresso_de_pontos', () => {
    render(
      <ExecutionView
        stage="auditing"
        plan={plano}
        cycleNumber={2}
        maxCycles={4}
        onReset={vi.fn()}
        auditResult={{
          id_pesquisa: plano.id_pesquisa,
          total_pontos: 2,
          aprovados: 1,
          reprovados: 0,
          pronto_para_writer: false,
          status_geral: 'parcial',
          auditorias: [
            {
              ponto_id: 'p1',
              ponto_n: 1,
              status: 'aprovado',
              pontuacao_percentual: 100,
              criterios_aprovados: 12,
              criterios_minimos: 11,
              valido: true,
              criterios: [],
            },
          ],
        }}
      />
    );

    expect(screen.getByText(/rodada 2 de 4/i)).toBeInTheDocument();
    expect(screen.getByText(/Restam 2 turno/i)).toBeInTheDocument();
    expect(screen.getByText('Ponto 1')).toBeInTheDocument();
    expect(screen.getByText('Ponto 2')).toBeInTheDocument();
    expect(screen.getByText('✓ Aprovado')).toBeInTheDocument();
    expect(screen.getByText('Aguardando')).toBeInTheDocument();
  });

  it('mostra o progresso real da redação durante a escrita', () => {
    render(
      <ExecutionView
        stage="writing"
        plan={plano}
        cycleNumber={2}
        maxCycles={4}
        onReset={vi.fn()}
        writerProgress={{ status: 'redigindo', total_caracteres: 12345 }}
      />
    );

    expect(screen.getByText(/12\.345 caracteres redigidos/i)).toBeInTheDocument();
  });
});
