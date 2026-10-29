import React from 'react';
import { Compass, Sparkles, ArrowRight } from 'lucide-react';

interface EmptyStateProps {
  onSelectTopic: (topic: string) => void;
}

const SAMPLE_TOPICS = [
  {
    title: 'O futuro da matriz energética no Brasil',
    description: 'Transição para fontes renováveis, hidrogênio verde, segurança energética e investimentos até 2035.',
  },
  {
    title: 'Impacto da IA generativa no mercado de trabalho de TI',
    description: 'Produtividade de desenvolvedores, demanda por novas competências e automação de código no cenário global.',
  },
  {
    title: 'Avanços e viabilidade comercial da fusão nuclear',
    description: 'Confinamento magnético, projetos ITER e SPARC, marcos científicos recentes e cronogramas de operação.',
  },
  {
    title: 'Regulação global de Inteligência Artificial',
    description: 'Comparativo entre AI Act da União Europeia, diretrizes dos EUA e o marco regulatório brasileiro (PL 2338).',
  },
];

export const EmptyState: React.FC<EmptyStateProps> = ({ onSelectTopic }) => {
  return (
    <section className="empty-state" aria-labelledby="empty-state-title">
      <div className="empty-state-badge" aria-hidden="true">
        <Compass size={24} />
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        <h1 id="empty-state-title" className="empty-state-title">
          Investigue a fundo. Audite cada ponto.
        </h1>
        <p className="empty-state-text">
          Plano, evidência auditada, dossiê: cada frase com sua fonte.
        </p>
      </div>

      <div style={{ width: '100%', marginTop: '8px' }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            marginBottom: '12px',
            fontSize: '0.85rem',
            fontWeight: 600,
            color: 'var(--color-text-muted)',
            textTransform: 'uppercase',
            letterSpacing: '0.04em',
          }}
        >
          <Sparkles size={14} aria-hidden="true" />
          <span>Comece por um tema</span>
        </div>

        {/* Lista semântica: ul -> li -> button acessível */}
        <ul className="sample-topics-grid" role="list" aria-label="Sugestões de temas investigativos">
          {SAMPLE_TOPICS.map((item, idx) => (
            <li key={idx} className="sample-topic-item">
              <button
                type="button"
                className="sample-topic-card"
                onClick={() => onSelectTopic(item.title)}
                title={`Preencher tema: ${item.title}`}
              >
                <span className="sample-topic-index" aria-hidden="true">{String(idx + 1).padStart(2, '0')}</span>
                <span className="sample-topic-body">
                  <span className="sample-topic-title">{item.title}</span>
                  <span className="sample-topic-desc">{item.description}</span>
                </span>
                <ArrowRight className="sample-topic-arrow" size={15} aria-hidden="true" />
              </button>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
};
