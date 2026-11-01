/**
 * Tipos TypeScript canônicos alinhados aos esquemas Pydantic v2 do backend.
 */

export interface PlanoEixo {
  pergunta_principal: string;
  subperguntas: string[];
  hipoteses: string[];
  consultas_iniciais: string[];
  fontes_primarias_desejadas: string[];
  riscos_de_vies: string[];
  evidencias_que_refutariam: string[];
  criterio_de_conclusao: string;
  investigabilidade: string;
  eixo_essencial: boolean;
}

export interface PlanoInvestigacao {
  pedido_original: string;
  pedido_normalizado: string;
  publico: string;
  formato_entrega: string;
  recorte_temporal?: string | null;
  pressupostos?: string[];
  ambiguidades?: string[];
  pergunta_de_esclarecimento?: string | null;
  eixos: PlanoEixo[];
}

export interface PlanPontoItem {
  ponto_id: string;
  ponto_n: number;
  ponto: string;
  status: 'pendente' | 'em_andamento' | 'coletado' | 'aprovado' | 'reprovado';
  pontos_fracos?: string | null;
  eixo_estruturado?: PlanoEixo | null;
  reasoning_planejamento?: string | null;
}

export type RecenciaPolitica =
  | 'auto'
  | 'recente'
  | '24h'
  | '7d'
  | '30d'
  | '12m'
  | 'historico';

export interface PlanRequest {
  tema: string;
  id_pesquisa?: string | null;
  async_execute: boolean;
  callback_url?: string | null;
  n_pontos?: number;
  personas?: string[];
  execution_mode?: 'parallel' | 'sequential';
  recencia?: RecenciaPolitica;
}

export interface PlanPreferencias {
  n_pontos?: number;
  personas?: string[];
  recencia?: RecenciaPolitica | null;
  execution_mode?: 'parallel' | 'sequential';
  /** Limiar de aprovação carregado no plano (Passo 4). */
  criterios_minimos?: number | null;
  /** Modo de disparo escolhido na criação (Passo 5). */
  async_execute?: boolean | null;
  callback_url?: string | null;
}

export interface ModeloMetadados {
  model_requested?: string | null;
  model_used?: string | null;
  finish_reason?: string | null;
  is_regular_finish?: boolean | null;
  total_attempts?: number | null;
  latency_seconds_total?: number | null;
  usage_complete?: boolean | null;
  n_envelopes_sem_usage?: number | null;
  usage_total?: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  } | null;
  cost_complete?: boolean | null;
  cost_estimated_total?: number | null;
  cost_currency?: string | null;
}

export interface PlanAsyncResponse {
  id_pesquisa: string;
  tema: string;
  status: string;
  status_pipeline?: string | null;
  mensagem?: string | null;
  n_pontos: number;
  callback_url?: string | null;
  pontos: PlanPontoItem[];
  plano_estruturado?: PlanoInvestigacao | null;
  preferencias?: PlanPreferencias;
  reasoning_planejamento?: string | null;
  metadados_modelo?: ModeloMetadados | null;
}

export interface PlanResponse {
  id_pesquisa: string;
  tema: string;
  n_pontos: number;
  criado_em: string;
  concluido_em?: string | null;
  pontos: PlanPontoItem[];
  status_pipeline?: string | null;
  plano_estruturado?: PlanoInvestigacao | null;
  preferencias?: PlanPreferencias;
  reasoning_planejamento?: string | null;
  /** Projeção pública de telemetria do planejamento (tokens reais, sem prompts). */
  metadados_modelo?: ModeloMetadados | null;
}

export interface PersonaColetaItem {
  persona: string;
  analise: string;
  urls_fonte: string[];
  queries_executadas: number;
  falha_coleta: boolean;
  diagnostico?: string | null;
  lacunas?: string[] | null;
  reasoning?: string | null;
}

export interface SearchColetaResumo {
  ponto_id: string;
  ponto_n: number;
  status: string;
  falha_coleta: boolean;
  diagnostico?: string | null;
  total_urls_lidas: number;
  total_urls_fonte: number;
  tamanho_conteudo_caracteres: number;
  tentativas: number;
  personas: PersonaColetaItem[];
}

export interface SearchRequest {
  id_pesquisa: string;
  ponto_id?: string | null;
  personas?: string[] | null;
  execution_mode?: 'parallel' | 'sequential';
}

export interface SearchResponse {
  id_pesquisa: string;
  total_pontos_processados: number;
  status_pesquisa: string;
  total_falhas_coleta: number;
  resumo_coletas: SearchColetaResumo[];
}

export interface AuditCriterionDetail {
  id: number;
  aprovado: boolean;
  justificativa: string;
  claim_ids: string[];
  source_ids: string[];
  lacuna?: string | null;
  correcao?: string | null;
  personas_pertinentes?: string[];
}

export interface AuditItem {
  ponto_id: string;
  ponto_n: number;
  status: 'aprovado' | 'reprovado';
  pontuacao_percentual: number;
  criterios_aprovados: number;
  criterios_minimos: number;
  valido: boolean;
  criterios?: AuditCriterionDetail[] | null;
  pontos_fracos?: string | null;
  diagnostico?: string | null;
  resumo_auditoria?: string | null;
  reasoning_auditoria?: string | null;
}

export interface AuditRequest {
  id_pesquisa: string;
  ponto_id?: string | null;
  criterios_minimos?: number;
}

export interface AuditResponse {
  id_pesquisa: string;
  total_pontos: number;
  aprovados: number;
  reprovados: number;
  status_geral: string;
  status_pesquisa?: string | null;
  pronto_para_writer: boolean;
  auditorias: AuditItem[];
}

export interface WebhookEntregaMetadata {
  url?: string | null;
  status: string;
  http_status_code?: number | null;
  tentativas?: number | null;
  detalhes_falha?: string | null;
}

export interface WriterRequest {
  id_pesquisa: string;
}

export type FontesStatus = 'completo' | 'parcial' | 'indisponivel';

export interface FonteItem {
  url: string;
  titulo?: string | null;
  dominio?: string | null;
}

export interface FontesResumo {
  id_pesquisa?: string | null;
  status: FontesStatus;
  total_consultadas: number | null;
  total_utilizadas: number | null;
  total_nao_utilizadas: number | null;
  consultadas: FonteItem[];
  utilizadas: FonteItem[];
  nao_utilizadas: FonteItem[];
  observacao?: string | null;
  artifact_hash?: string | null;
}

export interface WriterResponse {
  id_pesquisa: string;
  tema: string;
  status: 'concluido' | 'incompleto' | 'falha';
  total_caracteres_dossier: number;
  concluido_em?: string | null;
  webhook_entrega?: WebhookEntregaMetadata | null;
  dossier_final?: string | null;
  dossier_resumo?: string | null;
  diagnostico?: string | null;
  qualidade_artigo?: Record<string, unknown> | null;
  fontes?: FontesResumo | null;
  reasoning_dossier?: string | null;
}

export interface CredentialCreateRequest {
  chave: string;
  valor: string;
  tipo: 'llm' | 'jina' | 'webhook' | 'parametro';
  base_url?: string | null;
  descricao?: string | null;
}

export interface CredentialResponse {
  status: string;
  chave: string;
  tipo: string;
  base_url?: string | null;
  criptografado: boolean;
  algoritmo: string;
  atualizado_em: string;
}

export interface CredentialSanitizedListItem {
  chave: string;
  tipo: string;
  base_url?: string | null;
  origem_ativa: 'ambiente' | 'banco_cifrado';
  mascarado: string;
  atualizado_em: string;
}

export interface CredentialListResponse {
  credenciais: CredentialSanitizedListItem[];
}

export interface ApiValidationError {
  loc: (string | number)[];
  msg: string;
  type: string;
}

export interface SessionPreferences {
  n_pontos: number;
  personas: string[];
}

export interface SessionResponse {
  authenticated: boolean;
  mode: string;
  preferences: SessionPreferences;
}

export interface PipelinePontoResumo {
  ponto_id: string;
  ponto_n: number;
  status: string;
  tentativas: number;
  tentativas_auditoria?: number;
  pontos_fracos?: string | null;
}

export interface PipelineStatusResumo {
  id_pesquisa: string;
  tema: string;
  status_pipeline: string;
  erro_pipeline?: string | null;
  estagio_falha?: 'searching' | 'auditing' | 'writing' | null;
  criado_em?: string | null;
  concluido_em?: string | null;
  webhook_status?: string | null;
  total_pontos: number;
  pontos: PipelinePontoResumo[];
  tem_dossier: boolean;
  tokens_prompt?: number | null;
  tokens_completion?: number | null;
  tokens_total?: number | null;
}

export interface ResearchDetail {
  id_pesquisa: string;
  tema: string;
  status_pipeline: string | null;
  criado_em: string;
  concluido_em?: string | null;
  plano_estruturado?: PlanoInvestigacao | null;
  pontos: PlanPontoItem[];
  preferencias?: PlanPreferencias | null;
  dossier_final?: string | null;
  metadados_redacao?: Record<string, unknown> | null;
  fontes?: FontesResumo | null;
  auditoria?: AuditResponse | null;
}

export interface ResearchHistoryRecord {
  id_pesquisa: string;
  tema: string;
  criado_em: string;
  concluido_em?: string | null;
  status: 'planejado' | 'buscando' | 'auditando' | 'redigindo' | 'concluido' | 'reprovado' | 'falha';
  total_pontos: number;
  planResponse?: PlanResponse;
  writerResponse?: WriterResponse;
  /** Auditoria persistida: reabrir uma pesquisa reprovada mostra os critérios que falharam. */
  auditResponse?: AuditResponse;
  /** Telemetria persistida: garante que recarregar a tela não zere a contagem de tokens */
  tokens?: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  } | null;
  /** Fontes catalogadas persistidas: garante que recarregar a tela não zere as fontes coletadas */
  fontes?: FontesResumo | null;
}
