import React, { useEffect, useState } from 'react';
import {
  XCircle,
  RotateCcw,
  RefreshCw,
  Clock,
  ShieldCheck,
  Sparkles,
  BookOpen,
  ChevronRight,
  PanelRight,
} from 'lucide-react';
import { AuditResponse, PlanResponse, SearchResponse } from '../types/api';
import { ReasoningFeedItem } from '../types/stream';
import { LinearTimeline } from './LinearTimeline';
import '../styles/execution-view.css';
import { formatarTitulo } from '../utils/texto';
import { ConvergenceLogo } from './ResearchIcons';
import { ErrorNotice } from './ErrorNotice';
import { apresentarErro } from '../utils/erros';
import type { FalhaApresentada } from '../utils/erros';

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
          ? 'Mostrando a auditoria anterior enquanto a nova busca roda.'
          : undefined,
    };
  }

  if (currentCycle > auditCycle) {
    if (currentStage === 'searching') {
      return {
        heading: `Auditoria do ciclo ${auditCycle}: revisão no ciclo ${currentCycle}`,
        isPriorCycle: true,
        bannerText: `Auditoria do ciclo ${auditCycle} reprovada. Nova busca no ciclo ${currentCycle} para reforçar as evidências e responder aos apontamentos abaixo.`,
      };
    }
    if (currentStage === 'auditing') {
      return {
        heading: `Auditoria anterior (ciclo ${auditCycle}): nova auditoria no ciclo ${currentCycle}`,
        isPriorCycle: true,
        bannerText: `Avaliando os dados do ciclo ${currentCycle}. O parecer abaixo é do ciclo ${auditCycle}.`,
      };
    }
    return {
      heading: `Auditoria do ciclo ${auditCycle}`,
      isPriorCycle: false,
    };
  }

  if (currentStage === 'writing') {
    return {
      heading: `Auditoria do ciclo ${auditCycle}: aprovada`,
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
      return `Ciclo ${cycleNumber} de ${maxCycles}: coletando e varrendo a web.`;
    case 'auditing':
      return `Ciclo ${cycleNumber} de ${maxCycles}: auditando os 12 critérios.`;
    case 'writing':
      return 'Redigindo o dossiê final.';
    case 'completed':
      return 'Investigação concluída. Dossiê pronto.';
    case 'rejected':
      return 'A auditoria barrou a investigação: os pontos não atingiram o mínimo de critérios.';
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

/** Falha de execução traduzida: o que parou, o que sobrou e o próximo passo. */
function falhaDaExecucao({
  isTimeout,
  isProviderError,
  failedStage,
  errorMessage,
}: {
  isTimeout: boolean;
  isProviderError: boolean;
  failedStage?: 'searching' | 'auditing' | 'writing' | null;
  errorMessage?: string | null;
}): FalhaApresentada {
  const detalhe = errorMessage?.trim() || undefined;

  if (isTimeout) {
    return {
      titulo: 'A pesquisa passou do tempo limite',
      mensagem: 'O que já foi coletado continua salvo. Tente de novo. Se repetir, reduza o número de pontos.',
      detalhe,
      tom: 'erro',
    };
  }

  if (isProviderError) {
    return {
      titulo: 'O provedor de IA não respondeu',
      mensagem: 'Nada coletado foi perdido. Tente de novo em instantes.',
      detalhe,
      tom: 'erro',
    };
  }

  if (failedStage === 'writing') {
    return {
      titulo: 'A redação parou',
      mensagem: 'Os pontos já passaram na auditoria. Tente de novo para escrever o dossiê; nada precisa ser recoletado.',
      detalhe,
      tom: 'erro',
    };
  }

  if (failedStage === 'auditing') {
    return {
      titulo: 'A auditoria parou',
      mensagem: 'Os pontos coletados continuam salvos. Tente de novo para reauditar.',
      detalhe,
      tom: 'erro',
    };
  }

  return {
    titulo: 'A busca parou',
    mensagem: 'O que já foi coletado continua salvo. Tente de novo; a coleta retoma do último ponto concluído.',
    detalhe,
    tom: 'erro',
  };
}

/** Limite de critérios não cumpridos exibidos por ponto no banner. */
const LIMITE_CRITERIOS_POR_PONTO = 4;
/** Limite de pontos com pendências exibidos no banner (evita banner infinito). */
const LIMITE_PONTOS_NO_BANNER = 4;

type CriterioAuditoria = NonNullable<AuditResponse['auditorias'][number]['criterios']>[number];

interface PontoPendente {
  ponto_id: string;
  ponto_n: number;
  criterios_aprovados: number | null;
  criterios_minimos: number | null;
  naoCumpridos: CriterioAuditoria[];
}

/** Pendências por ponto: critérios reprovados da auditoria ou, sem parecer,
    os pontos do plano como alvo de recuperação. */
export function derivarPontosPendentes(
  auditResult: AuditResponse | null | undefined,
  pontosPlano: Array<{ ponto_id: string; ponto_n: number }> = []
): PontoPendente[] {
  const porPonto = (auditResult?.auditorias ?? [])
    .map((auditoria) => ({
      ponto_id: auditoria.ponto_id,
      ponto_n: auditoria.ponto_n,
      criterios_aprovados: auditoria.criterios_aprovados ?? null,
      criterios_minimos: auditoria.criterios_minimos ?? null,
      naoCumpridos: (auditoria.criterios ?? []).filter((c) => !c.aprovado),
    }))
    .filter((ponto) => ponto.naoCumpridos.length > 0);

  if (porPonto.length > 0) return porPonto;

  return pontosPlano.map((ponto) => ({
    ponto_id: ponto.ponto_id,
    ponto_n: ponto.ponto_n,
    criterios_aprovados: null,
    criterios_minimos: null,
    naoCumpridos: [],
  }));
}

/** Bloco compartilhado pelos banners de reprovação e de falha: pílulas de
    critérios não cumpridos por ponto + recuperação pontual. */
const BannerPontosPendentes: React.FC<{
  pontos: PontoPendente[];
  onRefazerBuscaPonto?: (ponto_id: string) => void;
  onReauditarPonto?: (ponto_id: string) => void;
  pontoEmReprocesso?: string | null;
}> = ({ pontos, onRefazerBuscaPonto, onReauditarPonto, pontoEmReprocesso = null }) => {
  if (pontos.length === 0) return null;
  const visiveis = pontos.slice(0, LIMITE_PONTOS_NO_BANNER);
  const pontosOcultos = pontos.length - visiveis.length;

  return (
    <div className="execution-stack exec-pontos-pendentes">
      {visiveis.map((ponto) => {
        const ocultos = ponto.naoCumpridos.length - LIMITE_CRITERIOS_POR_PONTO;
        const emReprocesso = pontoEmReprocesso === ponto.ponto_id;
        return (
          <div key={ponto.ponto_id} className="exec-ponto-pendencia" data-ponto-id={ponto.ponto_id}>
            <p className="execution-subheading">
              {ponto.criterios_aprovados !== null && ponto.criterios_minimos !== null
                ? `Ponto ${ponto.ponto_n} · ${ponto.criterios_aprovados}/${ponto.criterios_minimos} critérios`
                : `Ponto ${ponto.ponto_n}`}
            </p>
            {ponto.naoCumpridos.length > 0 && (
              <ul
                className="gdr-criteria-pills"
                aria-label={`Critérios não cumpridos do ponto ${ponto.ponto_n}`}
              >
                {ponto.naoCumpridos.slice(0, LIMITE_CRITERIOS_POR_PONTO).map((criterio) => (
                  <li
                    key={criterio.id}
                    className="gdr-criteria-pill"
                    title={criterio.justificativa || `Critério ${criterio.id}`}
                  >
                    {CANONICAL_CRITERIA_NAMES[criterio.id] ?? `Critério ${criterio.id}`}
                  </li>
                ))}
              </ul>
            )}
            {ocultos > 0 && (
              <p className="execution-subheading">
                +{ocultos} {ocultos === 1 ? 'critério não cumprido' : 'critérios não cumpridos'} neste ponto
              </p>
            )}
            {(onRefazerBuscaPonto || onReauditarPonto) && (
              <div className="execution-banner-actions">
                {onRefazerBuscaPonto && (
                  <button
                    type="button"
                    className="btn-start-research btn-compact"
                    onClick={() => onRefazerBuscaPonto(ponto.ponto_id)}
                    disabled={emReprocesso}
                    aria-label={`Refazer busca do ponto ${ponto.ponto_n}`}
                  >
                    <RefreshCw size={14} aria-hidden="true" />
                    <span>Refazer busca</span>
                  </button>
                )}
                {onReauditarPonto && (
                  <button
                    type="button"
                    className="btn-start-research btn-compact"
                    onClick={() => onReauditarPonto(ponto.ponto_id)}
                    disabled={emReprocesso}
                    aria-label={`Reauditar por ponto ${ponto.ponto_n}`}
                  >
                    <ShieldCheck size={14} aria-hidden="true" />
                    <span>Reauditar por ponto</span>
                  </button>
                )}
              </div>
            )}
          </div>
        );
      })}
      {pontosOcultos > 0 && (
        <p className="execution-subheading">
          +{pontosOcultos} {pontosOcultos === 1 ? 'ponto com pendência' : 'pontos com pendências'} não exibidos
        </p>
      )}
    </div>
  );
};

interface ExecutionViewProps {
  stage: PipelineStage;
  plan?: PlanResponse | null;
  searchResult?: SearchResponse | null;
  auditResult?: AuditResponse | null;
  cycleNumber: number;
  maxCycles: number;
  errorMessage?: string | null;
  /** Queda do canal ao vivo (SSE). O trabalho continua no servidor. */
  streamError?: string | null;
  onReconnect?: () => void;
  failedStage?: 'searching' | 'auditing' | 'writing' | null;
  isRetrying?: boolean;
  onRetry?: () => void;
  onReset: () => void;
  reasoningItems?: ReasoningFeedItem[];
  /** Passo 2: reprocessamento por ponto sem recarregar a página. */
  onRefazerBuscaPonto?: (ponto_id: string) => void;
  onReauditarPonto?: (ponto_id: string) => void;
  pontoEmReprocesso?: string | null;
  /** Segundos decorridos externos (ex: simulação ou temporizador pai). */
  elapsedSeconds?: number | null;
  /** Timestamp de início da pesquisa (ms ou ISO string). */
  startedAt?: string | number | null;
  /** Consumo de tokens ao vivo para exibição compacta no cabeçalho */
  tokensAoVivo?: { prompt_tokens: number; completion_tokens: number; total_tokens: number } | null;
  /** Total de fontes catalogadas ou lidas */
  sourcesCount?: number;
  /** Callback para alternar a gaveta lateral de fontes e contexto */
  onToggleRail?: (targetTab?: 'contexto' | 'fontes') => void;
  /** Estado de abertura da gaveta lateral */
  isRailOpen?: boolean;
}

export const ExecutionView: React.FC<ExecutionViewProps> = ({
  stage,
  plan,
  searchResult,
  auditResult,
  cycleNumber,
  maxCycles,
  errorMessage,
  streamError,
  onReconnect,
  failedStage,
  isRetrying = false,
  onRetry,
  onReset,
  reasoningItems = [],
  onRefazerBuscaPonto,
  onReauditarPonto,
  pontoEmReprocesso = null,
  elapsedSeconds = null,
  startedAt = null,
  tokensAoVivo = null,
  sourcesCount,
  onToggleRail,
  isRailOpen = false,
}) => {
  // Cronômetro visível: tempo desde o início da execução. A região é
  // aria-live="off" para não narrar cada segundo no leitor de tela.
  const [inicioExecucao, setInicioExecucao] = useState<number | null>(() => {
    if (elapsedSeconds != null) return null;
    if (startedAt != null) {
      const ts = typeof startedAt === 'number' ? startedAt : new Date(startedAt).getTime();
      if (!Number.isNaN(ts) && ts > 0) return ts;
    }
    if (plan?.criado_em) {
      const ts = new Date(plan.criado_em).getTime();
      if (!Number.isNaN(ts) && ts > 0 && Math.abs(Date.now() - ts) < 24 * 3600 * 1000) return ts;
    }
    return (stage === 'searching' || stage === 'auditing' || stage === 'writing') ? Date.now() : null;
  });
  const [agora, setAgora] = useState<number>(() => Date.now());
  const emAndamento = stage === 'searching' || stage === 'auditing' || stage === 'writing';

  useEffect(() => {
    if (elapsedSeconds != null) return;
    if (emAndamento) {
      setInicioExecucao((prev) => {
        if (prev !== null) return prev;
        if (startedAt != null) {
          const ts = typeof startedAt === 'number' ? startedAt : new Date(startedAt).getTime();
          if (!Number.isNaN(ts) && ts > 0) return ts;
        }
        if (plan?.criado_em) {
          const ts = new Date(plan.criado_em).getTime();
          if (!Number.isNaN(ts) && ts > 0 && Math.abs(Date.now() - ts) < 24 * 3600 * 1000) return ts;
        }
        return Date.now();
      });
    } else if (stage === 'idle') {
      setInicioExecucao(null);
    }
  }, [emAndamento, stage, startedAt, plan?.criado_em, elapsedSeconds]);

  useEffect(() => {
    if (elapsedSeconds != null || inicioExecucao === null || !emAndamento) return;
    const timer = window.setInterval(() => setAgora(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [inicioExecucao, emAndamento, elapsedSeconds]);

  const decorridoTotal =
    elapsedSeconds != null
      ? Math.max(0, elapsedSeconds)
      : inicioExecucao !== null
      ? Math.max(0, Math.floor((agora - inicioExecucao) / 1000))
      : plan?.criado_em && plan?.concluido_em
      ? Math.max(0, Math.floor((new Date(plan.concluido_em).getTime() - new Date(plan.criado_em).getTime()) / 1000))
      : null;

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

  // Pendências por ponto exibidas no banner. Em falha sem parecer, os pontos
  // do plano viram alvo de recuperação pontual.
  const pontosPendentes = derivarPontosPendentes(
    auditResult,
    stage === 'failed' ? plan?.pontos ?? [] : []
  );

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
        <div className="execution-heading-main" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <ConvergenceLogo phase={stage === 'auditing' ? 'audit' : (stage === 'writing' || stage === 'completed') ? 'synthesis' : 'stream'} size={18} />
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

      {/* Barra de telemetria compacta: tokens e fontes ao vivo com gatilho para o painel lateral */}
      {(Boolean(tokensAoVivo && tokensAoVivo.total_tokens > 0) || typeof sourcesCount === 'number' || Boolean(onToggleRail)) && (
        <div className="exec-telemetry-bar" aria-label="Telemetria ao vivo da pesquisa">
          {tokensAoVivo && tokensAoVivo.total_tokens > 0 && (
            <div
              className="exec-telemetry-chip exec-telemetry-chip--tokens"
              title={`Tokens: ${tokensAoVivo.total_tokens.toLocaleString('pt-BR')} (Entrada: ${tokensAoVivo.prompt_tokens.toLocaleString('pt-BR')} · Saída: ${tokensAoVivo.completion_tokens.toLocaleString('pt-BR')})`}
            >
              <Sparkles size={12} className="exec-telemetry-icon" aria-hidden="true" />
              <span className="exec-telemetry-val">
                {tokensAoVivo.total_tokens >= 1000
                  ? `${(tokensAoVivo.total_tokens / 1000).toLocaleString('pt-BR', { maximumFractionDigits: 1 })} mil`
                  : tokensAoVivo.total_tokens}{' '}
                tokens
              </span>
            </div>
          )}

          {typeof sourcesCount === 'number' && (
            <button
              type="button"
              className="exec-telemetry-chip exec-telemetry-chip--fontes"
              onClick={() => onToggleRail?.('fontes')}
              aria-expanded={Boolean(isRailOpen)}
              aria-controls="rr-rail-panel"
              aria-label={`Ver ${sourcesCount} fontes catalogadas`}
              title="Abrir painel lateral de fontes"
            >
              <BookOpen size={12} className="exec-telemetry-icon" aria-hidden="true" />
              <span className="exec-telemetry-val">
                {sourcesCount === 1 ? '1 fonte' : `${sourcesCount} fontes`}
              </span>
              <ChevronRight size={12} className="exec-telemetry-arrow" aria-hidden="true" />
            </button>
          )}

          {onToggleRail && (
            <button
              type="button"
              className="exec-telemetry-chip exec-telemetry-chip--toggle"
              onClick={() => onToggleRail?.()}
              aria-expanded={Boolean(isRailOpen)}
              aria-controls="rr-rail-panel"
              aria-label="Alternar painel lateral com contexto e fontes completas"
            >
              <PanelRight size={12} className="exec-telemetry-icon" aria-hidden="true" />
              <span>Painel</span>
            </button>
          )}
        </div>
      )}

      {/* Queda do canal ao vivo: o servidor continua trabalhando */}
      {streamError && stage !== 'failed' && (
        <ErrorNotice
          compact
          falha={apresentarErro(streamError, { acao: 'acompanhar a pesquisa ao vivo', tom: 'aviso' })}
          onRetry={onReconnect}
          retryLabel="Reconectar"
        />
      )}

      {/* Estado: Reprovado na Auditoria / Teto de Tentativas Excedido */}
      {stage === 'rejected' && (
        <div className="alert-banner danger exec-error-card" role="alert">
          <XCircle size={20} aria-hidden="true" className="execution-banner-icon" />
          <div className="execution-banner-body">
            <strong>A auditoria barrou o dossiê</strong>
            <p className="execution-banner-copy">
              Nenhum ponto chegou a 11 de 12 critérios depois das tentativas. O dossiê não foi escrito.
              Refazer a busca dos pontos abaixo é o caminho mais curto para liberar.
            </p>
            {auditResult?.auditorias?.some((a) => (a.criterios ?? []).some((c) => !c.aprovado)) && (
              <BannerPontosPendentes
                pontos={pontosPendentes}
                onRefazerBuscaPonto={onRefazerBuscaPonto}
                onReauditarPonto={onReauditarPonto}
                pontoEmReprocesso={pontoEmReprocesso}
              />
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
        <div className="exec-error-card">
          <ErrorNotice
            falha={falhaDaExecucao({ isTimeout, isProviderError, failedStage, errorMessage })}
            onRetry={onRetry}
            retrying={isRetrying}
            retryLabel={
              failedStage === 'writing' || auditResult?.pronto_para_writer
                ? 'Escrever o dossiê de novo'
                : failedStage === 'auditing'
                ? 'Reauditar'
                : 'Repetir busca e auditoria'
            }
            acaoExtra={{ rotulo: 'Formular novo tema', onClick: onReset }}
          />
          <div className="execution-banner-body">
            <BannerPontosPendentes
              pontos={pontosPendentes}
              onRefazerBuscaPonto={onRefazerBuscaPonto}
              onReauditarPonto={onReauditarPonto}
              pontoEmReprocesso={pontoEmReprocesso}
            />
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
            <strong>Pontos aprovados. Redigindo o dossiê.</strong>
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
