import React, { useRef, useState } from 'react';
import { PanelRightClose, PanelRightOpen } from 'lucide-react';
import { PlanResponse, ModeloMetadados, SearchResponse } from '../types/api';
import { TokenUsageMeter } from './TokenUsageMeter';
import { SourcesExplorer, derivarFontesParaExplorer, FonteExplorerItem } from './SourcesExplorer';
import '../styles/right-rail.css';

interface ContextSidebarProps {
  plan?: PlanResponse | null;
  pipelineStatus?: string | null;
  cycleNumber?: number;
  maxCycles?: number;
  collectedPoints?: number;
  auditSummary?: {
    aprovados: number;
    total: number;
    ciclo?: number | null;
    criteriosMinimos?: number | null;
  } | null;
  metadadosModelo?: ModeloMetadados | null;
  fontes?: FonteExplorerItem[] | null;
  searchResult?: SearchResponse | null;
  fontesAtivas?: boolean;
  pontosReprovados?: Set<string> | null;
}

type RailMode = 'raciocinio' | 'fontes';

const TAB_ID: Record<RailMode, string> = {
  raciocinio: 'rr-tab-raciocinio',
  fontes: 'rr-tab-fontes',
};

const PANEL_ID: Record<RailMode, string> = {
  raciocinio: 'rr-panel-raciocinio',
  fontes: 'rr-panel-fontes',
};

function getStatusLabel(status: string): string {
  switch (status) {
    case 'idle':
    case 'planejado':
    case 'aguardando':
      return 'Aguardando início';
    case 'searching':
    case 'buscando':
      return 'Buscando evidências';
    case 'auditing':
    case 'auditando':
      return 'Em auditoria';
    case 'writing':
    case 'redigindo':
      return 'Redigindo dossiê';
    case 'completed':
    case 'concluido':
      return 'Concluído';
    case 'rejected':
    case 'reprovado':
      return 'Reprovado';
    case 'failed':
    case 'falha':
      return 'Falha';
    default:
      return 'Em processamento';
  }
}

function getStatusBadgeClass(status: string): string {
  switch (status) {
    case 'idle':
    case 'planejado':
    case 'aguardando':
      return 'planejado';
    case 'searching':
    case 'buscando':
      return 'buscando';
    case 'auditing':
    case 'auditando':
      return 'auditando';
    case 'writing':
    case 'redigindo':
      return 'redigindo';
    case 'completed':
    case 'concluido':
      return 'concluido';
    case 'rejected':
    case 'reprovado':
    case 'failed':
    case 'falha':
      return 'reprovado';
    default:
      return 'planejado';
  }
}

const PONTO_STATUS: Record<string, { rotulo: string; tone: string }> = {
  pendente: { rotulo: 'Pendente', tone: 'muted' },
  em_andamento: { rotulo: 'Em curso', tone: 'accent' },
  coletado: { rotulo: 'Coletado', tone: 'info' },
  aprovado: { rotulo: 'Aprovado', tone: 'success' },
  reprovado: { rotulo: 'Reprovado', tone: 'danger' },
};

const ContextSidebarBase: React.FC<ContextSidebarProps> = ({
  plan,
  pipelineStatus,
  cycleNumber,
  maxCycles,
  collectedPoints,
  auditSummary,
  metadadosModelo,
  fontes,
  searchResult,
  fontesAtivas,
  pontosReprovados,
}) => {
  const [mode, setMode] = useState<RailMode>('raciocinio');
  const [collapsed, setCollapsed] = useState(false);
  const tabRefs = useRef<Record<RailMode, HTMLButtonElement | null>>({
    raciocinio: null,
    fontes: null,
  });

  if (collapsed) {
    return (
      <aside
        className="sidebar-container context-sidebar right-rail right-rail--sticky rr-rail rr-rail--collapsed"
        aria-label="Informações contextuais da pesquisa"
      >
        <button
          type="button"
          className="rr-rail__reopen"
          aria-expanded={false}
          aria-controls="rr-rail-shell"
          aria-label="Expandir painel de contexto"
          title="Expandir painel"
          onClick={() => setCollapsed(false)}
        >
          <PanelRightOpen size={16} aria-hidden="true" />
        </button>
      </aside>
    );
  }

  const statusNormalized = pipelineStatus || plan?.status_pipeline || 'aguardando';
  const statusLabel = plan ? getStatusLabel(statusNormalized) : 'Pronto para iniciar';
  const statusBadgeClass = getStatusBadgeClass(statusNormalized);

  const temasPorPonto = Array.isArray(plan?.pontos) ? plan.pontos : [];
  const nPontos = typeof plan?.n_pontos === 'number' ? plan.n_pontos : null;
  const personas = Array.isArray(plan?.preferencias?.personas) ? plan!.preferencias!.personas! : [];
  const itensFontes =
    fontes ?? derivarFontesParaExplorer(searchResult, { emColeta: fontesAtivas, pontosReprovados });

  const subtituloPartes: string[] = [];
  if (nPontos !== null) subtituloPartes.push(`${nPontos} ${nPontos === 1 ? 'ponto' : 'pontos'}`);
  if (personas.length) subtituloPartes.push(`${personas.length} personas`);
  if (typeof cycleNumber === 'number') {
    subtituloPartes.push(`ciclo ${cycleNumber}${maxCycles ? `/${maxCycles}` : ''}`);
  }
  const subtitulo = subtituloPartes.length ? subtituloPartes.join(' · ') : statusLabel;
  const titulo = plan?.tema?.trim() ? plan.tema.trim() : 'Nova pesquisa';

  const coletadosNota =
    typeof collectedPoints === 'number' && nPontos !== null
      ? `${collectedPoints}/${nPontos} pontos coletados`
      : null;
  const auditoriaNota = auditSummary ? `${auditSummary.aprovados}/${auditSummary.total} aprovados na auditoria` : null;
  const notas = [coletadosNota, auditoriaNota].filter(Boolean).join(' · ');

  const handleTabKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    let next: RailMode | null = null;
    if (event.key === 'ArrowRight') next = mode === 'raciocinio' ? 'fontes' : 'raciocinio';
    else if (event.key === 'ArrowLeft') next = mode === 'fontes' ? 'raciocinio' : 'fontes';
    else if (event.key === 'Home') next = 'raciocinio';
    else if (event.key === 'End') next = 'fontes';
    if (!next) return;
    event.preventDefault();
    setMode(next);
    tabRefs.current[next]?.focus();
  };

  const renderTab = (value: RailMode, rotulo: string, count?: number) => {
    const selected = mode === value;
    return (
      <button
        type="button"
        role="tab"
        id={TAB_ID[value]}
        aria-selected={selected}
        aria-controls={PANEL_ID[value]}
        tabIndex={selected ? 0 : -1}
        className="rr-rail__tab"
        ref={(node) => {
          tabRefs.current[value] = node;
        }}
        onClick={() => setMode(value)}
      >
        <span>{rotulo}</span>
        {typeof count === 'number' && <span className="rr-rail__tab-count">{count}</span>}
      </button>
    );
  };

  return (
    <aside
      id="rr-rail-shell"
      className="sidebar-container context-sidebar right-rail right-rail--sticky rr-rail"
      aria-label="Informações contextuais da pesquisa"
    >
      <header className="rr-rail__head">
        <div className="rr-rail__title-row">
          <h2 className="rr-rail__title" title={titulo}>
            {titulo}
          </h2>
          <button
            type="button"
            className="rr-rail__collapse"
            aria-expanded={true}
            aria-controls="rr-rail-shell"
            aria-label="Recolher painel de contexto"
            title="Recolher painel"
            onClick={() => setCollapsed(true)}
          >
            <PanelRightClose size={15} aria-hidden="true" />
          </button>
        </div>
        <div className="rr-rail__meta">
          {/* Contrato E2E: `.status-badge-container > .status-badge-chip` precisa
              continuar existindo com o painel expandido. */}
          <div className="status-badge-container rr-rail__status">
            <span className={`status-badge-chip ${statusBadgeClass} rr-status__badge`}>{statusLabel}</span>
          </div>
          <p className="rr-rail__subtitle" title={subtitulo}>
            {subtitulo}
          </p>
        </div>
      </header>

      <div
        className="rr-rail__tabs"
        role="tablist"
        aria-label="Modos do painel de contexto"
        onKeyDown={handleTabKeyDown}
      >
        {renderTab('raciocinio', 'Raciocínio')}
        {renderTab('fontes', 'Fontes exploradas', itensFontes.length)}
      </div>

      <div className="rr-rail__body" id="rr-rail-body">
        <div
          role="tabpanel"
          id={PANEL_ID.raciocinio}
          aria-labelledby={TAB_ID.raciocinio}
          className="rr-rail__pane"
          hidden={mode !== 'raciocinio'}
        >
          {temasPorPonto.length === 0 ? (
            <p className="rr-sources__empty">
              {plan ? 'O plano ainda não tem passos registrados.' : 'Digite um tema para iniciar a investigação'}
            </p>
          ) : (
            <ol className="rr-steps">
              {temasPorPonto.map((ponto, indice) => {
                const estado = PONTO_STATUS[ponto.status] ?? PONTO_STATUS.pendente;
                return (
                  <li key={ponto.ponto_id || `p-${indice}`} className="rr-steps__row">
                    <span className="rr-steps__index" aria-hidden="true">
                      {String(ponto.ponto_n ?? indice + 1).padStart(2, '0')}
                    </span>
                    <span className="rr-steps__text" title={ponto.ponto}>
                      {ponto.ponto}
                    </span>
                    <span className={`rr-steps__state is-${estado.tone}`}>{estado.rotulo}</span>
                  </li>
                );
              })}
            </ol>
          )}
          {notas && <p className="rr-rail__note">{notas}</p>}
          {temasPorPonto.length === 0 && plan && (
            <dl className="rr-steps rr-steps--fallback">
              <div className="rr-steps__meta">
                <dt>Estágio</dt>
                <dd>{statusLabel}</dd>
              </div>
              {typeof cycleNumber === 'number' && (
                <div className="rr-steps__meta">
                  <dt>Ciclo</dt>
                  <dd>{`${cycleNumber}${maxCycles ? ` / ${maxCycles}` : ''}`}</dd>
                </div>
              )}
              {typeof collectedPoints === 'number' && nPontos !== null && (
                <div className="rr-steps__meta">
                  <dt>Pontos coletados</dt>
                  <dd>{`${collectedPoints} / ${nPontos}`}</dd>
                </div>
              )}
            </dl>
          )}
        </div>

        <div
          role="tabpanel"
          id={PANEL_ID.fontes}
          aria-labelledby={TAB_ID.fontes}
          className="rr-rail__pane"
          hidden={mode !== 'fontes'}
        >
          <SourcesExplorer items={itensFontes} />
        </div>
      </div>

      <footer className="rr-rail__foot">
        <TokenUsageMeter metadados={metadadosModelo ?? plan?.metadados_modelo ?? null} compact />
      </footer>
    </aside>
  );
};

export const ContextSidebar = React.memo(ContextSidebarBase);
