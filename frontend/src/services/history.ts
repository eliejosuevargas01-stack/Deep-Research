import {
  ResearchHistoryRecord,
  PlanResponse,
  WriterResponse,
  AuditResponse,
  FontesResumo,
  FonteItem,
  FontesStatus,
} from '../types/api';

const STORAGE_KEY = 'deep_research_local_history_v1';

/**
 * Canal de falha de armazenamento local. O histórico vive no navegador; quando
 * o storage está bloqueado ou cheio, a lista some ao recarregar e a pessoa
 * precisa saber disso em vez de descobrir depois.
 */
type FalhaStorage = (mensagem: string) => void;
let aoFalharStorage: FalhaStorage | null = null;


/**
 * Valida se um número representa uma contagem inteira finita não-negativa.
 * Qualquer valor inválido, indefinido ou negativo é convertido estritamente em null.
 */
function sanitizeCount(val: unknown): number | null {
  if (typeof val === 'number' && Number.isInteger(val) && val >= 0) {
    return val;
  }
  return null;
}

/**
 * Sanitiza vetor de itens de fontes preservando exclusivamente itens HTTP(S) públicos válidos.
 * Remove credenciais na URL (userinfo), parâmetros de segredo em queries e metadados internos arbitrários.
 */
function sanitizeFonteList(list: unknown): FonteItem[] {
  if (!Array.isArray(list)) return [];
  const validItems: FonteItem[] = [];

  for (const item of list) {
    if (!item || typeof item !== 'object' || typeof (item as FonteItem).url !== 'string') {
      continue;
    }
    const rawUrl = String((item as FonteItem).url).trim();
    let parsedUrl: URL;
    try {
      parsedUrl = new URL(rawUrl);
    } catch {
      // Descarta strings que não sejam URLs válidas
      continue;
    }

    // Retém exclusivamente esquemas públicos HTTP ou HTTPS
    if (parsedUrl.protocol !== 'http:' && parsedUrl.protocol !== 'https:') {
      continue;
    }

    // Expulsa credenciais embutidas (userinfo)
    parsedUrl.username = '';
    parsedUrl.password = '';

    // Remove parâmetros sensíveis de consulta se presentes
    const sensitiveQueryParams = [
      'token',
      'api_key',
      'apikey',
      'key',
      'secret',
      'password',
      'auth',
      'access_token',
    ];
    for (const param of sensitiveQueryParams) {
      if (parsedUrl.searchParams.has(param)) {
        parsedUrl.searchParams.delete(param);
      }
    }

    // Preserva a URL limpa com seus caminhos e queries seguras
    const cleanUrl = parsedUrl.toString();

    let dominio = (item as FonteItem).dominio ? String((item as FonteItem).dominio).trim() : null;
    if (!dominio) {
      dominio = parsedUrl.hostname || null;
    }

    const rawTitulo = (item as FonteItem).titulo;
    const titulo = typeof rawTitulo === 'string' && rawTitulo.trim().length > 0
      ? rawTitulo.trim()
      : null;

    validItems.push({
      url: cleanUrl,
      titulo,
      dominio,
    });
  }

  return validItems;
}

/**
 * Projeta exclusivamente campos públicos e seguros, descartando reasoning interno,
 * telemetria privada, envelopes ou propriedades inesperadas do runtime.
 */
function sanitizeRecord(record: ResearchHistoryRecord): ResearchHistoryRecord | null {
  if (!record || typeof record.id_pesquisa !== 'string' || !record.tema) {
    return null;
  }

  let sanitizedPlan: PlanResponse | undefined = undefined;
  if (record.planResponse && typeof record.planResponse.id_pesquisa === 'string') {
    sanitizedPlan = {
      id_pesquisa: record.planResponse.id_pesquisa,
      tema: String(record.planResponse.tema || record.tema),
      n_pontos: Number(record.planResponse.n_pontos || 0),
      criado_em: String(record.planResponse.criado_em || record.criado_em),
      pontos: Array.isArray(record.planResponse.pontos)
        ? record.planResponse.pontos.map((p) => ({
            ponto_id: String(p.ponto_id),
            ponto_n: Number(p.ponto_n),
            ponto: String(p.ponto || ''),
            status: p.status || 'pendente',
            pontos_fracos: p.pontos_fracos ? String(p.pontos_fracos) : null,
            eixo_estruturado: p.eixo_estruturado || null,
          }))
        : [],
      status_pipeline: record.planResponse.status_pipeline || 'planejado',
      plano_estruturado: record.planResponse.plano_estruturado || null,
      preferencias: record.planResponse.preferencias && typeof record.planResponse.preferencias === 'object'
        ? {
            n_pontos: Number(record.planResponse.preferencias.n_pontos || record.planResponse.n_pontos || 0),
            personas: Array.isArray(record.planResponse.preferencias.personas)
              ? record.planResponse.preferencias.personas.map(String)
              : undefined,
            // Passo 1/4/5: recência, rigor e modo sobrevivem à reidratação do histórico.
            recencia: typeof record.planResponse.preferencias.recencia === 'string'
              ? record.planResponse.preferencias.recencia
              : null,
            execution_mode: record.planResponse.preferencias.execution_mode === 'sequential'
              ? 'sequential'
              : 'parallel',
            criterios_minimos: typeof record.planResponse.preferencias.criterios_minimos === 'number'
              ? record.planResponse.preferencias.criterios_minimos
              : null,
            async_execute: typeof record.planResponse.preferencias.async_execute === 'boolean'
              ? record.planResponse.preferencias.async_execute
              : null,
            callback_url: typeof record.planResponse.preferencias.callback_url === 'string'
              ? record.planResponse.preferencias.callback_url
              : null,
          }
        : undefined,
    };
  }

  let sanitizedWriter: WriterResponse | undefined = undefined;
  if (record.writerResponse && typeof record.writerResponse.id_pesquisa === 'string') {
    let sanitizedFontes: FontesResumo | undefined = undefined;
    if (record.writerResponse.fontes && typeof record.writerResponse.fontes === 'object') {
      const rawFontes = record.writerResponse.fontes;
      const rawStatus = String(rawFontes.status || '');
      const status: FontesStatus =
        rawStatus === 'completo' || rawStatus === 'parcial' || rawStatus === 'indisponivel'
          ? rawStatus
          : 'indisponivel';

      sanitizedFontes = {
        id_pesquisa: rawFontes.id_pesquisa ? String(rawFontes.id_pesquisa) : null,
        status,
        total_consultadas: sanitizeCount(rawFontes.total_consultadas),
        total_utilizadas: sanitizeCount(rawFontes.total_utilizadas),
        total_nao_utilizadas: sanitizeCount(rawFontes.total_nao_utilizadas),
        consultadas: sanitizeFonteList(rawFontes.consultadas),
        utilizadas: sanitizeFonteList(rawFontes.utilizadas),
        nao_utilizadas: sanitizeFonteList(rawFontes.nao_utilizadas),
        observacao: rawFontes.observacao ? String(rawFontes.observacao) : null,
        artifact_hash: rawFontes.artifact_hash ? String(rawFontes.artifact_hash) : null,
      };
    }

    sanitizedWriter = {
      id_pesquisa: record.writerResponse.id_pesquisa,
      tema: String(record.writerResponse.tema || record.tema),
      status: record.writerResponse.status || 'concluido',
      total_caracteres_dossier: Number(record.writerResponse.total_caracteres_dossier || 0),
      concluido_em: record.writerResponse.concluido_em || null,
      dossier_final: record.writerResponse.dossier_final ? String(record.writerResponse.dossier_final) : null,
      dossier_resumo: record.writerResponse.dossier_resumo ? String(record.writerResponse.dossier_resumo) : null,
      diagnostico: record.writerResponse.diagnostico ? String(record.writerResponse.diagnostico) : null,
      fontes: sanitizedFontes,
    };
  }

  let sanitizedAudit: AuditResponse | undefined = undefined;
  if (record.auditResponse && typeof record.auditResponse.id_pesquisa === 'string') {
    sanitizedAudit = {
      id_pesquisa: record.auditResponse.id_pesquisa,
      total_pontos: Number(record.auditResponse.total_pontos || 0),
      aprovados: Number(record.auditResponse.aprovados || 0),
      reprovados: Number(record.auditResponse.reprovados || 0),
      status_geral: String(record.auditResponse.status_geral || ''),
      status_pesquisa: record.auditResponse.status_pesquisa || null,
      pronto_para_writer: Boolean(record.auditResponse.pronto_para_writer),
      auditorias: Array.isArray(record.auditResponse.auditorias)
        ? record.auditResponse.auditorias.map((a) => ({
            ponto_id: String(a.ponto_id),
            ponto_n: Number(a.ponto_n),
            status: a.status === 'aprovado' ? 'aprovado' : 'reprovado',
            pontuacao_percentual: Number(a.pontuacao_percentual || 0),
            criterios_aprovados: Number(a.criterios_aprovados || 0),
            criterios_minimos: Number(a.criterios_minimos || 0),
            valido: Boolean(a.valido),
            criterios: a.criterios ?? null,
            pontos_fracos: a.pontos_fracos ? String(a.pontos_fracos) : null,
            diagnostico: a.diagnostico ? String(a.diagnostico) : null,
            resumo_auditoria: a.resumo_auditoria ? String(a.resumo_auditoria) : null,
            reasoning_auditoria: a.reasoning_auditoria ? String(a.reasoning_auditoria) : null,
          }))
        : [],
    };
  }

  return {
    id_pesquisa: record.id_pesquisa,
    tema: String(record.tema),
    criado_em: String(record.criado_em),
    concluido_em: record.concluido_em || null,
    status: record.status || 'planejado',
    total_pontos: Number(record.total_pontos || 0),
    planResponse: sanitizedPlan,
    writerResponse: sanitizedWriter,
    auditResponse: sanitizedAudit,
  };
}

export const historyService = {
  list(): ResearchHistoryRecord[] {
    try {
      const data = localStorage.getItem(STORAGE_KEY);
      if (!data) return [];
      const parsed = JSON.parse(data);
      if (Array.isArray(parsed)) {
        const validRecords: ResearchHistoryRecord[] = [];
        for (const item of parsed) {
          const sanitized = sanitizeRecord(item);
          if (sanitized) {
            validRecords.push(sanitized);
          }
        }
        return validRecords.sort(
          (a, b) => new Date(b.criado_em).getTime() - new Date(a.criado_em).getTime()
        );
      }
      return [];
    } catch {
      return [];
    }
  },

  save(record: ResearchHistoryRecord): void {
    try {
      const sanitized = sanitizeRecord(record);
      if (!sanitized) return;

      const list = this.list();
      const existingIndex = list.findIndex((item) => item.id_pesquisa === sanitized.id_pesquisa);
      if (existingIndex >= 0) {
        list[existingIndex] = { ...list[existingIndex], ...sanitized };
      } else {
        list.unshift(sanitized);
      }
      // Limite defensivo de até 50 pesquisas locais
      const trimmed = list.slice(0, 50);
      localStorage.setItem(STORAGE_KEY, JSON.stringify(trimmed));
    } catch (e) {
      console.warn('Falha ao persistir histórico local no navegador:', e);
      aoFalharStorage?.('Não foi possível salvar esta pesquisa no histórico do navegador.');
    }
  },

  get(id_pesquisa: string): ResearchHistoryRecord | undefined {
    return this.list().find((item) => item.id_pesquisa === id_pesquisa);
  },

  remove(id_pesquisa: string): void {
    try {
      const filtered = this.list().filter((item) => item.id_pesquisa !== id_pesquisa);
      localStorage.setItem(STORAGE_KEY, JSON.stringify(filtered));
    } catch (e) {
      console.warn('Falha ao remover item do histórico:', e);
      aoFalharStorage?.('Não foi possível remover a pesquisa do histórico.');
    }
  },

  clear(): void {
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch (e) {
      console.warn('Falha ao limpar histórico local:', e);
      aoFalharStorage?.('Não foi possível limpar o histórico deste navegador.');
    }
  },

  /** Registra quem mostra a falha de storage (a UI). */
  setFalhaHandler(handler: FalhaStorage | null): void {
    aoFalharStorage = handler;
  },
};
