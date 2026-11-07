/**
 * Storage do histórico bloqueado não pode falhar em silêncio.
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { historyService } from '../services/history';
import type { ResearchHistoryRecord } from '../types/api';

function comStorage(impl: Partial<Storage>): void {
  Object.defineProperty(globalThis, 'localStorage', {
    configurable: true,
    value: impl,
  });
}

const registro: ResearchHistoryRecord = {
  id_pesquisa: 'teste-storage-1',
  tema: 'Automação bancária no Brasil',
  status: 'concluido',
  criado_em: new Date().toISOString(),
  total_pontos: 3,
};

test('save avisa o handler quando o storage recusa a gravação', () => {
  const avisos: string[] = [];
  historyService.setFalhaHandler((m) => avisos.push(m));
  comStorage({
    getItem: () => null,
    setItem: () => {
      throw new DOMException('QuotaExceededError');
    },
    removeItem: () => undefined,
  });

  historyService.save(registro);

  assert.equal(avisos.length, 1);
  assert.match(avisos[0], /histórico do navegador/);
  historyService.setFalhaHandler(null);
});

test('remove e clear também avisam quando o storage falha', () => {
  const avisos: string[] = [];
  historyService.setFalhaHandler((m) => avisos.push(m));
  comStorage({
    getItem: () => '[]',
    setItem: () => {
      throw new Error('storage bloqueado');
    },
    removeItem: () => {
      throw new Error('storage bloqueado');
    },
  });

  historyService.remove('teste-storage-1');
  historyService.clear();

  assert.equal(avisos.length, 2);
  historyService.setFalhaHandler(null);
});

test('sem handler registrado a falha não quebra a chamada', () => {
  comStorage({
    getItem: () => null,
    setItem: () => {
      throw new Error('storage bloqueado');
    },
    removeItem: () => undefined,
  });

  assert.doesNotThrow(() => historyService.save(registro));
});
