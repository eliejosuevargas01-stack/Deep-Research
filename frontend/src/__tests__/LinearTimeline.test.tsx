import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { LinearTimeline } from '../components/LinearTimeline';
import type { AuditResponse, PlanResponse, SearchResponse } from '../types/api';

const PONTO_ID = 'plan-1-a9f4c21b-p1';

const plano = {
  id_pesquisa: 'plan-1-a9f4c21b',
  tema: 'Matriz energética Brasil',
  n_pontos: 1,
  criado_em: '2026-11-03T10:00:00Z',
  pontos: [{ ponto_id: PONTO_ID, ponto_n: 1, ponto: 'Qual a matriz?', status: 'aprovado' }],
} as unknown as PlanResponse;

const busca = {
  id_pesquisa: 'plan-1-a9f4c21b',
  total_pontos_processados: 1,
  status_pesquisa: 'coletado',
  total_falhas_coleta: 0,
  resumo_coletas: [
    {
      ponto_id: PONTO_ID,
      ponto_n: 1,
      status: 'coletado',
      falha_coleta: false,
      total_urls_lidas: 1,
      total_urls_fonte: 1,
      tamanho_conteudo_caracteres: 10,
      tentativas: 1,
      personas: [
        {
          persona: 'historiador',
          analise: 'ok',
          urls_fonte: ['https://epe.gov.br/x'],
          urls_lidas: ['https://epe.gov.br/x'],
          queries_executadas: 1,
          falha_coleta: false,
          lacunas: null,
        },
      ],
    },
  ],
} as unknown as SearchResponse;

const auditoria = {
  id_pesquisa: 'plan-1-a9f4c21b',
  total_pontos: 1,
  aprovados: 1,
  reprovados: 0,
  pronto_para_writer: true,
  auditorias: [
    {
      ponto_id: PONTO_ID,
      ponto_n: 1,
      status: 'aprovado',
      pontuacao_percentual: 100,
      criterios_aprovados: 12,
      criterios_minimos: 11,
      valido: true,
      criterios: Array.from({ length: 12 }, (_, i) => ({
        id: i + 1,
        aprovado: true,
        justificativa: `critério ${i + 1} atendido`,
        claim_ids: [],
        source_ids: [],
      })),
      pontos_fracos: null,
      resumo_auditoria: null,
      reasoning_auditoria: null,
    },
  ],
} as unknown as AuditResponse;

describe('LinearTimeline — linha do auditor', () => {
  it('test_linha_auditor_exibe_12_de_12_e_nao_12_de_11_quando_gabarita', () => {
    render(<LinearTimeline plan={plano} searchResult={busca} auditResult={auditoria} />);

    const texto = document.body.textContent ?? '';
    expect(texto).not.toContain('12/11');
    expect(texto).toContain('12/12');
    expect(texto).toContain('mín. 11');
    expect(texto).toContain('corte: 11');
  });
});
