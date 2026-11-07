/**
 * Cliente tipado da API v1.2 do DeepResearch.
 *
 * Rotas usadas (src/api.py) — e só estas:
 *   POST /research  → 202 {research_id, status}
 *   GET  /research/{id}
 *   GET  /config   (alias do endpoint de settings)
 *   PUT  /config   (alias do endpoint de settings)
 *
 * Sem cookies/sessão: autenticação via `X-API-Key` (chave guardada só no
 * navegador, em localStorage `dr:v12:apiKey`). Nenhum fetch às rotas legadas
 * (plan, search, audit, writer, pipeline, settings hermes, app session)
 * existe neste módulo.
 */

export interface ResearchCreateRequest {
  tema: string;
  profundidade: number;
  veracidade_alvo: number;
  max_rodadas_auditoria?: number;
  atualidade?: string;
  callback_url: string;
}

export interface ResearchCreateResponse {
  research_id: string;
  status: string;
}

export interface PontoDossie {
  ponto_id: number;
  enunciado: string;
  subperguntas?: string[] | null;
  hipoteses?: string[] | null;
  lacunas_iniciais?: string[] | null;
  perguntas_auditoria?: Record<string, string> | null;
  ultimo_resultado_auditor?: Record<string, boolean> | null;
  porcentagem_aprovacao?: number | null;
  rodada_atual?: number | null;
  aprovado?: boolean | null;
  relatorio_ponto?: string | null;
  lacunas_ponto?: string | null;
}

export interface AuditoriaItem {
  ponto_id: number;
  rodada: number;
  perguntas_respondidas?: Record<string, boolean> | null;
  perguntas_true?: number | null;
  porcentagem_aprovacao?: number | null;
  meta_veracidade_alvo?: number | null;
  aprovado?: boolean | null;
  model_used?: string | null;
  total_tokens?: number | null;
  created_at?: string | null;
}

export interface ResearchRun {
  research_id: string;
  tema: string;
  profundidade: number;
  veracidade_alvo: number;
  max_rodadas_auditoria: number;
  atualidade: string;
  callback_url: string;
  status: 'PROCESSING' | 'COMPLETED' | 'FAILED' | string;
  plano_inicial?: unknown;
  relatorio_final_consolidado?: string | null;
  lacunas_finais_consolidadas?: unknown;
  urls_usadas_globais?: string[] | null;
  urls_lidas_globais?: string[] | null;
  urls_nao_usadas_globais?: string[] | null;
  total_prompt_tokens?: number | null;
  total_completion_tokens?: number | null;
  total_reasoning_tokens?: number | null;
  total_tokens?: number | null;
  created_at?: string | null;
  completed_at?: string | null;
  pontos?: PontoDossie[] | null;
  /** Campo novo da D-04; ausente em backends anteriores — tratar como opcional. */
  auditorias?: AuditoriaItem[] | null;
  /** Avaliação por ponto (planner.avaliacao_pontos); só vem no GET final. */
  avaliacao_pontos?: Array<{
    ponto_id: number;
    aprovado?: boolean | null;
    porcentagem_aprovacao?: number | null;
    perguntas_true?: number | null;
    total_perguntas?: number | null;
    meta_veracidade_alvo?: number | null;
  }> | null;
  /** Mensagem de falha (evento run.falhou). */
  erro?: string | null;
}

export type PapelModelo =
  | 'planner'
  | 'historiador'
  | 'cetico'
  | 'visionario'
  | 'futurista'
  | 'auditor'
  | 'redator';

export const PAPEIS: PapelModelo[] = [
  'planner',
  'historiador',
  'cetico',
  'visionario',
  'futurista',
  'auditor',
  'redator',
];

export interface AppConfig {
  base_url: string;
  api_key: string;
  default_model: string;
  max_concurrent_children: number;
  max_spawn_depth: number;
  oneshot_max_children: number;
  modelos_por_papel: Record<PapelModelo, string>;
}

export class ApiV12Error extends Error {
  readonly status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiV12Error';
    this.status = status;
  }
}

/* ------------------------------------------------------------------ */
/* API key (guardada só no navegador; nunca logada)                     */
/* ------------------------------------------------------------------ */

/** Chave do localStorage onde a API key do backend é persistida. */
export const CHAVE_API_KEY = 'dr:v12:apiKey';

export const MENSAGEM_401 = 'API key inválida ou ausente — configure a API key.';

/** Evento global disparado a cada 401 para a UI abrir a configuração. */
export const EVENTO_PRECISA_API_KEY = 'dr:v12:precisa-api-key';

export function lerApiKey(): string | null {
  try {
    const v = localStorage.getItem(CHAVE_API_KEY);
    return v && v.trim() ? v : null;
  } catch {
    return null;
  }
}

export function gravarApiKey(chave: string): void {
  try {
    const v = chave.trim();
    if (v) localStorage.setItem(CHAVE_API_KEY, v);
    else localStorage.removeItem(CHAVE_API_KEY);
  } catch {
    /* armazenamento indisponível: segue sem persistir */
  }
}

export function limparApiKey(): void {
  try {
    localStorage.removeItem(CHAVE_API_KEY);
  } catch {
    /* ignora */
  }
}

/** True quando o erro é 401 (auth) — a pesquisa ativa deve ser preservada. */
export function ehErroApiKey(err: unknown): boolean {
  return err instanceof ApiV12Error && err.status === 401;
}

function sinalizarPrecisaApiKey(): void {
  try {
    if (typeof window !== 'undefined' && typeof window.dispatchEvent === 'function') {
      window.dispatchEvent(new CustomEvent(EVENTO_PRECISA_API_KEY));
    }
  } catch {
    /* ignora */
  }
}

/** Base da API: mesma origem por padrão; sobrescrevível via VITE_API_BASE. */
export function apiBase(): string {
  const env = import.meta.env?.VITE_API_BASE as string | undefined;
  if (env && env.trim()) return env.replace(/\/+$/, '');
  return '';
}

/** Extrai mensagem legível do corpo de erro do FastAPI ({detail}). */
export async function mensagemDeErro(res: Response): Promise<string> {
  let corpo: unknown = null;
  try {
    corpo = await res.json();
  } catch {
    /* corpo não-JSON: usa status text abaixo */
  }
  if (corpo && typeof corpo === 'object' && 'detail' in corpo) {
    const detail = (corpo as { detail: unknown }).detail;
    if (typeof detail === 'string' && detail.trim()) return detail;
    if (Array.isArray(detail)) {
      const partes = detail
        .map((item) => {
          if (typeof item === 'string') return item;
          if (item && typeof item === 'object' && 'msg' in item) {
            return String((item as { msg: unknown }).msg);
          }
          return '';
        })
        .filter(Boolean);
      if (partes.length > 0) return partes.join('; ');
    }
  }
  return `requisição falhou (HTTP ${res.status})`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  const apiKey = lerApiKey();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...((init?.headers ?? {}) as Record<string, string>),
  };
  if (apiKey) headers['X-API-Key'] = apiKey;
  try {
    res = await fetch(`${apiBase()}${path}`, { ...init, headers });
  } catch (e) {
    throw new ApiV12Error(
      e instanceof Error ? `rede indisponível: ${e.message}` : 'rede indisponível',
      0,
    );
  }
  if (res.status === 401) {
    sinalizarPrecisaApiKey();
    throw new ApiV12Error(MENSAGEM_401, 401);
  }
  if (!res.ok) throw new ApiV12Error(await mensagemDeErro(res), res.status);
  if (res.status === 204) return undefined as unknown as T;
  return (await res.json()) as T;
}

export function criarPesquisa(body: ResearchCreateRequest): Promise<ResearchCreateResponse> {
  return request<ResearchCreateResponse>('/research', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export function obterPesquisa(researchId: string): Promise<ResearchRun> {
  return request<ResearchRun>(`/research/${encodeURIComponent(researchId)}`);
}

export function lerConfig(): Promise<AppConfig> {
  return request<AppConfig>('/config');
}

/** Payload parcial: campos omitidos ficam como estão (PUT /config).
 *  base_url/api_key são provedor (ambiente) — nunca entram no PUT. */
export type ConfigUpdate = Partial<
  Omit<AppConfig, 'modelos_por_papel' | 'base_url' | 'api_key'> & {
    modelos_por_papel: Partial<Record<PapelModelo, string>>;
  }
>;

export function salvarConfig(patch: ConfigUpdate): Promise<AppConfig> {
  return request<AppConfig>('/config', { method: 'PUT', body: JSON.stringify(patch) });
}
