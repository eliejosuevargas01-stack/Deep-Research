import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Check, Copy, PanelRightClose } from 'lucide-react';
import { PlanResponse, ModeloMetadados, SearchResponse } from '../types/api';
import { TokenUsageMeter } from './TokenUsageMeter';
import { SourcesExplorer, derivarFontesParaExplorer, FonteExplorerItem } from './SourcesExplorer';
import '../styles/right-rail.css';

export type RailMode = 'contexto' | 'fontes';

interface ContextSidebarProps {
  plan?: PlanResponse | null;
  pipelineStatus?: string | null;
  cycleNumber?: number;
  maxCycles?: number;
  collectedPoints?: number;
  auditAoVivo?: boolean;
  auditSummary?: {
    aprovados: number;
    total: number;
    ciclo?: number | null;
    criteriosMinimos?: number | null;
  } | null;
  metadadosModelo?: ModeloMetadados | null;
  tokensAoVivo?: { prompt_tokens: number; completion_tokens: number; total_tokens: number } | null;
  fontes?: FonteExplorerItem[] | null;
  searchResult?: SearchResponse | null;
  fontesAtivas?: boolean;
  pontosReprovados?: Set<string> | null;
  reasoningItems?: Array<{
    reasoning?: string | null;
    pointNumber?: number;
    details?: { ponto_id?: string; urls_lidas?: number; [key: string]: unknown };
  }>;
  isCollapsed?: boolean;
  onToggleCollapse?: () => void;
  initialMode?: RailMode;
  mode?: RailMode;
}

const RAIL_MODE_KEY = 'deepResearch.railMode';
const RAIL_PANEL_ID = 'rr-rail-panel';

const TAB_ID: Record<RailMode, string> = {
  contexto: 'rr-tab-contexto',
  fontes: 'rr-tab-fontes',
};

const PANEL_ID: Record<RailMode, string> = {
  contexto: 'rr-panel-contexto',
  fontes: 'rr-panel-fontes',
};

const MODES: RailMode[] = ['contexto', 'fontes'];

function readStoredMode(): RailMode | null {
  try {
    const raw = typeof localStorage !== 'undefined' ? localStorage.getItem(RAIL_MODE_KEY) : null;
    if (raw === 'fontes' || raw === 'contexto' || raw === 'raciocinio') {
      if (raw === 'raciocinio') return 'contexto';
      return raw;
    }
  } catch {
    /* storage bloqueado */
  }
  return null;
}

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

const ContextSidebarBase: React.FC<ContextSidebarProps> = ({
  plan,
  pipelineStatus,
  cycleNumber,
  maxCycles,
  collectedPoints,
  auditSummary,
  auditAoVivo = false,
  metadadosModelo,
  tokensAoVivo,
  fontes,
  searchResult,
  fontesAtivas,
  pontosReprovados,
  reasoningItems,
  isCollapsed,
  onToggleCollapse,
  initialMode,
  mode: modeProp,
}) => {
  const [collapsedInternal, setCollapsedInternal] = useState(false);
  const collapsed = isCollapsed !== undefined ? isCollapsed : collapsedInternal;

  const handleToggle = (next: boolean) => {
    setCollapsedInternal(next);
    if (onToggleCollapse) {
      onToggleCollapse();
    }
  };
  const [copiado, setCopiado] = useState(false);

  useEffect(() => {
    const isMobile = typeof window !== 'undefined' && window.matchMedia('(max-width: 899px)').matches;
    if (isMobile && isCollapsed === undefined) {
      setCollapsedInternal(true);
    }
  }, [isCollapsed]);

  useEffect(() => {
    if (collapsed) return;
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return;
    const isMobile = window.matchMedia('(max-width: 899px)').matches;
    if (!isMobile) return;
    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = originalOverflow;
    };
  }, [collapsed]);
  const tabRefs = useRef<Record<RailMode, HTMLButtonElement | null>>({
    contexto: null,
    fontes: null,
  });
  const copiadoTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const itensFontes =
    fontes ??
    derivarFontesParaExplorer(searchResult, {
      emColeta: fontesAtivas,
      pontosReprovados,
      reasoningItems,
    });
  const temFontesColetadas = Array.isArray(itensFontes) && itensFontes.length > 0;

  const effectiveInitial = initialMode ?? modeProp;
  const [mode, setMode] = useState<RailMode>(() => {
    if (effectiveInitial) return effectiveInitial;
    const stored = readStoredMode();
    if (stored) return stored;
    return temFontesColetadas ? 'fontes' : 'contexto';
  });
  const userChangedModeRef = useRef(false);

  useEffect(() => {
    const targetMode = initialMode ?? modeProp;
    if (targetMode) {
      setMode(targetMode);
    }
  }, [initialMode, modeProp, collapsed]);

  useEffect(() => {
    if (userChangedModeRef.current) {
      try {
        localStorage.setItem(RAIL_MODE_KEY, mode);
      } catch {
        /* storage bloqueado */
      }
    }
  }, [mode]);

  useEffect(() => {
    if (userChangedModeRef.current) return;
    const stored = readStoredMode();
    if (stored) return;
    setMode(temFontesColetadas ? 'fontes' : 'contexto');
  }, [temFontesColetadas]);

  useEffect(
    () => () => {
      if (copiadoTimer.current) clearTimeout(copiadoTimer.current);
    },
    []
  );

  const statusNormalized = pipelineStatus || plan?.status_pipeline || 'aguardando';
  const statusLabel = plan ? getStatusLabel(statusNormalized) : 'Pronto para iniciar';
  const statusBadgeClass = getStatusBadgeClass(statusNormalized);

  const nPontos = typeof plan?.n_pontos === 'number' ? plan.n_pontos : null;
  const personas = Array.isArray(plan?.preferencias?.personas) ? plan!.preferencias!.personas! : [];
  const titulo = plan?.tema?.trim() ? plan.tema.trim() : 'Nova pesquisa';

  const resumoPartes: string[] = [];
  if (nPontos !== null) resumoPartes.push(`${nPontos} ${nPontos === 1 ? 'ponto' : 'pontos'}`);
  if (personas.length) resumoPartes.push(`${personas.length} personas`);
  const resumo = resumoPartes.join(' · ');

  const cicloTexto =
    typeof cycleNumber === 'number' ? `${cycleNumber}/${maxCycles ?? 4}` : '—';
  const coletadosTexto =
    typeof collectedPoints === 'number' && nPontos !== null ? `${collectedPoints}/${nPontos}` : '—';
  const auditoriaTexto = auditSummary
    ? `${auditSummary.aprovados}/${auditSummary.total}`
    : auditAoVivo
    ? 'Em auditoria'
    : 'Aguardando';

  const idPesquisa = plan?.id_pesquisa ? String(plan.id_pesquisa) : null;
  const idCurto = idPesquisa ? (idPesquisa.length > 8 ? idPesquisa.slice(0, 8) : idPesquisa) : '—';

  const plano = plan?.plano_estruturado ?? null;
  const escopoPartes: string[] = [];
  if (plano?.publico) escopoPartes.push(`Público: ${plano.publico}`);
  if (plano?.formato_entrega) escopoPartes.push(`Entrega: ${plano.formato_entrega}`);
  if (plano?.recorte_temporal) escopoPartes.push(`Recorte: ${plano.recorte_temporal}`);
  if (!escopoPartes.length && plan) {
    const recencia = plan.preferencias?.recencia;
    if (recencia) escopoPartes.push(`Recência: ${recencia}`);
    if (nPontos !== null) escopoPartes.push(`${nPontos} ${nPontos === 1 ? 'ponto' : 'pontos'}`);
  }
  const escopo = escopoPartes.length ? escopoPartes.join(' · ') : 'Escopo não informado';

  const copiarId = useCallback(async () => {
    if (!idPesquisa) return;
    try {
      await navigator.clipboard.writeText(idPesquisa);
      setCopiado(true);
      if (copiadoTimer.current) clearTimeout(copiadoTimer.current);
      copiadoTimer.current = setTimeout(() => setCopiado(false), 1600);
    } catch {
      setCopiado(false);
    }
  }, [idPesquisa]);

  const handleTabKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    const atual = MODES.indexOf(mode);
    let next: RailMode | null = null;
    if (event.key === 'ArrowRight') next = MODES[(atual + 1) % MODES.length];
    else if (event.key === 'ArrowLeft') next = MODES[(atual - 1 + MODES.length) % MODES.length];
    else if (event.key === 'Home') next = MODES[0];
    else if (event.key === 'End') next = MODES[MODES.length - 1];
    if (!next) return;
    event.preventDefault();
    userChangedModeRef.current = true;
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
        onClick={() => {
          userChangedModeRef.current = true;
          setMode(value);
        }}
      >
        <span>{rotulo}</span>
        {typeof count === 'number' && (
          <>
            <span className="rr-rail__tab-sep" aria-hidden="true">
              ·
            </span>
            <span className="rr-rail__tab-count">{count}</span>
          </>
        )}
      </button>
    );
  };

  if (collapsed) {
    return null;
  }

  return (
    <>
      <div
        className="rr-rail-backdrop"
        onClick={() => handleToggle(true)}
        aria-hidden="true"
      />
      <aside
        className="sidebar-container context-sidebar right-rail right-rail--sticky rr-rail"
        aria-label="Contexto da pesquisa"
      >
      <div className="rr-rail__panel" id={RAIL_PANEL_ID}>
        <header className="rr-rail__head">
          <h2 className="rr-rail__title" title={titulo}>
            {titulo}
          </h2>
          <button
            type="button"
            className="rr-rail__collapse"
            aria-expanded={true}
            aria-controls={RAIL_PANEL_ID}
            aria-label="Recolher painel de contexto"
            title="Recolher painel"
            onClick={() => handleToggle(true)}
          >
            <PanelRightClose size={16} aria-hidden="true" />
          </button>
        </header>

        <div
          className="rr-rail__tabs"
          role="tablist"
          aria-label="Modos do painel de contexto"
          onKeyDown={handleTabKeyDown}
        >
          {renderTab('contexto', 'Contexto')}
          {renderTab('fontes', 'Fontes', itensFontes.length)}
        </div>

        <TokenUsageMeter metadados={metadadosModelo ?? plan?.metadados_modelo ?? null} aoVivo={tokensAoVivo ?? null} />

        {/* Contrato E2E: `.context-sidebar .status-badge-container > .status-badge-chip`
            precisa existir e estar visível nos dois modos. */}
        <div className="status-badge-container rr-rail__status">
          <span className={`status-badge-chip ${statusBadgeClass} rr-status__badge`}>{statusLabel}</span>
          {resumo && (
            <span className="rr-rail__status-meta" title={resumo}>
              {resumo}
            </span>
          )}
        </div>

        <div className="rr-rail__body">
          <div
            role="tabpanel"
            id={PANEL_ID.contexto}
            aria-labelledby={TAB_ID.contexto}
            className="rr-rail__pane"
            hidden={mode !== 'contexto'}
          >
            <dl className="rr-facts">
              <div className="rr-facts__row">
                <dt>Estágio</dt>
                <dd>{statusLabel}</dd>
              </div>
              <div className="rr-facts__row">
                <dt>Ciclo</dt>
                <dd className="rr-facts__mono">{cicloTexto}</dd>
              </div>
              <div className="rr-facts__row">
                <dt>Pontos coletados</dt>
                <dd className="rr-facts__mono">{coletadosTexto}</dd>
              </div>
              <div className="rr-facts__row">
                <dt>Auditoria</dt>
                <dd className="rr-facts__mono">{auditoriaTexto}</dd>
              </div>
              <div className="rr-facts__row">
                <dt>ID</dt>
                <dd className="rr-facts__id">
                  <span className="rr-facts__mono" title={idPesquisa ?? undefined}>
                    {idCurto}
                  </span>
                  {idPesquisa && (
                    <button
                      type="button"
                      className={`rr-copy${copiado ? ' is-copied' : ''}`}
                      aria-label={copiado ? 'ID copiado' : 'Copiar ID da pesquisa'}
                      title={copiado ? 'Copiado' : 'Copiar ID completo'}
                      onClick={copiarId}
                      style={{ padding: '6px', minWidth: '28px', minHeight: '28px' }}
                    >
                      {copiado ? <Check size={13} aria-hidden="true" /> : <Copy size={13} aria-hidden="true" />}
                    </button>
                  )}
                </dd>
              </div>
              <div className="rr-facts__row rr-facts__row--stack">
                <dt>Escopo</dt>
                <dd className="rr-facts__scope">{escopo}</dd>
              </div>
            </dl>
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
      </div>
    </aside>
    </>
  );
};

export const ContextSidebar = React.memo(ContextSidebarBase);
