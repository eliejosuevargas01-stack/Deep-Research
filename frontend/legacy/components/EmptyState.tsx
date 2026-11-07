import React, { useRef, useState, useEffect } from 'react';
import { ChevronRight, ChevronLeft } from 'lucide-react';
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
    title: 'IA generativa em TI',
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
  {
    title: 'Criptografia pós-quântica',
    description: 'Padrões NIST, migração de chaves e segurança bancária.',
  },
  {
    title: 'Baterias estado sólido',
    description: 'Densidade energética, veículos elétricos e custos.',
  },
  {
    title: 'Automação na saúde',
    description: 'Diagnóstico precoce, radiologia e prontuários inteligentes.',
  },
  {
    title: 'Transição agroecológica',
    description: 'Bioinsumos, rastreabilidade e agricultura de baixo carbono.',
  },
];

export const EmptyState: React.FC<EmptyStateHeroProps> = ({ tema, rascunho }) => {
  const escrevendo = rascunho.trim().length > 0;
  return (
    <section className="empty-state" aria-label="Personas analíticas da investigação Deep Research">
      <div className="empty-state-hero">
        <DeepResearchCharacters
          phase="interactive"
          isTyping={escrevendo}
          typingProgress={Math.min(1, rascunho.trim().length / 120)}
          theme={tema}
        />
      </div>
    </section>
  );
};

/**
 * Pílulas de temas recomendados em carrossel deslizável polido:
 * - Exibe exatamente 2 pílulas completas e a 3ª cortada pela metade com gradiente de transparência.
 * - Botão '>' avança suavemente para as próximas 2 recomendações deslizando as primeiras para o lado esquerdo transparente.
 * - Micro-indicador de pares e botão '<' flutuante sem causar layout shift (CLS 0).
 */
export const TopicPills: React.FC<EmptyStateProps> = ({ onSelect }) => {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(true);

  const updateScrollState = () => {
    const el = scrollRef.current;
    if (!el) return;
    const scrollLeft = el.scrollLeft;
    const maxScroll = el.scrollWidth - el.clientWidth;
    setCanScrollLeft(scrollLeft > 8);
    setCanScrollRight(scrollLeft < maxScroll - 8);
  };

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    updateScrollState();
    el.addEventListener('scroll', updateScrollState, { passive: true });
    window.addEventListener('resize', updateScrollState);
    return () => {
      el.removeEventListener('scroll', updateScrollState);
      window.removeEventListener('resize', updateScrollState);
    };
  }, []);

  const handleNext = () => {
    const el = scrollRef.current;
    if (!el) return;
    const firstPill = el.querySelector<HTMLElement>('.topic-pill');
    const step = firstPill ? (firstPill.offsetWidth + 8) * 2 : 264;
    const maxScroll = el.scrollWidth - el.clientWidth;

    if (el.scrollLeft >= maxScroll - 16) {
      el.scrollTo({ left: 0, behavior: 'smooth' });
    } else {
      el.scrollBy({ left: step, behavior: 'smooth' });
    }
  };

  const handlePrev = () => {
    const el = scrollRef.current;
    if (!el) return;
    const firstPill = el.querySelector<HTMLElement>('.topic-pill');
    const step = firstPill ? (firstPill.offsetWidth + 8) * 2 : 264;
    el.scrollBy({ left: -step, behavior: 'smooth' });
  };

  return (
    <div
      className={`topic-pills-wrapper ${canScrollLeft ? 'has-left-fade' : ''} ${
        canScrollRight ? 'has-right-fade' : ''
      }`}
    >
      <button
        type="button"
        className={`topic-pill-nav-btn topic-pill-nav-prev ${canScrollLeft ? 'is-visible' : 'is-hidden'}`}
        onClick={handlePrev}
        aria-label="Recomendações anteriores"
        title="Ver recomendações anteriores"
        tabIndex={canScrollLeft ? 0 : -1}
      >
        <ChevronLeft size={20} strokeWidth={2.4} aria-hidden="true" />
      </button>

      <div
        ref={scrollRef}
        className="topic-pills-track"
        role="region"
        aria-label="Sugestões de temas para investigação técnica"
        tabIndex={0}
      >
        {SAMPLE_TOPICS.map((item, idx) => (
          <button
            key={idx}
            type="button"
            className="topic-pill"
            onClick={() => onSelect(item.title)}
            title={item.description}
          >
            <span className="topic-pill-dot" aria-hidden="true" />
            <span className="topic-pill-text">{item.title}</span>
          </button>
        ))}
      </div>

      <button
        type="button"
        className="topic-pill-nav-btn topic-pill-nav-next"
        onClick={handleNext}
        aria-label="Próximas recomendações de temas"
        title="Ver próximas recomendações"
      >
        <ChevronRight size={20} strokeWidth={2.4} aria-hidden="true" />
      </button>
    </div>
  );
};
