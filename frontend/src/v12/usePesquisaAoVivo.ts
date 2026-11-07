import { useEffect, useReducer } from 'react';
import {
  ApiV12Error,
  obterPesquisa,
  type AuditoriaItem,
  type ResearchRun,
} from '../services/apiV12';
import { assinarEventosPesquisa } from '../services/ssePesquisa';

/* ------------------------------------------------------------------ */
/* Chaves de persistência                                               */
/* ------------------------------------------------------------------ */

/** Id da pesquisa ativa — restaura a mesma tela após reload/troca de página. */
export const CHAVE_ATIVA = 'dr:v12:ativa';

export function lerIdAtivo(): string | null {
  try {
    return localStorage.getItem(CHAVE_ATIVA);
  } catch {
    return null;
  }
}

export function gravarIdAtivo(id: string): void {
  try {
    localStorage.setItem(CHAVE_ATIVA, id);
  } catch {
    /* segue sem persistir */
  }
}

export function limparIdAtivo(): void {
  try {
    localStorage.removeItem(CHAVE_ATIVA);
  } catch {
    /* ignora */
  }
}

/* ------------------------------------------------------------------ */
/* Estado ao vivo (snapshot GET + eventos SSE consolidados)             */
/* ------------------------------------------------------------------ */

export type EstadoPonto =
  | 'iniciado'
  | 'coletado'
  | 'auditando'
  | 'aprovado'
  | 'reprovado'
  | 'finalizado'
  | 'incompleto'
  | 'erro';

export interface PontoVivo {
  ponto_id: number;
  enunciado?: string | null;
  estado: EstadoPonto;
  persona?: string | null;
  rodada?: number | null;
  porcentagem_aprovacao?: number | null;
  aprovado?: boolean | null;
  relatorio_trecho?: string | null;
  mensagem_erro?: string | null;
  urls_lidas: string[];
  urls_usadas: string[];
}

export interface FonteViva {
  url: string;
  ponto_id?: number | null;
  persona?: string | null;
  usada?: boolean | null;
}

export interface AuditoriaViva {
  ponto_id: number;
  rodada: number;
  porcentagem_aprovacao?: number | null;
  aprovado?: boolean | null;
  model_used?: string | null;
  total_tokens?: number | null;
  perguntas_respondidas?: Record<string, boolean> | null;
  perguntas_true?: number | null;
  total_perguntas?: number | null;
}

export interface TokensVivos {
  total: number;
  prompt: number;
  completion: number;
  reasoning: number;
  porPapel: Record<string, number>;
}

export interface EstadoAoVivo {
  researchId: string | null;
  run: ResearchRun | null;
  pontos: PontoVivo[];
  fontes: FonteViva[];
  auditorias: AuditoriaViva[];
  tokens: TokensVivos;
  /** Contagens por tipo de evento (reasoning/tool calls chegam via eventos). */
  contagens: Record<string, number>;
  conectado: boolean;
  erro: string | null;
  naoEncontrada: boolean;
  ultimoId: string | null;
}

export function estadoInicial(): EstadoAoVivo {
  return {
    researchId: null,
    run: null,
    pontos: [],
    fontes: [],
    auditorias: [],
    tokens: { total: 0, prompt: 0, completion: 0, reasoning: 0, porPapel: {} },
    contagens: {},
    conectado: false,
    erro: null,
    naoEncontrada: false,
    ultimoId: null,
  };
}

/* Leituras defensivas — payloads de evento variam por versão do backend. */

function num(v: unknown): number | null {
  return typeof v === 'number' && Number.isFinite(v) ? v : null;
}

function str(v: unknown): string | null {
  return typeof v === 'string' ? v : null;
}

function listaStr(v: unknown): string[] {
  return Array.isArray(v) ? v.filter((i): i is string => typeof i === 'string') : [];
}

function reg(v: unknown): Record<string, unknown> {
  if (v && typeof v === 'object' && !Array.isArray(v)) return v as Record<string, unknown>;
  return {};
}

function boolResp(v: unknown): Record<string, boolean> | null {
  const r = reg(v);
  const keys = Object.keys(r);
  if (keys.length === 0) return null;
  const saida: Record<string, boolean> = {};
  for (const k of keys) saida[k] = r[k] === true;
  return saida;
}

function novoPonto(ponto_id: number): PontoVivo {
  return { ponto_id, estado: 'iniciado', urls_lidas: [], urls_usadas: [] };
}

function comPonto(pontos: PontoVivo[], ponto_id: number, patch: Partial<PontoVivo>): PontoVivo[] {
  const i = pontos.findIndex((p) => p.ponto_id === ponto_id);
  if (i < 0) return [...pontos, { ...novoPonto(ponto_id), ...patch }];
  const copia = pontos.slice();
  copia[i] = { ...copia[i], ...patch };
  return copia;
}

function semDup(lista: string[], extras: string[]): string[] {
  const vistos = new Set(lista);
  const saida = lista.slice();
  for (const u of extras) {
    if (!vistos.has(u)) {
      vistos.add(u);
      saida.push(u);
    }
  }
  return saida;
}

function estadoDoSnapshot(
  aprovado: boolean | null | undefined,
  temRelatorio: boolean,
  terminal: boolean,
): EstadoPonto {
  if (aprovado === true) return 'aprovado';
  if (aprovado === false) return terminal ? 'reprovado' : 'auditando';
  if (terminal) return 'incompleto';
  return temRelatorio ? 'coletado' : 'iniciado';
}

function derivarDoSnapshot(run: ResearchRun): Pick<EstadoAoVivo, 'pontos' | 'fontes' | 'auditorias' | 'tokens'> {
  const terminal = run.status === 'COMPLETED' || run.status === 'FAILED';
  const pontos: PontoVivo[] = (run.pontos ?? []).map((p) => ({
    ponto_id: p.ponto_id,
    enunciado: p.enunciado ?? null,
    estado: estadoDoSnapshot(p.aprovado, !!p.relatorio_ponto, terminal),
    rodada: p.rodada_atual ?? null,
    porcentagem_aprovacao: p.porcentagem_aprovacao ?? null,
    aprovado: p.aprovado ?? null,
    relatorio_trecho: p.relatorio_ponto ? p.relatorio_ponto.slice(0, 500) : null,
    mensagem_erro: null,
    urls_lidas: [],
    urls_usadas: [],
  }));
  const usadas = new Set(run.urls_usadas_globais ?? []);
  const fontes: FonteViva[] = (run.urls_lidas_globais ?? []).map((url) => ({
    url,
    usada: usadas.has(url),
  }));
  const auditorias: AuditoriaViva[] = (run.auditorias ?? []).map((a: AuditoriaItem) => ({
    ponto_id: a.ponto_id,
    rodada: a.rodada,
    porcentagem_aprovacao: a.porcentagem_aprovacao ?? null,
    aprovado: a.aprovado ?? null,
    model_used: a.model_used ?? null,
    total_tokens: a.total_tokens ?? null,
    perguntas_respondidas: a.perguntas_respondidas ?? null,
    perguntas_true: a.perguntas_true ?? null,
  }));
  return {
    pontos,
    fontes,
    auditorias,
    tokens: {
      total: run.total_tokens ?? 0,
      prompt: run.total_prompt_tokens ?? 0,
      completion: run.total_completion_tokens ?? 0,
      reasoning: run.total_reasoning_tokens ?? 0,
      porPapel: {},
    },
  };
}

/* ------------------------------------------------------------------ */
/* Reducer puro (testável sem React/DOM)                                */
/* ------------------------------------------------------------------ */

export type AcaoAoVivo =
  | { tipo: 'definir-id'; researchId: string }
  | { tipo: 'snapshot'; run: ResearchRun; id: string | null }
  | { tipo: 'evento'; eventoTipo: string; dados: unknown; id: string | null }
  | { tipo: 'conexao'; conectado: boolean }
  | { tipo: 'erro'; mensagem: string }
  | { tipo: 'nao-encontrada' }
  | { tipo: 'dossie'; run: ResearchRun; id: string | null }
  | { tipo: 'limpar' };

function aplicarEvento(estado: EstadoAoVivo, eventoTipo: string, dados: unknown): EstadoAoVivo {
  const d = reg(dados);
  const ponto_id = num(d.ponto_id);
  switch (eventoTipo) {
    case 'snapshot': {
      const run = dados as ResearchRun;
      if (!run || typeof run !== 'object' || !('research_id' in run)) return estado;
      return { ...estado, run, ...derivarDoSnapshot(run), erro: null };
    }
    case 'run.criado':
    case 'run.status': {
      const status = str(d.status);
      if (!estado.run || !status) return estado;
      return { ...estado, run: { ...estado.run, status } };
    }
    case 'plano.pronto': {
      if (!estado.run) return estado;
      // Backend real: {pontos:[ids], total_pontos}. Sem ids, ignora o evento
      // para não apagar o plano já guardado.
      const ids = Array.isArray(d.pontos)
        ? (d.pontos as unknown[]).filter((i): i is number => typeof i === 'number' && Number.isFinite(i))
        : [];
      if (ids.length === 0) return estado;
      const total = num(d.total_pontos);
      return {
        ...estado,
        run: {
          ...estado.run,
          plano_inicial: { pontos: ids, total_pontos: total ?? ids.length },
        },
      };
    }
    case 'ponto.iniciado': {
      if (ponto_id === null) return estado;
      return {
        ...estado,
        pontos: comPonto(estado.pontos, ponto_id, {
          estado: 'iniciado',
          persona: str(d.persona) ?? str(d.papel),
          rodada: num(d.rodada),
          enunciado: str(d.enunciado) ?? undefined,
        }),
      };
    }
    case 'fonte.lida': {
      // Backend novo envia arrays; formato antigo trazia só contagens (ints).
      const lidas = listaStr(d.urls_lidas ?? d.urls);
      const usadas = listaStr(d.urls_usadas);
      const unica = str(d.url);
      const novasLidas = unica && !lidas.includes(unica) ? [...lidas, unica] : lidas;
      if (novasLidas.length === 0 && usadas.length === 0) return estado;
      const persona = str(d.persona) ?? str(d.papel);
      const usadasSet = new Set(usadas);
      const fontes = estado.fontes.slice();
      const marcarFonte = (url: string, usada: boolean | null): void => {
        const i = fontes.findIndex((f) => f.url === url);
        if (i < 0) {
          fontes.push({ url, ponto_id, persona, usada });
        } else if (usada === true) {
          fontes[i] = { ...fontes[i], usada: true };
        }
      };
      for (const url of novasLidas) {
        marcarFonte(url, usadasSet.has(url) || d.usada === true ? true : null);
      }
      for (const url of usadas) {
        if (!novasLidas.includes(url)) marcarFonte(url, true);
      }
      const run =
        estado.run != null
          ? {
              ...estado.run,
              urls_lidas_globais: semDup(estado.run.urls_lidas_globais ?? [], novasLidas),
              urls_usadas_globais: semDup(estado.run.urls_usadas_globais ?? [], usadas),
            }
          : estado.run;
      const pontoAtual = estado.pontos.find((p) => p.ponto_id === ponto_id);
      const pontos =
        ponto_id !== null
          ? comPonto(estado.pontos, ponto_id, {
              urls_lidas: semDup(pontoAtual?.urls_lidas ?? [], novasLidas),
              urls_usadas: semDup(pontoAtual?.urls_usadas ?? [], usadas),
            })
          : estado.pontos;
      return { ...estado, fontes, run, pontos };
    }
    case 'ponto.coletado': {
      if (ponto_id === null) return estado;
      const usadas = listaStr(d.urls_usadas ?? d.urls);
      const lidas = listaStr(d.urls_lidas);
      const atual = estado.pontos.find((p) => p.ponto_id === ponto_id);
      // Sem URLs no payload, preserva o que já existe.
      const run =
        estado.run != null && (usadas.length > 0 || lidas.length > 0)
          ? {
              ...estado.run,
              urls_usadas_globais: semDup(estado.run.urls_usadas_globais ?? [], usadas),
              urls_lidas_globais: semDup(estado.run.urls_lidas_globais ?? [], lidas),
            }
          : estado.run;
      const fontes =
        usadas.length > 0
          ? (() => {
              const copia = estado.fontes.slice();
              for (const url of usadas) {
                const i = copia.findIndex((f) => f.url === url);
                if (i < 0) copia.push({ url, ponto_id, usada: true });
                else copia[i] = { ...copia[i], usada: true };
              }
              return copia;
            })()
          : estado.fontes;
      return {
        ...estado,
        run,
        fontes,
        pontos: comPonto(estado.pontos, ponto_id, {
          estado: 'coletado',
          rodada: num(d.rodada) ?? atual?.rodada ?? null,
          urls_usadas: semDup(atual?.urls_usadas ?? [], usadas),
          urls_lidas: semDup(atual?.urls_lidas ?? [], lidas),
        }),
      };
    }
    case 'auditoria.executada': {
      if (ponto_id === null) return estado;
      const rodada = num(d.rodada) ?? 1;
      const perguntas =
        boolResp(d.perguntas_respondidas) ?? boolResp(d.respostas) ?? boolResp(d.perguntas);
      const verdadeiras = perguntas ? Object.values(perguntas).filter(Boolean).length : null;
      const auditoria: AuditoriaViva = {
        ponto_id,
        rodada,
        porcentagem_aprovacao: num(d.porcentagem_aprovacao) ?? num(d.porcentagem),
        aprovado: typeof d.aprovado === 'boolean' ? d.aprovado : null,
        model_used: str(d.model_used) ?? str(d.modelo) ?? str(d.model),
        total_tokens: num(d.total_tokens) ?? num(d.tokens),
        perguntas_respondidas: perguntas,
        perguntas_true: num(d.perguntas_true) ?? verdadeiras,
        total_perguntas:
          num(d.total_perguntas) ??
          num(d.total) ??
          (perguntas ? Object.keys(perguntas).length : null),
      };
      return {
        ...estado,
        auditorias: [...estado.auditorias, auditoria],
        pontos: comPonto(estado.pontos, ponto_id, {
          estado: 'auditando',
          rodada,
          porcentagem_aprovacao: auditoria.porcentagem_aprovacao,
        }),
      };
    }
    case 'ponto.aprovado':
    case 'ponto.reprovado': {
      if (ponto_id === null) return estado;
      const aprovado = eventoTipo === 'ponto.aprovado';
      // Um ponto reprovado/bloqueado marca só o próprio ponto — os demais seguem.
      // Patch condicional: o backend real manda só {ponto_id, rodada}; nunca
      // sobrescreve %/rodada com undefined.
      const patch: Partial<PontoVivo> = {
        estado: aprovado ? 'aprovado' : 'reprovado',
        aprovado,
      };
      const rodada = num(d.rodada);
      if (rodada !== null) patch.rodada = rodada;
      const pct = num(d.porcentagem_aprovacao) ?? num(d.porcentagem);
      if (pct !== null) patch.porcentagem_aprovacao = pct;
      return {
        ...estado,
        pontos: comPonto(estado.pontos, ponto_id, patch),
      };
    }
    case 'ponto.finalizado': {
      if (ponto_id === null) return estado;
      const atual = estado.pontos.find((p) => p.ponto_id === ponto_id);
      // Contrato: backend pode mandar relatorio/relatorio_trecho/tamanho
      // (ou relatorio_ponto/relatorio_tamanho). Sem relatório, preserva o vivo.
      const rel =
        str(d.relatorio) ??
        str(d.relatorio_trecho) ??
        str(d.relatorio_ponto) ??
        str(d.trecho);
      const tamanho = num(d.tamanho) ?? num(d.relatorio_tamanho) ?? num(d.total_caracteres);
      let relatorio_trecho: string | null | undefined;
      if (rel) relatorio_trecho = rel.slice(0, 500);
      else if (tamanho !== null) relatorio_trecho = `(relatório, ${tamanho} caracteres)`;
      else relatorio_trecho = atual?.relatorio_trecho ?? null;
      return {
        ...estado,
        pontos: comPonto(estado.pontos, ponto_id, {
          estado: 'finalizado',
          relatorio_trecho,
        }),
      };
    }
    case 'ponto.erro': {
      if (ponto_id === null) return estado;
      return {
        ...estado,
        pontos: comPonto(estado.pontos, ponto_id, {
          estado: 'erro',
          mensagem_erro: str(d.mensagem) ?? str(d.erro) ?? 'falha no ponto',
        }),
      };
    }
    case 'tokens.atualizados': {
      const papel = str(d.papel) ?? str(d.persona) ?? str(d.role);
      // Delta da execução atual; cumulativos globais vindos do backend.
      const delta = num(d.tokens_execucao);
      const cum = num(d.total_tokens) ?? num(d.tokens) ?? num(d.total);
      const prompt = num(d.prompt_tokens) ?? num(d.prompt);
      const completion = num(d.completion_tokens) ?? num(d.completion);
      const reasoning = num(d.reasoning_tokens) ?? num(d.reasoning);
      const porPapel = { ...estado.tokens.porPapel };
      let total = estado.tokens.total;
      if (delta !== null && delta > 0) {
        if (papel) porPapel[papel] = (porPapel[papel] ?? 0) + delta;
        total += delta;
        if (cum !== null) total = Math.max(total, cum);
      } else if (cum !== null && cum > total) {
        // Só veio o cumulativo: diff monotônico, nunca soma o cumulativo.
        const diff = cum - total;
        total = cum;
        if (papel && diff > 0) porPapel[papel] = (porPapel[papel] ?? 0) + diff;
      }
      return {
        ...estado,
        tokens: {
          total,
          prompt: prompt !== null ? Math.max(estado.tokens.prompt, prompt) : estado.tokens.prompt,
          completion:
            completion !== null ? Math.max(estado.tokens.completion, completion) : estado.tokens.completion,
          reasoning:
            reasoning !== null ? Math.max(estado.tokens.reasoning, reasoning) : estado.tokens.reasoning,
          porPapel,
        },
      };
    }
    case 'run.concluido': {
      if (!estado.run) return estado;
      const run: ResearchRun = {
        ...estado.run,
        status: 'COMPLETED',
        relatorio_final_consolidado: str(d.relatorio_final_consolidado) ?? str(d.relatorio_final) ?? estado.run.relatorio_final_consolidado,
        lacunas_finais_consolidadas: (d.lacunas_finais_consolidadas ?? d.lacunas_finais ?? null) as ResearchRun['lacunas_finais_consolidadas'] ?? estado.run.lacunas_finais_consolidadas,
        urls_usadas_globais: listaStr(d.urls_usadas_globais ?? d.urls_usadas).length > 0 ? listaStr(d.urls_usadas_globais ?? d.urls_usadas) : estado.run.urls_usadas_globais,
        urls_lidas_globais: listaStr(d.urls_lidas_globais ?? d.urls_lidas).length > 0 ? listaStr(d.urls_lidas_globais ?? d.urls_lidas) : estado.run.urls_lidas_globais,
        urls_nao_usadas_globais: listaStr(d.urls_nao_usadas_globais ?? d.urls_nao_usadas).length > 0 ? listaStr(d.urls_nao_usadas_globais ?? d.urls_nao_usadas) : estado.run.urls_nao_usadas_globais,
        completed_at: str(d.completed_at) ?? estado.run.completed_at,
      };
      const metricas = d.metricas_tokens;
      if (metricas && typeof metricas === 'object' && !Array.isArray(metricas)) {
        const m = metricas as Record<string, unknown>;
        const tot = num(m.total_tokens);
        if (tot !== null && tot > run.total_tokens!) run.total_tokens = tot;
        const pr = num(m.prompt_tokens);
        if (pr !== null) run.total_prompt_tokens = Math.max(run.total_prompt_tokens ?? 0, pr);
        const cp = num(m.completion_tokens);
        if (cp !== null) run.total_completion_tokens = Math.max(run.total_completion_tokens ?? 0, cp);
        const rs = num(m.reasoning_tokens);
        if (rs !== null) run.total_reasoning_tokens = Math.max(run.total_reasoning_tokens ?? 0, rs);
      }
      const avaliacao = d.avaliacao_pontos;
      if (Array.isArray(avaliacao)) {
        run.avaliacao_pontos = avaliacao as ResearchRun['avaliacao_pontos'];
      }
      // Pontos sem veredito viram incompletos — visíveis, sem esconder o resto.
      const pontos = estado.pontos.map((p) =>
        p.estado === 'aprovado' || p.estado === 'finalizado' || p.estado === 'reprovado'
          ? p
          : { ...p, estado: 'incompleto' as EstadoPonto },
      );
      return { ...estado, run, pontos };
    }
    case 'run.falhou': {
      if (!estado.run) return estado;
      return {
        ...estado,
        run: {
          ...estado.run,
          status: 'FAILED',
          erro: str(d.mensagem) ?? str(d.erro) ?? estado.run.erro ?? 'falha na pesquisa',
        },
      };
    }
    default:
      // redator.iniciado e tipos futuros: contam, sem mexer no resto.
      return estado;
  }
}

export function reduzirAoVivo(estado: EstadoAoVivo, acao: AcaoAoVivo): EstadoAoVivo {
  switch (acao.tipo) {
    case 'definir-id':
      return estado.researchId === acao.researchId
        ? estado
        : { ...estadoInicial(), researchId: acao.researchId };
    case 'snapshot':
      return {
        ...estado,
        run: acao.run,
        ...derivarDoSnapshot(acao.run),
        erro: null,
        naoEncontrada: false,
        ultimoId: acao.id ?? estado.ultimoId,
        contagens: { ...estado.contagens, snapshot: (estado.contagens.snapshot ?? 0) + 1 },
      };
    case 'evento': {
      // Dedupe at-least-once: replay do snapshot pode re-entregar o mesmo id.
      if (acao.id != null && acao.id !== '' && acao.id === estado.ultimoId) return estado;
      const contagens = { ...estado.contagens };
      contagens[acao.eventoTipo] = (contagens[acao.eventoTipo] ?? 0) + 1;
      const aplicado = aplicarEvento({ ...estado, contagens }, acao.eventoTipo, acao.dados);
      return { ...aplicado, ultimoId: acao.id ?? estado.ultimoId };
    }
    case 'conexao':
      return { ...estado, conectado: acao.conectado };
    case 'erro':
      return { ...estado, erro: acao.mensagem, conectado: false };
    case 'nao-encontrada':
      return { ...estado, naoEncontrada: true, run: null };
    case 'dossie': {
      const terminal = acao.run.status === 'COMPLETED' || acao.run.status === 'FAILED';
      const base = { ...estado, run: acao.run, erro: null, naoEncontrada: false };
      if (!terminal) return { ...base, ultimoId: acao.id ?? estado.ultimoId };
      // Eventos ao vivo não podem regredir o dossiê do GET: mescla tudo,
      // preservando pontos/fontes/token-vivo já consolidados acima do GET.
      const dossie = derivarDoSnapshot(acao.run);
      const porPonto = new Map(estado.pontos.map((p) => [p.ponto_id, p]));
      const pontos = dossie.pontos.map((p) => {
        const vivo = porPonto.get(p.ponto_id);
        if (!vivo) return p;
        return {
          ...p,
          urls_lidas: vivo.urls_lidas.length > 0 ? vivo.urls_lidas : p.urls_lidas,
          urls_usadas: vivo.urls_usadas.length > 0 ? vivo.urls_usadas : p.urls_usadas,
          relatorio_trecho: vivo.relatorio_trecho ?? p.relatorio_trecho,
          mensagem_erro: vivo.mensagem_erro ?? p.mensagem_erro,
          persona: vivo.persona ?? p.persona,
          estado: vivo.estado !== 'iniciado' ? vivo.estado : p.estado,
        };
      });
      const urlsVivas = new Set<string>([
        ...estado.fontes.map((f) => f.url),
        ...(estado.run?.urls_lidas_globais ?? []),
      ]);
      const fontes = dossie.fontes.length > 0 ? dossie.fontes : estado.fontes;
      const fonteUrls = new Set(fontes.map((f) => f.url));
      for (const u of urlsVivas) {
        if (!fonteUrls.has(u)) fontes.push({ url: u, usada: null });
      }
      const auditorias = dossie.auditorias.length > 0 ? dossie.auditorias : estado.auditorias;
      const interativo = Object.keys(estado.tokens.porPapel).length > 0 || estado.tokens.total > 0;
      const tokens = interativo
        ? {
            total: Math.max(estado.tokens.total, acao.run.total_tokens ?? 0),
            prompt: Math.max(estado.tokens.prompt, acao.run.total_prompt_tokens ?? 0),
            completion: Math.max(estado.tokens.completion, acao.run.total_completion_tokens ?? 0),
            reasoning: Math.max(estado.tokens.reasoning, acao.run.total_reasoning_tokens ?? 0),
            porPapel: estado.tokens.porPapel,
          }
        : dossie.tokens;
      return { ...base, pontos, fontes, auditorias, tokens, ultimoId: acao.id ?? estado.ultimoId };
    }
    case 'limpar':
      return estadoInicial();
  }
}

/* ------------------------------------------------------------------ */
/* Hook: GET único ao abrir + SSE; sem polling                          */
/* ------------------------------------------------------------------ */

export interface OpcoesAoVivo {
  implEventSource?: typeof EventSource;
}

export function usePesquisaAoVivo(
  researchId: string | null,
  geracaoChave = 0,
  opcoes: OpcoesAoVivo = {},
): EstadoAoVivo {
  const [estado, dispatch] = useReducer(reduzirAoVivo, estadoInicial());

  useEffect(() => {
    if (!researchId) {
      dispatch({ tipo: 'limpar' });
      return;
    }
    let vivo = true;
    const idAtual = researchId;
    dispatch({ tipo: 'definir-id', researchId });

    // Fallback único: snapshot inicial via GET. O resto chega pelo SSE.
    obterPesquisa(researchId).then(
      (run) => {
        if (vivo) dispatch({ tipo: 'snapshot', run, id: null });
      },
      (e: unknown) => {
        if (!vivo) return;
        if (e instanceof ApiV12Error && e.status === 404) {
          limparIdAtivo();
          dispatch({ tipo: 'nao-encontrada' });
        } else {
          // 401 preserva id ativo e run — só sinaliza o erro (aviso na UI).
          dispatch({
            tipo: 'erro',
            mensagem: e instanceof ApiV12Error ? e.message : 'Falha ao carregar pesquisa.',
          });
        }
      },
    );

    // Dossiê completo após conclusão: o evento traz só metadados.
    const refazerDossie = (tipo: string): void => {
      if (tipo !== 'run.concluido' && tipo !== 'run.falhou') return;
      obterPesquisa(idAtual).then(
        (run) => {
          if (vivo) dispatch({ tipo: 'dossie', run, id: null });
        },
        (e: unknown) => {
          if (!vivo) return;
          if (e instanceof ApiV12Error && e.status === 404) {
            limparIdAtivo();
            dispatch({ tipo: 'nao-encontrada' });
          }
          // Outros erros: mantém o estado parcial do SSE, sem sobrescrever.
        },
      );
    };

    const sub = assinarEventosPesquisa(researchId, {
      implEventSource: opcoes.implEventSource,
      // GET-404 imediato no primeiro erro do stream: run apagado limpa sem
      // esperar as reconexões; falha transitória segue no ciclo normal.
      verificarSumico: () => obterPesquisa(idAtual),
      aoEvento: (ev) => {
        if (!vivo) return;
        dispatch({ tipo: 'evento', eventoTipo: ev.tipo, dados: ev.dados, id: ev.id || null });
        refazerDossie(ev.tipo);
      },
      aoAbrir: () => {
        if (vivo) dispatch({ tipo: 'conexao', conectado: true });
      },
      aoErro: () => {
        if (vivo) dispatch({ tipo: 'conexao', conectado: false });
      },
      aoEsgotar: () => {
        // Reconexões esgotadas: sem loop infinito — confere se o run sumiu (404 limpa).
        if (!vivo) return;
        obterPesquisa(idAtual).then(
          () => {
            if (vivo) dispatch({ tipo: 'conexao', conectado: false });
          },
          (e: unknown) => {
            if (!vivo) return;
            if (e instanceof ApiV12Error && e.status === 404) {
              limparIdAtivo();
              dispatch({ tipo: 'nao-encontrada' });
            } else if (vivo) {
              dispatch({ tipo: 'conexao', conectado: false });
            }
          },
        );
      },
    });
    return () => {
      vivo = false;
      sub.fechar();
    };
  }, [researchId, geracaoChave]);

  return estado;
}
