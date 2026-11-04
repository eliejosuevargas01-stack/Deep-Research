import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { SourcesExplorer, derivarFontesParaExplorer } from '../components/SourcesExplorer';
import { ContextSidebar } from '../components/ContextSidebar';
import type { SearchResponse } from '../types/api';

const busca = {
  id_pesquisa: 'plan-9-xyz',
  total_pontos_processados: 1,
  status_pesquisa: 'coletado',
  total_falhas_coleta: 0,
  resumo_coletas: [
    {
      ponto_id: 'plan-9-xyz-p1',
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

describe('SourcesExplorer — invariantes de status e contagem', () => {
  it('test_nenhuma_fonte_fica_lendo_quando_coleta_terminou', () => {
    const itens = derivarFontesParaExplorer(busca, { emColeta: false });
    expect(itens).toHaveLength(2);
    expect(itens.some((i) => i.status === 'lendo')).toBe(false);
    for (const item of itens) {
      expect(['lida_nao_utilizada', 'utilizada']).toContain(item.status);
    }

    render(<SourcesExplorer items={itens} isActive={false} />);
    expect(screen.queryByText('Lendo')).toBeNull();
    expect(screen.getByText('2 lidas · 1 citadas')).toBeInTheDocument();
  });

  it('test_componente_rebaixa_lendo_quando_inativo', () => {
    const { rerender } = render(
      <SourcesExplorer
        isActive
        items={[{ url: 'https://a.com/artigo', status: 'lendo', ponto_n: null }]}
      />
    );
    expect(screen.getByText('Lendo')).toBeInTheDocument();
    expect(screen.getByText('0 lidas · 0 citadas')).toBeInTheDocument();

    rerender(
      <SourcesExplorer
        isActive={false}
        items={[{ url: 'https://a.com/artigo', status: 'lendo', ponto_n: null }]}
      />
    );
    expect(screen.queryByText('Lendo')).toBeNull();
    expect(screen.getByText('Lida (não utilizada)')).toBeInTheDocument();
    expect(screen.getByText('1 lidas · 0 citadas')).toBeInTheDocument();
  });

  it('test_urls_lidas_nao_encolhem_quando_parecer_substitui_log_ao_vivo', () => {
    const reasoningItems = [
      { reasoning: '- lendo https://a.com/x\n- lendo https://b.com/y\n', pointNumber: 1 },
    ];
    const { rerender } = render(
      <ContextSidebar
        searchResult={busca}
        fontesAtivas
        reasoningItems={reasoningItems}
        initialMode="fontes"
      />
    );
    const contagem = () => screen.getByRole('tab', { name: /Fontes/ }).textContent ?? '';
    expect(contagem()).toContain('4');

    // Parecer final só cita uma das fontes lidas.
    rerender(
      <ContextSidebar
        fontes={[
          {
            url: 'https://epe.gov.br/relatorio',
            titulo: 'Relatório EPE',
            dominio: 'epe.gov.br',
            status: 'utilizada',
            ponto_n: 1,
          },
        ]}
        fontesAtivas={false}
        initialMode="fontes"
      />
    );
    expect(contagem()).toContain('4');
    expect(screen.queryByText('Lendo')).toBeNull();
    expect(screen.getByText('4 lidas · 1 citadas')).toBeInTheDocument();
  });

  it('test_status_utilizada_nao_regride_para_lida_nao_utilizada', () => {
    const { rerender } = render(
      <ContextSidebar
        fontes={[
          { url: 'https://epe.gov.br/relatorio', status: 'utilizada', ponto_n: 1 },
        ]}
        fontesAtivas={false}
        initialMode="fontes"
      />
    );
    expect(screen.getByText('1 lidas · 1 citadas')).toBeInTheDocument();

    rerender(
      <ContextSidebar
        fontes={[
          { url: 'https://epe.gov.br/relatorio', status: 'lida_nao_utilizada', ponto_n: 1 },
        ]}
        fontesAtivas={false}
        initialMode="fontes"
      />
    );
    expect(screen.getByText('1 lidas · 1 citadas')).toBeInTheDocument();
  });
});
