import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AppV12 } from '../v12/AppV12';
import { CHAVE_API_KEY } from '../services/apiV12';

function mockBackend() {
  (globalThis as unknown as { fetch: typeof fetch }).fetch = ((entrada: string, init?: RequestInit) => {
    const url = String(entrada);
    const headers = (init?.headers ?? {}) as Record<string, string>;
    const resp = (corpo: unknown, status: number, ok: boolean) =>
      ({ ok, status, json: async () => corpo }) as Response;
    if (url.endsWith('/research') && init?.method === 'POST') {
      if (headers['X-API-Key'] !== 'test-api-key') {
        return Promise.resolve(resp({ detail: 'não' }, 401, false));
      }
      return Promise.resolve(resp({ research_id: 'r1', status: 'PROCESSING' }, 202, true));
    }
    if (url.includes('/research/r1/eventos')) {
      return Promise.resolve(resp({}, 404, false));
    }
    if (url.endsWith('/research/r1')) {
      return Promise.resolve(
        resp(
          {
            research_id: 'r1',
            tema: 'tema teste',
            profundidade: 3,
            veracidade_alvo: 80,
            max_rodadas_auditoria: 4,
            atualidade: 'ALL',
            callback_url: '',
            status: 'PROCESSING',
          },
          200,
          true,
        ),
      );
    }
    if (url.endsWith('/config')) {
      if (headers['X-API-Key'] !== 'test-api-key') {
        return Promise.resolve(resp({ detail: 'não' }, 401, false));
      }
      return Promise.resolve(
        resp(
          {
            base_url: 'https://x',
            api_key: '',
            default_model: 'm',
            max_concurrent_children: 40,
            max_spawn_depth: 2,
            oneshot_max_children: 0,
            modelos_por_papel: {},
          },
          200,
          true,
        ),
      );
    }
    return Promise.resolve(resp({}, 200, true));
  }) as typeof fetch;
}

beforeEach(() => {
  const mem = new Map<string, string>();
  const store = {
    getItem: (k: string) => (mem.has(k) ? mem.get(k)! : null),
    setItem: (k: string, v: string) => void mem.set(k, String(v)),
    removeItem: (k: string) => void mem.delete(k),
    clear: () => mem.clear(),
    get length() {
      return mem.size;
    },
    key: (i: number) => [...mem.keys()][i] ?? null,
  };
  Object.defineProperty(globalThis, 'localStorage', { configurable: true, value: store });
  Object.defineProperty(window, 'localStorage', { configurable: true, value: store });
  store.clear();
  window.location.hash = '#research';
  mockBackend();
  // jsdom sem EventSource: stub mínimo que nunca abre (hook segue via GET).
  vi.stubGlobal(
    'EventSource',
    class {
      url: string;
      onmessage: null = null;
      onopen: null = null;
      onerror: null = null;
      constructor(url: string) {
        this.url = url;
      }
      addEventListener() {}
      close() {}
    } as unknown as typeof EventSource,
  );
});

describe('AppV12 shell', () => {
  it('renderiza casca: sidebar, navbar, hero e navegação por hash', async () => {
    const user = userEvent.setup();
    render(<AppV12 />);
    // Sidebar (desktop) + navbar (mobile) + hero do estado vazio.
    expect(screen.getByRole('complementary', { name: 'Navegação lateral' })).toBeInTheDocument();
    expect(screen.getByRole('banner')).toBeInTheDocument();
    expect(screen.getByText('O que vamos investigar hoje?')).toBeInTheDocument();
    const novas = screen.getAllByRole('button', { name: 'Nova pesquisa' });
    expect(novas.length).toBeGreaterThanOrEqual(2);

    // Hero preenche o formulário preservando os campos atuais.
    await user.click(screen.getByRole('button', { name: /matriz energética brasil/i }));
    expect(screen.getByLabelText('Tema')).toHaveValue('Matriz energética Brasil');
    expect(screen.getByLabelText(/Profundidade/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Veracidade alvo/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Rodadas de auditoria/)).toBeInTheDocument();
    expect(screen.getByLabelText('Atualidade')).toBeInTheDocument();
    expect(screen.getByLabelText('callback_url')).toBeInTheDocument();

    // Navegação por hash: sidebar reflete a rota.
    const lateral = screen.getByRole('complementary', { name: 'Navegação lateral' });
    await user.click(within(lateral).getByRole('button', { name: 'Histórico' }));
    await waitFor(() => expect(window.location.hash).toBe('#history'));
    expect(screen.getByText('Nenhuma pesquisa ainda')).toBeInTheDocument();
  });
});

describe('ApiKeyGateV12', () => {
  it('sem chave mostra gate; salvar dispara GET /config com X-API-Key', async () => {
    const user = userEvent.setup();
    const chamadas: Array<{ url: string; headers: Record<string, string> }> = [];
    const fetchReal = globalThis.fetch;
    (globalThis as unknown as { fetch: typeof fetch }).fetch = ((entrada: string, init?: RequestInit) => {
      chamadas.push({ url: String(entrada), headers: { ...((init?.headers ?? {}) as object) } as Record<string, string> });
      return fetchReal(entrada as unknown as RequestInfo | URL, init);
    }) as typeof fetch;

    render(<AppV12 />);
    expect(await screen.findByTestId('api-key-gate')).toBeInTheDocument();

    await user.type(screen.getByLabelText('API key do backend'), 'test-api-key');
    await user.click(screen.getByRole('button', { name: 'Salvar e testar' }));
    await waitFor(() =>
      expect(screen.getByTestId('api-key-ativa')).toBeInTheDocument(),
    );
    expect(localStorage.getItem(CHAVE_API_KEY)).toBe('test-api-key');
    const getConfig = chamadas.filter((c) => c.url.endsWith('/config') && !c.url.includes('modelos'));
    expect(getConfig.length).toBeGreaterThan(0);
    expect(
      getConfig.every((c) => c.headers['X-API-Key'] === 'test-api-key'),
    ).toBe(true);
  });

  it('com chave salva mostra estado ativo e botão trocar', async () => {
    localStorage.setItem(CHAVE_API_KEY, 'test-api-key');
    const user = userEvent.setup();
    render(<AppV12 />);
    expect(await screen.findByTestId('api-key-ativa')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Trocar chave' }));
    expect(await screen.findByTestId('api-key-gate')).toBeInTheDocument();
  });
});
