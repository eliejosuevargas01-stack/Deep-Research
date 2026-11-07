import { describe, expect, it } from 'vitest';
import type { ResearchRun } from '../services/apiV12';
import {
  estadoInicial,
  reduzirAoVivo,
  type EstadoAoVivo,
} from '../v12/usePesquisaAoVivo';

function runBase(): ResearchRun {
  return {
    research_id: 'r1',
    tema: 'Tema',
    profundidade: 2,
    veracidade_alvo: 80,
    max_rodadas_auditoria: 3,
    atualidade: 'ALL',
    callback_url: 'https://x.test/hook',
    status: 'PROCESSING',
    pontos: [
      { ponto_id: 1, enunciado: 'P1', aprovado: null },
      { ponto_id: 2, enunciado: 'P2', aprovado: null },
    ],
    urls_lidas_globais: [],
    urls_usadas_globais: [],
    total_tokens: 0,
    total_prompt_tokens: 0,
    total_completion_tokens: 0,
    total_reasoning_tokens: 0,
  };
}

function comEvento(estado: EstadoAoVivo, tipo: string, dados: unknown, id = '1'): EstadoAoVivo {
  return reduzirAoVivo(estado, { tipo: 'evento', eventoTipo: tipo, dados, id });
}

describe('reduzirAoVivo', () => {
  it('snapshot + sequência de eventos consolida pontos/fontes/auditorias/tokens', () => {
    let e = estadoInicial();
    e = reduzirAoVivo(e, { tipo: 'definir-id', researchId: 'r1' });
    e = reduzirAoVivo(e, { tipo: 'snapshot', run: runBase(), id: '1' });
    expect(e.pontos).toHaveLength(2);
    expect(e.tokens.total).toBe(0);

    e = comEvento(e, 'ponto.iniciado', { ponto_id: 1, persona: 'historiador', rodada: 1 }, '2');
    // Formato novo: arrays de URLs lidas/usadas.
    e = comEvento(
      e,
      'fonte.lida',
      {
        ponto_id: 1,
        persona: 'historiador',
        urls_lidas: ['https://a.test/1'],
        urls_usadas: ['https://a.test/1'],
      },
      '3',
    );
    // Formato antigo: só contagens — não mexe nas fontes.
    e = comEvento(e, 'fonte.lida', { ponto_id: 1, urls_lidas: 5, urls_usadas: 2 }, '3b');
    e = comEvento(e, 'ponto.coletado', { ponto_id: 1, urls_usadas: ['https://a.test/1'] }, '4');
    e = comEvento(
      e,
      'auditoria.executada',
      {
        ponto_id: 1,
        rodada: 1,
        perguntas_respondidas: { q1: true, q2: false },
        porcentagem_aprovacao: 50,
        aprovado: false,
        model_used: 'm-auditor',
        total_tokens: 120,
        total_perguntas: 2,
      },
      '5',
    );
    e = comEvento(e, 'ponto.reprovado', { ponto_id: 1, rodada: 1, porcentagem_aprovacao: 50 }, '6');
    // Delta por execução, com cumulativos do backend.
    e = comEvento(
      e,
      'tokens.atualizados',
      {
        papel: 'auditor',
        ponto_id: 1,
        tokens_execucao: 120,
        total_tokens: 120,
        prompt_tokens: 80,
        completion_tokens: 40,
        reasoning_tokens: 0,
      },
      '7',
    );

    const p1 = e.pontos.find((p) => p.ponto_id === 1);
    expect(p1?.estado).toBe('reprovado');
    expect(p1?.urls_lidas).toEqual(['https://a.test/1']);
    expect(e.fontes.map((f) => f.url)).toEqual(['https://a.test/1']);
    expect(e.fontes[0].usada).toBe(true);
    expect(e.auditorias).toHaveLength(1);
    expect(e.auditorias[0].perguntas_true).toBe(1);
    expect(e.auditorias[0].model_used).toBe('m-auditor');
    expect(e.auditorias[0].total_tokens).toBe(120);
    expect(e.tokens.total).toBe(120);
    expect(e.tokens.porPapel.auditor).toBe(120);
    expect(e.ultimoId).toBe('7');
    expect(e.contagens['auditoria.executada']).toBe(1);
  });

  it('ponto reprovado não derruba os demais; run.concluido marca resto como incompleto', () => {
    let e = estadoInicial();
    e = reduzirAoVivo(e, { tipo: 'definir-id', researchId: 'r1' });
    e = reduzirAoVivo(e, { tipo: 'snapshot', run: runBase(), id: '1' });
    e = comEvento(e, 'ponto.reprovado', { ponto_id: 1, rodada: 2 }, '2');
    e = comEvento(e, 'ponto.aprovado', { ponto_id: 2, rodada: 1 }, '3');
    // Evento real do backend: metadados + métricas, sem dossiê.
    e = comEvento(
      e,
      'run.concluido',
      {
        status: 'COMPLETED',
        pontos_falhos: [],
        metricas_tokens: { total_tokens: 900, prompt_tokens: 600, completion_tokens: 300, reasoning_tokens: 0 },
        avaliacao_pontos: [
          { ponto_id: 1, aprovado: false, porcentagem_aprovacao: 50, perguntas_true: 1, total_perguntas: 2 },
          { ponto_id: 2, aprovado: true, porcentagem_aprovacao: 100, perguntas_true: 2, total_perguntas: 2 },
        ],
      },
      '4',
    );

    expect(e.pontos.find((p) => p.ponto_id === 1)?.estado).toBe('reprovado');
    expect(e.pontos.find((p) => p.ponto_id === 2)?.estado).toBe('aprovado');
    expect(e.run?.status).toBe('COMPLETED');
    expect(e.run?.avaliacao_pontos).toHaveLength(2);

    // Dossiê refeito via GET após conclusão: relatório + lacunas + URLs entram sem perder eventos.
    const final: ResearchRun = {
      ...runBase(),
      status: 'COMPLETED',
      relatorio_final_consolidado: '# Dossiê final',
      urls_lidas_globais: ['https://a.test/1'],
      urls_usadas_globais: ['https://a.test/1'],
      total_tokens: 900,
      total_prompt_tokens: 600,
      total_completion_tokens: 300,
      total_reasoning_tokens: 0,
      completed_at: '2026-11-07T00:00:00Z',
    };
    e = reduzirAoVivo(e, { tipo: 'dossie', run: final, id: '5' });
    expect(e.run?.relatorio_final_consolidado).toBe('# Dossiê final');
    expect(e.run?.urls_usadas_globais).toEqual(['https://a.test/1']);
    expect(e.pontos.find((p) => p.ponto_id === 2)?.estado).toBe('aprovado');
    expect(e.fontes.map((f) => f.url)).toContain('https://a.test/1');
  });

  it('tokens.atualizados usa tokens_execucao como delta; cumulativo vira diff monotônico', () => {
    let e = estadoInicial();
    e = reduzirAoVivo(e, { tipo: 'definir-id', researchId: 'r1' });
    e = reduzirAoVivo(e, { tipo: 'snapshot', run: runBase(), id: '1' });
    // Dois deltas do mesmo papel somam 300.
    e = comEvento(e, 'tokens.atualizados', { papel: 'redator', tokens_execucao: 100, total_tokens: 100 }, '2');
    e = comEvento(e, 'tokens.atualizados', { papel: 'redator', tokens_execucao: 200, total_tokens: 300 }, '3');
    expect(e.tokens.total).toBe(300);
    expect(e.tokens.porPapel.redator).toBe(300);
    // Sem delta, só cumulativo maior: diff 50 vai para o papel.
    e = comEvento(e, 'tokens.atualizados', { papel: 'redator', total_tokens: 350 }, '4');
    expect(e.tokens.total).toBe(350);
    expect(e.tokens.porPapel.redator).toBe(350);
    // Cumulativo menor (replay): não regride.
    e = comEvento(e, 'tokens.atualizados', { papel: 'redator', total_tokens: 100 }, '5');
    expect(e.tokens.total).toBe(350);
    expect(e.tokens.porPapel.redator).toBe(350);
  });

  it('ponto.coletado sem URLs preserva as existentes; auditoria detalhada preenche campos', () => {
    let e = estadoInicial();
    e = reduzirAoVivo(e, { tipo: 'definir-id', researchId: 'r1' });
    e = reduzirAoVivo(e, { tipo: 'snapshot', run: runBase(), id: '1' });
    e = comEvento(
      e,
      'fonte.lida',
      { ponto_id: 1, urls_lidas: ['https://a.test/1'], urls_usadas: ['https://a.test/1'] },
      '2',
    );
    // Payload mínimo do backend: só ids — URLs existentes ficam.
    e = comEvento(e, 'ponto.coletado', { ponto_id: 1, rodada: 1 }, '3');
    expect(e.pontos.find((p) => p.ponto_id === 1)?.urls_usadas).toEqual(['https://a.test/1']);
    expect(e.pontos.find((p) => p.ponto_id === 1)?.estado).toBe('coletado');
    // Auditoria detalhada do GET/payload cheio.
    e = comEvento(
      e,
      'auditoria.executada',
      {
        ponto_id: 1,
        rodada: 1,
        perguntas_respondidas: { q1: true, q2: true, q3: false },
        perguntas_true: 2,
        total_perguntas: 3,
        porcentagem_aprovacao: 66,
        aprovado: false,
        model_used: 'auditor-x',
        total_tokens: 45,
      },
      '4',
    );
    expect(e.auditorias[0].perguntas_true).toBe(2);
    expect(e.auditorias[0].total_perguntas).toBe(3);
    expect(e.auditorias[0].model_used).toBe('auditor-x');
    expect(e.auditorias[0].total_tokens).toBe(45);
  });

  it('reload com lastEventId: snapshot restaura run; replay não regride tokens', () => {
    let e = estadoInicial();
    e = reduzirAoVivo(e, { tipo: 'definir-id', researchId: 'r1' });
    e = reduzirAoVivo(e, { tipo: 'snapshot', run: { ...runBase(), total_tokens: 500 }, id: '10' });
    expect(e.tokens.total).toBe(500);
    // Replay antigo de total absoluto menor não regride.
    e = comEvento(e, 'tokens.atualizados', { total_tokens: 100 }, '11');
    expect(e.tokens.total).toBe(500);
    // Delta por papel soma de forma cumulativa.
    e = comEvento(e, 'tokens.atualizados', { papel: 'redator', tokens_execucao: 40, total_tokens: 540 }, '12');
    e = comEvento(e, 'tokens.atualizados', { papel: 'redator', tokens_execucao: 40, total_tokens: 580 }, '13');
    expect(e.tokens.porPapel.redator).toBe(80);
  });

  it('run.falhou e ponto.erro marcam erro sem limpar o restante', () => {
    let e = estadoInicial();
    e = reduzirAoVivo(e, { tipo: 'definir-id', researchId: 'r1' });
    e = reduzirAoVivo(e, { tipo: 'snapshot', run: runBase(), id: '1' });
    e = comEvento(e, 'ponto.erro', { ponto_id: 2, mensagem: 'timeout' }, '2');
    e = comEvento(e, 'run.falhou', { mensagem: 'boom' }, '3');
    expect(e.pontos.find((p) => p.ponto_id === 2)?.estado).toBe('erro');
    expect(e.run?.status).toBe('FAILED');
    expect(e.pontos.find((p) => p.ponto_id === 1)?.estado).toBe('iniciado');
  });

  it('nao-encontrada sinaliza 404 e limpar zera o estado', () => {
    let e = estadoInicial();
    e = reduzirAoVivo(e, { tipo: 'definir-id', researchId: 'zzz' });
    e = reduzirAoVivo(e, { tipo: 'nao-encontrada' });
    expect(e.naoEncontrada).toBe(true);
    e = reduzirAoVivo(e, { tipo: 'limpar' });
    expect(e).toEqual(estadoInicial());
  });

  it('erro 401 preserva researchId e run (não limpa pesquisa ativa)', () => {
    let e = estadoInicial();
    e = reduzirAoVivo(e, { tipo: 'definir-id', researchId: 'r1' });
    e = reduzirAoVivo(e, { tipo: 'snapshot', run: runBase(), id: '1' });
    e = reduzirAoVivo(e, {
      tipo: 'erro',
      mensagem: 'API key inválida ou ausente — configure a API key.',
    });
    expect(e.erro).toContain('API key');
    expect(e.researchId).toBe('r1');
    expect(e.run?.research_id).toBe('r1');
    expect(e.naoEncontrada).toBe(false);
  });

  it('R2: plano.pronto preenche plano_inicial a partir de pontos/total_pontos', () => {
    let e = estadoInicial();
    e = reduzirAoVivo(e, { tipo: 'definir-id', researchId: 'r1' });
    e = reduzirAoVivo(e, { tipo: 'snapshot', run: runBase(), id: '1' });
    e = comEvento(e, 'plano.pronto', { pontos: [1, 2], total_pontos: 2 }, '2');
    expect(e.run?.plano_inicial).toEqual({ pontos: [1, 2], total_pontos: 2 });
    // Payload sem ids: evento ignorado, sem apagar o anterior.
    e = comEvento(e, 'plano.pronto', { total_pontos: 2 }, '3');
    expect(e.run?.plano_inicial).toEqual({ pontos: [1, 2], total_pontos: 2 });
    // Formato antigo inexistente: ignorado.
    e = comEvento(e, 'plano.pronto', {}, '4');
    expect(e.run?.plano_inicial).toEqual({ pontos: [1, 2], total_pontos: 2 });
  });

  it('R3: ponto.aprovado/reprovado não apaga %/rodada prévias', () => {
    let e = estadoInicial();
    e = reduzirAoVivo(e, { tipo: 'definir-id', researchId: 'r1' });
    e = reduzirAoVivo(e, { tipo: 'snapshot', run: runBase(), id: '1' });
    e = comEvento(
      e,
      'auditoria.executada',
      { ponto_id: 1, rodada: 2, porcentagem_aprovacao: 75, aprovado: false },
      '2',
    );
    // Payload real do backend: só ponto_id + rodada.
    e = comEvento(e, 'ponto.reprovado', { ponto_id: 1, rodada: 2 }, '3');
    const p = e.pontos.find((x) => x.ponto_id === 1);
    expect(p?.estado).toBe('reprovado');
    expect(p?.rodada).toBe(2);
    expect(p?.porcentagem_aprovacao).toBe(75);
    // Com % explícita no payload, atualiza.
    e = comEvento(e, 'ponto.aprovado', { ponto_id: 1, rodada: 3, porcentagem_aprovacao: 100 }, '4');
    const p2 = e.pontos.find((x) => x.ponto_id === 1);
    expect(p2?.porcentagem_aprovacao).toBe(100);
    expect(p2?.rodada).toBe(3);
  });

  it('R4: ponto.finalizado exibe trecho/tamanho ao vivo e preserva sem payload', () => {
    let e = estadoInicial();
    e = reduzirAoVivo(e, { tipo: 'definir-id', researchId: 'r1' });
    e = reduzirAoVivo(e, { tipo: 'snapshot', run: runBase(), id: '1' });
    e = comEvento(
      e,
      'ponto.finalizado',
      { ponto_id: 1, relatorio_trecho: 'trecho ao vivo', tamanho: 1234 },
      '2',
    );
    expect(e.pontos.find((p) => p.ponto_id === 1)?.relatorio_trecho).toBe('trecho ao vivo');
    e = comEvento(e, 'ponto.finalizado', { ponto_id: 2, tamanho: 500 }, '3');
    expect(e.pontos.find((p) => p.ponto_id === 2)?.relatorio_trecho).toBe('(relatório, 500 caracteres)');
    // Sem relatório no payload: preserva o vivo em vez de apagar.
    e = comEvento(e, 'ponto.finalizado', { ponto_id: 1 }, '4');
    expect(e.pontos.find((p) => p.ponto_id === 1)?.relatorio_trecho).toBe('trecho ao vivo');
  });

  it('R6: evento repetido com mesmo id não re-aplica contagens/tokens', () => {
    let e = estadoInicial();
    e = reduzirAoVivo(e, { tipo: 'definir-id', researchId: 'r1' });
    e = reduzirAoVivo(e, { tipo: 'snapshot', run: runBase(), id: '1' });
    e = comEvento(e, 'tokens.atualizados', { papel: 'redator', tokens_execucao: 40 }, '2');
    expect(e.tokens.total).toBe(40);
    expect(e.contagens['tokens.atualizados']).toBe(1);
    // Replay do mesmo id: ignorado por completo.
    e = comEvento(e, 'tokens.atualizados', { papel: 'redator', tokens_execucao: 40 }, '2');
    expect(e.tokens.total).toBe(40);
    expect(e.tokens.porPapel.redator).toBe(40);
    expect(e.contagens['tokens.atualizados']).toBe(1);
  });
});
