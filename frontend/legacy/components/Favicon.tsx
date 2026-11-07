import React, { useState } from 'react';
void React;
import { faviconCandidates } from '../utils/favicon';

interface FaviconProps {
  dominio: string;
  size?: number;
  className?: string;
}

/**
 * Favicon com cadeia de fallback controlada por React.
 *
 * A versão anterior mutava `img.src` dentro de onError. Como o painel direito
 * re-renderiza a cada atualização de tokens, o React reescrevia o `src` de
 * volta para a primeira URL e a cadeia nunca completava — o ícone ficava
 * escondido com `display: none` herdado da mutação anterior.
 *
 * Aqui o índice é estado: cada falha avança um candidato, e quando a lista
 * acaba o componente não renderiza nada (o tile com a inicial aparece).
 */
export function Favicon({ dominio, size = 64, className }: FaviconProps) {
  const [index, setIndex] = useState(0);
  const candidates = faviconCandidates(dominio, size);
  const src = candidates[index];

  if (!src) return null;

  return (
    // Sem `loading="lazy"`: no rail o <img> nasce com `display: none` e só
    // aparece quando `.is-loaded` entra — imagem sem caixa nunca é buscada,
    // então o lazy criava um ciclo em que o favicon nunca carregava.
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={src}
      alt=""
      width={14}
      height={14}
      className={className}
      onLoad={(event) => {
        const img = event.currentTarget;
        // 404 do Google chega como load com naturalWidth 0 (corpo HTML).
        if (img.naturalWidth > 0) {
          img.classList.add('is-loaded');
          return;
        }
        setIndex((atual) => atual + 1);
      }}
      onError={() => setIndex((atual) => atual + 1)}
    />
  );
}
