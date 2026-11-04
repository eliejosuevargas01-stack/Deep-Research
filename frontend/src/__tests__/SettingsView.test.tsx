import { render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { PAPEIS_MODELO, SettingsView, initialSettingsFormData } from '../components/SettingsView';

const jsonResponse = (corpo: unknown) =>
  ({ ok: true, json: async () => corpo, status: 200 }) as unknown as Response;

beforeEach(() => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (entrada: RequestInfo | URL) => {
      const url = String(entrada);
      if (url.includes('/admin/credentials')) return jsonResponse({ credenciais: [] });
      if (url.includes('/settings/hermes')) {
        return jsonResponse({
          openai_base_url: 'https://llm.exemplo.com/v1',
          tem_api_key: true,
          modelo_padrao: 'modelo-base',
          modelos_por_papel: { planejador: 'modelo-base', auditor: 'modelo-audit' },
        });
      }
      return jsonResponse({});
    })
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('SettingsView', () => {
  it('test_settings_view_nao_exibe_campos_jina_e_renderiza_modelos_por_subagente', () => {
    render(<SettingsView draft={{ ...initialSettingsFormData }} onDraftChange={() => undefined} />);

    const texto = document.body.textContent ?? '';
    expect(texto).not.toMatch(/JINA/i);
    expect(screen.queryByLabelText(/JINA/i)).toBeNull();

    for (const [, rotulo] of PAPEIS_MODELO) {
      expect(screen.getByText(rotulo)).toBeInTheDocument();
    }
    expect(screen.getByLabelText('Auditor (12 critérios)')).toBeInTheDocument();
    expect(screen.getByLabelText('Redator do dossiê')).toBeInTheDocument();
  });
});
