/**
 * Cadeia de favicons por domínio.
 *
 * Ordem: DuckDuckGo -> Google (com domínio normalizado) -> /favicon.ico do próprio domínio -> tile com a inicial (CSS).
 */
export function faviconCandidates(dominio: string, size = 64): string[] {
  const host = dominio
    .replace(/^https?:\/\//i, '')
    .replace(/\/.*$/, '')
    .replace(/^www\./i, '');
  const httpsHost = host;
  return [
    `https://icons.duckduckgo.com/ip3/${httpsHost}.ico`,
    `https://www.google.com/s2/favicons?domain=${encodeURIComponent(httpsHost)}&sz=${size}`,
    `https://${httpsHost}/favicon.ico`,
  ];
}

/**
 * 404 do Google chega como `load` com naturalWidth 0 (o corpo é HTML), então
 * `onError` sozinho nunca dispara: sem tratar isso a cadeia morria no item 1.
 */
export function onFaviconLoad(event: { currentTarget: HTMLImageElement }): void {
  const img = event.currentTarget;
  if (img.naturalWidth > 0) {
    img.classList.add('is-loaded');
    img.style.display = '';
    return;
  }
  onFaviconError(event);
}

/** Avança a cadeia; quando esgota, esconde o <img> e deixa o tile aparecer. */
export function onFaviconError(event: { currentTarget: HTMLImageElement }): void {
  const img = event.currentTarget;
  const chain = (img.dataset.faviconChain || '').split('|').filter(Boolean);
  const next = chain.shift();
  if (next) {
    img.dataset.faviconChain = chain.join('|');
    img.src = next;
    return;
  }
  img.style.display = 'none';
}
