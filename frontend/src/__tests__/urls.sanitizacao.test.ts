import { describe, expect, it } from 'vitest';
import { sanitizarUrlFonte } from '../utils/urls';

describe('sanitizarUrlFonte — lixo do feed de raciocínio', () => {
  it.each([
    ['https://^'],
    ['https:///;'],
    ['https://{host}/w/api.php?'],
    ['https://^/x'],
    ['https://html.duckduckgo.com/html/?q=teste'],
    ['ftp://arquivo.invalid/x'],
  ])('test_rejeita_url_invalida_%s', (bruta) => {
    expect(sanitizarUrlFonte(bruta)).toBeNull();
  });

  it('test_corta_quebra_de_linha_e_texto_colado_na_url', () => {
    expect(sanitizarUrlFonte('https://epe.gov.br/relatorio\nAirbnb')).toBe(
      'https://epe.gov.br/relatorio'
    );
    expect(sanitizarUrlFonte('https://epe.gov.br/relatorio Airbnb')).toBe(
      'https://epe.gov.br/relatorio'
    );
  });

  it('test_preserva_url_valida', () => {
    expect(sanitizarUrlFonte('https://epe.gov.br/relatorio')).toBe('https://epe.gov.br/relatorio');
    expect(sanitizarUrlFonte('HTTPS://EPE.GOV.BR/relatorio')).toBe('https://epe.gov.br/relatorio');
  });
});
