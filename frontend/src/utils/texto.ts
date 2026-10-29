/**
 * Formatação editorial de títulos digitados pelo usuário.
 * "maria corina machado" → "Maria Corina Machado"; preserva siglas (IA, ESG)
 * e não capitaliza conectivos no meio da frase.
 */
const CONECTIVOS = new Set([
  'a', 'o', 'as', 'os', 'um', 'uma', 'uns', 'umas',
  'de', 'da', 'do', 'das', 'dos', 'e', 'em', 'no', 'na', 'nos', 'nas',
  'para', 'por', 'com', 'sem', 'sobre', 'entre', 'ao', 'aos', 'à', 'às',
]);

export function formatarTitulo(texto: string): string {
  const limpo = (texto || '').trim();
  if (!limpo) return limpo;
  return limpo
    .split(/\s+/)
    .map((palavra, indice) => {
      const nucleo = palavra.replace(/[^\p{L}\p{N}]/gu, '');
      if (!nucleo) return palavra;
      // Siglas e códigos ficam como estão: IA, ESG, PIB, 2026.
      if (nucleo.length > 1 && nucleo === nucleo.toUpperCase() && /\p{L}/u.test(nucleo)) {
        return palavra;
      }
      if (indice > 0 && CONECTIVOS.has(nucleo.toLowerCase())) {
        return palavra.toLowerCase();
      }
      return palavra.charAt(0).toUpperCase() + palavra.slice(1).toLowerCase();
    })
    .join(' ');
}
