import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { SettingsView } from '../v12/SettingsV12';

const jsonResponse = (corpo: unknown) =>
  ({ ok: true, json: async () => corpo, status: 200 }) as unknown as Response;

function mockConfig(salvos: unknown[] = []) {
  const cfg = {
    base_url: 'https://llm.exemplo.com/v1',
    api_key: '',
    default_model: 'modelo-base',
    max_concurrent_children: 40,
    max_spawn_depth: 2,
    oneshot_max_children: 0,
    modelos_por_papel: { auditor: 'm-audit' },
  };
  (globalThis as unknown as { fetch: typeof fetch }).fetch = (async (entrada: unknown, init?: RequestInit) => {
    const url = String(entrada);
    if (url.endsWith('/config') && (!init || !init.method || init.method === 'GET')) {
      return jsonResponse(cfg);
    }
    if (url.endsWith('/config') && init?.method === 'PUT') {
      const corpo = JSON.parse(String(init.body));
      salvos.push(corpo);
      return jsonResponse({ ...cfg, ...corpo });
    }
    return jsonResponse({});
  }) as typeof fetch;
  return salvos;
}

describe('SettingsV12', () => {
  it('mostra base_url como leitura e nunca expõe campo de api_key do provedor', async () => {
    mockConfig();
    render(<SettingsView />);
    await waitFor(() => expect(screen.getByText('Configuração')).toBeInTheDocument());
    // base_url aparece como texto (definido por ambiente), sem input editável.
    const base = screen.getByTestId('v12-base-url');
    expect(base.textContent).toContain('https://llm.exemplo.com/v1');
    expect(base.textContent).toContain('definido por ambiente');
    expect(screen.queryByLabelText(/base_url/)).toBeNull();
    expect(screen.queryByLabelText(/api_key \(em branco/)).toBeNull();
    // API key do backend (navegador) continua existindo, separada do provedor.
    expect(screen.getByLabelText(/API key do backend/)).toBeInTheDocument();
  });

  it('PUT /config nunca envia base_url/api_key e barra limites < 1', async () => {
    const salvos: unknown[] = [];
    mockConfig(salvos);
    const user = userEvent.setup();
    render(<SettingsView />);
    await waitFor(() => expect(screen.getByLabelText('max_concurrent_children')).toBeInTheDocument());

    await user.clear(screen.getByLabelText('max_concurrent_children'));
    await user.type(screen.getByLabelText('max_concurrent_children'), '0');
    await user.click(screen.getByRole('button', { name: 'Salvar' }));
    await waitFor(() =>
      expect(screen.getByRole('alert').textContent).toMatch(/max_concurrent_children.*≥ 1/),
    );
    expect(salvos).toHaveLength(0);

    await user.clear(screen.getByLabelText('max_concurrent_children'));
    await user.type(screen.getByLabelText('max_concurrent_children'), '8');
    await user.click(screen.getByRole('button', { name: 'Salvar' }));
    await waitFor(() => expect(salvos).toHaveLength(1));
    const corpo = salvos[0] as Record<string, unknown>;
    expect(corpo).not.toHaveProperty('base_url');
    expect(corpo).not.toHaveProperty('api_key');
    expect(corpo.max_concurrent_children).toBe(8);
  });
});
