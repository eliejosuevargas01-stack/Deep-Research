import '@testing-library/jest-dom/vitest';

// jsdom não implementa scrollTo; ReportView rola para o topo ao montar.
if (typeof window.scrollTo !== 'function') {
  window.scrollTo = () => undefined;
}
