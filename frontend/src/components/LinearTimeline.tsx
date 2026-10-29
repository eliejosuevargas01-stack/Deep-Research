import React, { Suspense } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  FileSearch,
  PenTool,
  RefreshCw,
  Search,
  ShieldCheck,
  XCircle,
} from 'lucide-react';
import type { AuditResponse, PlanResponse, SearchResponse } from '../types/api';
import type { ReasoningFeedItem } from '../types/stream';
import '../styles/linear-timeline.css';

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

/** Domínio legível de uma URL para o favicon (item 3 da crítica). */
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

/** Primeira consulta executada por uma persona: vira o "ver query". */
function primeiraQuery(reasoning: string): string | null {
  const m = reasoning.match(/Ferramenta · SERP\*\*\s*`([^`]+)`/);
  return m ? m[1] : null;
}

function focoPersona(persona: string, pontoTitulo: string): string {
  const mapa: Record<string, string> = {
    historiador: 'antecedentes e séries históricas',
    visionario: 'tendências emergentes e fronteira',
    cetico: 'riscos e contra-evidências',
    futurista: 'cenários prospectivos',
  };
  const foco = mapa[persona.toLowerCase()] ?? 'evidências verificáveis';
  const assunto = pontoTitulo.length > 80 ? `${pontoTitulo.slice(0, 80)}…` : pontoTitulo;
  return `${nomePersona(persona)} está analisando ${assunto || `ponto`} com foco em ${foco}`;
}

interface NoCabecalhoProps {
  icone: React.ReactNode;
  linha: React.ReactNode;
  estado?: 'ativo' | 'ok' | 'falha' | 'neutro';
  expansivel?: boolean;
  expandido?: boolean;
  onAlternar?: () => void;
  corpoId?: string;
  acoes?: React.ReactNode;
}

const NoCabecalho: React.FC<NoCabecalhoProps> = ({
  icone,
  linha,
  estado = 'neutro',
  expansivel = false,
  expandido = false,
  onAlternar,
  corpoId,
  acoes,
}) => {
  const conteudo = (
    <>
      <span className={`tl-icone tl-${estado}`} aria-hidden="true">
        {icone}
      </span>
      <span className="tl-linha">{linha}</span>
      {expansivel && (
        <ChevronDown size={14} aria-hidden="true" className={`tl-chevron${expandido ? ' aberto' : ''}`} />
      )}
    </>
  );
  return (
    <div className="tl-no-cabecalho">
      {expansivel ? (
        <button
          type="button"
          className="tl-frase"
          aria-expanded={expandido}
          aria-controls={expandido && corpoId ? corpoId : undefined}
          onClick={onAlternar}
        >
          {conteudo}
        </button>
      ) : (
        <span className="tl-frase tl-estatica">{conteudo}</span>
      )}
      {acoes}
    </div>
  );
};

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
  const [expandidos, setExpandidos] = React.useState<Record<string, boolean>>({});
  const alternar = React.useCallback((id: string) => {
    setExpandidos((anterior) => ({ ...anterior, [id]: !anterior[id] }));
  }, []);

  const porPonto = React.useMemo(() => {
    const mapa = new Map<string, ReasoningFeedItem[]>();
    for (const item of reasoningItems) {
      const pid = (item.details as Record<string, unknown> | undefined)?.ponto_id;
      if (typeof pid !== 'string' || !pid) continue;
      const lista = mapa.get(pid) ?? [];
      lista.push(item);
      mapa.set(pid, lista);
    }
    return mapa;
  }, [reasoningItems]);

  const pontos = plan?.pontos ?? [];
  if (pontos.length === 0 && !searchResult && !auditResult) return null;

  const auditorias = new Map((auditResult?.auditorias ?? []).map((a) => [a.ponto_id, a]));
  const coletas = new Map((searchResult?.resumo_coletas ?? []).map((c) => [c.ponto_id, c]));

  return (
    <ol className="tl-linear" aria-label="Linha do tempo da investigação">
      {pontos.map((ponto, indice) => {
        const coleta = coletas.get(ponto.ponto_id);
        const auditoria = auditorias.get(ponto.ponto_id);
        const eventos = porPonto.get(ponto.ponto_id) ?? [];
        const reprovado = auditoria?.status === 'reprovado';
        const emReprocesso = pontoEmReprocesso === ponto.ponto_id;
        const ultimo = indice === pontos.length - 1;

        const personas = coleta?.personas ?? [];
        const idBusca = `tl-busca-${ponto.ponto_id}`;
        const buscaAberta = expandidos[idBusca] ?? false;
        const primeira = personas[0];
        const query = primeira?.reasoning ? primeiraQuery(primeira.reasoning) : null;

        const idAuditoria = `tl-auditoria-${ponto.ponto_id}`;
        const auditoriaAberta = expandidos[idAuditoria] ?? reprovado;
        const reprovados = auditoria?.criterios?.filter((c) => !c.aprovado) ?? [];

        const acoes = (onRefazerBuscaPonto || onReauditarPonto) && (
          <span className={`tl-acoes${reprovado || emReprocesso ? ' sempre' : ''}`}>
            {onRefazerBuscaPonto && (
              <button
                type="button"
                className="tl-acao"
                disabled={emReprocesso}
                onClick={() => onRefazerBuscaPonto(ponto.ponto_id)}
                aria-label={`Refazer busca do ponto ${ponto.ponto_n}`}
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
                onClick={() => onReauditarPonto(ponto.ponto_id)}
                aria-label={`Reauditar ponto ${ponto.ponto_n}`}
              >
                <ShieldCheck size={12} aria-hidden="true" />
                <span>{emReprocesso ? 'auditando…' : 'reauditar'}</span>
              </button>
            )}
          </span>
        );

        return (
          <No key={ponto.ponto_id} ultimo={ultimo}>
            {/* Nó 1: análise das personas */}
            <NoCabecalho
              icone={<Search size={13} aria-hidden="true" />}
              estado={coleta ? (coleta.falha_coleta ? 'falha' : 'ok') : 'ativo'}
              linha={
                primeira ? (
                  <><strong>{tituloPasso(primeira.persona, ponto.ponto_n)}</strong> — {focoPersona(primeira.persona, ponto.ponto)}</>
                ) : (
                  <>Ponto {ponto.ponto_n}: aguardando varredura das personas</>
                )
              }
            />

            {/* Nó 2: busca executada */}
            {coleta && (
              <NoCabecalho
                icone={<FileSearch size={13} aria-hidden="true" />}
                estado={coleta.falha_coleta ? 'falha' : 'ok'}
                expansivel={Boolean(query)}
                expandido={buscaAberta}
                corpoId={idBusca}
                onAlternar={() => alternar(idBusca)}
                linha={
                  <>
                    {primeira
                      ? `${nomePersona(primeira.persona)} fez uma busca`
                      : `Busca do ponto ${ponto.ponto_n} concluída`}
                    {query && (
                      <span className="tl-ver">
                        {' '}[ver query <ChevronDown size={11} aria-hidden="true" />]
                      </span>
                    )}
                  </>
                }
                acoes={acoes}
              />
            )}
            {coleta && query && buscaAberta && (
              <div id={idBusca} className="tl-detalhe">
                <code className="tl-query">{query}</code>
                {(() => {
                  const todas = personas.flatMap((p) => p.urls_fonte ?? []);
                  const doms = dominiosFontes(todas);
                  if (doms.length === 0) return null;
                  return (
                    <ul className="tl-fontes" aria-label={`${doms.length} domínios lidos`}>
                      {doms.map(({ dominio, paginas }) => (
                        <li key={dominio} className="tl-fonte">
                          {/* eslint-disable-next-line @next/next/no-img-element */}
                          <img
                            src={`https://www.google.com/s2/favicons?domain=${encodeURIComponent(dominio)}&sz=32`}
                            alt=""
                            width={14}
                            height={14}
                            loading="lazy"
                            className="tl-fonte-icone"
                          />
                          <span className="tl-fonte-dominio">{dominio}</span>
                          <span className="tl-fonte-paginas">
                            {paginas} {paginas === 1 ? 'página lida' : 'páginas lidas'}
                          </span>
                        </li>
                      ))}
                    </ul>
                  );
                })()}
                <span className="tl-meta">
                  {coleta.total_urls_lidas} URLs lidas · {coleta.total_urls_fonte} fontes · {coleta.tentativas}{' '}
                  {coleta.tentativas === 1 ? 'tentativa' : 'tentativas'}
                </span>
              </div>
            )}

            {/* Nó 3: deliberação do auditor */}
            {auditoria ? (
              <>
                <NoCabecalho
                  icone={
                    auditoria.status === 'aprovado' ? (
                      <CheckCircle2 size={13} aria-hidden="true" />
                    ) : (
                      <AlertTriangle size={13} aria-hidden="true" />
                    )
                  }
                  estado={auditoria.status === 'aprovado' ? 'ok' : 'falha'}
                  expansivel={reprovados.length > 0}
                  expandido={auditoriaAberta}
                  corpoId={idAuditoria}
                  onAlternar={() => alternar(idAuditoria)}
                  linha={
                    auditoria.status === 'aprovado' ? (
                      <>
                        Ponto {ponto.ponto_n} aprovado ({auditoria.criterios_aprovados}/
                        {auditoria.criterios?.length ?? 12})
                      </>
                    ) : (
                      <>
                        Auditor reprovou o ponto #{ponto.ponto_n} por{' '}
                        {reprovados.length > 0
                          ? reprovados
                              .slice(0, 2)
                              .map((c) => c.justificativa)
                              .join('; ')
                          : 'critérios não atendidos'}{' '}
                        ({(auditoria.pontuacao_percentual ?? 0).toFixed(0)}% · {auditoria.criterios_aprovados}/
                        {auditoria.criterios_minimos ?? rigorAtual ?? 12}) — reenviado para pesquisa
                      </>
                    )
                  }
                />
                {reprovados.length > 0 && auditoriaAberta && (
                  <div id={idAuditoria} className="tl-detalhe">
                    {reprovados.slice(0, 4).map((c) => (
                      <p key={c.id} className="tl-criterio">
                        <strong>Critério {c.id}:</strong> {c.justificativa}
                        {c.correcao && <> — correção: {c.correcao}</>}
                      </p>
                    ))}
                    {reprovados.length > 4 && (
                      <p className="tl-meta">+{reprovados.length - 4} critérios não atendidos</p>
                    )}
                  </div>
                )}
              </>
            ) : (
              coleta &&
              !coleta.falha_coleta && (
                <NoCabecalho
                  icone={<ShieldCheck size={13} aria-hidden="true" />}
                  estado="neutro"
                  linha={
                    personas.length >= 2 ? (
                      <>
                        Auditor está analisando discrepâncias entre alegações de{' '}
                        {nomePersona(personas[0].persona)} e {nomePersona(personas[1].persona)}
                      </>
                    ) : (
                      <>
                        Auditor está analisando ponto {ponto.ponto_n} com foco em contradições entre alegações
                      </>
                    )
                  }
                />
              )
            )}

            {/* Reasoning residual por ponto: só sob demanda */}
            {eventos.length > 0 && (
              <details className="tl-reasoning">
                <summary className="tl-reasoning-toggle">
                  ver reasoning ({eventos.length} {eventos.length === 1 ? 'registro' : 'registros'})
                </summary>
                <div className="tl-detalhe">
                  {eventos.map((item) => (
                    <div key={item.id} className="tl-reasoning-item">
                      <p className="tl-meta tl-meta-pill">
                        <span className={`tl-pill ${classePersona(item.agentName)}`}>{item.agentName}</span>
                        <span>{item.title.replace(/\s*\(ao vivo\)\s*$/i, '')}</span>
                      </p>
                      <Suspense fallback={<span className="tl-reasoning-corpo">{item.reasoning.slice(0, 400)}</span>}>
                        <LinhaReasoning texto={item.reasoning} />
                      </Suspense>
                    </div>
                  ))}
                </div>
              </details>
            )}
          </No>
        );
      })}

      {/* Nó final: redação, quando há parecer */}
      {auditResult && (
        <No ultimo>
          <NoCabecalho
            icone={
              auditResult.pronto_para_writer ? (
                <PenTool size={13} aria-hidden="true" />
              ) : (
                <XCircle size={13} aria-hidden="true" />
              )
            }
            estado={auditResult.pronto_para_writer ? 'ok' : 'falha'}
            linha={
              auditResult.pronto_para_writer ? (
                <>Pesquisa aprovada, Redator está gerando o relatório final</>
              ) : (
                <>
                  {auditResult.aprovados}/{auditResult.total_pontos} pontos aprovados — redação bloqueada até
                  aprovação total
                </>
              )
            }
          />
        </No>
      )}
    </ol>
  );
};
