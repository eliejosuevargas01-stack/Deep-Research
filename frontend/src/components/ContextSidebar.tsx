import React, { useState } from 'react';
import { Clock, Target, Calendar, Hash, FileCheck, Layers, BookMarked, RefreshCw, ShieldCheck, Copy, Check } from 'lucide-react';
import { PlanResponse, ModeloMetadados, SearchResponse } from '../types/api';
import { TokenUsageMeter } from './TokenUsageMeter';
import { SourcesExplorer, derivarFontesParaExplorer, FonteExplorerItem } from './SourcesExplorer';

interface ContextSidebarProps {
  plan?: PlanResponse | null;
  pipelineStatus?: string | null;
  /** Ciclo atual do pipeline (1-based) e teto de ciclos. */
  cycleNumber?: number;
  maxCycles?: number;
  /** Pontos cuja coleta já terminou, para o resumo de progresso. */
  collectedPoints?: number;
  /** Resumo da última auditoria disponível. */
  auditSummary?: {
    aprovados: number;
    total: number;
    ciclo?: number | null;
    /** Corte mínimo exigido pelo backend para aprovar um ponto. */
    criteriosMinimos?: number | null;
  } | null;
  /** NOVO: telemetria real do plano (só leitura). */
  metadadosModelo?: ModeloMetadados | null;
  /** NOVO: itens já derivados (App deriva via helper) ou search bruto como fallback. */
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
      return 'Buscando evidências...';
    case 'auditing':
    case 'auditando':
      return 'Em auditoria...';
    case 'writing':
    case 'redigindo':
      return 'Redigindo dossiê...';
    case 'completed':
    case 'concluido':
      return 'Dossiê concluído';
    case 'rejected':
    case 'reprovado':
      return 'Reprovado na auditoria';
    case 'failed':
    case 'falha':
      return 'Falha na execução';
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
      <aside className="sidebar-container" aria-label="Informações contextuais">
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
            <Clock size={16} aria-hidden="true" color="var(--color-text-muted)" />
            <h2 className="card-title" style={{ fontSize: '0.95rem' }}>
              Status da pesquisa
            </h2>
          </div>
          <span className="status-badge-chip planejado">Pronto para iniciar</span>
          <p style={{ marginTop: '10px', fontSize: '0.82rem', color: 'var(--color-text-muted)' }}>
            Digite um tema no campo abaixo ou clique em uma das sugestões para elaborar o plano de investigação.
          </p>
        </div>
      </aside>
    );
  }

  const structured = plan.plano_estruturado;
  const statusNormalized = pipelineStatus || plan.status_pipeline || 'aguardando';

  return (
    <aside className="sidebar-container" aria-label="Informações contextuais da pesquisa">
      <TokenUsageMeter metadados={metadadosModelo ?? plan?.metadados_modelo ?? null} />

      {/* Card 1: Status da Pesquisa (Comp C Top Right) */}
      <div className="card">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
          <Clock size={16} aria-hidden="true" color="var(--color-text-muted)" />
          <h2 className="card-title" style={{ fontSize: '0.95rem' }}>
            Status da pesquisa
          </h2>
        </div>

        <span className={`status-badge-chip ${getStatusBadgeClass(statusNormalized)}`}>
          {getStatusLabel(statusNormalized)}
        </span>

        <div className="meta-divider" />

        <div className="meta-list">
          <div className="meta-item">
            <Hash className="meta-item-icon" aria-hidden="true" />
            <div className="meta-item-content">
              <span className="meta-item-label">
                {`${plan.n_pontos} ${plan.n_pontos === 1 ? 'ponto' : 'pontos'}${
                  Array.isArray(plan.preferencias?.personas) && plan.preferencias.personas.length
                    ? ` · ${plan.preferencias.personas.length} personas`
                    : ''
                }`}
              </span>
              <span className="meta-item-subtext">Plano de investigação</span>
            </div>
          </div>

          <div className="meta-item">
            <Calendar className="meta-item-icon" aria-hidden="true" />
            <div className="meta-item-content">
              <span className="meta-item-label">Criada em</span>
              <span className="meta-item-subtext">
                {plan.criado_em
                  ? new Date(plan.criado_em).toLocaleDateString('pt-BR', {
                      day: '2-digit',
                      month: 'short',
                      year: 'numeric',
                      hour: '2-digit',
                      minute: '2-digit',
                    })
                  : 'Recém criada'}
              </span>
            </div>
          </div>


          {typeof cycleNumber === 'number' && (
            <div className="meta-item">
              <RefreshCw className="meta-item-icon" aria-hidden="true" />
              <div className="meta-item-content">
                <span className="meta-item-label">
                  {`Ciclo ${cycleNumber}${maxCycles ? ` de ${maxCycles}` : ''}`}
                </span>
                <span className="meta-item-subtext">
                  {typeof collectedPoints === 'number'
                    ? `${collectedPoints} de ${plan.n_pontos} pontos coletados`
                    : 'Ciclo de busca e auditoria'}
                </span>
              </div>
            </div>
          )}

          <div className="meta-item">
            <Layers className="meta-item-icon" aria-hidden="true" />
            <div className="meta-item-content">
              <span className="meta-item-label">ID da pesquisa</span>
              <span className="meta-item-subtext" style={{ fontFamily: 'var(--font-mono)', display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                <span title={plan.id_pesquisa}>{plan.id_pesquisa.slice(0, 8)}...</span>
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
                  {copiouId ? <Check size={12} aria-hidden="true" /> : <Copy size={12} aria-hidden="true" />}
                </button>
              </span>
            </div>
          </div>
        </div>
      </div>

      <SourcesExplorer
        items={fontes ?? derivarFontesParaExplorer(searchResult, { emColeta: fontesAtivas, pontosReprovados })}
        isActive={Boolean(fontesAtivas)}
      />

      {auditSummary && (
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
            <FileCheck size={16} aria-hidden="true" color="var(--color-text-muted)" />
            <h2 className="card-title" style={{ fontSize: '0.95rem' }}>
              {auditSummary.ciclo ? `Auditoria do ciclo ${auditSummary.ciclo}` : 'Auditoria'}
            </h2>
          </div>
          <div className="meta-list">
            <div className="meta-item">
              <ShieldCheck className="meta-item-icon" aria-hidden="true" />
              <div className="meta-item-content">
                <span className="meta-item-label">
                  {`${auditSummary.aprovados} de ${auditSummary.total} ${
                    auditSummary.total === 1 ? 'ponto aprovado' : 'pontos aprovados'
                  }`}
                </span>
                <span className="meta-item-subtext">
                  {auditSummary.criteriosMinimos
                    ? `Corte mínimo de ${auditSummary.criteriosMinimos} de 12 critérios`
                    : 'Corte definido pela auditoria'}
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Card 2: Escopo da Investigação (Comp C Bottom Right) */}
      <div className="card">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
          <Target size={16} aria-hidden="true" color="var(--color-text-muted)" />
          <h2 className="card-title" style={{ fontSize: '0.95rem' }}>
            Escopo da pesquisa
          </h2>
        </div>

        <div className="meta-list">
          <div className="meta-item">
            <BookMarked className="meta-item-icon" aria-hidden="true" />
            <div className="meta-item-content">
              <span className="meta-item-label">Público-alvo</span>
              <span className="meta-item-subtext">
                {structured?.publico || 'Analistas e tomadores de decisão'}
              </span>
            </div>
          </div>

          <div className="meta-item">
            <Calendar className="meta-item-icon" aria-hidden="true" />
            <div className="meta-item-content">
              <span className="meta-item-label">Abrangência temporal</span>
              <span className="meta-item-subtext">
                {structured?.recorte_temporal || 'Contemporânea com contexto histórico'}
              </span>
            </div>
          </div>

          <div className="meta-item">
            <Target className="meta-item-icon" aria-hidden="true" />
            <div className="meta-item-content">
              <span className="meta-item-label">Entregável</span>
              <span className="meta-item-subtext">
                {structured?.formato_entrega || 'Dossiê analítico com fontes canônicas'}
              </span>
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
};

export const ContextSidebar = React.memo(ContextSidebarBase);

