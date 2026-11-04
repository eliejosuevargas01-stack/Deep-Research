import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ReportView } from '../components/ReportView';
import { resolverEstagioInicial } from '../utils/estagio';
import type { WriterResponse } from '../types/api';

const relatorio = {
  id_pesquisa: 'plan-1790000000000-a9f4c21b',
  tema: 'Matriz energética Brasil',
  status: 'concluido',
  total_caracteres_dossier: 40,
  concluido_em: null,
  dossier_final: '# Dossiê final\n\nMatriz energética consolidada.',
  fontes: null,
} as unknown as WriterResponse;

describe('navegação do histórico', () => {
  it('test_selecionar_pesquisa_concluida_no_historico_abre_report_view_direto', () => {
    // Regra usada ao abrir o item do histórico: dossiê presente ⇒ relatório.
    expect(resolverEstagioInicial('concluido', true)).toBe('completed');
    expect(resolverEstagioInicial('concluido', false)).toBe('idle');
    expect(resolverEstagioInicial('buscando', false)).toBe('searching');

    render(<ReportView report={relatorio} onReset={vi.fn()} />);

    expect(screen.getByText(/Matriz energética consolidada/)).toBeInTheDocument();
    expect(screen.queryByText('Iniciar pesquisa')).toBeNull();
  });
});
