export type RailMode = 'contexto' | 'fontes';

/**
 * Chip do topo do app: só fecha quando o painel está aberto E já visivelmente
 * naquela aba. Fora isso abre e troca de aba — antes o App usava `railMode`
 * velho e fechava o painel inteiro depois de o usuário trocar de aba por dentro.
 */
export function proximoRail(
  aberto: boolean,
  modoAtual: RailMode,
  alvo: RailMode
): { aberto: boolean; modo: RailMode } {
  if (aberto && modoAtual === alvo) return { aberto: false, modo: modoAtual };
  return { aberto: true, modo: alvo };
}
