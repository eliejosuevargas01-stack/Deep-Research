import React from 'react';
import { Compass } from 'lucide-react';

interface EmptyStateProps {
  onSelectTopic: (topic: string) => void;
}

const SAMPLE_TOPICS = [
  {
    title: 'Matriz energética Brasil',
    description: 'Renováveis, hidrogênio verde e segurança energética.',
  },
  {
    title: 'IA generativa no trabalho de TI',
    description: 'Produtividade, competências e automação de código.',
  },
  {
    title: 'Fusão nuclear comercial',
    description: 'ITER/SPARC, marcos e cronogramas operacionais.',
  },
  {
    title: 'Regulação global de IA',
    description: 'AI Act, EUA e marco brasileiro PL 2338.',
  },
];

export const EmptyState: React.FC<EmptyStateProps> = ({ onSelectTopic }) => {
  return (
    <section className="empty-state" aria-labelledby="empty-state-title">
      <div className="empty-state-header">
        <div className="empty-state-badge" aria-hidden="true">
          <Compass size={20} />
        </div>
        <div>
          <h1 id="empty-state-title" className="empty-state-title">
            Investigue a fundo. Audite cada ponto.
          </h1>
        </div>
      </div>

      <div className="empty-state-pills" aria-label="Sugestões de temas investigativos">
        {SAMPLE_TOPICS.map((item, idx) => (
          <button
            key={idx}
            type="button"
            className="empty-state-pill"
            onClick={() => onSelectTopic(item.title)}
            title={`Preencher tema: ${item.title}`}
          >
            <span className="empty-state-pill-title">{item.title}</span>
            <span className="empty-state-pill-desc">{item.description}</span>
          </button>
        ))}
      </div>
    </section>
  );
};
