import React from 'react';
import { Compass } from 'lucide-react';
import { DeepResearchCharacters } from '../deepresearch_hero_7_personas_interativas';

interface EmptyStateProps {
  onSelect: (topic: string) => void;
}

interface EmptyStateHeroProps {
  tema: 'light' | 'dark';
  rascunho: string;
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

export const EmptyState: React.FC<EmptyStateHeroProps> = ({ tema, rascunho }) => {
  const escrevendo = rascunho.trim().length > 0;
  return (
    <section className="empty-state" aria-labelledby="empty-state-title">
      <div className="empty-state-hero">
        <DeepResearchCharacters
          phase={escrevendo ? 'planning' : 'interactive'}
          isTyping={escrevendo}
          typingProgress={Math.min(1, rascunho.trim().length / 120)}
          theme={tema}
        />
      </div>
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

    </section>
  );
};

/** Pílulas compactas: ficam abaixo do compositor, não ocupam a área central. */
export const TopicPills: React.FC<EmptyStateProps> = ({ onSelect }) => (
  <div className="topic-pills" aria-label="Sugestões de temas investigativos">
    {SAMPLE_TOPICS.map((item, idx) => (
      <button
        key={idx}
        type="button"
        className="topic-pill"
        onClick={() => onSelect(item.title)}
        title={item.description}
      >
        {item.title}
      </button>
    ))}
  </div>
);
