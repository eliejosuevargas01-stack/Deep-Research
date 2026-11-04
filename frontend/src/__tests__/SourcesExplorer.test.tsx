import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { SourcesExplorer, derivarFontesParaExplorer } from '../components/SourcesExplorer';
import type { SearchResponse } from '../types/api';

const busca = {
  id_pesquisa: 'plan-1-abc',
  total_pontos_processados: 1,
  status_pesquisa: 'coletado',
  total_falhas_coleta: 0,
  resumo_coletas: [
    {
      ponto_id: 'plan-1-abc-p1',
      ponto_n: 1,
      status: 'coletado',
      falha_coleta: false,
      total_urls_lidas: 2,
      total_urls_fonte: 1,
      tamanho_conteudo_caracteres: 10,
      tentativas: 1,
      personas: [
        {
          persona: 'historiador',
          analise: 'ok',
          urls_fonte: ['https://epe.gov.br/relatorio'],
          urls_lidas: ['https://epe.gov.br/relatorio', 'https://exemplo.com/leitura'],
          queries_executadas: 1,
          falha_coleta: false,
          lacunas: null,
        },
      ],
    },
  ],
} as unknown as SearchResponse;

describe('SourcesExplorer', () => {
  it('test_sources_explorer_transiciona_status_lendo_para_lida_quando_coleta_termina', () => {
    const durante = derivarFontesParaExplorer(busca, { emColeta: true });
    expect(durante.every((item) => item.status === 'lendo')).toBe(true);

    const depois = derivarFontesParaExplorer(busca, { emColeta: false });
    expect(depois.some((item) => item.status === 'lendo')).toBe(false);
    expect(depois.find((item) => item.url.includes('epe.gov.br'))?.status).toBe('utilizada');
    expect(depois.find((item) => item.url.includes('exemplo.com'))?.status).toBe('lida_nao_utilizada');

    render(<SourcesExplorer items={depois} />);
    expect(screen.queryByText('Lendo')).toBeNull();
    expect(screen.getByText('2 lidas · 1 citadas')).toBeInTheDocument();
  });

  it('descarta URL quebrada vinda do feed de raciocínio', () => {
    const itens = derivarFontesParaExplorer(null, {
      emColeta: false,
      reasoningItems: [{ reasoning: '- lendo https://^\n- lendo https://epe.gov.br/x\n' }],
    });
    expect(itens.map((i) => i.url)).toEqual(['https://epe.gov.br/x']);
  });
});
