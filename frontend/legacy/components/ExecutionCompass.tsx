import React from 'react';
import type { AuditResponse, PlanResponse, SearchResponse } from '../types/api';
import type { PipelineStage } from './ExecutionView';

interface ExecutionCompassProps {
  stage: PipelineStage;
  plan?: PlanResponse | null;
  searchResult?: SearchResponse | null;
  auditResult?: AuditResponse | null;
  cycleNumber: number;
  maxCycles: number;
  writerProgress?: { status: string; total_caracteres: number } | null;
}

const FASES = ['Planejamento', 'Busca (4 personas)', 'Auditoria (12 critérios)', 'Redação do dossiê'];

function faseAtiva(stage: PipelineStage): number {
  if (stage === 'searching') return 1;
  if (stage === 'auditing' || stage === 'rejected' || stage === 'failed') return 2;
  if (stage === 'writing' || stage === 'completed') return 3;
  return 0;
}

function rotuloPonto(status: string | undefined, aprovadoNaAuditoria: boolean): string {
  if (aprovadoNaAuditoria || status === 'aprovado') return '✓ Aprovado';
  if (status === 'reprovado') return '↻ Re-busca solicitada';
  if (status === 'coletado') return 'Coletado, aguardando auditoria';
  return 'Aguardando';
}

/**
 * Bússola da execução: onde estamos, quantas rodadas de auditoria restam e o
 * estado de cada ponto do plano. Sem ela os ~20 minutos de pesquisa são opacos.
 */
export const ExecutionCompass: React.FC<ExecutionCompassProps> = ({
  stage,
  plan,
  searchResult,
  auditResult,
  cycleNumber,
  maxCycles,
  writerProgress,
}) => {
  const ativa = faseAtiva(stage);
  const pontos = plan?.pontos ?? [];
  const aprovadosPorPonto = new Set(
    (auditResult?.auditorias ?? [])
      .filter((a) => a.status === 'aprovado')
      .map((a) => String(a.ponto_id))
  );
  const personasConcluidas = searchResult?.resumo_coletas?.[0]?.personas?.length ?? 0;
  const rodada = Math.max(1, Math.min(cycleNumber || 1, maxCycles || 1));
  const restantes = Math.max((maxCycles || 0) - rodada, 0);
  const escritos = writerProgress?.total_caracteres ?? 0;

  return (
    <section className="exec-compass" aria-label="Progresso da execução">
      <ol className="exec-compass__phases">
        {FASES.map((fase, indice) => {
          const estado = indice < ativa ? 'concluida' : indice === ativa ? 'ativa' : 'pendente';
          return (
            <li
              key={fase}
              className={`exec-compass__phase is-${estado}`}
              aria-current={estado === 'ativa' ? 'step' : undefined}
            >
              <span className="exec-compass__phase-num">{indice + 1}</span>
              <span>{fase}</span>
            </li>
          );
        })}
      </ol>

      {pontos.length > 0 && (
        <ul className="exec-compass__points" aria-label="Pontos do plano">
          {pontos.map((ponto, indice) => {
            const n = ponto.ponto_n ?? indice + 1;
            const aprovado = aprovadosPorPonto.has(String(ponto.ponto_id));
            return (
              <li key={ponto.ponto_id ?? n} className="exec-compass__point">
                <strong>{`Ponto ${n}`}</strong>
                <span>{rotuloPonto(ponto.status, aprovado)}</span>
              </li>
            );
          })}
        </ul>
      )}

      {stage === 'auditing' && (
        <p className="exec-compass__live">
          {`Auditoria em andamento — rodada ${rodada} de ${maxCycles}. Restam ${restantes} turno(s) de auditoria.`}
          {personasConcluidas > 0 ? ` ${personasConcluidas}/4 personas concluídas.` : ''}
        </p>
      )}

      {stage === 'writing' && (
        <p className="exec-compass__live" aria-live="polite">
          {`Redator escrevendo o dossiê — ${escritos.toLocaleString('pt-BR')} caracteres redigidos.`}
        </p>
      )}
    </section>
  );
};
