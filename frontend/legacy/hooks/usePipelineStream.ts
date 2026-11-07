import { useState, useEffect, useRef, useCallback } from 'react';
import {
  AgentDeltaEvent,
  AgentRoleType,
  AuditResultEvent,
  PipelineErrorEvent,
  PipelineStatusEvent,
  PointStatusEvent,
  ReasoningFeedItem,
  ReportFinalEvent,
  SearchProgressEvent,
  StageLifecycleEvent,
  WriterProgressEvent,
} from '../types/stream';

const STAGE_TO_ROLE: Record<string, AgentRoleType> = {
  plan: 'planejador',
  search: 'busca',
  audit: 'auditor',
  writer: 'redator',
};

const STAGE_LABEL: Record<string, string> = {
  plan: 'Planejador',
  search: 'Varredura Web',
  audit: 'Auditoria',
  writer: 'Redação',
};

/** Intervalo de coalescência dos deltas SSE antes de atualizar o estado React. */
const DELTA_FLUSH_MS = 80;

interface PendingDelta {
  id: string;
  role: AgentRoleType;
  agentLabel: string;
  stageLabel: string;
  stage: string;
  pontoId?: string | null;
  kind: string;
  text: string;
}

/** ID estável do item "ao vivo" de um agente/estágio/ponto. */
export function liveReasoningId(stage: string, agent?: string | null, pontoId?: string | null): string {
  return `live-${stage}-${agent || 'agent'}-${pontoId || 'global'}`;
}

interface UsePipelineStreamOptions {
  idPesquisa?: string | null;
  enabled?: boolean;
  onStatusChange?: (status: string) => void;
  onPointStatus?: (event: PointStatusEvent) => void;
  onSearchProgress?: (event: SearchProgressEvent) => void;
  onAuditResult?: (event: AuditResultEvent) => void;
  onWriterProgress?: (event: WriterProgressEvent) => void;
  /** Consumo real do processo Hermes (usage.json) durante a execução. */
  onUsageProgress?: (event: { tokens_prompt: number; tokens_completion: number; tokens_total: number }) => void;
  onReportFinal?: (event: ReportFinalEvent) => void;
  onAgentDelta?: (event: AgentDeltaEvent) => void;
  onStageLifecycle?: (event: StageLifecycleEvent) => void;
  onError?: (error: string) => void;
}

export function formatPersonaTitle(name: string): string {
  const map: Record<string, string> = {
    historiador: 'Historiador',
    visionario: 'Visionário',
    cetico: 'Cético',
    futurista: 'Futurista',
  };
  return map[name.toLowerCase()] || name.charAt(0).toUpperCase() + name.slice(1);
}

export function usePipelineStream(options: UsePipelineStreamOptions) {
  const { idPesquisa, enabled = true } = options;
  const callbacksRef = useRef(options);
  callbacksRef.current = options;

  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [isCompleted, setIsCompleted] = useState<boolean>(false);
  const isCompletedRef = useRef<boolean>(false);
  const [streamError, setStreamError] = useState<string | null>(null);
  const [reasoningItems, setReasoningItems] = useState<ReasoningFeedItem[]>([]);
  const [lastEvent, setLastEvent] = useState<string | null>(null);

  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const retryCountRef = useRef<number>(0);
  const isMountedRef = useRef<boolean>(true);
  const activeIdRef = useRef<string | null>(null);
  const pendingDeltasRef = useRef<Map<string, PendingDelta>>(new Map());
  const flushTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const flushDeltasRef = useRef<(() => void) | null>(null);
  const finalizarItensAoVivoRef = useRef<(() => void) | null>(null);

  const finalizarItensAoVivo = useCallback(() => {
    if (!isMountedRef.current) return;
    setReasoningItems((prev) => {
      if (!prev.some((item) => item.streaming)) return prev;
      return prev.map((item) =>
        item.streaming
          ? {
              ...item,
              streaming: false,
              status: 'concluido',
              title: item.title.replace(/\s*\(ao vivo\)\s*$/i, ''),
            }
          : item
      );
    });
  }, []);

  const closeConnection = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    // Descarrega os deltas pendentes ANTES de encerrar: sem isto, os últimos
    // ~80ms de raciocínio eram perdidos em report.final, erro e desmontagem.
    flushDeltasRef.current?.();
    // Nenhum card pode continuar "(ao vivo)"/streaming depois que a conexão cai.
    finalizarItensAoVivoRef.current?.();
    if (flushTimerRef.current !== null) {
      clearTimeout(flushTimerRef.current);
      flushTimerRef.current = null;
    }
    setIsConnected(false);
  }, []);

  const addReasoningItem = useCallback((item: ReasoningFeedItem) => {
    setReasoningItems((prev) => {
      // Evita duplicatas pelo ID único
      if (prev.some((p) => p.id === item.id)) {
        return prev;
      }
      return [...prev, item];
    });
  }, []);

  /**
   * Insere ou atualiza um item, opcionalmente substituindo o item "ao vivo"
   * (`previousId`) no MESMO índice — o card não salta para o fim da lista nem
   * perde o timestamp do início do trabalho do agente.
   */
  const upsertReasoningItem = useCallback((item: ReasoningFeedItem, previousId?: string) => {
    setReasoningItems((prev) => {
      const idx = prev.findIndex((p) => p.id === item.id || (previousId && p.id === previousId));
      if (idx === -1) return [...prev, item];
      const next = [...prev];
      const anterior = next[idx];
      next[idx] = {
        ...anterior,
        ...item,
        id: item.id,
        timestamp: anterior.timestamp || item.timestamp,
        // Preserva métricas do item ao vivo (duration_ms) e registra de onde o
        // card veio, para o feed manter o estado aberto na troca de ID.
        details: {
          ...(anterior.details || {}),
          ...(item.details || {}),
          previous_id: previousId ?? (anterior.details as Record<string, unknown> | undefined)?.previous_id,
        },
      };
      return next;
    });
  }, []);

  const clearReasoningItems = useCallback(() => {
    pendingDeltasRef.current.clear();
    setReasoningItems([]);
  }, []);

  const removeReasoningItem = useCallback((id: string) => {
    pendingDeltasRef.current.delete(id);
    setReasoningItems((prev) => prev.filter((p) => p.id !== id));
  }, []);

  /**
   * Descarrega os deltas acumulados em UMA atualização de estado.
   *
   * Motivo: um delta por token gerava uma renderização da árvore inteira por
   * token (174+ numa execução). O buffer coalesce por item e aplica em lote a
   * cada ~80ms, mantendo a sensação de tempo real sem inundar o React.
   */
  const flushDeltas = useCallback(() => {
    if (!isMountedRef.current) return;
    if (flushTimerRef.current !== null) {
      clearTimeout(flushTimerRef.current);
      flushTimerRef.current = null;
    }
    const pendentes = pendingDeltasRef.current;
    if (pendentes.size === 0) return;
    const lote = Array.from(pendentes.values());
    pendentes.clear();

    setReasoningItems((prev) => {
      const next = [...prev];
      const indicePorId = new Map(next.map((item, i) => [item.id, i]));
      for (const delta of lote) {
        const idx = indicePorId.get(delta.id);
        if (idx === undefined) {
          indicePorId.set(delta.id, next.length);
          next.push({
            id: delta.id,
            timestamp: new Date().toISOString(),
            agentType: delta.role,
            agentName: delta.agentLabel,
            title: `${delta.stageLabel} — ${delta.agentLabel} (ao vivo)`,
            reasoning: delta.text,
            status: 'em_andamento',
            streaming: true,
            details: {
              stage: delta.stage,
              ponto_id: delta.pontoId,
              kind: delta.kind,
              started_at: Date.now(),
            },
          });
        } else {
          next[idx] = {
            ...next[idx],
            reasoning: next[idx].reasoning + delta.text,
            streaming: true,
          };
        }
      }
      return next;
    });
  }, []);

  flushDeltasRef.current = flushDeltas;

  /** Aplica um delta ao vivo ao buffer; cria o item na primeira vez, concatena depois. */
  const applyAgentDelta = useCallback((data: AgentDeltaEvent) => {
    const role: AgentRoleType = STAGE_TO_ROLE[data.stage] || 'busca';
    const agentLabel = data.agent ? formatPersonaTitle(data.agent) : (STAGE_LABEL[data.stage] || data.stage);
    const id = liveReasoningId(data.stage, data.agent, data.ponto_id);

    const atual = pendingDeltasRef.current.get(id);
    if (atual) {
      atual.text += data.text;
    } else {
      pendingDeltasRef.current.set(id, {
        id,
        role,
        agentLabel,
        stageLabel: STAGE_LABEL[data.stage] || data.stage,
        stage: data.stage,
        pontoId: data.ponto_id,
        kind: data.kind,
        text: data.text,
      });
    }

    if (flushTimerRef.current === null) {
      flushTimerRef.current = setTimeout(flushDeltas, DELTA_FLUSH_MS);
    }
  }, [flushDeltas]);

  /** Encerra o indicador de streaming dos itens ao vivo de um estágio. */
  const finishStage = useCallback((stage: string, pontoId?: string | null) => {
    // Garante que o texto já recebido apareça antes de fechar o item.
    flushDeltas();
    setReasoningItems((prev) =>
      prev.map((item) => {
        const details = item.details as Record<string, unknown> | undefined;
        if (!item.streaming || details?.stage !== stage) return item;
        if (pontoId && details?.ponto_id && details.ponto_id !== pontoId) return item;
        const inicio = (details?.started_at as number | undefined) ?? null;
        return {
          ...item,
          streaming: false,
          status: 'concluido',
          // Não deixar "(ao vivo)" vazando para o histórico concluído.
          title: item.title.replace(/\s*\(ao vivo\)\s*$/i, ''),
          details: {
            ...(details || {}),
            duration_ms: inicio ? Date.now() - inicio : undefined,
          },
        };
      })
    );
  }, [flushDeltas]);

  const connect = useCallback(() => {
    if (!idPesquisa || !enabled) return;

    closeConnection();
    activeIdRef.current = idPesquisa;

    const streamUrl = `/api/v1/pipeline/${encodeURIComponent(idPesquisa)}/stream`;
    const es = new EventSource(streamUrl, { withCredentials: true });
    eventSourceRef.current = es;

    es.onopen = () => {
      if (!isMountedRef.current) return;
      setIsConnected(true);
      setStreamError(null);
      retryCountRef.current = 0;
    };

    es.addEventListener('pipeline.status', (event: MessageEvent) => {
      if (!isMountedRef.current || activeIdRef.current !== idPesquisa) return;
      try {
        const data: PipelineStatusEvent = JSON.parse(event.data);
        setLastEvent('pipeline.status');
        callbacksRef.current.onStatusChange?.(data.status_pipeline);

        if (data.status_pipeline === 'concluido') {
          setIsCompleted(true);
          isCompletedRef.current = true;
        } else if (data.status_pipeline === 'falha' || data.status_pipeline === 'reprovado') {
          setIsCompleted(true);
          isCompletedRef.current = true;
          closeConnection();
        }
      } catch (err) {
        console.warn('[usePipelineStream] Erro ao parsear pipeline.status:', err);
      }
    });

    es.addEventListener('point.status', (event: MessageEvent) => {
      if (!isMountedRef.current || activeIdRef.current !== idPesquisa) return;
      try {
        const data: PointStatusEvent = JSON.parse(event.data);
        setLastEvent('point.status');
        callbacksRef.current.onPointStatus?.(data);
      } catch (err) {
        console.warn('[usePipelineStream] Erro ao parsear point.status:', err);
      }
    });

    es.addEventListener('agent.delta', (event: MessageEvent) => {
      if (!isMountedRef.current || activeIdRef.current !== idPesquisa) return;
      try {
        const data: AgentDeltaEvent = JSON.parse(event.data);
        setLastEvent('agent.delta');
        callbacksRef.current.onAgentDelta?.(data);
        // `content` é a resposta bruta do agente; o feed mostra o raciocínio.
        if (data.kind === 'reasoning' && data.text) {
          applyAgentDelta(data);
        }
      } catch (err) {
        console.warn('[usePipelineStream] Erro ao parsear agent.delta:', err);
      }
    });

    es.addEventListener('stage.start', (event: MessageEvent) => {
      if (!isMountedRef.current || activeIdRef.current !== idPesquisa) return;
      try {
        const data: StageLifecycleEvent = JSON.parse(event.data);
        setLastEvent('stage.start');
        callbacksRef.current.onStageLifecycle?.(data);
      } catch (err) {
        console.warn('[usePipelineStream] Erro ao parsear stage.start:', err);
      }
    });

    es.addEventListener('stage.end', (event: MessageEvent) => {
      if (!isMountedRef.current || activeIdRef.current !== idPesquisa) return;
      try {
        const data: StageLifecycleEvent = JSON.parse(event.data);
        setLastEvent('stage.end');
        callbacksRef.current.onStageLifecycle?.(data);
        finishStage(data.stage, data.ponto_id);
      } catch (err) {
        console.warn('[usePipelineStream] Erro ao parsear stage.end:', err);
      }
    });

    es.addEventListener('search.progress', (event: MessageEvent) => {
      if (!isMountedRef.current || activeIdRef.current !== idPesquisa) return;
      try {
        const data: SearchProgressEvent = JSON.parse(event.data);
        setLastEvent('search.progress');
        callbacksRef.current.onSearchProgress?.(data);

        if (data.reasoning_coleta && data.reasoning_coleta.trim().length > 0) {
          const personaTitle = formatPersonaTitle(data.persona);
          // O parecer final substitui o item ao vivo da persona neste ponto,
          // no mesmo slot da lista (previousId no fim da chamada).
          upsertReasoningItem({
            id: `search-${data.ponto_id}-${data.persona}-${data.queries_executadas}`,
            timestamp: new Date().toISOString(),
            agentType: 'busca',
            agentName: personaTitle,
            title: `Persona ${personaTitle} · Busca`,
            reasoning: data.reasoning_coleta,
            status: data.falha_coleta ? 'falha' : 'concluido',
            details: {
              queries_executadas: data.queries_executadas,
              urls_lidas: data.urls_lidas,
              ponto_id: data.ponto_id,
            },
          }, liveReasoningId('search', data.persona, data.ponto_id));
        }
      } catch (err) {
        console.warn('[usePipelineStream] Erro ao parsear search.progress:', err);
      }
    });

    es.addEventListener('audit.result', (event: MessageEvent) => {
      if (!isMountedRef.current || activeIdRef.current !== idPesquisa) return;
      try {
        const data: AuditResultEvent = JSON.parse(event.data);
        setLastEvent('audit.result');
        callbacksRef.current.onAuditResult?.(data);

        if (data.reasoning_auditoria && data.reasoning_auditoria.trim().length > 0) {
          upsertReasoningItem({
            id: `audit-${data.ponto_id}`,
            timestamp: new Date().toISOString(),
            agentType: 'auditor',
            agentName: 'Auditor Analítico',
            title: `Auditoria · Ponto ${data.ponto_n} (${data.criterios_aprovados}/12)`,
            reasoning: data.reasoning_auditoria,
            status: data.status,
            score: data.pontuacao_percentual,
            pointNumber: data.ponto_n,
            details: {
              criterios_aprovados: data.criterios_aprovados,
              pontos_fracos: data.pontos_fracos,
            },
          }, liveReasoningId('audit', 'auditor', data.ponto_id));
        }
      } catch (err) {
        console.warn('[usePipelineStream] Erro ao parsear audit.result:', err);
      }
    });

    es.addEventListener('usage.progress', (event: MessageEvent) => {
      if (!isMountedRef.current || activeIdRef.current !== idPesquisa) return;
      try {
        const data = JSON.parse(event.data) as {
          tokens_prompt?: number;
          tokens_completion?: number;
          tokens_total?: number;
        };
        callbacksRef.current.onUsageProgress?.({
          tokens_prompt: Number(data.tokens_prompt ?? 0),
          tokens_completion: Number(data.tokens_completion ?? 0),
          tokens_total: Number(data.tokens_total ?? 0),
        });
      } catch (err) {
        console.warn('[usePipelineStream] Erro ao parsear usage.progress:', err);
      }
    });

    es.addEventListener('writer.progress', (event: MessageEvent) => {
      if (!isMountedRef.current || activeIdRef.current !== idPesquisa) return;
      try {
        const data: WriterProgressEvent = JSON.parse(event.data);
        setLastEvent('writer.progress');
        callbacksRef.current.onWriterProgress?.(data);

        if (data.reasoning_dossier && data.reasoning_dossier.trim().length > 0) {
          upsertReasoningItem({
            id: `writer-${idPesquisa}`,
            timestamp: new Date().toISOString(),
            agentType: 'redator',
            agentName: 'Redator Final',
            title: 'Redação do dossiê',
            reasoning: data.reasoning_dossier,
            status: data.status,
            details: {
              total_caracteres: data.total_caracteres,
            },
          }, liveReasoningId('writer', 'redator final', null));
        }
      } catch (err) {
        console.warn('[usePipelineStream] Erro ao parsear writer.progress:', err);
      }
    });

    es.addEventListener('report.final', (event: MessageEvent) => {
      if (!isMountedRef.current || activeIdRef.current !== idPesquisa) return;
      try {
        const data: ReportFinalEvent = JSON.parse(event.data);
        setLastEvent('report.final');
        setIsCompleted(true);
        isCompletedRef.current = true;
        callbacksRef.current.onReportFinal?.(data);
        closeConnection();
      } catch (err) {
        console.warn('[usePipelineStream] Erro ao parsear report.final:', err);
      }
    });

    es.addEventListener('pipeline.error', (event: MessageEvent) => {
      if (!isMountedRef.current || activeIdRef.current !== idPesquisa) return;
      try {
        const data: PipelineErrorEvent = JSON.parse(event.data);
        setLastEvent('pipeline.error');
        setStreamError(data.erro);
        callbacksRef.current.onError?.(data.erro);
        closeConnection();
      } catch (err) {
        console.warn('[usePipelineStream] Erro ao parsear pipeline.error:', err);
      }
    });

    es.onerror = () => {
      if (!isMountedRef.current) return;
      setIsConnected(false);

      // Se já concluiu, encerra silenciosamente
      if (isCompletedRef.current) {
        closeConnection();
        return;
      }

      // Reconexão automática com backoff exponencial até 5 tentativas
      if (retryCountRef.current < 5) {
        const delay = Math.min(1000 * Math.pow(1.5, retryCountRef.current), 10000);
        retryCountRef.current += 1;
        reconnectTimeoutRef.current = setTimeout(() => {
          if (isMountedRef.current && activeIdRef.current === idPesquisa) {
            connect();
          }
        }, delay);
      } else {
        setStreamError('A conexão ao vivo caiu depois de várias tentativas.');
        closeConnection();
      }
    };
  }, [
    idPesquisa,
    enabled,
    closeConnection,
    addReasoningItem,
    upsertReasoningItem,
    removeReasoningItem,
    applyAgentDelta,
    finishStage,
  ]);

  useEffect(() => {
    isMountedRef.current = true;
    finalizarItensAoVivoRef.current = finalizarItensAoVivo;
    return () => {
      isMountedRef.current = false;
      finalizarItensAoVivoRef.current = null;
    };
  }, [finalizarItensAoVivo]);

  useEffect(() => {
    isMountedRef.current = true;
    if (enabled && idPesquisa) {
      connect();
    }
    return () => {
      isMountedRef.current = false;
      closeConnection();
    };
  }, [idPesquisa, enabled, connect, closeConnection]);

  return {
    isConnected,
    isCompleted,
    streamError,
    reasoningItems,
    lastEvent,
    addReasoningItem,
    upsertReasoningItem,
    clearReasoningItems,
    flushDeltas,
    reconnect: connect,
    closeStream: closeConnection,
  };
}
