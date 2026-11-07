import { describe, expect, it, vi, beforeEach } from 'vitest';
import {
  criarPesquisa,
  gravarApiKey,
  limparApiKey,
  lerConfig,
  obterPesquisa,
  salvarConfig,
} from '../services/apiV12';
import { urlDoStream } from '../services/ssePesquisa';

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status });
}

function mockFetch() {
  const chamadas: Array<{ url: string; headers: Record<string, string> }> = [];
  vi.stubGlobal(
    'fetch',
    ((entrada: string, init?: RequestInit) => {
      chamadas.push({
        url: String(entrada),
        headers: { ...((init?.headers ?? {}) as Record<string, string>) },
      });
      return Promise.resolve(jsonResponse({ ok: true }));
    }) as typeof fetch,
  );
  return chamadas;
}

beforeEach(() => {
  vi.unstubAllGlobals();
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
  limparApiKey();
});

describe('api key em todas as rotas + SSE', () => {
  it('criar/obter/ler/salvar enviam X-API-Key; SSE anexa ?api_key=', async () => {
    gravarApiKey('chave-aceita');
    const chamadas = mockFetch();

    await criarPesquisa({
      tema: 'tema de teste',
      profundidade: 3,
      veracidade_alvo: 80,
      callback_url: 'https://exemplo.com/hook',
    });
    await obterPesquisa('r1');
    await lerConfig();
    await salvarConfig({ max_spawn_depth: 3 } as never);

    expect(chamadas).toHaveLength(4);
    for (const c of chamadas) {
      expect(c.headers['X-API-Key']).toBe('chave-aceita');
    }
    expect(chamadas[0].url).toBe('/research');
    expect(chamadas[1].url).toBe('/research/r1');
    expect(chamadas[2].url).toBe('/config');
    expect(chamadas[3].url).toBe('/config');

    const stream = urlDoStream('r1', '9');
    expect(stream).toContain('desde=9');
    expect(stream).toContain('api_key=chave-aceita');

    limparApiKey();
    expect(urlDoStream('r1')).toBe('/research/r1/eventos');
  });
});
