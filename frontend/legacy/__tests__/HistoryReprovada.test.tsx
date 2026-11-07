import { describe, expect, it } from 'vitest';
import { deveMostrarDossie, naoRebaixarDossie, resolverEstagioInicial } from '../utils/estagio';

describe('pesquisa reprovada que redigiu o dossiê', () => {
  it('abre o relatório em vez da tela de auditoria reprovada', () => {
    expect(deveMostrarDossie('reprovado', true)).toBe(true);
    expect(deveMostrarDossie('reprovado', false)).toBe(false);
    expect(deveMostrarDossie('falha', true)).toBe(true);
    expect(deveMostrarDossie('concluido', false)).toBe(true);
    expect(resolverEstagioInicial('concluido', true)).toBe('completed');
    // Replay do SSE com status antigo não desmonta o dossiê.
    expect(naoRebaixarDossie('completed', 'rejected')).toBe('completed');
    expect(naoRebaixarDossie('auditing', 'rejected')).toBe('rejected');
  });
});
