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
