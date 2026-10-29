import React from 'react';

interface HorizonBackgroundProps {
  theme: 'light' | 'dark';
}

/**
 * Ambientação em CSS puro: três auroras em gradiente radial que derivam por
 * transform (só compositor, zero trabalho de JS por frame). O tema entra pelas
 * variáveis de cor; `prefers-reduced-motion` congela tudo.
 */
export const HorizonBackground: React.FC<HorizonBackgroundProps> = ({ theme }) => (
  <div className={`ambient-field ambient-${theme}`} aria-hidden="true">
    <span className="ambient-blob ambient-blob-a" />
    <span className="ambient-blob ambient-blob-b" />
    <span className="ambient-blob ambient-blob-c" />
    <span className="ambient-grain" />
  </div>
);
