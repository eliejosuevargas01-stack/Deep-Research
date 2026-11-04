import React, { useState } from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { ContextSidebar } from '../components/ContextSidebar';
import { proximoRail, type RailMode } from '../utils/rail';
import type { PlanResponse } from '../types/api';

const plano = {
  id_pesquisa: 'plan-1791234567890-a9f4c21b',
  tema: 'Matriz energética Brasil',
  n_pontos: 1,
  criado_em: '2026-11-03T10:00:00Z',
  pontos: [{ ponto_id: 'p1', ponto_n: 1, ponto: 'Qual a matriz?', status: 'pendente' }],
  preferencias: { personas: ['historiador', 'visionetico'] },
} as unknown as PlanResponse;

/** Reproduz o app-shell: estado do rail fora da sidebar, como em App.tsx. */
const Harness: React.FC = () => {
  const [aberto, setAberto] = useState(true);
  const [modo, setModo] = useState<RailMode>('fontes');
  return (
    <div>
      <button
        type="button"
        onClick={() => {
          const proximo = proximoRail(aberto, modo, 'fontes');
          setModo(proximo.modo);
          setAberto(proximo.aberto);
        }}
      >
        Fontes
      </button>
      <ContextSidebar
        plan={plano}
        isCollapsed={!aberto}
        onToggleCollapse={() => setAberto(false)}
        mode={modo}
        initialMode={modo}
        onModeChange={setModo}
        pipelineStatus="searching"
        cycleNumber={1}
        maxCycles={4}
        fontes={[
          { url: 'https://epe.gov.br/x', titulo: 'EPE', dominio: 'epe.gov.br', status: 'lida_nao_utilizada' },
        ]}
        fontesAtivas
      />
      <p data-testid="estado">{`${aberto ? 'aberto' : 'fechado'}:${modo}`}</p>
    </div>
  );
};

describe('barra lateral direita', () => {
  it('test_clicar_botao_fontes_quando_aba_contexto_ativa_muda_para_fontes_sem_fechar_painel', async () => {
    const user = userEvent.setup();
    render(<Harness />);

    expect(screen.getByTestId('estado')).toHaveTextContent('aberto:fontes');

    // Usuário troca para Contexto por dentro da sidebar.
    await user.click(screen.getByRole('tab', { name: /contexto/i }));
    expect(screen.getByTestId('estado')).toHaveTextContent('aberto:contexto');

    // Chip do topo "Fontes" reabre/troca — não fecha o painel.
    await user.click(screen.getByRole('button', { name: 'Fontes' }));
    expect(screen.getByTestId('estado')).toHaveTextContent('aberto:fontes');

    // Clicar de novo, já visivelmente em Fontes, fecha.
    await user.click(screen.getByRole('button', { name: 'Fontes' }));
    expect(screen.getByTestId('estado')).toHaveTextContent('fechado:fontes');
  });
});
