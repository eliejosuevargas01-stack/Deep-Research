import React, { Suspense } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  PenTool,
  RefreshCw,
  ShieldCheck,
  XCircle,
} from 'lucide-react';
import type { AuditItem, AuditResponse, PlanResponse, SearchResponse } from '../types/api';
import type { ReasoningFeedItem } from '../types/stream';
import '../styles/linear-timeline.css';
import { PersonaIcon } from './ResearchIcons';
import { Favicon } from './Favicon';


const MarkdownBody = React.lazy(() => import('./ReasoningMarkdownBody'));

export interface TimelineNodeAction {
  ponto_id: string;
  ponto_n: number;
  reprovado: boolean;
  emReprocesso: boolean;
}

export interface LinearTimelineProps {
  plan?: PlanResponse | null;
  searchResult?: SearchResponse | null;
  auditResult?: AuditResponse | null;
  reasoningItems?: ReasoningFeedItem[];
  onRefazerBuscaPonto?: (ponto_id: string) => void;
  onReauditarPonto?: (ponto_id: string) => void;
  pontoEmReprocesso?: string | null;
  rigorAtual?: number | null;
}

function nomePersona(id: string): string {
  const mapa: Record<string, string> = {
    historiador: 'Historiador',
    visionario: 'Visionário',
    cetico: 'Cético',
    futurista: 'Futurista',
  };
  return mapa[id.toLowerCase()] ?? id;
}

/** Classe da pílula cromática por persona (item 1 da crítica: logs com identidade). */
function classePersona(agentName: string): string {
  const n = agentName.toLowerCase();
  if (n.includes('historiador')) return 'tl-pill-historiador';
  if (n.includes('vision')) return 'tl-pill-visionario';
  if (n.includes('cetico') || n.includes('cético')) return 'tl-pill-cetico';
  if (n.includes('futurista')) return 'tl-pill-futurista';
  if (n.includes('auditor')) return 'tl-pill-auditor';
  if (n.includes('redator') || n.includes('planejador')) return 'tl-pill-sistema';
  return 'tl-pill-sistema';
}

function mapearPersonaParaTipo(persona: string): string {
  const p = persona.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
  if (p.includes('planejador')) return 'planejador';
  if (p.includes('historiador')) return 'historiador';
  if (p.includes('cetico')) return 'cetico';
  if (p.includes('visionario')) return 'visionario';
  if (p.includes('futurista')) return 'futurista';
  if (p.includes('auditor')) return 'auditor';
  if (p.includes('redator')) return 'redator';
  return 'cetico';
}

/**
 * Hora HH:MM:SS do carimbo ISO de um ReasoningFeedItem, no formato pt-BR.
 * Carimbo sem fuso é tratado como UTC (mesma convenção do ReasoningCardItem).
 * Retorna string vazia quando o valor não é uma data válida.
 */
export function formatarHoraTimelog(iso: string): string {
  if (!iso) return '';
  try {
    const comFuso = /[zZ]|[+-]\d{2}:?\d{2}$/.test(iso) ? iso : `${iso}Z`;
    const data = new Date(comFuso);
    if (Number.isNaN(data.getTime())) return '';
    const texto = data.toLocaleTimeString('pt-BR', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hourCycle: 'h23',
    });
    const casado = texto.match(/(\d{2}:\d{2}:\d{2})/);
    return casado ? casado[1] : '';
  } catch {
    return '';
  }
}

/**
 * Todas as queries SERP citadas no reasoning (linhas "Ferramenta · SERP"),
 * na ordem em que aparecem. Aceita query entre crases ou texto livre após o
 * marcador; ignora linhas de outras ferramentas (Reader).
 */
export function extrairQueriesTimelog(reasoning: string): string[] {
  if (!reasoning) return [];
  const queries: string[] = [];
  for (const linha of reasoning.split(/\r?\n/)) {
    const marca = linha.match(/Ferramenta\s*(?:[·•:\-–—]\s*)?SERP\b(.*)$/i);
    if (!marca) continue;
    const resto = marca[1] ?? '';
    const entreCrases = resto.match(/`([^`]+)`/);
    if (entreCrases) {
      const query = entreCrases[1].trim();
      if (query) queries.push(query);
      continue;
    }
    const antesDaSeta = resto.split('→')[0];
    const texto = antesDaSeta
      .replace(/^[\s*:·•\-–—]+/, '')
      .replace(/[\s*]+$/, '')
      .replace(/^["“”']|["“”']$/g, '')
      .trim();
    if (texto) queries.push(texto);
  }
  return queries;
}

/** Domínio legível de uma URL para o favicon. */
function dominioDe(url: string): string | null {
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return null;
  }
}

/** Até N domínios únicos das fontes lidas, com contagem de páginas cada. */
function dominiosFontes(urls: string[], limite = 6): Array<{ dominio: string; paginas: number }> {
  const contagem = new Map<string, number>();
  for (const u of urls) {
    const d = dominioDe(u);
    if (d) contagem.set(d, (contagem.get(d) ?? 0) + 1);
  }
  return [...contagem.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, limite)
    .map(([dominio, paginas]) => ({ dominio, paginas }));
}

/** Linha de reasoning com sintaxe mínima: linhas de ferramenta viram tag
    mono destacada; texto corrido passa pelo markdown final (item 1 da crítica). */
type BlocoReasoning =
  | { tipo: 'tool'; ferramenta: string; resto: string }
  | { tipo: 'md'; texto: string };

function blocosReasoning(texto: string): BlocoReasoning[] {
  const blocos: BlocoReasoning[] = [];
  for (const linha of texto.split('\n')) {
    const m = linha.match(/^\s*(?:\*\*)?Ferramenta\s*[·•-]\s*(SERP|Reader)(?:\*\*)?\s*(.*)$/i);
    if (m) {
      blocos.push({ tipo: 'tool', ferramenta: m[1], resto: m[2].trim() || '—' });
      continue;
    }
    const ultimo = blocos[blocos.length - 1];
    if (ultimo && ultimo.tipo === 'md') {
      ultimo.texto += `\n${linha}`;
    } else {
      blocos.push({ tipo: 'md', texto: linha });
    }
  }
  return blocos;
}

const LinhaReasoning: React.FC<{ texto: string }> = ({ texto }) => (
  <div className="tl-reasoning-corpo">
    {blocosReasoning(texto).map((b, i) =>
      b.tipo === 'tool' ? (
        <span key={i} className={`tl-tool tl-tool-${b.ferramenta.toLowerCase()}`}>
          <span className="tl-tool-tag">{b.ferramenta}</span>
          <span className="tl-tool-resto">{b.resto}</span>
          {'\n'}
        </span>
      ) : (
        <MarkdownBody key={i} text={b.texto} />
      ),
    )}
  </div>
);

function tituloPasso(persona: string, pontoN?: number | null): string {
  const foco: Record<string, string> = {
    historiador: 'Sintetizando evidências históricas',
    visionario: 'Mapeando tendências emergentes',
    cetico: 'Auditando riscos e contra-evidências',
    futurista: 'Projetando cenários prospectivos',
    auditor: 'Auditando contra os 12 critérios',
    redator: 'Consolidando o dossiê',
    planejador: 'Decompondo o tema',
  };
  const base = foco[persona.toLowerCase()] ?? 'Analisando evidências';
  return typeof pontoN === 'number' ? `Passo ${pontoN}: ${base}` : base;
}

interface NoProps {
  ultimo?: boolean;
  children: React.ReactNode;
}

const No: React.FC<NoProps> = ({ ultimo = false, children }) => (
  <li className={`tl-no${ultimo ? ' ultimo' : ''}`}>
    <span className="tl-trilho" aria-hidden="true" />
    <div className="tl-conteudo">{children}</div>
  </li>
);

function eventosDaPersona(nome: string, eventos: ReasoningFeedItem[]): ReasoningFeedItem[] {
  const alvo = mapearPersonaParaTipo(nome).toLowerCase();
  if (!alvo) return [];
  return eventos.filter((evento) => {
    const nomeEvento = mapearPersonaParaTipo(evento.agentName).toLowerCase();
    return nomeEvento === alvo;
  });
}

function queriesDaPersona(personaReasoning: string | null | undefined, eventos: ReasoningFeedItem[]): string[] {
  const queries = new Set<string>();
  for (const query of extrairQueriesTimelog(personaReasoning ?? '')) queries.add(query);
  for (const evento of eventos) {
    for (const query of extrairQueriesTimelog(evento.reasoning)) queries.add(query);
  }
  return [...queries];
}

function horaDe(evento: ReasoningFeedItem | undefined): string {
  return formatarHoraTimelog(evento?.timestamp ?? '');
}

interface LinhaAuditorProps {
  auditoria: AuditItem;
  pontoN: number;
  minimos: number;
  hora: string;
  timestamp?: string;
  emReprocesso: boolean;
  onRefazerBuscaPonto?: (ponto_id: string) => void;
  onReauditarPonto?: (ponto_id: string) => void;
}

const LinhaAuditor: React.FC<LinhaAuditorProps> = ({
  auditoria,
  pontoN,
  minimos,
  hora,
  timestamp,
  emReprocesso,
  onRefazerBuscaPonto,
  onReauditarPonto,
}) => {
  const reprovado = auditoria.status === 'reprovado';
  const reprovados = auditoria.criterios?.filter((c) => !c.aprovado) ?? [];
  const motivo = reprovados[0]?.justificativa?.trim() || 'critérios não atendidos';
  const percentual = Math.round(auditoria.pontuacao_percentual ?? 0);
  const frase = reprovado
    ? `Auditor reprovou o ponto número ${pontoN} por ${motivo} (${percentual}% × ${auditoria.criterios_aprovados}/${minimos}) — reenviado`
    : `Auditor aprovou o ponto número ${pontoN} (${percentual}% × ${auditoria.criterios_aprovados}/${minimos})`;

  return (
    <div className={`tl-entrada tl-entrada-auditor${reprovado ? ' reprovado' : ' aprovado'}`}>
      <time className="tl-hora" dateTime={timestamp}>
        {hora || '--:--:--'}
      </time>
      <span className={`tl-icone tl-${reprovado ? 'falha' : 'ok'}`} aria-hidden="true">
        {reprovado ? <AlertTriangle size={13} aria-hidden="true" /> : <CheckCircle2 size={13} aria-hidden="true" />}
      </span>
      <div className="tl-entrada-corpo">
        <div className="tl-linha-auditor">
          <span className={`tl-pill ${classePersona('auditor')}`}>Auditor</span>
          <span className="tl-auditor-frase">{frase}</span>
          {reprovado && (onRefazerBuscaPonto || onReauditarPonto) && (
            <span className="tl-acoes tl-acoes-log sempre">
              {onRefazerBuscaPonto && (
                <button
                  type="button"
                  className="tl-acao"
                  disabled={emReprocesso}
                  onClick={() => onRefazerBuscaPonto(auditoria.ponto_id)}
                  aria-label={`Refazer busca do ponto ${pontoN}`}
                >
                  <RefreshCw size={12} aria-hidden="true" />
                  <span>{emReprocesso ? 'buscando…' : 'refazer busca'}</span>
                </button>
              )}
              {onReauditarPonto && (
                <button
                  type="button"
                  className="tl-acao"
                  disabled={emReprocesso}
                  onClick={() => onReauditarPonto(auditoria.ponto_id)}
                  aria-label={`Reauditar ponto ${pontoN}`}
                >
                  <ShieldCheck size={12} aria-hidden="true" />
                  <span>{emReprocesso ? 'auditando…' : 'reauditar'}</span>
                </button>
              )}
            </span>
          )}
        </div>
        {reprovado && reprovados.length > 0 && (
          <div id={`tl-auditoria-${auditoria.ponto_id}`} className="tl-detalhe">
            {reprovados.slice(0, 4).map((c) => (
              <p key={c.id} className="tl-criterio">
                <strong>{`Critério ${c.id}:`}</strong> {c.justificativa}
                {c.correcao ? ` — correção: ${c.correcao}` : ''}
              </p>
            ))}
            {reprovados.length > 4 && <p className="tl-meta">+{reprovados.length - 4} critérios não atendidos</p>}
          </div>
        )}
      </div>
    </div>
  );
};

export const LinearTimeline: React.FC<LinearTimelineProps> = ({
  plan,
  searchResult,
  auditResult,
  reasoningItems = [],
  onRefazerBuscaPonto,
  onReauditarPonto,
  pontoEmReprocesso = null,
  rigorAtual = null,
}) => {
  const porPonto = React.useMemo(() => {
    const mapa = new Map<string, ReasoningFeedItem[]>();
    for (const item of reasoningItems) {
      const detalhes = item.details as Record<string, unknown> | undefined;
      const pid = detalhes?.ponto_id;
      const chave = typeof pid === 'string' && pid ? pid : typeof item.pointNumber === 'number' ? `n:${item.pointNumber}` : null;
      if (!chave) continue;
      const lista = mapa.get(chave) ?? [];
      lista.push(item);
      mapa.set(chave, lista);
    }
    return mapa;
  }, [reasoningItems]);

  const pontos = plan?.pontos ?? [];
  if (pontos.length === 0 && !searchResult && !auditResult) return null;

  const auditorias = new Map((auditResult?.auditorias ?? []).map((a) => [a.ponto_id, a]));
  const coletas = new Map((searchResult?.resumo_coletas ?? []).map((c) => [c.ponto_id, c]));
  const ultimaHora = formatarHoraTimelog(reasoningItems[reasoningItems.length - 1]?.timestamp ?? '');

  return (
    <ol className="tl-linear" aria-label="Linha do tempo da investigação">
      {pontos.map((ponto, indice) => {
        const coleta = coletas.get(ponto.ponto_id);
        const auditoria = auditorias.get(ponto.ponto_id);
        const eventos = porPonto.get(ponto.ponto_id) ?? porPonto.get(`n:${ponto.ponto_n}`) ?? [];
        const emReprocesso = pontoEmReprocesso === ponto.ponto_id;
        const ultimo = indice === pontos.length - 1;

        const personas = coleta?.personas ?? [];
        const buscaEventos = eventos.filter((e) => e.agentType === 'busca');
        const auditorEvento =
          eventos.find((e) => e.agentType === 'auditor') ?? eventos.find((e) => /auditor/i.test(e.agentName));
        const consumidos = new Set<string>();

        const minimos = auditoria?.criterios_minimos ?? rigorAtual ?? 12;

        return (
          <No key={ponto.ponto_id} ultimo={ultimo}>
            {personas.map((persona, personaIndice) => {
              const candidatos = eventosDaPersona(persona.persona, buscaEventos);
              const evento = candidatos[0] ?? buscaEventos[personaIndice] ?? buscaEventos[0];
              for (const usado of candidatos) consumidos.add(usado.id);
              if (evento) consumidos.add(evento.id);
              const queries = queriesDaPersona(persona.reasoning, candidatos.length > 0 ? candidatos : evento ? [evento] : []);
              return (
                <div className="tl-entrada" key={`${ponto.ponto_id}-${persona.persona}-${personaIndice}`}>
                  <time className="tl-hora" dateTime={evento?.timestamp}>
                    {horaDe(evento) || '--:--:--'}
                  </time>
                  <span className={`tl-icone tl-${persona.falha_coleta ? 'falha' : 'ok'}`} aria-hidden="true">
                    <PersonaIcon persona={mapearPersonaParaTipo(persona.persona) as any} size={16} />
                  </span>
                  <div className="tl-entrada-corpo">
                    <div className="tl-entrada-topo">
                      <span className={`tl-pill ${classePersona(persona.persona)}`}>{nomePersona(persona.persona)}</span>
                      <span className="tl-entrada-titulo">{tituloPasso(persona.persona)}</span>
                    </div>
                    {persona.analise && <p className="tl-analise">{persona.analise}</p>}
                    {queries.length > 0 && (
                      <div className="tl-queries">
                        {queries.map((query) => (
                          <code className="tl-query-line" key={`${persona.persona}-${query}`}>
                            {`$ ${query}`}
                          </code>
                        ))}
                      </div>
                    )}
                    {(() => {
                      const doms = dominiosFontes(persona.urls_fonte ?? []);
                      if (doms.length === 0) return null;
                      return (
                        <ul className="tl-fontes" aria-label={`${doms.length} domínios lidos`}>
                          {doms.map(({ dominio, paginas }) => (
                            <li key={dominio} className="tl-fonte">
                              <Favicon dominio={dominio} size={32} className="tl-fonte-icone" />
                              <span className="tl-fonte-dominio">{dominio}</span>
                              <span className="tl-fonte-paginas">
                                {paginas} {paginas === 1 ? 'página lida' : 'páginas lidas'}
                              </span>
                            </li>
                          ))}
                        </ul>
                      );
                    })()}
                  </div>
                </div>
              );
            })}

            {personas.length === 0 && buscaEventos.length > 0 &&
              buscaEventos.map((evento) => (
                <div className="tl-entrada" key={`busca-${evento.id}`}>
                  <time className="tl-hora" dateTime={evento.timestamp}>
                    {horaDe(evento) || '--:--:--'}
                  </time>
                  <span className="tl-icone tl-ok" aria-hidden="true">
                    <PersonaIcon persona={mapearPersonaParaTipo(evento.agentName) as any} size={16} />
                  </span>
                  <div className="tl-entrada-corpo">
                    <div className="tl-entrada-topo">
                      <span className={`tl-pill ${classePersona(evento.agentName)}`}>{evento.agentName}</span>
                      <span className="tl-entrada-titulo">{evento.title}</span>
                    </div>
                    <div className="tl-queries">
                      {extrairQueriesTimelog(evento.reasoning).map((query) => (
                        <code className="tl-query-line" key={`${evento.id}-${query}`}>
                          {`$ ${query}`}
                        </code>
                      ))}
                    </div>
                  </div>
                </div>
              ))}

            {personas.length === 0 && buscaEventos.length === 0 && (
              <div className="tl-entrada">
                <time className="tl-hora" dateTime={auditorEvento?.timestamp}>
                  {horaDe(auditorEvento) || ultimaHora || '--:--:--'}
                </time>
                <span className="tl-icone tl-ativo" aria-hidden="true">
                  <PersonaIcon persona='planejador' size={16} />
                </span>
                <div className="tl-entrada-corpo">
                  <div className="tl-entrada-topo">
                    <span className="tl-entrada-titulo">
                      Ponto {ponto.ponto_n}: aguardando varredura das personas
                    </span>
                  </div>
                </div>
              </div>
            )}

            {auditoria && (
              <LinhaAuditor
                auditoria={auditoria}
                pontoN={ponto.ponto_n}
                minimos={minimos}
                hora={horaDe(auditorEvento) || ultimaHora}
                timestamp={auditorEvento?.timestamp}
                emReprocesso={emReprocesso}
                onRefazerBuscaPonto={onRefazerBuscaPonto}
                onReauditarPonto={onReauditarPonto}
              />
            )}

            {!auditoria && coleta && !coleta.falha_coleta && (
              <div className="tl-entrada">
                <time className="tl-hora" dateTime={buscaEventos[buscaEventos.length - 1]?.timestamp}>
                  {horaDe(buscaEventos[buscaEventos.length - 1]) || ultimaHora || '--:--:--'}
                </time>
                <span className="tl-icone tl-neutro" aria-hidden="true">
                  <ShieldCheck size={13} aria-hidden="true" />
                </span>
                <div className="tl-entrada-corpo">
                  <div className="tl-entrada-topo">
                    <span className="tl-pill tl-pill-auditor">Auditor</span>
                    <span className="tl-entrada-titulo">
                      {personas.length >= 2
                        ? `Analisando discrepâncias entre ${nomePersona(personas[0].persona)} e ${nomePersona(
                            personas[1].persona,
                          )}`
                        : `Analisando o ponto ${ponto.ponto_n} com foco em contradições entre alegações`}
                    </span>
                  </div>
                </div>
              </div>
            )}

            {(() => {
              const extras = eventos.filter((evento) => !consumidos.has(evento.id) && evento.id !== auditorEvento?.id);
              if (extras.length === 0) return null;
              return (
                <details className="tl-reasoning">
                  <summary className="tl-reasoning-toggle">
                    ver reasoning ({extras.length} {extras.length === 1 ? 'registro' : 'registros'})
                  </summary>
                  <div className="tl-detalhe tl-reasoning-lista">
                    {extras.map((item) => (
                      <div className="tl-entrada tl-entrada-reasoning" key={item.id}>
                        <time className="tl-hora" dateTime={item.timestamp}>
                          {formatarHoraTimelog(item.timestamp) || '--:--:--'}
                        </time>
                      <span className={`tl-icone tl-neutro`} aria-hidden="true">
                        <PersonaIcon persona={mapearPersonaParaTipo(item.agentName) as any} size={16} />
                      </span>
                        <div className="tl-entrada-corpo">
                          <p className="tl-meta tl-meta-pill">
                            <span className={`tl-pill ${classePersona(item.agentName)}`}>{item.agentName}</span>
                            <span>{item.title.replace(/\s*\(ao vivo\)\s*$/i, '')}</span>
                          </p>
                          <Suspense fallback={<span className="tl-reasoning-corpo">{item.reasoning.slice(0, 400)}</span>}>
                            <LinhaReasoning texto={item.reasoning} />
                          </Suspense>
                        </div>
                      </div>
                    ))}
                  </div>
                </details>
              );
            })()}
          </No>
        );
      })}

      {/* Nó final: redação, quando há parecer */}
      {auditResult && (
        <No ultimo>
          <div className="tl-entrada tl-entrada-final">
            <time className="tl-hora" dateTime={reasoningItems[reasoningItems.length - 1]?.timestamp}>
              {ultimaHora || '--:--:--'}
            </time>
            <span className={`tl-icone tl-${auditResult.pronto_para_writer ? 'ok' : 'falha'}`} aria-hidden="true">
              {auditResult.pronto_para_writer ? (
                <PenTool size={13} aria-hidden="true" />
              ) : (
                <XCircle size={13} aria-hidden="true" />
              )}
            </span>
            <div className="tl-entrada-corpo">
              <span className="tl-entrada-titulo">
                {auditResult.pronto_para_writer ? (
                  'Pesquisa aprovada, Redator está gerando o relatório final'
                ) : (
                  <>
                    {auditResult.aprovados}/{auditResult.total_pontos} pontos aprovados — redação bloqueada até
                    aprovação total
                  </>
                )}
              </span>
            </div>
          </div>
        </No>
      )}
    </ol>
  );
};
