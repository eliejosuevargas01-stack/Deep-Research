/**
 * Sanitização de URL de fonte — espelho de `app/core/urls.py`.
 *
 * Os logs dos subagentes entram no feed como texto; sem isso viram link
 * `https://^` ou `https://epe.gov.br/relatorio\nAirbnb`.
 */

const ESCAPE_LITERAL = /\\[nrt]/;
const PONTUACAO_FINAL = /[.,;:!?)\]}'"]+$/;
const HOST_INVALIDO = /[\s^/{};\\<>|@]/;
const BUSCA_INTERNA = ['duckduckgo.com', 'mojeek.com', 'html.duckduckgo.com'];

export function sanitizarUrlFonte(raw: unknown): string | null {
  if (typeof raw !== 'string') return null;
  let texto = raw.trim();
  if (!texto) return null;
  texto = texto.split(ESCAPE_LITERAL)[0].trim();
  if (!texto) return null;
  texto = texto.split(/\s+/)[0].replace(PONTUACAO_FINAL, '');
  if (!texto) return null;
  let url: URL;
  try {
    url = new URL(texto);
  } catch {
    return null;
  }
  if (url.protocol !== 'http:' && url.protocol !== 'https:') return null;
  const host = url.hostname.toLowerCase().replace(/\.$/, '');
  if (!host || HOST_INVALIDO.test(host) || !host.includes('.')) return null;
  const tld = host.slice(host.lastIndexOf('.') + 1);
  if (!/^[a-z]{2,24}$/.test(tld)) return null;
  if (BUSCA_INTERNA.includes(host) || host.endsWith('.duckduckgo.com') || host.endsWith('.mojeek.com')) return null;
  if (url.pathname.toLowerCase().includes('/w/api.php')) return null;
  return url.toString();
}
