import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { ResearchRun } from '../services/apiV12';
import { gravarApiKey, limparApiKey } from '../services/apiV12';
import {
  assinarEventosPesquisa,
  chaveUltimoEvento,
  gravarUltimoEventoId,
  lerUltimoEventoId,
  urlDoStream,
} from '../services/ssePesquisa';

/* EventSource falso: cada instância tem seus listeners; dá para disparar eventos. */

type Ouvinte = (ev: { data?: string; lastEventId?: string; type?: string }) => void;

interface InstanciaFalsa {
  url: string;
  fechado: boolean;
  onmessage: Ouvinte | null;
  onopen: Ouvinte | null;
  onerror: Ouvinte | null;
  disparar(tipo: string, dados: unknown, id: string): void;
}

function criarEventSourceFalso() {
  const instancias: InstanciaFalsa[] = [];
  const Impl = class {
    url: string;
    onmessage: Ouvinte | null = null;
    onopen: Ouvinte | null = null;
    onerror: Ouvinte | null = null;
    fechado = false;
    private ouvintes = new Map<string, Ouvinte[]>();
    constructor(url: string) {
      this.url = url;
      instancias.push(this as unknown as InstanciaFalsa);
    }
    addEventListener(tipo: string, fn: Ouvinte) {
      const lista = this.ouvintes.get(tipo) ?? [];
      lista.push(fn);
      this.ouvintes.set(tipo, lista);
    }
    close() {
      this.fechado = true;
    }
    disparar(tipo: string, dados: unknown, id: string) {
      const lista = this.ouvintes.get(tipo) ?? [];
      const ev = {
        data: typeof dados === 'string' ? dados : JSON.stringify(dados),
        lastEventId: id,
        type: tipo,
      };
      for (const fn of lista) fn(ev);
    }
  };
  return { Impl: Impl as unknown as typeof EventSource, instancias };
}

beforeEach(() => {
  const mem = new Map<string, string>();
  Object.defineProperty(globalThis, 'localStorage', {
    configurable: true,
    value: {
      getItem: (k: string) => (mem.has(k) ? mem.get(k)! : null),
      setItem: (k: string, v: string) => void mem.set(k, String(v)),
      removeItem: (k: string) => void mem.delete(k),
      clear: () => mem.clear(),
    },
  });
  Object.defineProperty(window, 'localStorage', {
    configurable: true,
    value: globalThis.localStorage,
  });
  vi.useFakeTimers();
  return () => {
    vi.useRealTimers();
  };
});

describe('ssePesquisa', () => {
  it('urlDoStream codifica o id e anexa ?desde=', () => {
    limparApiKey();
    expect(urlDoStream('a/b')).toBe('/research/a%2Fb/eventos');
    expect(urlDoStream('a/b', '42')).toBe('/research/a%2Fb/eventos?desde=42');
  });

  it('urlDoStream inclui api_key quando há chave; reconexão mantém', () => {
    gravarApiKey('k-segredo');
    const url = urlDoStream('a/b', '42');
    expect(url).toContain('/research/a%2Fb/eventos?');
    expect(url).toContain('desde=42');
    expect(url).toContain('api_key=k-segredo');
    limparApiKey();
  });

  it('persiste lastEventId em localStorage por research_id', () => {
    expect(lerUltimoEventoId('r1')).toBeNull();
    gravarUltimoEventoId('r1', '7');
    expect(lerUltimoEventoId('r1')).toBe('7');
    expect(localStorage.getItem(chaveUltimoEvento('r1'))).toBe('7');
  });

  it('reabre com ?desde= após erro e trata snapshot', () => {
    const falso = criarEventSourceFalso();
    const tipos: string[] = [];
    const dadosRecebidos: unknown[] = [];
    const sub = assinarEventosPesquisa('r9', {
      implEventSource: falso.Impl,
      intervaloReconexaoMs: 2000,
      aoEvento: (ev) => {
        tipos.push(ev.tipo);
        dadosRecebidos.push(ev.dados);
      },
    });
    expect(falso.instancias).toHaveLength(1);
    expect(falso.instancias[0].url).toBe('/research/r9/eventos');

    // Snapshot inicial guarda o lastEventId.
    falso.instancias[0].disparar('snapshot', { research_id: 'r9', status: 'PROCESSING' }, '3');
    expect(tipos).toEqual(['snapshot']);
    expect(lerUltimoEventoId('r9')).toBe('3');
    expect((dadosRecebidos[0] as ResearchRun).research_id).toBe('r9');

    // Erro: reabre após 2s com ?desde=3.
    falso.instancias[0].onerror?.({});
    vi.advanceTimersByTime(2000);
    expect(falso.instancias).toHaveLength(2);
    expect(falso.instancias[1].url).toBe('/research/r9/eventos?desde=3');

    // Voltar online reabre do ponto atual.
    falso.instancias[1].disparar('tokens.atualizados', { total_tokens: 10 }, '4');
    window.dispatchEvent(new Event('online'));
    expect(falso.instancias).toHaveLength(3);
    expect(falso.instancias[2].url).toBe('/research/r9/eventos?desde=4');

    sub.fechar();
    vi.useRealTimers();
  });

  it('para de reconectar após o limite (sem loop infinito em 404)', () => {
    const falso = criarEventSourceFalso();
    let esgotou = 0;
    const sub = assinarEventosPesquisa('r404', {
      implEventSource: falso.Impl,
      intervaloReconexaoMs: 1000,
      maxTentativasReconexao: 3,
      aoEsgotar: () => {
        esgotou += 1;
      },
    });
    expect(falso.instancias).toHaveLength(1);
    expect(sub.tentativas()).toBe(0);
    // 3 erros seguidos: reabre 2x, na 3ª esgota e para.
    falso.instancias[0].onerror?.({});
    expect(sub.tentativas()).toBe(1);
    vi.advanceTimersByTime(1000);
    expect(falso.instancias).toHaveLength(2);
    falso.instancias[1].onerror?.({});
    vi.advanceTimersByTime(1000);
    expect(falso.instancias).toHaveLength(3);
    falso.instancias[2].onerror?.({});
    expect(esgotou).toBe(1);
    expect(sub.tentativas()).toBe(3);
    vi.advanceTimersByTime(5000);
    expect(falso.instancias).toHaveLength(3);
    sub.fechar();
    vi.useRealTimers();
  });

  it('R5: padrão novo é 4 tentativas; GET-404 imediato esgota no 1º erro', async () => {
    const falso = criarEventSourceFalso();
    let esgotou = 0;
    const sub = assinarEventosPesquisa('r-suma', {
      implEventSource: falso.Impl,
      intervaloReconexaoMs: 1000,
      verificarSumico: () => Promise.reject(new Error('404')),
      aoEsgotar: () => {
        esgotou += 1;
      },
    });
    falso.instancias[0].onerror?.({});
    expect(sub.tentativas()).toBe(1);
    await Promise.resolve();
    await Promise.resolve();
    expect(esgotou).toBe(1);
    // Nada reagenda após o sumiço confirmado.
    vi.advanceTimersByTime(10000);
    expect(falso.instancias).toHaveLength(1);
    sub.fechar();
    vi.useRealTimers();
  });

  it('R5: verificarSumico OK mantém a reconexão para falha transitória', async () => {
    const falso = criarEventSourceFalso();
    let esgotou = 0;
    const sub = assinarEventosPesquisa('r-volta', {
      implEventSource: falso.Impl,
      intervaloReconexaoMs: 1000,
      verificarSumico: () => Promise.resolve({ status: 'PROCESSING' }),
      aoEsgotar: () => {
        esgotou += 1;
      },
    });
    falso.instancias[0].onerror?.({});
    await Promise.resolve();
    await Promise.resolve();
    vi.advanceTimersByTime(1000);
    expect(falso.instancias).toHaveLength(2);
    expect(esgotou).toBe(0);
    sub.fechar();
    vi.useRealTimers();
  });
});
