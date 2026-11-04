import '@testing-library/jest-dom/vitest';

// jsdom não implementa scrollTo; ReportView rola para o topo ao montar.
if (typeof window.scrollTo !== 'function') {
  window.scrollTo = () => undefined;
}

// jsdom também não traz matchMedia — a sidebar consulta para o modo mobile.
if (typeof window.matchMedia !== 'function') {
  window.matchMedia = ((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => undefined,
    removeListener: () => undefined,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    dispatchEvent: () => false,
  })) as unknown as typeof window.matchMedia;
}
