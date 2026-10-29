import React, { useEffect, useState } from 'react';

type NodeId = 'plano' | 'busca' | 'auditoria' | 'redacao' | 'dossie';

interface GraphNode {
  id: NodeId;
  label: string;
  caption: string;
  detail: string;
  metric: string;
}

interface PlacedNode extends GraphNode {
  x: number;
  y: number;
  w: number;
}

const NODE_H = 52;

const NODES: GraphNode[] = [
  {
    id: 'plano',
    label: 'Plano',
    caption: 'N pontos',
    detail:
      'O tema vira um plano com pontos analíticos e critérios de aprovação. Cada ponto é uma pergunta que pode ser reprovada — não um tópico decorativo.',
    metric: '1 endpoint · N pontos',
  },
  {
    id: 'busca',
    label: 'Busca',
    caption: 'personas',
    detail:
      'As personas investigam em paralelo ou em sequência, cada uma com suas queries. O resultado é coletado por ponto, com a rodada de retries preservada para a auditoria.',
    metric: '4 personas · rodadas de retry',
  },
  {
    id: 'auditoria',
    label: 'Auditoria',
    caption: '12 crit.',
    detail:
      'Cada ponto é julgado contra critérios com nota. Abaixo do limiar, o ciclo volta para a busca com o motivo da reprovação; acima, segue para a redação.',
    metric: 'limiar 11/12 · até 3 auditorias',
  },
  {
    id: 'redacao',
    label: 'Redação',
    caption: 'fontes',
    detail:
      'O redator escreve apenas com evidência aprovada, marcando a origem de cada afirmação e mantendo a rastreabilidade até a URL canônica.',
    metric: '1 dossiê · fontes por afirmação',
  },
  {
    id: 'dossie',
    label: 'Dossiê',
    caption: 'rastreável',
    detail:
      'O resultado sai com pontos aprovados, fonte de cada trecho e o histórico de auditoria. Dá para reabrir, revisar e cobrar a origem de qualquer frase.',
    metric: 'aprovado · auditável',
  },
];

const EDGES: { from: NodeId; to: NodeId; loop?: boolean }[] = [
  { from: 'plano', to: 'busca' },
  { from: 'busca', to: 'auditoria' },
  { from: 'auditoria', to: 'redacao' },
  { from: 'redacao', to: 'dossie' },
  { from: 'auditoria', to: 'busca', loop: true },
];

const useNarrow = () => {
  const query = '(max-width: 640px)';
  const [narrow, setNarrow] = useState(() =>
    typeof window !== 'undefined' ? window.matchMedia(query).matches : false
  );
  useEffect(() => {
    const mql = window.matchMedia(query);
    const onChange = (e: MediaQueryListEvent) => setNarrow(e.matches);
    mql.addEventListener('change', onChange);
    setNarrow(mql.matches);
    return () => mql.removeEventListener('change', onChange);
  }, []);
  return narrow;
};

const place = (narrow: boolean): PlacedNode[] =>
  narrow
    ? NODES.map((n, i) => ({ ...n, x: 16, y: 10 + i * 88, w: 288 }))
    : NODES.map((n, i) => ({ ...n, x: [8, 152, 298, 444, 590][i], y: 118, w: 120 }));

const edgePath = (from: PlacedNode, to: PlacedNode, loop: boolean, narrow: boolean) => {
  if (narrow) {
    if (loop) {
      const ax = from.x + from.w;
      const ay = from.y + NODE_H / 2;
      const bx = to.x + to.w;
      const by = to.y + NODE_H / 2;
      return `M ${ax} ${ay} C ${ax + 26} ${ay}, ${bx + 26} ${by}, ${bx} ${by}`;
    }
    const ax = from.x + from.w / 2;
    const ay = from.y + NODE_H;
    const bx = to.x + to.w / 2;
    const by = to.y;
    return `M ${ax} ${ay} C ${ax} ${ay + 18}, ${bx} ${by - 18}, ${bx} ${by}`;
  }
  if (loop) {
    const ax = from.x + from.w / 2;
    const ay = from.y + NODE_H;
    const bx = to.x + to.w / 2;
    const by = to.y + NODE_H;
    return `M ${ax} ${ay} C ${ax - 20} ${ay + 74}, ${bx + 40} ${by + 74}, ${bx} ${by}`;
  }
  const ax = from.x + from.w;
  const ay = from.y + NODE_H / 2;
  const bx = to.x;
  const by = to.y + NODE_H / 2;
  const mid = (ax + bx) / 2;
  return `M ${ax} ${ay} C ${mid} ${ay}, ${mid} ${by}, ${bx} ${by}`;
};

/**
 * Grafo interativo da arquitetura e dos loops dos agentes. No desktop os cinco
 * estágios ficam em linha; no telefone empilham na vertical — sem rolagem
 * horizontal e sem rótulo cortado. SVG puro, foco por teclado, detalhe abaixo.
 */
export const ArchitectureGraph: React.FC = () => {
  const narrow = useNarrow();
  const [active, setActive] = useState<NodeId>('auditoria');
  const nodes = place(narrow);
  const byId = Object.fromEntries(nodes.map((n) => [n.id, n])) as Record<NodeId, PlacedNode>;
  const current = byId[active];
  const viewBox = narrow ? '0 0 320 468' : '0 0 720 316';

  const connected = (id: NodeId) =>
    EDGES.some((e) => (e.from === active && e.to === id) || (e.to === active && e.from === id));

  return (
    <section className="arch-graph" aria-labelledby="arch-graph-title">
      <header className="arch-graph-head">
        <h2 id="arch-graph-title">Como a investigação circula</h2>
        <p>Toque em um estágio para ver o que ele faz e o que o faz voltar.</p>
      </header>

      <div className="arch-graph-canvas" data-compact={narrow ? 'true' : 'false'}>
        <svg viewBox={viewBox} role="group" aria-label="Fluxo entre plano, busca, auditoria, redação e dossiê">
          <defs>
            <marker id="arch-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" className="arch-arrow-head" />
            </marker>
          </defs>

          {EDGES.map((e) => {
            const from = byId[e.from];
            const to = byId[e.to];
            const lit = active === e.from || active === e.to;
            return (
              <g key={`${e.from}-${e.to}`} className={`arch-edge ${e.loop ? 'is-loop' : ''} ${lit ? 'is-lit' : ''}`}>
                <path d={edgePath(from, to, Boolean(e.loop), narrow)} markerEnd="url(#arch-arrow)" />
              </g>
            );
          })}

          {nodes.map((n) => {
            const isActive = active === n.id;
            return (
              <g
                key={n.id}
                className={`arch-node ${isActive ? 'is-active' : ''} ${connected(n.id) ? 'is-near' : ''}`}
                tabIndex={0}
                role="button"
                aria-pressed={isActive}
                aria-label={`${n.label}: ${n.caption}`}
                onClick={() => setActive(n.id)}
                onKeyDown={(ev) => {
                  if (ev.key === 'Enter' || ev.key === ' ') {
                    ev.preventDefault();
                    setActive(n.id);
                  }
                }}
                transform={`translate(${n.x}, ${n.y})`}
              >
                <rect className="arch-node-box" width={n.w} height={NODE_H} rx="10" />
                {isActive && <rect className="arch-node-bar" width="2.5" height="34" x="0" y="9" rx="1.2" />}
                <text className="arch-node-label" x="14" y="22">{n.label}</text>
                <text className="arch-node-caption" x="14" y="39">{n.caption}</text>
              </g>
            );
          })}
        </svg>
      </div>

      <div className="arch-detail" aria-live="polite">
        <div className="arch-detail-head">
          <h3>{current.label}</h3>
          <span className="arch-metric">{current.metric}</span>
        </div>
        <p>{current.detail}</p>
      </div>
    </section>
  );
};
