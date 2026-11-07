import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  Sparkles,
  Play,
  ChevronDown,
  ChevronUp,
  Layers,
  FileText,
  RotateCcw,
  SlidersHorizontal,
} from 'lucide-react';
import { PlanResponse } from '../types/api';
import '../styles/plan-settings-polish.css';
import { formatarTitulo } from '../utils/texto';

interface PlanViewProps {
  plan: PlanResponse;
  onStartExecution: () => void;
  onReset: () => void;
  onEditTheme?: (tema: string) => void;
  onEditParameters?: (tema: string) => void;
  onReplan?: (params: any) => void;
  isStarting: boolean;
}

export const PlanView: React.FC<PlanViewProps> = ({
  plan,
  onStartExecution,
  onReset,
  isStarting,
}) => {
  const [contextOpen, setContextOpen] = useState(false);
  const [confirmResetOpen, setConfirmResetOpen] = useState(false);

  const triggerButtonRef = useRef<HTMLButtonElement | null>(null);
  const cancelButtonRef = useRef<HTMLButtonElement | null>(null);
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const shouldRestoreFocusRef = useRef(false);
  const rafRef = useRef<number | null>(null);

  // Atalho global: Cmd/Ctrl+Enter inicia a pesquisa a partir da revisão do plano.
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
        event.preventDefault();
        if (!isStarting) onStartExecution();
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [isStarting, onStartExecution]);

  useEffect(() => {
    return () => {
      if (rafRef.current !== null && typeof cancelAnimationFrame === 'function') {
        cancelAnimationFrame(rafRef.current);
      }
    };
  }, []);

  const handleOpenConfirmReset = useCallback(() => {
    setConfirmResetOpen(true);
    shouldRestoreFocusRef.current = true;
  }, []);

  const handleCancelReset = useCallback(() => {
    setConfirmResetOpen(false);
  }, []);

  const handleConfirmReset = useCallback(() => {
    setConfirmResetOpen(false);
    onReset();
  }, [onReset]);

  useEffect(() => {
    if (!confirmResetOpen) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        handleCancelReset();
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [confirmResetOpen, handleCancelReset]);

  useEffect(() => {
    if (confirmResetOpen) {
      if (cancelButtonRef.current) {
        cancelButtonRef.current.focus();
      } else if (typeof window !== 'undefined' && typeof window.requestAnimationFrame === 'function') {
        if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
        rafRef.current = window.requestAnimationFrame(() => {
          rafRef.current = null;
          cancelButtonRef.current?.focus();
        });
      }
    } else if (shouldRestoreFocusRef.current) {
      shouldRestoreFocusRef.current = false;
      if (triggerButtonRef.current) {
        triggerButtonRef.current.focus();
      } else if (typeof window !== 'undefined' && typeof window.requestAnimationFrame === 'function') {
        if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
        rafRef.current = window.requestAnimationFrame(() => {
          rafRef.current = null;
          triggerButtonRef.current?.focus();
        });
      }
    }
  }, [confirmResetOpen, handleCancelReset]);

  // Revisão compacta: eixos analíticos recolhidos por padrão para visualização imediata
  const [expandedPoints, setExpandedPoints] = useState<Record<string, boolean>>({});

  const allExpanded =
    plan.pontos.length > 0 && plan.pontos.every((p) => Boolean(expandedPoints[p.ponto_id]));

  const toggleAll = () => {
    const nextState = !allExpanded;
    const updated: Record<string, boolean> = {};
    plan.pontos.forEach((p) => {
      updated[p.ponto_id] = nextState;
    });
    setExpandedPoints(updated);
  };

  const togglePoint = (id: string) => {
    setExpandedPoints((prev) => ({
      ...prev,
      [id]: !prev[id],
    }));
  };

  const structured = plan.plano_estruturado;
  const activePersonas = plan.preferencias?.personas;
  const hasPersonasSnapshot = Array.isArray(activePersonas);
  const activePersonasCount = hasPersonasSnapshot ? activePersonas.length : null;
  const personaNames = hasPersonasSnapshot && activePersonas.length > 0
    ? activePersonas.map((p) => p.charAt(0).toUpperCase() + p.slice(1)).join(', ')
    : null;
  const activePointsCount = plan.preferencias?.n_pontos ?? plan.n_pontos ?? plan.pontos.length;

  return (
    <div className="plan-container" id="plan-workspace">
      {/* Banner de Consulta Ativa com Ação Primária Consolidada */}
      <section className="query-banner" aria-label="Tema em planejamento">
        <div className="query-banner-left">
          <div className="query-icon-badge" aria-hidden="true">
            <FileText size={18} />
          </div>
          <div className="query-text-group">
            <span className="query-label">Tema da investigação</span>
            <span className="query-title" title={plan.tema}>
              {formatarTitulo(plan.tema)}
            </span>
          </div>
        </div>

        <div className="query-banner-actions plan-header-primary-action plan-actions-row">
          {/* Botão Primário Definitivo de Início */}
          <button
            type="button"
            className="gdr-plan-action gdr-plan-action--primary btn-start-research"
            id="start-research-btn"
            data-gdr-action="approve-and-start"
            onClick={onStartExecution}
            disabled={isStarting}
            aria-busy={isStarting}
            title="Iniciar execução dos eixos de investigação planejados"
            aria-label="Iniciar pesquisa"
          >
            {isStarting ? (
              <>
                <span className="spinner" aria-hidden="true" />
                <span>Iniciando…</span>
              </>
            ) : (
              <>
                <Play size={15} fill="currentColor" aria-hidden="true" />
                <span>Iniciar pesquisa</span>
              </>
            )}
          </button>

          {confirmResetOpen ? (
            <div
              ref={dialogRef}
              className="query-confirm-reset"
              role="alertdialog"
              aria-labelledby="confirm-reset-title"
            >
              <span id="confirm-reset-title" className="confirm-reset-text">
                Descartar plano formulado?
              </span>
              <div className="confirm-reset-buttons">
                <button
                  type="button"
                  className="query-action-btn danger"
                  onClick={handleConfirmReset}
                  disabled={isStarting}
                  title="Confirmar o descarte deste plano de pesquisa"
                >
                  <span>Descartar plano</span>
                </button>
                <button
                  ref={cancelButtonRef}
                  type="button"
                  autoFocus
                  className="query-action-btn"
                  onClick={handleCancelReset}
                  disabled={isStarting}
                  title="Cancelar e manter o plano atual"
                >
                  <span>Cancelar</span>
                </button>
              </div>
            </div>
          ) : (
            <button
              ref={triggerButtonRef}
              type="button"
              className="query-action-btn"
              onClick={handleOpenConfirmReset}
              disabled={isStarting}
              title="Descartar este plano e formular um novo tema"
            >
              <RotateCcw size={14} aria-hidden="true" />
              <span>Novo tema</span>
            </button>
          )}
        </div>
      </section>

      {/* Cartão Principal do Plano com Foco Direto nos Eixos */}
      <article className="plan-card" aria-labelledby="plan-heading">
        <header className="plan-header plan-header--compact">
          <div className="plan-header-main-row">
            <div className="plan-badge-row">
              <div className="plan-ai-icon" aria-hidden="true">
                <Sparkles size={16} />
              </div>
              <h2 id="plan-heading" className="plan-subheading">
                Eixos investigativos formulados
              </h2>

              {/* Chips de Metadados Essenciais */}
              <div className="plan-snapshot-chips" aria-label="Resumo do plano">
                <span className="pill pill-violet" title="Número de eixos formulados">
                  {`${activePointsCount} ${activePointsCount === 1 ? 'ponto analítico' : 'pontos analíticos'}`}
                </span>
                {activePersonasCount !== null && (
                  <span
                    className="pill pill-indigo"
                    title={personaNames ? `Personas ativas: ${personaNames}` : 'Personas analíticas ativas'}
                  >
                    {`${activePersonasCount} ${activePersonasCount === 1 ? 'persona ativa' : 'personas ativas'}`}
                  </span>
                )}
              </div>
            </div>

            <div className="plan-toggle-row">
              <button
                type="button"
                className="btn-toggle-all-details"
                onClick={toggleAll}
                aria-label={allExpanded ? 'Recolher detalhes de todos os pontos' : 'Expandir detalhes de todos os pontos'}
              >
                <SlidersHorizontal size={13} aria-hidden="true" />
                <span>{allExpanded ? 'Recolher detalhes' : 'Expandir todos os detalhes'}</span>
              </button>
            </div>
          </div>
        </header>

        {/* Stepper Vertical dos Eixos com Apresentação Limpa e Imediata */}
        <section className="plan-stepper" aria-label="Eixos do plano">
          {plan.pontos.map((ponto, idx) => {
            const eixo = ponto.eixo_estruturado;
            const pontoNum = ponto.ponto_n ?? (ponto as any).n ?? (idx + 1);
            const pontoId = ponto.ponto_id ?? (ponto as any).id ?? `ponto-${pontoNum}`;
            const isExpanded = Boolean(expandedPoints[pontoId]);
            const pontoTitle =
              eixo?.pergunta_principal ||
              (eixo as any)?.pergunta_investigativa ||
              ponto.ponto ||
              (ponto as any)?.foco ||
              `Eixo investigativo ${pontoNum}`;
            const subperguntas = eixo?.subperguntas || (eixo as any)?.perguntas || [];
            const hipoteses = eixo?.hipoteses || [];
            const fontes = eixo?.fontes_primarias_desejadas || (eixo as any)?.fontes_prioritarias || [];
            const criterio = eixo?.criterio_de_conclusao;

            return (
              <div key={pontoId} className={`stepper-item ${isExpanded ? 'is-expanded' : 'is-collapsed'}`}>
                <div
                  className={`stepper-badge ${ponto.status || 'planejado'}`}
                  aria-label={`Ponto ${pontoNum}`}
                >
                  {pontoNum}
                </div>

                <div className="stepper-content">
                  <div className="stepper-header-row">
                    <h3 className="stepper-point-title">
                      {pontoTitle}
                    </h3>

                    {eixo && (
                      <button
                        type="button"
                        className="stepper-point-toggle"
                        onClick={() => togglePoint(pontoId)}
                        aria-expanded={isExpanded}
                        aria-controls={`point-details-${pontoId}`}
                        aria-label={`Alternar detalhes do ponto ${pontoNum}`}
                        title={isExpanded ? 'Recolher detalhes deste ponto' : 'Expandir hipóteses e subperguntas'}
                      >
                        <span className="toggle-text">{isExpanded ? 'Menos detalhes' : 'Mais detalhes'}</span>
                        {isExpanded ? <ChevronUp size={14} aria-hidden="true" /> : <ChevronDown size={14} aria-hidden="true" />}
                      </button>
                    )}
                  </div>

                  {eixo && isExpanded && (
                    <div className="stepper-point-details" id={`point-details-${pontoId}`} role="region" aria-label={`Detalhes do ponto ${pontoNum}`}>
                      {subperguntas.length > 0 && (
                        <div className="point-detail-row">
                          <span className="point-detail-label">Subperguntas:</span>
                          <ul className="point-detail-list">
                            {subperguntas.map((sub: string, sIdx: number) => (
                              <li key={sIdx} className="point-detail-value">
                                {sub}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {hipoteses.length > 0 && (
                        <div className="point-detail-row">
                          <span className="point-detail-label">Hipóteses:</span>
                          <span className="point-detail-value">{hipoteses.join(' • ')}</span>
                        </div>
                      )}

                      {fontes.length > 0 && (
                        <div className="point-detail-row">
                          <span className="point-detail-label">Fontes prioritárias:</span>
                          <div className="point-tags-row">
                            {fontes.map((src: string, srcIdx: number) => (
                              <span key={srcIdx} className="point-tag">
                                {src}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                      {criterio && (
                        <div className="point-detail-row">
                          <span className="point-detail-label">Critério de conclusão:</span>
                          <span className="point-detail-value">{criterio}</span>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </section>

        {/* Painel Colapsável de Parâmetros e Contexto Geral */}
        {structured && (
          <section className="context-panel" aria-label="Contexto da pesquisa">
            <button
              type="button"
              className="context-panel-header"
              onClick={() => setContextOpen(!contextOpen)}
              aria-expanded={contextOpen}
              aria-label="Contexto e parâmetros da pesquisa"
            >
              <div className="context-panel-header-left">
                <Layers size={16} aria-hidden="true" />
                <span>Contexto e parâmetros da pesquisa</span>
              </div>
              {contextOpen ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            </button>

            {contextOpen && (
              <div className="context-panel-body">
                <span className="context-key">Público-alvo:</span>
                <span className="context-val">{structured.publico || 'Geral / Analítico'}</span>

                <span className="context-key">Entregável:</span>
                <span className="context-val">{structured.formato_entrega || 'Dossiê analítico'}</span>

                {structured.recorte_temporal && (
                  <>
                    <span className="context-key">Recorte temporal:</span>
                    <span className="context-val">{structured.recorte_temporal}</span>
                  </>
                )}

                {structured.pressupostos && structured.pressupostos.length > 0 && (
                  <>
                    <span className="context-key">Pressupostos:</span>
                    <span className="context-val">{structured.pressupostos.join('; ')}</span>
                  </>
                )}

                {structured.ambiguidades && structured.ambiguidades.length > 0 && (
                  <>
                    <span className="context-key">Ambiguidades:</span>
                    <span className="context-val">{structured.ambiguidades.join('; ')}</span>
                  </>
                )}
              </div>
            )}
          </section>
        )}
      </article>
    </div>
  );
};
