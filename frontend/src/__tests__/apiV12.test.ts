import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  CHAVE_API_KEY,
  MENSAGEM_401,
  criarPesquisa,
  ehErroApiKey,
  gravarApiKey,
  lerApiKey,
  lerConfig,
  limparApiKey,
  obterPesquisa,
  salvarConfig,
  ApiV12Error,
} from '../services/apiV12';

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
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
});

describe('apiV12', () => {
  it('criarPesquisa faz POST /research e devolve research_id', async () => {
    const fetchMock = vi.fn(async () => jsonResponse({ research_id: 'abc', status: 'PROCESSING' }, 202));
    vi.stubGlobal('fetch', fetchMock);
    const res = await criarPesquisa({
      tema: 'tema de teste',
      profundidade: 3,
      veracidade_alvo: 80,
      callback_url: 'https://exemplo.com/hook',
    });
    expect(res.research_id).toBe('abc');
    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe('/research');
    expect(init.method).toBe('POST');
    expect(JSON.parse(String(init.body)).tema).toBe('tema de teste');
  });

  it('obterPesquisa faz GET /research/{id} com id codificado', async () => {
    const fetchMock = vi.fn(async () => jsonResponse({ research_id: 'a/b', status: 'PROCESSING' }));
    vi.stubGlobal('fetch', fetchMock);
    await obterPesquisa('a/b');
    const primeira = fetchMock.mock.calls[0] as unknown as [string];
    expect(primeira[0]).toBe('/research/a%2Fb');
  });

  it('lerConfig faz GET /config', async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse({ base_url: 'https://x', modelos_por_papel: {} }),
    );
    vi.stubGlobal('fetch', fetchMock);
    await lerConfig();
    const chamada = fetchMock.mock.calls[0] as unknown as [string];
    expect(chamada[0]).toBe('/config');
  });

  it('salvarConfig faz PUT /config com patch parcial', async () => {
    const fetchMock = vi.fn(async () => jsonResponse({ base_url: 'https://x' }));
    vi.stubGlobal('fetch', fetchMock);
    await salvarConfig({ max_spawn_depth: 3 } as never);
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe('/config');
    expect(init.method).toBe('PUT');
    expect(JSON.parse(String(init.body)).max_spawn_depth).toBe(3);
  });

  it('propaga mensagem do detail do FastAPI (incluindo lista de 422)', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        jsonResponse({ detail: [{ loc: ['body', 'tema'], msg: 'tema curto', type: 'x' }] }, 422),
      ),
    );
    await expect(
      criarPesquisa({
        tema: 'ab',
        profundidade: 3,
        veracidade_alvo: 80,
        callback_url: 'https://exemplo.com/hook',
      }),
    ).rejects.toMatchObject({ message: 'tema curto', status: 422 });
  });

  it('detail string vira a mensagem do erro', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse({ detail: 'não encontrada' }, 404)));
    const err = (await obterPesquisa('x').catch((e: unknown) => e)) as ApiV12Error;
    expect(err).toBeInstanceOf(ApiV12Error);
    expect(err.message).toBe('não encontrada');
    expect(err.status).toBe(404);
  });

  it('falha de rede vira ApiV12Error com status 0', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        throw new Error('down');
      }),
    );
    const err = (await lerConfig().catch((e: unknown) => e)) as ApiV12Error;
    expect(err).toBeInstanceOf(ApiV12Error);
    expect(err.status).toBe(0);
  });

  it('envia X-API-Key quando há chave salva; sem chave, sem header', async () => {
    gravarApiKey('segredo-123');
    const fetchMock = vi.fn(async () => jsonResponse({ base_url: 'https://x' }));
    vi.stubGlobal('fetch', fetchMock);
    await lerConfig();
    const [, initCom] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect((initCom.headers as Record<string, string>)['X-API-Key']).toBe('segredo-123');

    limparApiKey();
    fetchMock.mockClear();
    await lerConfig();
    const [, initSem] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect((initSem.headers as Record<string, string>)['X-API-Key']).toBeUndefined();
  });

  it('401 vira mensagem clara de API key; chave persiste em dr:v12:apiKey', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse({ detail: 'não' }, 401)));
    const err = (await obterPesquisa('x').catch((e: unknown) => e)) as ApiV12Error;
    expect(err.status).toBe(401);
    expect(err.message).toBe(MENSAGEM_401);
    expect(ehErroApiKey(err)).toBe(true);

    gravarApiKey('k');
    expect(lerApiKey()).toBe('k');
    expect(localStorage.getItem(CHAVE_API_KEY)).toBe('k');
    limparApiKey();
    expect(lerApiKey()).toBeNull();
  });
});
