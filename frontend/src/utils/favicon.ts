/**
 * Cadeia de favicons por domínio.
 *
 * O endpoint do Google responde 301 para `t*.gstatic.com/faviconV2`, que
 * devolve 404 para vários domínios públicos (bcb.gov.br, ibge.gov.br). Sem
 * cadeia, todo chip cai no tile com a inicial e o requisito "favicon
 * automático do domínio" nunca é cumprido de fato.
 *
 * Ordem: Google (melhor cobertura para marcas grandes) -> DuckDuckGo ->
 * /favicon.ico do próprio domínio -> tile com a inicial (CSS).
 */
export function faviconCandidates(dominio: string, size = 64): string[] {
  const host = dominio.replace(/^https?:\/\//i, '').replace(/\/.*$/, '');
  return [
    `https://www.google.com/s2/favicons?domain=${encodeURIComponent(host)}&sz=${size}`,
    `https://icons.duckduckgo.com/ip3/${host}.ico`,
    `https://${host}/favicon.ico`,
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
