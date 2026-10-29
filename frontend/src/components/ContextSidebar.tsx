import React, { useState } from 'react';
import { Clock, Target, Copy, Check } from 'lucide-react';
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
  metadadosModelo,
  fontes,
  searchResult,
  fontesAtivas,
  pontosReprovados,
}) => {
  const [copiouId, setCopiouId] = useState(false);
  if (!plan) {
    return (
      <aside className="sidebar-container right-rail right-rail--sticky" aria-label="Informações contextuais">
        <TokenUsageMeter metadados={metadadosModelo ?? null} />
        <div className="right-rail__section">
          <div className="right-rail__header">
            <Clock size={12} aria-hidden="true" className="right-rail__header-icon" />
            <span>Status</span>
          </div>
          <span className="rr-status__badge planejado">Pronto para iniciar</span>
          <p className="rr-sources__empty">Digite um tema para iniciar a investigação</p>
        </div>
        <SourcesExplorer items={[]} />
        <div className="right-rail__section">
          <div className="right-rail__header">
            <Target size={12} aria-hidden="true" className="right-rail__header-icon" />
            <span>Escopo</span>
          </div>
          <p className="rr-sources__empty">Sem escopo definido</p>
        </div>
      </aside>
    );
  }

  const structured = plan.plano_estruturado;
  const statusNormalized = pipelineStatus || plan.status_pipeline || 'aguardando';

  return (
    <aside className="sidebar-container context-sidebar right-rail right-rail--sticky" aria-label="Informações contextuais da pesquisa">
      <TokenUsageMeter metadados={metadadosModelo ?? plan?.metadados_modelo ?? null} />

      <div className="right-rail__section">
        <div className="right-rail__header">
          <Clock size={12} aria-hidden="true" className="right-rail__header-icon" />
          <span>Status</span>
        </div>
        {/* Contrato E2E: `.status-badge-container > .status-badge-chip` precisa
            continuar existindo (features/step_definitions/*.ts). */}
        <div className="status-badge-container">
          <span className={`status-badge-chip ${getStatusBadgeClass(statusNormalized)} rr-status__badge`}>
            {getStatusLabel(statusNormalized)}
          </span>
        </div>
        <div className="rr-status__meta">
          <div className="rr-status__meta-row">
            <span className="rr-status__meta-label">
              {`${plan.n_pontos} ${plan.n_pontos === 1 ? 'ponto' : 'pontos'}`}
            </span>
            <span className="rr-status__meta-value">
              {Array.isArray(plan.preferencias?.personas) && plan.preferencias.personas.length
                ? `${plan.preferencias.personas.length} personas`
                : '—'}
            </span>
          </div>
          {typeof cycleNumber === 'number' && (
            <div className="rr-status__meta-row">
              <span className="rr-status__meta-label">Ciclo</span>
              <span className="rr-status__meta-value">
                {`${cycleNumber}${maxCycles ? ` / ${maxCycles}` : ''}`}
              </span>
            </div>
          )}
          {typeof collectedPoints === 'number' && (
            <div className="rr-status__meta-row">
              <span className="rr-status__meta-label">Pontos coletados</span>
              <span className="rr-status__meta-value">{`${collectedPoints} / ${plan.n_pontos}`}</span>
            </div>
          )}
          <div className="rr-status__meta-row">
            <span className="rr-status__meta-label">ID</span>
            <span className="rr-status__meta-value mono" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
              <span title={plan.id_pesquisa}>{plan.id_pesquisa.slice(0, 8)}</span>
              <button
                type="button"
                className="icon-button"
                aria-label="Copiar ID completo da pesquisa"
                title={plan.id_pesquisa}
                onClick={() => {
                  void navigator.clipboard?.writeText(plan.id_pesquisa);
                  setCopiouId(true);
                  window.setTimeout(() => setCopiouId(false), 1500);
                }}
              >
                {copiouId ? <Check size={10} aria-hidden="true" /> : <Copy size={10} aria-hidden="true" />}
              </button>
            </span>
          </div>
        </div>
        {auditSummary && (
          <div className="rr-status__meta-row">
            <span className="rr-status__meta-label">Auditoria</span>
            <span className="rr-status__meta-value">{`${auditSummary.aprovados}/${auditSummary.total} aprovados`}</span>
          </div>
        )}
      </div>

      <SourcesExplorer
        items={fontes ?? derivarFontesParaExplorer(searchResult, { emColeta: fontesAtivas, pontosReprovados })}
      />

      <div className="right-rail__section">
        <div className="right-rail__header">
          <Target size={12} aria-hidden="true" className="right-rail__header-icon" />
          <span>Escopo</span>
        </div>
        <div className="rr-scope">
          <div className="rr-scope__row">
            <span className="rr-scope__label">Público</span>
            <span className="rr-scope__value">{structured?.publico || 'Analistas e tomadores de decisão'}</span>
          </div>
          <div className="rr-scope__row">
            <span className="rr-scope__label">Recorte temporal</span>
            <span className="rr-scope__value">{structured?.recorte_temporal || 'Contemporânea'}</span>
          </div>
          <div className="rr-scope__row">
            <span className="rr-scope__label">Entregável</span>
            <span className="rr-scope__value">{structured?.formato_entrega || 'Dossiê analítico com fontes'}</span>
          </div>
        </div>
      </div>
    </aside>
  );
};

export const ContextSidebar = React.memo(ContextSidebarBase);
