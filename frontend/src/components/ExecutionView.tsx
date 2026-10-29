import React, { useEffect, useState } from 'react';
import {
  AlertTriangle,
  XCircle,
  RotateCcw,
  RefreshCw,
  Clock,
} from 'lucide-react';
import { AuditResponse, PlanResponse, SearchResponse } from '../types/api';
import { ReasoningFeedItem } from '../types/stream';
import { LinearTimeline } from './LinearTimeline';
import '../styles/execution-view.css';
import { formatarTitulo } from '../utils/texto';

export type PipelineStage = 'idle' | 'searching' | 'auditing' | 'writing' | 'completed' | 'rejected' | 'failed';

export const CANONICAL_CRITERIA_NAMES: Record<number, string> = {
  1: 'Clareza Temática',
  2: 'Corroboração Canônica',
  3: 'Atualidade',
  4: 'Ausência de Contradições',
  5: 'Embasamento Factual',
  6: 'Aderência ao Escopo',
  7: 'Profundidade Analítica',
  8: 'Precisão de Dados',
  9: 'Neutralidade',
  10: 'Densidade de Evidências',
  11: 'Declaração de Incertezas',
  12: 'Solidez Lógica',
};

/** Item da linha de estágios: texto com estado, sem caixa. */
function StageLineItem({
  ativo,
  falhou,
  concluido,
  rotulo,
}: {
  ativo: boolean;
  falhou: boolean;
  concluido: boolean;
  rotulo: string;
}): React.ReactElement {
  const estado = falhou ? 'falhou' : ativo ? 'em andamento' : concluido ? 'concluído' : 'pendente';
  return (
    <span
      role="listitem"
      aria-current={ativo ? 'step' : undefined}
      className={`stage-line-item${ativo ? ' ativo' : ''}${falhou ? ' falhou' : ''}${concluido ? ' concluido' : ''}`}
    >
      {rotulo}
      <span className="sr-only">{` (${estado})`}</span>
    </span>
  );
}

export function formatPersonaName(name: string): string {
  const map: Record<string, string> = {
    historiador: 'Historiador',
    visionario: 'Visionário',
    cetico: 'Cético',
    futurista: 'Futurista',
  };
  return map[name.toLowerCase()] || name.charAt(0).toUpperCase() + name.slice(1);
}

export function getAuditContextualLabel(
  currentStage: PipelineStage,
  currentCycle: number,
  auditCycle: number | null | undefined
): { heading: string; isPriorCycle: boolean; bannerText?: string } {
  if (auditCycle === null || auditCycle === undefined) {
    return {
      heading: 'Última auditoria disponível',
      isPriorCycle: currentStage === 'searching',
      bannerText:
        currentStage === 'searching'
          ? 'Exibindo parecer da última auditoria disponível enquanto a nova busca está em andamento.'
          : undefined,
    };
  }

  if (currentCycle > auditCycle) {
    if (currentStage === 'searching') {
      return {
        heading: `Auditoria do ciclo ${auditCycle} — revisão em andamento no ciclo ${currentCycle}`,
        isPriorCycle: true,
        bannerText: `Auditoria do ciclo ${auditCycle} reprovada. Nova busca em andamento no ciclo ${currentCycle} para enriquecer evidências e superar os apontamentos abaixo.`,
      };
    }
    if (currentStage === 'auditing') {
      return {
        heading: `Auditoria anterior (ciclo ${auditCycle}) — nova auditoria em andamento no ciclo ${currentCycle}`,
        isPriorCycle: true,
        bannerText: `Avaliando novos dados do ciclo ${currentCycle}. O parecer abaixo refere-se ao ciclo anterior (${auditCycle}).`,
      };
    }
    return {
      heading: `Auditoria do ciclo ${auditCycle}`,
      isPriorCycle: false,
    };
  }

  if (currentStage === 'writing') {
    return {
      heading: `Auditoria do ciclo ${auditCycle} (Aprovada)`,
      isPriorCycle: false,
    };
  }

  return {
    heading: `Auditoria do ciclo ${auditCycle}`,
    isPriorCycle: false,
  };
}

export function getSuccinctStatus(
  stage: PipelineStage,
  cycleNumber: number,
  maxCycles: number,
  failedStage?: 'searching' | 'auditing' | 'writing' | null,
  errorMessage?: string | null
): string {
  switch (stage) {
    case 'searching':
      return `Ciclo ${cycleNumber} de ${maxCycles}: Coleta e varredura web em andamento.`;
    case 'auditing':
      return `Ciclo ${cycleNumber} de ${maxCycles}: Auditoria dos 12 critérios em andamento.`;
    case 'writing':
      return 'Redigindo o dossiê analítico final.';
    case 'completed':
      return 'Investigação e dossiê final concluídos com sucesso.';
    case 'rejected':
      return 'Investigação bloqueada na auditoria de qualidade: limiar mínimo de critérios não atendido.';
    case 'failed': {
      const stageLabel =
        failedStage === 'searching'
          ? 'busca'
          : failedStage === 'auditing'
          ? 'auditoria'
          : failedStage === 'writing'
          ? 'redação'
          : 'execução';
      return `Falha no estágio de ${stageLabel}: ${errorMessage || 'erro inesperado'}.`;
    }
    default:
      return 'Investigação em andamento.';
  }
}

export function getCycleBadgeClass(stage: PipelineStage): string {
  switch (stage) {
    case 'searching':
      return 'buscando';
    case 'auditing':
      return 'auditando';
    case 'writing':
      return 'redigindo';
    case 'completed':
      return 'concluido';
    case 'rejected':
    case 'failed':
      return 'reprovado';
    default:
      return 'planejado';
  }
}

interface ExecutionViewProps {
  stage: PipelineStage;
  plan?: PlanResponse | null;
  searchResult?: SearchResponse | null;
  auditResult?: AuditResponse | null;
  cycleNumber: number;
  maxCycles: number;
  errorMessage?: string | null;
  failedStage?: 'searching' | 'auditing' | 'writing' | null;
  isRetrying?: boolean;
  onRetry?: () => void;
  onReset: () => void;
  reasoningItems?: ReasoningFeedItem[];
  /** Passo 2: reprocessamento por ponto sem recarregar a página. */
  onRefazerBuscaPonto?: (ponto_id: string) => void;
  onReauditarPonto?: (ponto_id: string) => void;
  pontoEmReprocesso?: string | null;
}

export const ExecutionView: React.FC<ExecutionViewProps> = ({
  stage,
  plan,
  searchResult,
  auditResult,
  cycleNumber,
  maxCycles,
  errorMessage,
  failedStage,
  isRetrying = false,
  onRetry,
  onReset,
  reasoningItems = [],
  onRefazerBuscaPonto,
  onReauditarPonto,
  pontoEmReprocesso = null,
}) => {
  // Cronômetro visível: tempo desde o início da execução. A região é
  // aria-live="off" para não narrar cada segundo no leitor de tela.
  const [inicioExecucao, setInicioExecucao] = useState<number | null>(null);
  const [agora, setAgora] = useState<number>(() => Date.now());
  const emAndamento = stage === 'searching' || stage === 'auditing' || stage === 'writing';

  useEffect(() => {
    if (emAndamento) {
      setInicioExecucao((prev) => prev ?? Date.now());
    } else if (stage === 'idle') {
      setInicioExecucao(null);
    }
  }, [emAndamento, stage]);

  useEffect(() => {
    if (inicioExecucao === null || !emAndamento) return;
    const timer = window.setInterval(() => setAgora(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [inicioExecucao, emAndamento]);

  const decorridoTotal = inicioExecucao !== null ? Math.max(0, Math.floor((agora - inicioExecucao) / 1000)) : null;
  const decorridoTexto =
    decorridoTotal === null
      ? null
      : decorridoTotal >= 60
      ? `${Math.floor(decorridoTotal / 60)}m ${String(decorridoTotal % 60).padStart(2, '0')}s`
      : `${decorridoTotal}s`;


  const isTimeout = Boolean(
    errorMessage &&
      (errorMessage.toLowerCase().includes('timeout') ||
        errorMessage.includes('504') ||
        errorMessage.toLowerCase().includes('timed out'))
  );

  const isProviderError = Boolean(
    errorMessage &&
      (errorMessage.includes('502') ||
        errorMessage.includes('LLM_PROVIDER_ERROR') ||
        errorMessage.includes('EXTERNAL_PROVIDER_ERROR'))
  );

  // Status resumido exclusivo para leitores de tela (WCAG aria-live focado)
  const succinctStatus = getSuccinctStatus(
    stage,
    cycleNumber,
    maxCycles,
    failedStage,
    errorMessage
  );

  // Determinação determinística de estados dos estágios no rastreador
  const isSearchActive = stage === 'searching';
  const isSearchFailed = stage === 'failed' && failedStage === 'searching';
  // Falha sem etapa identificada não pode pintar a busca de verde.
  const isSearchDone =
    !isSearchActive && !isSearchFailed && stage !== 'idle' && stage !== 'failed';

  const isAuditActive = stage === 'auditing';
  const isAuditFailed = stage === 'rejected' || (stage === 'failed' && failedStage === 'auditing');
  const isAuditDone =
    stage === 'writing' ||
    stage === 'completed' ||
    (auditResult?.pronto_para_writer === true && !isAuditActive && !isAuditFailed);

  const isWritingActive = stage === 'writing';
  const isWritingFailed = stage === 'failed' && failedStage === 'writing';
  const isWritingDone = stage === 'completed';

  // Progresso macro: cada estágio avança a barra de 2px do topo.
  const progresso =
    stage === 'completed'
      ? 100
      : stage === 'writing'
        ? 90
        : stage === 'auditing' || stage === 'rejected'
          ? 62
          : stage === 'searching'
            ? 30
            : stage === 'failed'
              ? failedStage === 'writing'
                ? 90
                : failedStage === 'auditing'
                  ? 62
                  : 30
              : 0;

  return (
    <article className="execution-card">
      {/* Região dinâmica atômica e concisa para tecnologias assistivas */}
      <div className="sr-only" aria-live="polite" aria-atomic="true">
        {succinctStatus}
      </div>

      <header className="card-header execution-heading-row">
        <div className="execution-heading-main">
          <h1 className="card-title execution-heading-title">
            {stage === 'failed'
              ? 'Investigação interrompida'
              : stage === 'rejected'
              ? 'Investigação reprovada na auditoria'
              : stage === 'completed'
              ? 'Investigação concluída'
              : 'Investigação em andamento'}
          </h1>
          {plan?.tema && (
            <p className="execution-theme-inline" title={plan.tema}>
              {formatarTitulo(plan.tema)}
            </p>
          )}
        </div>
        <span className={`status-badge-chip ${getCycleBadgeClass(stage)}`}>
          {stage === 'searching'
            ? 'Buscando evidências'
            : stage === 'auditing'
            ? 'Auditando evidências'
            : stage === 'writing'
            ? 'Redigindo dossiê'
            : stage === 'completed'
            ? 'Concluída'
            : stage === 'rejected'
            ? 'Reprovada'
            : stage === 'failed'
            ? 'Interrompida'
            : 'Pronta'}
        </span>
        {decorridoTexto && (
          <span className="execution-elapsed" aria-live="off" title="Tempo desde o início desta execução">
            <Clock size={13} aria-hidden="true" />
            <span>{decorridoTexto}</span>
          </span>
        )}
      </header>

      <div
        className="exec-progress"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={progresso}
        aria-label="Progresso da investigação"
      >
        <span style={{ transform: `scaleX(${Math.max(0, Math.min(100, progresso)) / 100})` }} />
      </div>

      {/* Tracker de estágios: linha única de texto, sem caixas. O detalhe por
          ponto vive na timeline abaixo. */}
      <p className="stage-line" role="list" aria-label="Estágio atual">
        <StageLineItem
          ativo={isSearchActive}
          falhou={isSearchFailed}
          concluido={isSearchDone}
          rotulo="Busca com personas"
        />
        <span aria-hidden="true"> · </span>
        <StageLineItem
          ativo={isAuditActive}
          falhou={isAuditFailed}
          concluido={isAuditDone}
          rotulo="Auditoria (12 critérios)"
        />
        <span aria-hidden="true"> · </span>
        <StageLineItem
          ativo={isWritingActive}
          falhou={isWritingFailed}
          concluido={isWritingDone}
          rotulo="Redação do dossiê"
        />
      </p>





      {/* Estado: Reprovado na Auditoria / Teto de Tentativas Excedido */}
      {stage === 'rejected' && (
        <div className="alert-banner danger exec-error-card" role="alert">
          <XCircle size={20} aria-hidden="true" className="execution-banner-icon" />
          <div className="execution-banner-body">
            <strong>Investigação bloqueada na auditoria de qualidade</strong>
            <p className="execution-banner-copy">
              Nem todos os pontos atingiram o limiar mínimo de 11/12 critérios após as tentativas de busca e refinamento.
              Conforme as diretrizes de confiabilidade, a redação final do dossiê não pode ser executada com dados não
              aprovados.
            </p>
            {auditResult?.auditorias?.some((a) => (a.criterios ?? []).some((c) => !c.aprovado)) && (
              <ul className="gdr-criteria-pills" aria-label="Critérios não cumpridos">
                {auditResult.auditorias.flatMap((a) =>
                  (a.criterios ?? []).filter((c) => !c.aprovado).map((c) => (
                    <li key={`${a.ponto_id}-${c.id}`} className="gdr-criteria-pill" title={c.justificativa || `Critério ${c.id}`}>
                      {CANONICAL_CRITERIA_NAMES[c.id] ?? `Critério ${c.id}`}
                    </li>
                  ))
                ).slice(0, 12)}
              </ul>
            )}
            <div className="execution-banner-actions">
              <button
                type="button"
                className="btn-secondary btn-compact"
                onClick={onReset}
                
              >
                <RotateCcw size={14} aria-hidden="true" />
                <span>Formular novo tema</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Estado: Falha na Execução (Timeout, 502, 504, erro de provedor) com Recuperação Específica */}
      {stage === 'failed' && (
        <div className="alert-banner danger exec-error-card" role="alert">
          <AlertTriangle size={20} aria-hidden="true" className="execution-banner-icon" />
          <div className="execution-banner-body">
            <strong>
              {isTimeout
                ? 'Tempo limite de execução excedido (Timeout):'
                : isProviderError
                ? 'Falha temporária de comunicação com o provedor (502 Gateway):'
                : 'Falha na execução da pesquisa:'}
            </strong>
            <p className="execution-banner-copy execution-banner-copy--break">
              {errorMessage || 'Ocorreu uma instabilidade na execução do pipeline de pesquisa ou comunicação com o servidor.'}
            </p>
            <div className="execution-banner-actions">
              {onRetry && (
                <button
                  type="button"
                  className="btn-start-research btn-compact"
                  onClick={onRetry}
                  disabled={isRetrying}
                  
                >
                  <RefreshCw size={14} className={isRetrying ? 'spinner' : ''} aria-hidden="true" />
                  <span>
                    {failedStage === 'writing' || auditResult?.pronto_para_writer
                      ? 'Tentar redigir dossiê novamente'
                      : failedStage === 'auditing'
                      ? 'Tentar auditoria novamente'
                      : 'Tentar busca e auditoria novamente'}
                  </span>
                </button>
              )}
              <button
                type="button"
                className="btn-secondary btn-compact"
                onClick={onReset}
                
              >
                <RotateCcw size={14} aria-hidden="true" />
                <span>Formular novo tema</span>
              </button>
            </div>
          </div>
        </div>
      )}


      {/* Timeline linear: 1 trilho, nós por ponto, reasoning sob demanda.
          Substitui o stage-tracker em caixas + feed de cartões + breakdown
          aninhado — zero box-in-box, zero despejo de reasoning. */}
      <LinearTimeline
        plan={plan}
        searchResult={searchResult}
        auditResult={auditResult}
        reasoningItems={reasoningItems}
        onRefazerBuscaPonto={onRefazerBuscaPonto}
        onReauditarPonto={onReauditarPonto}
        pontoEmReprocesso={pontoEmReprocesso}
        rigorAtual={plan?.preferencias?.criterios_minimos ?? auditResult?.auditorias?.[0]?.criterios_minimos ?? null}
      />
      {/* Estado: Redigindo */}
      {stage === 'writing' && (
        <div className="alert-banner info">
          <span className="spinner" aria-hidden="true" />
          <div>
            <strong>Pontos aprovados pela auditoria! Redigindo dossiê final...</strong>
            <p className="execution-banner-copy">
              Consolidando evidências canônicas e redigindo o relatório analítico integral em Markdown.
            </p>
          </div>
        </div>
      )}

      {/* O detalhamento por ponto vive na timeline linear acima — sem breakdown aninhado. */}
    </article>
  );
};
