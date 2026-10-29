/**
 * Congela animações SMIL sob `prefers-reduced-motion: reduce`.
 *
 * O CSS cobre `animation` e `transition`, mas SMIL (`<animate>`,
 * `animateTransform`, `animateMotion`) NÃO é estilizável: nenhuma regra de
 * `@media (prefers-reduced-motion: reduce)` alcança a timeline SMIL. Sem
 * `pauseAnimations()` os anéis de progresso dos ícones continuam girando para
 * quem pediu menos movimento (medido: `svg.getCurrentTime()` avançando
 * 8 -> 9 em ~0,9s sob `reduce`).
 *
 * O MutationObserver cobre SVGs que montam depois do boot (troca de rota,
 * streaming do feed) — só congela quando a query casa.
 */
const QUERY = '(prefers-reduced-motion: reduce)';

/** Coleta os <svg> com filhos SMIL dentro de `root` (sem duplicatas). */
function svgsComSmil(root: ParentNode): SVGSVGElement[] {
  const encontrados = new Set<SVGSVGElement>();

  const considerar = (svg: Element) => {
    if (svg.tagName.toLowerCase() !== 'svg') return;
    if (!svg.querySelector('animate, animateTransform, animateMotion')) return;
    encontrados.add(svg as unknown as SVGSVGElement);
  };

  if (root instanceof Element) considerar(root);
  root.querySelectorAll?.('svg').forEach(considerar);

  return [...encontrados];
}

/** Pausa (ou retoma) todos os SVGs com SMIL do documento. */
function congelar(reduzido: boolean): void {
  svgsComSmil(document).forEach((svg) => {
    try {
      if (reduzido) svg.pauseAnimations();
      else svg.unpauseAnimations();
    } catch {
      /* navegador sem suporte a SMIL: nada a fazer */
    }
  });
}

/** Liga/desliga o congelamento de SMIL. Retorna a função de cleanup. */
export function initReducedMotionSMIL(): () => void {
  const mq = window.matchMedia(QUERY);
  congelar(mq.matches);

  const aoMudar = () => congelar(mq.matches);
  mq.addEventListener('change', aoMudar);

  // SVG montado depois do boot (rota nova, item do feed) já nasce congelado.
  const observador = new MutationObserver((mutacoes) => {
    if (!mq.matches) return;
    for (const mutacao of mutacoes) {
      mutacao.addedNodes.forEach((no) => {
        if (no.nodeType !== Node.ELEMENT_NODE) return;
        svgsComSmil(no as Element).forEach((svg) => {
          try {
            svg.pauseAnimations();
          } catch {
            /* noop */
          }
        });
      });
    }
  });
  observador.observe(document.body, { childList: true, subtree: true });

  return () => {
    mq.removeEventListener('change', aoMudar);
    observador.disconnect();
  };
}
