import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import {
  TokenUsageMeter,
  linhasBreakdownTokens,
  tituloTokensPorEtapa,
} from '../components/TokenUsageMeter';
import type { ModeloMetadados } from '../types/api';

const metadados: ModeloMetadados = {
  model_used: 'deepseek-v4.1',
  usage_total: { prompt_tokens: 12000, completion_tokens: 3000, total_tokens: 15000 },
};

describe('TokenUsageMeter — rótulo por etapa e breakdown', () => {
  it('test_titulo_tokens_so_fala_de_planejamento_no_planejamento', () => {
    for (const etapa of ['idle', 'planejando', 'planejado', 'aguardando', 'PLANEJADO']) {
      expect(tituloTokensPorEtapa(etapa)).toBe('Tokens do planejamento');
    }
    for (const etapa of ['searching', 'buscando', 'auditing', 'auditando', 'writing', 'redigindo', 'completed', 'concluido', 'failed']) {
      expect(tituloTokensPorEtapa(etapa)).toBe('Consumo de tokens da pesquisa');
    }
    expect(tituloTokensPorEtapa(null)).toBe('Consumo de tokens da pesquisa');
  });

  it('test_medidor_renderiza_rotulo_dinamico_recebido', () => {
    const { rerender } = render(
      <TokenUsageMeter metadados={metadados} titulo={tituloTokensPorEtapa('planejado')} />
    );
    expect(screen.getByText('Tokens do planejamento')).toBeInTheDocument();
    expect(screen.queryByText('Consumo de tokens da pesquisa')).toBeNull();
    expect(screen.getAllByText('15 mil').length).toBeGreaterThan(0);

    rerender(<TokenUsageMeter metadados={metadados} titulo={tituloTokensPorEtapa('writing')} />);
    expect(screen.getByText('Consumo de tokens da pesquisa')).toBeInTheDocument();
    expect(screen.queryByText('Tokens do planejamento')).toBeNull();
  });

  it('test_medidor_expandido_mostra_breakdown_por_etapa', () => {
    const comEtapas: ModeloMetadados = {
      ...metadados,
      por_etapa: {
        plan: { input_tokens: 900, output_tokens: 300, total_tokens: 1200 },
        search: { input_tokens: 6000, output_tokens: 2000, total_tokens: 8000 },
        audit: { input_tokens: 2000, output_tokens: 500, total_tokens: 2500 },
      },
    };
    expect(linhasBreakdownTokens(comEtapas).map((l) => l.rotulo)).toEqual([
      'Busca',
      'Auditoria',
      'Planejamento',
    ]);

    render(<TokenUsageMeter metadados={comEtapas} />);
    expect(screen.getByText('Detalhes por etapa e agente')).toBeInTheDocument();
    expect(screen.getByText('Busca')).toBeInTheDocument();
    expect(screen.getByText('Auditoria')).toBeInTheDocument();
    expect(screen.getByText('Planejamento')).toBeInTheDocument();
    expect(screen.getByText('8 mil')).toBeInTheDocument();
  });

  it('test_medidor_expandido_mostra_breakdown_por_agente', () => {
    const comAgentes: ModeloMetadados = {
      usage_total: { prompt_tokens: 3000, completion_tokens: 1000, total_tokens: 4000 },
      por_agente: {
        planejador: { input_tokens: 1000, output_tokens: 200, total_tokens: 1200 },
        'subagente-coleta': { input_tokens: 2000, output_tokens: 800, total_tokens: 2800 },
      },
    };
    render(<TokenUsageMeter metadados={comAgentes} />);
    expect(screen.getByText('planejador')).toBeInTheDocument();
    expect(screen.getByText('subagente-coleta')).toBeInTheDocument();
  });

  it('test_medidor_sem_breakdown_nao_inventa_agente', () => {
    render(<TokenUsageMeter metadados={metadados} />);
    expect(screen.getByText('sem quebra por etapa disponível')).toBeInTheDocument();
  });

  it('test_medidor_sem_telemetria_mostra_rotulo_e_estado_vazio', () => {
    render(<TokenUsageMeter metadados={null} titulo="Consumo de tokens da pesquisa" />);
    expect(screen.getByText('Consumo de tokens da pesquisa')).toBeInTheDocument();
    expect(screen.getByText('sem dados de tokens')).toBeInTheDocument();
  });
});
