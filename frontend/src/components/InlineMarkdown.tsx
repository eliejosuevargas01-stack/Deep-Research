import React from 'react';

/**
 * Markdown mínimo para o texto que ainda está chegando por streaming.
 * react-markdown a cada token seria caro; aqui só negrito, itálico e código,
 * sem dangerouslySetInnerHTML. Marcadores abertos são fechados na hora de
 * renderizar para não aparecer "**Título" cru enquanto o token seguinte não chega.
 */
export function equilibrarMarcadores(texto: string): string {
  let saida = texto;
  const negritos = (saida.match(/\*\*/g) || []).length;
  if (negritos % 2 === 1) saida += '**';
  const crases = (saida.match(/`/g) || []).length;
  if (crases % 2 === 1) saida += '`';
  return saida;
}

export function InlineMarkdown({ text }: { text: string }) {
  const partes = equilibrarMarcadores(text).split(/(\*\*[^*]+\*\*|`[^`]+`|\*[^*\n]+\*)/g);
  return (
    <>
      {partes.map((parte, indice) => {
        if (parte.startsWith('**') && parte.endsWith('**') && parte.length > 4) {
          return <strong key={indice}>{parte.slice(2, -2)}</strong>;
        }
        if (parte.startsWith('`') && parte.endsWith('`') && parte.length > 2) {
          return <code key={indice}>{parte.slice(1, -1)}</code>;
        }
        if (parte.startsWith('*') && parte.endsWith('*') && parte.length > 2) {
          return <em key={indice}>{parte.slice(1, -1)}</em>;
        }
        return <React.Fragment key={indice}>{parte}</React.Fragment>;
      })}
    </>
  );
}
