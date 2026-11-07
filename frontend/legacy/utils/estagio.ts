import type { PipelineStage } from '../components/ExecutionView';

const POR_STATUS: Record<string, PipelineStage> = {
  buscando: 'searching',
  em_andamento: 'searching',
  coletado: 'auditing',
  auditando: 'auditing',
  redigindo: 'writing',
  bloqueado: 'rejected',
  reprovado: 'rejected',
  incompleto: 'failed',
  falha: 'failed',
};

/**
 * Estágio inicial ao abrir uma pesquisa existente.
 *
 * Dossiê pronto abre o relatório direto — nunca a tela de "aprovar plano".
 */
export function resolverEstagioInicial(
  status: string | null | undefined,
  temDossie: boolean
): PipelineStage {
  if (temDossie) return 'completed';
  return POR_STATUS[status ?? ''] ?? 'idle';
}

/**
 * Dossiê persistido vence o status do pipeline: a auditoria pode reprovar e o
 * Redator ainda assim ter gravado o relatório — a tela abre o relatório.
 */
export function deveMostrarDossie(status: string | null | undefined, temDossie: boolean): boolean {
  if (temDossie) return true;
  return status === 'concluido';
}

/**
 * Dossiê já pronto não volta para "reprovada"/"falha" por replay de status do SSE.
 */
export function naoRebaixarDossie(prev: PipelineStage, novo: PipelineStage): PipelineStage {
  return prev === 'completed' ? prev : novo;
}
