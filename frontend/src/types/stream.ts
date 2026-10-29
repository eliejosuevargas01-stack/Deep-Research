/**
 * Tipos e contratos TypeScript para Streaming SSE e Reasoning em Tempo Real.
 * Conforme Adendo v8 e Checkpoint 2.
 */

export interface PipelineStatusEvent {
  id_pesquisa: string;
  status_pipeline: string;
  timestamp?: string | null;
}

export interface PointStatusEvent {
  id_pesquisa: string;
  ponto_id: string;
  ponto_n: number;
  status: string;
  tentativas: number;
}

export interface SearchProgressEvent {
  id_pesquisa: string;
  ponto_id: string;
  persona: string;
  queries_executadas: number;
  urls_lidas: number;
  falha_coleta: boolean;
  reasoning_coleta?: string | null;
}

export interface AuditResultEvent {
  id_pesquisa: string;
  ponto_id: string;
  ponto_n: number;
  status: 'aprovado' | 'reprovado';
  pontuacao_percentual: number;
  criterios_aprovados: number;
  reasoning_auditoria?: string | null;
  pontos_fracos?: string | null;
}

export interface WriterProgressEvent {
  id_pesquisa: string;
  status: string;
  reasoning_dossier?: string | null;
  total_caracteres?: number | null;
}

export interface ReportFinalEvent {
  id_pesquisa: string;
  status: string;
  dossier_final: string;
  total_caracteres: number;
  concluido_em: string;
}

export interface PipelineErrorEvent {
  id_pesquisa: string;
  erro: string;
}

/** Delta ao vivo de raciocínio/resposta vindo do provedor LLM (SSE em tempo real). */
export interface AgentDeltaEvent {
  id_pesquisa: string;
  stage: 'plan' | 'search' | 'audit' | 'writer' | string;
  agent?: string | null;
  ponto_id?: string | null;
  kind: 'reasoning' | 'content' | string;
  text: string;
}

/** Início/fim de um estágio do pipeline (stage.start / stage.end). */
export interface StageLifecycleEvent {
  id_pesquisa: string;
  stage: string;
  agent?: string | null;
  ponto_id?: string | null;
}

export type AgentRoleType = 'planejador' | 'busca' | 'auditor' | 'redator';

export interface ReasoningFeedItem {
  id: string;
  timestamp: string;
  agentType: AgentRoleType;
  agentName: string;
  title: string;
  reasoning: string;
  status?: string;
  score?: number;
  cycle?: number;
  pointNumber?: number;
  details?: Record<string, unknown>;
  /** true enquanto o agente ainda está gerando texto (delta em andamento). */
  streaming?: boolean;
}
