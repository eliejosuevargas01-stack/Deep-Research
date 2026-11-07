/**
 * Cliente SSE do stream de pesquisa (API v1.2).
 *
 * Contrato (implementado no backend em paralelo):
 *   GET /research/{id}/eventos  (alias /events), text/event-stream.
 *   Cada mensagem: `id: <n>`, `event: <tipo>`, `data: <json>`.
 *   Sem Last-Event-ID, a primeira mensagem é `snapshot` com o payload de
 *   GET /research/{id}. Com Last-Event-ID (header ou `?desde=`), o backend
 *   faz replay dos eventos seguintes.
 *
 * Sem polling como fallback: ao abrir, o hook faz um único GET (snapshot
 * inicial) e o SSE entrega todo o resto. EventSource nativo já reconecta
 * sozinho, mas aqui a reconexão é manual para reenviar `?desde=<lastId>`.
 */

import { apiBase, lerApiKey } from './apiV12';

export const TIPOS_EVENTO_SSE = [
  'snapshot',
  'run.criado',
  'run.status',
  'plano.pronto',
  'ponto.iniciado',
  'fonte.lida',
  'ponto.coletado',
  'auditoria.executada',
  'ponto.aprovado',
  'ponto.reprovado',
  'redator.iniciado',
  'ponto.finalizado',
  'tokens.atualizados',
  'run.concluido',
  'run.falhou',
  'ponto.erro',
] as const;

export type TipoEventoSse = (typeof TIPOS_EVENTO_SSE)[number];

export interface EventoSse<T = unknown> {
  id: string;
  tipo: string;
  dados: T;
}

export interface OpcoesAssinatura {
  /** Ponto de partida do replay. Padrão: id persistido em localStorage. */
  desde?: string | null;
  aoEvento?: (evento: EventoSse) => void;
  aoAbrir?: () => void;
  aoErro?: (tentativa: number) => void;
  /** Ms antes de reabrir após erro. Padrão 2000. */
  intervaloReconexaoMs?: number;
  /** Máx. tentativas de reconexão (padrão 4). 0 = infinito. */
  maxTentativasReconexao?: number;
  /** Chamado ao esgotar as tentativas; deve encerrar o ciclo. */
  aoEsgotar?: () => void;
  /** GET direto executado no primeiro erro para detectar 404 sem esperar o ciclo. */
  verificarSumico?: () => Promise<unknown>;
  /** Injetável para testes (jsdom não tem EventSource). */
  implEventSource?: typeof EventSource;
}

export interface AssinaturaSse {
  fechar(): void;
  tentativas(): number;
}

export function chaveUltimoEvento(researchId: string): string {
  return `dr:v12:sse:${researchId}:ultimo`;
}

export function lerUltimoEventoId(researchId: string): string | null {
  try {
    return localStorage.getItem(chaveUltimoEvento(researchId));
  } catch {
    return null;
  }
}

export function gravarUltimoEventoId(researchId: string, id: string): void {
  try {
    localStorage.setItem(chaveUltimoEvento(researchId), id);
  } catch {
    /* armazenamento indisponível: segue sem persistir */
  }
}

export function urlDoStream(researchId: string, desde?: string | null): string {
  const base = `${apiBase()}/research/${encodeURIComponent(researchId)}/eventos`;
  const params = new URLSearchParams();
  if (desde) params.set('desde', desde);
  // EventSource não envia headers: a chave vai na query e é reanexada a
  // cada reconexão (abrir() lê a chave atual a cada chamada).
  const apiKey = lerApiKey();
  if (apiKey) params.set('api_key', apiKey);
  const qs = params.toString();
  return qs ? `${base}?${qs}` : base;
}

function extrairDados(raw: string): unknown {
  if (!raw) return null;
  try {
    return JSON.parse(raw) as unknown;
  } catch {
    return raw;
  }
}

/**
 * Abre o EventSource e reabre com `?desde=<lastId>` em caso de erro (após o
 * intervalo) ou ao voltar online. Nunca faz polling: sem eventos, sem tráfego.
 */
export function assinarEventosPesquisa(
  researchId: string,
  opcoes: OpcoesAssinatura = {},
): AssinaturaSse {
  const Impl = opcoes.implEventSource ?? EventSource;
  const intervalo = opcoes.intervaloReconexaoMs ?? 2000;
  const maxTentativas = opcoes.maxTentativasReconexao ?? 4;
  let desde: string | null = opcoes.desde !== undefined ? opcoes.desde : lerUltimoEventoId(researchId);
  let fonte: EventSource | null = null;
  let timer: number | null = null;
  let fechado = false;
  let tentativasFalha = 0;
  let esgotado = false;

  function despachar(tipo: string, ev: MessageEvent): void {
    const id = (ev.lastEventId || '').trim();
    if (id) {
      desde = id;
      gravarUltimoEventoId(researchId, id);
    }
    opcoes.aoEvento?.({ id, tipo, dados: extrairDados(ev.data as string) });
  }

  function abrir(): void {
    if (fechado || esgotado) return;
    try {
      fonte = new Impl(urlDoStream(researchId, desde));
    } catch {
      agendarReabertura();
      return;
    }
    for (const tipo of TIPOS_EVENTO_SSE) {
      fonte.addEventListener(tipo, (e) => despachar(tipo, e as MessageEvent));
    }
    // Qualquer evento fora do contrato cai aqui em vez de se perder.
    fonte.onmessage = (e) => despachar((e as MessageEvent).type || 'mensagem', e as MessageEvent);
    fonte.onopen = () => {
      tentativasFalha = 0;
      opcoes.aoAbrir?.();
    };
    fonte.onerror = () => {
      tentativasFalha += 1;
      opcoes.aoErro?.(tentativasFalha);
      // Fecha o canal com erro e reabre do ponto onde parou.
      try {
        fonte?.close();
      } catch {
        /* ignora */
      }
      fonte = null;
      if (maxTentativas > 0 && tentativasFalha >= maxTentativas) {
        esgotado = true;
        opcoes.aoEsgotar?.();
        return;
      }
      // 404 rápido: no primeiro erro, GET direto decide se o run sumiu,
      // sem esperar o ciclo de reconexões esgotar.
      if (tentativasFalha === 1 && opcoes.verificarSumico) {
        opcoes.verificarSumico().then(
          () => {
            if (!fechado && !esgotado) agendarReabertura();
          },
          () => {
            if (fechado || esgotado) return;
            esgotado = true;
            opcoes.aoEsgotar?.();
          },
        );
        return;
      }
      agendarReabertura();
    };
  }

  function agendarReabertura(): void {
    if (fechado || timer !== null) return;
    timer = window.setTimeout(() => {
      timer = null;
      abrir();
    }, intervalo);
  }

  function aoVoltarOnline(): void {
    if (fechado) return;
    if (fonte) {
      try {
        fonte.close();
      } catch {
        /* ignora */
      }
      fonte = null;
    }
    if (timer !== null) {
      window.clearTimeout(timer);
      timer = null;
    }
    abrir();
  }

  window.addEventListener('online', aoVoltarOnline);
  abrir();

  return {
    fechar() {
      fechado = true;
      window.removeEventListener('online', aoVoltarOnline);
      if (timer !== null) {
        window.clearTimeout(timer);
        timer = null;
      }
      try {
        fonte?.close();
      } catch {
        /* ignora */
      }
      fonte = null;
    },
    tentativas() {
      return tentativasFalha;
    },
  };
}
