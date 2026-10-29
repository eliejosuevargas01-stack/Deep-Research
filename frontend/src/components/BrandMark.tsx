import React from 'react';

interface BrandMarkProps {
  size?: number;
  className?: string;
  withWordmark?: boolean;
}

/**
 * Marca do Deep Research: convergência — três trilhas de personas que
 * atravessam a régua de corte do auditor e fundem num ponto focal, o dossiê.
 * Desenhada em SVG puro, com a paleta do sistema via currentColor.
 */
export const BrandMark: React.FC<BrandMarkProps> = ({ size = 28, className, withWordmark = false }) => {
  const mark = (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
      focusable="false"
      className="brand-mark-svg"
    >
      {/* Trilhas paralelas das personas */}
      <path d="M6 3.5V10.5" stroke="currentColor" strokeOpacity="0.55" strokeWidth="1.5" strokeLinecap="round" />
      <path d="M12 3.5V10.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <path d="M18 3.5V10.5" stroke="currentColor" strokeOpacity="0.55" strokeWidth="1.5" strokeLinecap="round" />
      <circle cx="6" cy="3.5" r="0.98" fill="currentColor" fillOpacity="0.55" />
      <circle cx="12" cy="3.5" r="0.98" fill="currentColor" />
      <circle cx="18" cy="3.5" r="0.98" fill="currentColor" fillOpacity="0.55" />
      {/* Barra de corte do Auditor */}
      <line x1="3.5" y1="10.5" x2="20.5" y2="10.5" stroke="currentColor" strokeOpacity="0.7" strokeWidth="1.5" strokeLinecap="round" />
      {/* Funil de convergência e síntese */}
      <path d="M6 10.5L12 16.5M18 10.5L12 16.5M12 10.5V19.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="12" cy="20" r="1.72" fill="currentColor" />
    </svg>
  );

  if (!withWordmark) return <span className={className}>{mark}</span>;

  return (
    <span className={`brand-lockup ${className || ''}`}>
      {mark}
      <span className="brand-wordmark">
        Deep<b>Research</b>
      </span>
    </span>
  );
};
