import {
  ApiValidationError,
  AuditRequest,
  AuditResponse,
  CredentialCreateRequest,
  CredentialListResponse,
  CredentialResponse,
  PipelineStatusResumo,
  PlanAsyncResponse,
  PlanRequest,
  PlanResponse,
  RecenciaPolitica,
  ResearchDetail,
  SearchRequest,
  SearchResponse,
  SessionResponse,
  WriterRequest,
  WriterResponse,
  FontesResumo,
} from '../types/api';

/** Limites do rigor de auditoria conforme AuditRequest (10..12, padrão 11). */
export const RIGOR_MINIMO = 10;
export const RIGOR_MAXIMO = 12;
export const RIGOR_PADRAO = 11;

export function normalizarRigor(valor: unknown): number {
  const n = typeof valor === 'number' ? Math.floor(valor) : parseInt(String(valor ?? ''), 10);
  if (Number.isNaN(n)) return RIGOR_PADRAO;
  return Math.min(RIGOR_MAXIMO, Math.max(RIGOR_MINIMO, n));
}

export interface CreatePlanOptions {
  tema: string;
  n_pontos?: number;
  personas?: string[];
  idPesquisa?: string;
  recencia?: RecenciaPolitica;
  criterios_minimos?: number;
  execution_mode?: 'parallel' | 'sequential';
  async_execute?: boolean;
  callback_url?: string | null;
  signal?: AbortSignal;
}

function isLocalCallbackUrl(url: string): boolean {
  const v = url.trim().toLowerCase();
  return (
    v.startsWith('http://localhost') ||
    v.startsWith('https://localhost') ||
    v.startsWith('http://127.') ||
    v.startsWith('https://127.') ||
    v.startsWith('http://[::1]') ||
    v.startsWith('https://[::1]') ||
    v.startsWith('http://0.0.0.0') ||
    v === 'localhost'
  );
}

/** Valida callback http/https e sinaliza host local (não roteável pelo servidor). */
export function validarCallbackUrl(url: string): { valida: boolean; avisoLocal: boolean; motivo?: string } {
  const v = url.trim();
  if (!v) return { valida: false, avisoLocal: false, motivo: 'Informe a URL de callback.' };
  let parsed: URL;
  try {
    parsed = new URL(v);
  } catch {
    return { valida: false, avisoLocal: false, motivo: 'URL inválida: use http(s)://host/caminho.' };
  }
  if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
    return { valida: false, avisoLocal: false, motivo: 'Use http:// ou https://.' };
  }
  return { valida: true, avisoLocal: isLocalCallbackUrl(v) };
}

/**
 * Falha de API com status HTTP e detalhe técnico preservados.
 * A UI nunca mostra `message` cru: `utils/erros.ts` traduz para texto humano
 * e mantém o detalhe dentro de "Detalhes técnicos".
 */
export class ApiError extends Error {
  readonly status: number;
  readonly detalhe: string;

  constructor(status: number, detalhe: string) {
    super(detalhe ? `HTTP ${status} · ${detalhe}` : `HTTP ${status}`);
    this.name = 'ApiError';
    this.status = status;
    this.detalhe = detalhe;
  }
}

/** Converte uma resposta HTTP de erro em ApiError. */
export async function apiError(response: Response): Promise<ApiError> {
  const detalhe = await parseApiError(response);
  return new ApiError(response.status, detalhe);
}

/**
 * Extrai o detalhe técnico de uma resposta de erro (uso interno/log).
 */
export async function parseApiError(response: Response): Promise<string> {
  try {
    const text = await response.text();
    if (!text) {
      return 'Resposta sem corpo';
    }

    try {
      const data = JSON.parse(text);
      if (typeof data.detail === 'string') {
        return data.detail;
      }
      if (typeof data.detail === 'object' && data.detail !== null) {
        if (Array.isArray(data.detail)) {
          // Erros de validação Pydantic (RequestValidationError)
          const msgs = (data.detail as ApiValidationError[]).map((err) => {
            const field = Array.isArray(err.loc) ? err.loc.filter((p) => p !== 'body').join('.') : '';
            return field ? `${field}: ${err.msg}` : (err.msg || JSON.stringify(err));
          });
          return msgs.join('; ');
        }
        // Objeto de detalhe estruturado do FastAPI (ex: ambiguidade, mensagem, esclarecimento)
        const parts: string[] = [];
        if (data.detail.mensagem) parts.push(String(data.detail.mensagem));
        if (data.detail.pergunta_de_esclarecimento) {
          parts.push(`Esclarecimento: ${data.detail.pergunta_de_esclarecimento}`);
        }
        if (data.detail.diagnostico) parts.push(`Diagnóstico: ${data.detail.diagnostico}`);
        if (data.detail.error) parts.push(String(data.detail.error));
        if (data.detail.msg) parts.push(String(data.detail.msg));
        if (parts.length > 0) {
          return parts.join(' — ');
        }
        return JSON.stringify(data.detail);
      }
      if (data.message && typeof data.message === 'string') {
        return data.message;
      }
    } catch {
      // Not JSON, return truncated text
      return text.slice(0, 300);
    }
  } catch {
    return 'Resposta ilegível';
  }

  return 'Resposta sem detalhe';
}

/**
 * Monta cabeçalhos padrão para requisições JSON.
 */
function buildHeaders(extraHeaders: Record<string, string> = {}): Record<string, string> {
  return {
    'Content-Type': 'application/json',
    Accept: 'application/json',
    ...extraHeaders,
  };
}

export const api = {
  async getSession(): Promise<SessionResponse> {
    const res = await fetch('/app/session', {
      method: 'GET',
      credentials: 'same-origin',
      headers: buildHeaders(),
    });
    if (!res.ok) {
      throw await apiError(res);
    }
    return res.json();
  },

  async healthCheck(): Promise<{ status: string }> {
    const res = await fetch('/health', {
      method: 'GET',
      credentials: 'same-origin',
      headers: buildHeaders(),
    });
    if (!res.ok) {
      throw await apiError(res);
    }
    return res.json();
  },

  async createPlan(
    temaOuOpcoes: string | CreatePlanOptions,
    n_pontos?: number,
    personas?: string[],
    idPesquisa?: string,
    signal?: AbortSignal
  ): Promise<PlanResponse> {
    const opcoes: CreatePlanOptions =
      typeof temaOuOpcoes === 'string'
        ? { tema: temaOuOpcoes, n_pontos, personas, idPesquisa, signal }
        : temaOuOpcoes;
    const reqSignal = opcoes.signal ?? signal;
    const payload: PlanRequest = {
      tema: opcoes.tema,
      async_execute: opcoes.async_execute ?? false,
      ...(opcoes.idPesquisa ? { id_pesquisa: opcoes.idPesquisa } : {}),
      ...(opcoes.n_pontos !== undefined ? { n_pontos: opcoes.n_pontos } : {}),
      ...(opcoes.personas && opcoes.personas.length > 0 ? { personas: opcoes.personas } : {}),
      ...(opcoes.execution_mode ? { execution_mode: opcoes.execution_mode } : {}),
      ...(opcoes.recencia ? { recencia: opcoes.recencia } : {}),
      ...(opcoes.async_execute && opcoes.callback_url ? { callback_url: opcoes.callback_url } : {}),
    };

    const res = await fetch('/api/v1/plan', {
      method: 'POST',
      credentials: 'same-origin',
      headers: buildHeaders(),
      body: JSON.stringify(payload),
      signal: reqSignal,
    });

    if (!res.ok) {
      throw await apiError(res);
    }
    if (res.status === 202) {
      // Modo assíncrono: o backend agenda o job e devolve o id para polling.
      const data = (await res.json()) as PlanAsyncResponse;
      if (!data || typeof data.id_pesquisa !== 'string' || !Array.isArray(data.pontos)) {
        throw new Error('Resposta inválida do backend: agendamento assíncrono incompleto');
      }
      return data as unknown as PlanResponse;
    }
    const data = await res.json();
    if (!data || typeof data.id_pesquisa !== 'string' || !Array.isArray(data.pontos)) {
      throw new Error('Resposta inválida do backend: estrutura do plano ausente ou incompleta');
    }
    return data;
  },

  async searchPoints(
    id_pesquisa: string,
    ponto_id?: string | null,
    personas?: string[] | null,
    execution_mode?: 'parallel' | 'sequential',
    signal?: AbortSignal
  ): Promise<SearchResponse> {
    const payload: SearchRequest = {
      id_pesquisa,
      ponto_id: ponto_id || undefined,
      personas: personas && personas.length > 0 ? personas : undefined,
      ...(execution_mode ? { execution_mode } : {}),
    };

    const res = await fetch('/api/v1/search', {
      method: 'POST',
      credentials: 'same-origin',
      headers: buildHeaders(),
      body: JSON.stringify(payload),
      signal,
    });

    if (!res.ok) {
      throw await apiError(res);
    }
    const data = await res.json();
    if (!data || typeof data.id_pesquisa !== 'string') {
      throw new Error('Resposta inválida do backend: estrutura de busca incompleta');
    }
    return data;
  },

  async auditResearch(
    id_pesquisa: string,
    ponto_id?: string | null,
    criterios_minimos: number = RIGOR_PADRAO,
    signal?: AbortSignal
  ): Promise<AuditResponse> {
    const payload: AuditRequest = {
      id_pesquisa,
      ponto_id: ponto_id || undefined,
      criterios_minimos: normalizarRigor(criterios_minimos),
    };

    const res = await fetch('/api/v1/audit', {
      method: 'POST',
      credentials: 'same-origin',
      headers: buildHeaders(),
      body: JSON.stringify(payload),
      signal,
    });

    if (!res.ok) {
      throw await apiError(res);
    }
    const data = await res.json();
    if (!data || typeof data.id_pesquisa !== 'string' || !Array.isArray(data.auditorias)) {
      throw new Error('Resposta inválida do backend: estrutura de auditoria incompleta');
    }
    return data;
  },

  async writeDossier(id_pesquisa: string, signal?: AbortSignal): Promise<WriterResponse> {
    const payload: WriterRequest = {
      id_pesquisa,
    };

    const res = await fetch('/api/v1/writer', {
      method: 'POST',
      credentials: 'same-origin',
      headers: buildHeaders(),
      body: JSON.stringify(payload),
      signal,
    });

    if (!res.ok) {
      throw await apiError(res);
    }
    const data = await res.json();
    if (!data || typeof data.id_pesquisa !== 'string' || typeof data.status !== 'string') {
      throw new Error('Resposta inválida do backend: estrutura do dossiê incompleta');
    }
    return data;
  },

  async listCredentials(): Promise<CredentialListResponse> {
    const res = await fetch('/api/v1/admin/credentials', {
      method: 'GET',
      credentials: 'same-origin',
      headers: buildHeaders(),
    });

    if (!res.ok) {
      throw await apiError(res);
    }
    return res.json();
  },

  async saveCredential(payload: CredentialCreateRequest): Promise<CredentialResponse> {
    const res = await fetch('/api/v1/admin/credentials', {
      method: 'POST',
      credentials: 'same-origin',
      headers: buildHeaders(),
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      throw await apiError(res);
    }
    return res.json();
  },

  /** Provedor OpenAI-compatible e modelos por subagente (perfil Hermes). */
  async getHermesSettings(): Promise<Record<string, unknown>> {
    const res = await fetch('/api/v1/settings/hermes', {
      method: 'GET',
      credentials: 'same-origin',
      headers: buildHeaders(),
    });
    if (!res.ok) throw await apiError(res);
    return res.json();
  },

  async saveHermesSettings(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
    const res = await fetch('/api/v1/settings/hermes', {
      method: 'PUT',
      credentials: 'same-origin',
      headers: buildHeaders(),
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw await apiError(res);
    return res.json();
  },

  async getPipelineStatus(id_pesquisa: string): Promise<PipelineStatusResumo> {
    const res = await fetch(`/api/v1/pipeline/${encodeURIComponent(id_pesquisa)}/status`, {
      method: 'GET',
      credentials: 'same-origin',
      headers: buildHeaders(),
    });

    if (!res.ok) {
      throw await apiError(res);
    }
    const data = (await res.json()) as PipelineStatusResumo;
    if (!data || typeof data.id_pesquisa !== 'string' || !Array.isArray(data.pontos)) {
      throw new Error('Resposta inválida do backend: status do pipeline incompleto');
    }
    return data;
  },

  async getResearch(id_pesquisa: string): Promise<ResearchDetail> {
    const res = await fetch(`/api/v1/research/${encodeURIComponent(id_pesquisa)}`, {
      method: 'GET',
      credentials: 'same-origin',
      headers: buildHeaders(),
    });

    if (!res.ok) {
      throw await apiError(res);
    }
    const data = (await res.json()) as ResearchDetail;
    if (!data || typeof data.id_pesquisa !== 'string' || !Array.isArray(data.pontos)) {
      throw new Error('Resposta inválida do backend: pesquisa incompleta');
    }
    return data;
  },

  async getSources(id_pesquisa: string, signal?: AbortSignal): Promise<FontesResumo> {
    const res = await fetch(`/api/v1/pipeline/${encodeURIComponent(id_pesquisa)}/sources`, {
      method: 'GET',
      credentials: 'same-origin',
      headers: buildHeaders(),
      signal,
    });

    if (!res.ok) {
      throw await apiError(res);
    }
    const data = await res.json();
    if (!data || typeof data !== 'object' || typeof data.status !== 'string') {
      throw new Error('Resposta inválida do backend: estrutura de fontes incompleta');
    }
    return data;
  },
};
