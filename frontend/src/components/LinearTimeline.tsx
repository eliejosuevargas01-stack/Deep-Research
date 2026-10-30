import React, { Suspense } from 'react';
import { ChevronDown, RefreshCw, ShieldCheck } from 'lucide-react';
import type { AuditCriterionDetail, AuditItem, AuditResponse, PlanResponse, SearchResponse } from '../types/api';
import type { ReasoningFeedItem } from '../types/stream';
import '../styles/linear-timeline.css';
import { PersonaIcon } from './ResearchIcons';
import type { PersonaType } from './ResearchIcons';
import { Favicon } from './Favicon';

const MarkdownBody = React.lazy(() => import('./ReasoningMarkdownBody'));

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
    auditor: 'Auditor',
    planejador: 'Planejador',
    redator: 'Redator',
  };
  return mapa[id.toLowerCase()] ?? id;
}

function mapearPersonaParaTipo(persona: string): PersonaType {
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

/** "Persona — o que está fazendo": a frase densa da linha fechada. */
function tituloPasso(persona: string): string {
  const foco: Record<string, string> = {
    historiador: 'Sintetizando evidências históricas',
    visionario: 'Mapeando tendências emergentes',
    cetico: 'Auditando riscos e contra-evidências',
    futurista: 'Projetando cenários prospectivos',
    auditor: 'Auditando contra os 12 critérios',
    redator: 'Consolidando o dossiê',
    planejador: 'Decompondo o tema',
  };
  return foco[persona.toLowerCase()] ?? 'Analisando evidências';
}

function eventosDaPersona(nome: string, eventos: ReasoningFeedItem[]): ReasoningFeedItem[] {
  const alvo = mapearPersonaParaTipo(nome);
  return eventos.filter((evento) => mapearPersonaParaTipo(evento.agentName) === alvo);
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

function idSeguro(texto: string): string {
  return texto
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

interface FonteResumo {
  dominio: string;
  paginas: number;
}

interface PassoProps {
  idBase: string;
  persona: PersonaType;
  rotulo: string;
  resumo: string;
  aoVivo?: boolean;
  falha?: boolean;
  hora?: string;
  timestamp?: string;
  consultas?: string[];
  analise?: string | null;
  reasoning?: string | null;
  fontes?: FonteResumo[];
  detalhe?: React.ReactNode;
  acoes?: React.ReactNode;
}

/**
 * Passo da timeline: a linha fechada é UM rótulo denso (`Persona — o que
 * faz`) com o ícone à esquerda e o chevron à direita. Hora, queries, análise,
 * reasoning, chips de fonte e critérios vivem só no corpo expandido.
 */
const Passo: React.FC<PassoProps> = ({
  idBase,
  persona,
  rotulo,
  resumo,
  aoVivo = false,
  falha = false,
  hora,
  timestamp,
  consultas,
  analise,
  reasoning,
  fontes,
  detalhe,
  acoes,
}) => {
  const [aberto, setAberto] = React.useState(false);
  const jaEsteveAoVivo = React.useRef(aoVivo);

  // Streaming: ao concluir, o item recolhe sozinho e o ícone volta a ser o da
  // persona (DESIGN §6). Só recolhe se estava ao vivo na renderização anterior.
  React.useEffect(() => {
    if (jaEsteveAoVivo.current && !aoVivo) setAberto(false);
    jaEsteveAoVivo.current = aoVivo;
  }, [aoVivo]);

  const listaConsultas = consultas ?? [];
  const listaFontes = fontes ?? [];
  const corpoId = `tl-corpo-${idBase}`;
  const temCorpo = Boolean(
    hora || listaConsultas.length > 0 || analise || reasoning || listaFontes.length > 0 || detalhe || acoes,
  );

  const rotuloInterno = (
    <>
      <span className={`tl-icone${falha ? ' tl-falha' : ''}`} aria-hidden="true">
        <PersonaIcon persona={persona} size={aoVivo ? 18 : 16} />
      </span>
      <span className="tl-texto">
        <span className="tl-persona">{rotulo}</span>
        <span className="tl-traco" aria-hidden="true">
          {' — '}
        </span>
        <span className="tl-acao-texto" title={resumo}>
          {resumo}
        </span>
        {aoVivo ? <span className="tl-estado-vivo">ao vivo</span> : null}
      </span>
    </>
  );

  if (!temCorpo) {
    return (
      <div className={`tl-entrada${falha ? ' reprovado' : ''}${aoVivo ? ' ao-vivo' : ''}`}>
        <div className="tl-entrada-linha tl-linha-estatica">{rotuloInterno}</div>
      </div>
    );
  }

  return (
    <div
      className={`tl-entrada${falha ? ' reprovado' : ''}${aoVivo ? ' ao-vivo' : ''}${aberto ? ' aberto' : ''}`}
    >
      <button
        type="button"
        className="tl-entrada-linha"
        aria-expanded={aberto}
        aria-controls={corpoId}
        onClick={() => setAberto((atual) => !atual)}
      >
        {rotuloInterno}
        <ChevronDown className={`tl-chevron${aberto ? ' aberto' : ''}`} size={16} aria-hidden="true" />
      </button>
      <div id={corpoId} className="tl-entrada-corpo" hidden={!aberto}>
        {hora || listaConsultas.length > 0 ? (
          <div className="tl-corpo-meta">
            {hora ? (
              <time className="tl-hora" dateTime={timestamp}>
                {hora}
              </time>
            ) : null}
            {listaConsultas.length > 0 ? (
              <span className="tl-contagem">
                {listaConsultas.length} {listaConsultas.length === 1 ? 'consulta' : 'consultas'}
              </span>
            ) : null}
          </div>
        ) : null}
        {analise ? <p className="tl-analise">{analise}</p> : null}
        {listaConsultas.length > 0 ? (
          <div className="tl-queries">
            {listaConsultas.map((query, indice) => (
              <code className="tl-query-line" key={`${idBase}-q${indice}`}>
                {`$ ${query}`}
              </code>
            ))}
          </div>
        ) : null}
        {reasoning ? (
          <Suspense fallback={<div className="tl-reasoning-corpo">{reasoning.slice(0, 400)}</div>}>
            <MarkdownBody text={reasoning} />
          </Suspense>
        ) : null}
        {listaFontes.length > 0 ? (
          <ul className="tl-fontes" aria-label={`${listaFontes.length} domínios lidos`}>
            {listaFontes.map(({ dominio, paginas }) => (
              <li key={`${idBase}-${dominio}`} className="tl-fonte">
                <Favicon dominio={dominio} size={16} className="tl-fonte-icone" />
                <span className="tl-fonte-dominio">{dominio}</span>
                <span className="tl-fonte-paginas">
                  {paginas} {paginas === 1 ? 'página' : 'páginas'}
                </span>
              </li>
            ))}
          </ul>
        ) : null}
        {detalhe}
        {acoes ? <div className="tl-acoes">{acoes}</div> : null}
      </div>
    </div>
  );
};

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
  const reprovados: AuditCriterionDetail[] = auditoria.criterios?.filter((c) => !c.aprovado) ?? [];
  const motivo = (reprovados[0]?.justificativa?.trim() || 'critérios não atendidos').replace(/[.;]+$/, '');
  const percentual = Math.round(auditoria.pontuacao_percentual ?? 0);
  const frase = reprovado
    ? `reprovou o ponto ${pontoN} (${percentual}% · ${auditoria.criterios_aprovados}/${minimos}). Motivo: ${motivo}. Nova busca em andamento.`
    : `aprovou o ponto ${pontoN} (${percentual}% · ${auditoria.criterios_aprovados}/${minimos})`;

  const acoes =
    reprovado && (onRefazerBuscaPonto || onReauditarPonto) ? (
      <>
        {onRefazerBuscaPonto ? (
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
        ) : null}
        {onReauditarPonto ? (
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
        ) : null}
      </>
    ) : null;

  return (
    <Passo
      idBase={`auditor-${idSeguro(auditoria.ponto_id)}`}
      persona="auditor"
      rotulo="Auditor"
      resumo={frase}
      falha={reprovado}
      hora={hora}
      timestamp={timestamp}
      analise={auditoria.resumo_auditoria ?? null}
      reasoning={auditoria.reasoning_auditoria ?? null}
      acoes={acoes}
      detalhe={
        <div className="tl-detalhe tl-callout">
          <p className="tl-callout-score">
            <strong>{`${percentual}%`}</strong>
            <span>{`${auditoria.criterios_aprovados}/${minimos} critérios`}</span>
            <span className={`tl-callout-status ${reprovado ? 'reprovado' : 'aprovado'}`}>
              {reprovado ? 'reprovado' : 'aprovado'}
            </span>
          </p>
          {reprovados.length > 0 ? (
            <div className="tl-criterios">
              {reprovados.slice(0, 4).map((c) => (
                <p key={c.id} className="tl-criterio">
                  <strong>{`Critério ${c.id}:`}</strong> {c.justificativa}
                  {c.correcao ? ` — correção: ${c.correcao}` : ''}
                </p>
              ))}
              {reprovados.length > 4 ? (
                <p className="tl-meta">{`+${reprovados.length - 4} critérios não atendidos`}</p>
              ) : null}
            </div>
          ) : null}
        </div>
      }
    />
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
          <li className={`tl-no${ultimo ? ' ultimo' : ''}`} key={ponto.ponto_id}>
            <span className="tl-trilho" aria-hidden="true" />
            <div className="tl-conteudo">
              <p className="tl-grupo">
                <span className="tl-grupo-rotulo">{`Ponto ${String(ponto.ponto_n).padStart(2, '0')} ·`}</span>
                <span className="tl-grupo-tema" title={ponto.ponto}>{ponto.ponto}</span>
              </p>

              {personas.map((persona, personaIndice) => {
                const candidatos = eventosDaPersona(persona.persona, buscaEventos);
                const evento = candidatos[0] ?? buscaEventos[personaIndice] ?? buscaEventos[0];
                for (const usado of candidatos) consumidos.add(usado.id);
                if (evento) consumidos.add(evento.id);
                const queries = queriesDaPersona(persona.reasoning, candidatos.length > 0 ? candidatos : evento ? [evento] : []);
                const aoVivo = candidatos.some((c) => c.streaming) || Boolean(evento?.streaming);
                return (
                  <Passo
                    key={`${ponto.ponto_id}-${persona.persona}-${personaIndice}`}
                    idBase={`${idSeguro(ponto.ponto_id)}-${mapearPersonaParaTipo(persona.persona)}-${personaIndice}`}
                    persona={mapearPersonaParaTipo(persona.persona)}
                    rotulo={nomePersona(persona.persona)}
                    resumo={tituloPasso(persona.persona)}
                    aoVivo={aoVivo}
                    falha={persona.falha_coleta}
                    hora={horaDe(evento)}
                    timestamp={evento?.timestamp}
                    consultas={queries}
                    analise={persona.analise}
                    reasoning={persona.reasoning || evento?.reasoning}
                    fontes={dominiosFontes(persona.urls_fonte ?? [])}
                  />
                );
              })}

              {personas.length === 0 &&
                buscaEventos.map((evento, eventoIndice) => {
                  consumidos.add(evento.id);
                  return (
                    <Passo
                      key={`busca-${evento.id}`}
                      idBase={`${idSeguro(ponto.ponto_id)}-busca-${eventoIndice}`}
                      persona={mapearPersonaParaTipo(evento.agentName)}
                      rotulo={nomePersona(evento.agentName)}
                      resumo={evento.title.replace(/\s*\(ao vivo\)\s*$/i, '')}
                      aoVivo={Boolean(evento.streaming)}
                      hora={horaDe(evento)}
                      timestamp={evento.timestamp}
                      consultas={extrairQueriesTimelog(evento.reasoning)}
                      reasoning={evento.reasoning}
                    />
                  );
                })}

              {personas.length === 0 && buscaEventos.length === 0 && (
                <Passo
                  idBase={`${idSeguro(ponto.ponto_id)}-aguardando`}
                  persona="planejador"
                  rotulo="Planejador"
                  resumo={`aguardando varredura das personas no ponto ${ponto.ponto_n}`}
                />
              )}

              {auditoria ? (
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
              ) : null}

              {!auditoria && coleta && !coleta.falha_coleta && (
                <Passo
                  idBase={`${idSeguro(ponto.ponto_id)}-auditoria-pendente`}
                  persona="auditor"
                  rotulo="Auditor"
                  resumo={
                    personas.length >= 2
                      ? `analisando discrepâncias entre ${nomePersona(personas[0].persona)} e ${nomePersona(
                          personas[1].persona,
                        )}`
                      : `analisando o ponto ${ponto.ponto_n} com foco em contradições entre alegações`
                  }
                />
              )}

              {(() => {
                const extras = eventos.filter((evento) => !consumidos.has(evento.id) && evento.id !== auditorEvento?.id);
                if (extras.length === 0) return null;
                return extras.map((evento, extraIndice) => (
                  <Passo
                    key={`extra-${evento.id}`}
                    idBase={`${idSeguro(ponto.ponto_id)}-extra-${extraIndice}`}
                    persona={mapearPersonaParaTipo(evento.agentName)}
                    rotulo={nomePersona(evento.agentName)}
                    resumo={evento.title.replace(/\s*\(ao vivo\)\s*$/i, '')}
                    aoVivo={Boolean(evento.streaming)}
                    hora={formatarHoraTimelog(evento.timestamp)}
                    timestamp={evento.timestamp}
                    consultas={extrairQueriesTimelog(evento.reasoning)}
                    reasoning={evento.reasoning}
                  />
                ));
              })()}
            </div>
          </li>
        );
      })}

      {/* Nó final: redação, quando há parecer */}
      {auditResult ? (
        <li className="tl-no ultimo">
          <span className="tl-trilho" aria-hidden="true" />
          <div className="tl-conteudo">
            <Passo
              idBase="redator-final"
              persona="redator"
              rotulo="Redator"
              resumo={
                auditResult.pronto_para_writer
                  ? 'pesquisa aprovada, gerando o relatório final'
                  : `${auditResult.aprovados} de ${auditResult.total_pontos} pontos aprovados. A redação começa quando todos passarem.`
              }
            />
          </div>
        </li>
      ) : null}
    </ol>
  );
};
