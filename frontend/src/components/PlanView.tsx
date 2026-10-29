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
import './plan-settings-polish.css';
import { formatarTitulo } from '../utils/texto';

interface PlanViewProps {
  plan: PlanResponse;
  onStartExecution: () => void;
  onReset: () => void;
  onEditTheme?: (tema: string) => void;
  onEditParameters?: (tema: string) => void;
  isStarting: boolean;
}

export const PlanView: React.FC<PlanViewProps> = ({
  plan,
  onStartExecution,
  onReset,
  onEditTheme,
  onEditParameters,
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
        rafRef.current = null;
      }
    };
  }, []);

  const handleOpenConfirmReset = () => {
    shouldRestoreFocusRef.current = true;
    setConfirmResetOpen(true);
  };

  const handleCancelReset = useCallback(() => {
    shouldRestoreFocusRef.current = true;
    setConfirmResetOpen(false);
  }, []);

  const handleConfirmReset = () => {
    shouldRestoreFocusRef.current = false;
    setConfirmResetOpen(false);
    onReset();
  };

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

      const handleClickOutside = (event: MouseEvent) => {
        const dialog = dialogRef.current;
        if (dialog && !dialog.contains(event.target as Node)) {
          shouldRestoreFocusRef.current = false;
          setConfirmResetOpen(false);
        }
      };

      const handleKeyDown = (event: KeyboardEvent) => {
        if (event.key === 'Escape') {
          event.preventDefault();
          event.stopPropagation();
          handleCancelReset();
          return;
        }

        if (event.key === 'Tab') {
          const dialog = dialogRef.current;
          if (!dialog) return;

          const focusable = Array.from(
            dialog.querySelectorAll<HTMLElement>(
              'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
            )
          );

          if (focusable.length === 0) return;

          const first = focusable[0];
          const last = focusable[focusable.length - 1];

          if (event.shiftKey) {
            if (document.activeElement === first || !dialog.contains(document.activeElement)) {
              event.preventDefault();
              last.focus();
            }
          } else {
            if (document.activeElement === last || !dialog.contains(document.activeElement)) {
              event.preventDefault();
              first.focus();
            }
          }
        }
      };

      document.addEventListener('keydown', handleKeyDown);
      document.addEventListener('mousedown', handleClickOutside);
      return () => {
        if (rafRef.current !== null && typeof cancelAnimationFrame === 'function') {
          cancelAnimationFrame(rafRef.current);
          rafRef.current = null;
        }
        document.removeEventListener('keydown', handleKeyDown);
        document.removeEventListener('mousedown', handleClickOutside);
      };
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

  // Revisão compacta inicial para qualquer contagem de pontos (inclusive N=1 e N=2 longos):
  // todos iniciam recolhidos para que a visão geral e a única ação Iniciar Pesquisa
  // estejam imediatamente visíveis no viewport (incluindo 1280x720 e mobile).
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

  // Faixa numerada de fases exibida no cartão de pré-voo, antes de iniciar a busca.
  const fases = [
    { num: '01', nome: 'Mapeamento', meta: `${plan.n_pontos} ${plan.n_pontos === 1 ? 'eixo' : 'eixos'}` },
    { num: '02', nome: 'Busca', meta: activePersonasCount !== null ? `${activePersonasCount} personas` : 'Personas' },
    { num: '03', nome: 'Auditoria', meta: '12 critérios' },
    { num: '04', nome: 'Dossiê', meta: structured?.formato_entrega?.split(' ').slice(0, 2).join(' ') || 'Analítico' },
  ];

  const handleEditParameters = () => {
    if (onEditParameters) {
      onEditParameters(plan.tema);
      return;
    }
    if (onEditTheme) onEditTheme(plan.tema);
  };

  return (
    <div className="plan-container" id="plan-workspace">
      {/* Banner de Consulta Ativa (Comp C Top Left) */}
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

        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center' }}>
          {onEditTheme && (
            <button
              type="button"
              className="query-action-btn"
              onClick={() => onEditTheme(plan.tema)}
              disabled={isStarting}
              title="Editar o texto deste tema no compositor"
            >
              <span>Editar tema</span>
            </button>
          )}
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

      {/* Cartão Principal do Plano (Comp C Main Canvas) */}
      <article className="plan-card" aria-labelledby="plan-heading">
        <header className="plan-header plan-header--compact">
          <div className="plan-header-main-row">
            <div className="plan-header-text">
              <div className="plan-badge-row">
                <div className="plan-ai-icon" aria-hidden="true">
                  <Sparkles size={16} />
                </div>
                <span className="plan-eyebrow">Plano estruturado</span>

                {/* Chips de Snapshot de Preferências */}
                <div className="plan-snapshot-chips" aria-label="Preferências gravadas para este plano">
                  <span className="pill pill-violet" title="Número de pontos formulados">
                    {activePointsCount} {activePointsCount === 1 ? 'ponto analítico' : 'pontos analíticos'}
                  </span>
                  <span
                    className="pill pill-indigo"
                    title={
                      personaNames
                        ? `Personas configuradas: ${personaNames}`
                        : activePersonasCount !== null
                        ? 'Personas de busca configuradas'
                        : 'Personas analíticas de busca'
                    }
                  >
                    {activePersonasCount !== null
                      ? `${activePersonasCount} ${activePersonasCount === 1 ? 'persona ativa' : 'personas ativas'}`
                      : 'Personas analíticas'}
                  </span>
                </div>
              </div>

              <h2 id="plan-heading" className="plan-main-title">
                Plano pronto para revisão
              </h2>

              <p className="plan-description">
                O planejador formulou {plan.n_pontos} {plan.n_pontos === 1 ? 'eixo investigativo estruturado' : 'eixos investigativos estruturados'} para o tema,
                com hipóteses falseáveis, consultas direcionadas e critérios claros de conclusão antes da busca web.
              </p>
            </div>

            {/* Ação Primária Única de Continuidade: Iniciar Pesquisa (no cabeçalho compacto, imediatamente visível acima da dobra) */}
            <div className="plan-actions plan-header-primary-action">
              <button
                type="button"
                className="btn-start-research"
                onClick={onStartExecution}
                disabled={isStarting}
                id="start-research-btn"
                aria-label="Iniciar pesquisa síncrona dos eixos formulados"
              >
                {isStarting ? (
                  <>
                    <span className="spinner" aria-hidden="true" />
                    <span>Iniciando pesquisa síncrona...</span>
                  </>
                ) : (
                  <>
                    <Play size={16} fill="currentColor" aria-hidden="true" />
                    <span>Iniciar pesquisa</span>
                  </>
                )}
              </button>
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
        </header>

      {/* Cartão de pré-voo: faixa de fases + ações primárias antes da busca */}
      <section className="gdr-plan-preflight" aria-label="Pré-voo da investigação">
        <p className="gdr-plan-preflight-summary">
          {plan.n_pontos} {plan.n_pontos === 1 ? 'eixo investigativo' : 'eixos investigativos'} prontos para revisão.
        </p>
        <ol className="gdr-phases" aria-label="Fases da investigação">
          {fases.map((f) => (
            <li key={f.num} className="gdr-phase">
              <span className="gdr-phase-num">{f.num}</span>
              <span className="gdr-phase-name">{f.nome}</span>
              <span className="gdr-phase-meta" title={f.meta}>{f.meta}</span>
            </li>
          ))}
        </ol>

        <div
          className="gdr-plan-actions"
        >
          <button
            type="button"
            className="gdr-plan-action gdr-plan-action--outline"
            data-gdr-action="edit-parameters"
            onClick={handleEditParameters}
            disabled={isStarting}
            title="Revisar tema, personas e pontos antes de iniciar"
            aria-label="Editar parâmetros do plano"
          >
            <SlidersHorizontal size={14} aria-hidden="true" />
            <span>Editar parâmetros</span>
          </button>
          <button
            type="button"
            className="gdr-plan-action gdr-plan-action--primary"
            data-gdr-action="approve-and-start"
            onClick={onStartExecution}
            disabled={isStarting}
            title="Aprovar o plano e iniciar a pesquisa"
            aria-label="Aprovar plano e iniciar pesquisa"
          >
            <Play size={16} aria-hidden="true" />
            <span>Aprovar e iniciar</span>
          </button>
        </div>
      </section>

        {/* Stepper Vertical dos Pontos (1..N) com Divulgação Progressiva */}
        <section className="plan-stepper" aria-label="Eixos investigativos do plano">
          {plan.pontos.map((ponto) => {
            const eixo = ponto.eixo_estruturado;
            const isExpanded = Boolean(expandedPoints[ponto.ponto_id]);

            return (
              <div key={ponto.ponto_id} className={`stepper-item ${isExpanded ? 'is-expanded' : 'is-collapsed'}`}>
                <div
                  className={`stepper-badge ${ponto.status}`}
                  aria-label={`Ponto ${ponto.ponto_n}`}
                >
                  {ponto.ponto_n}
                </div>

                <div className="stepper-content">
                  <div className="stepper-header-row">
                    <h3 className="stepper-point-title">
                      {eixo ? eixo.pergunta_principal : ponto.ponto}
                    </h3>

                    {eixo && (
                      <button
                        type="button"
                        className="stepper-point-toggle"
                        onClick={() => togglePoint(ponto.ponto_id)}
                        aria-expanded={isExpanded}
                        aria-label={`Alternar detalhes do ponto ${ponto.ponto_n}`}
                        title={isExpanded ? 'Recolher detalhes deste ponto' : 'Expandir hipóteses e subperguntas'}
                      >
                        <span className="toggle-text">{isExpanded ? 'Menos detalhes' : 'Mais detalhes'}</span>
                        {isExpanded ? <ChevronUp size={14} aria-hidden="true" /> : <ChevronDown size={14} aria-hidden="true" />}
                      </button>
                    )}
                  </div>

                  {eixo && isExpanded && (
                    <div className="stepper-point-details">
                      {eixo.subperguntas && eixo.subperguntas.length > 0 && (
                        <div className="point-detail-row">
                          <span className="point-detail-label">Subperguntas analíticas:</span>
                          <ul className="point-detail-list">
                            {eixo.subperguntas.map((sub, sIdx) => (
                              <li key={sIdx} className="point-detail-value">
                                {sub}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {eixo.hipoteses && eixo.hipoteses.length > 0 && (
                        <div className="point-detail-row">
                          <span className="point-detail-label">Hipóteses a verificar:</span>
                          <span className="point-detail-value">{eixo.hipoteses.join(' • ')}</span>
                        </div>
                      )}

                      {eixo.fontes_primarias_desejadas && eixo.fontes_primarias_desejadas.length > 0 && (
                        <div className="point-detail-row">
                          <span className="point-detail-label">Fontes canônicas prioritárias:</span>
                          <div className="point-tags-row">
                            {eixo.fontes_primarias_desejadas.map((src, srcIdx) => (
                              <span key={srcIdx} className="point-tag">
                                {src}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                      {eixo.criterio_de_conclusao && (
                        <div className="point-detail-row">
                          <span className="point-detail-label">Critério de conclusão:</span>
                          <span className="point-detail-value">{eixo.criterio_de_conclusao}</span>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </section>

        {/* Painel Colapsável de Contexto da Pesquisa (Comp C Accordion) */}
        {structured && (
          <section className="context-panel" aria-label="Contexto metodológico da pesquisa">
            <button
              type="button"
              className="context-panel-header"
              onClick={() => setContextOpen(!contextOpen)}
              aria-expanded={contextOpen}
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
