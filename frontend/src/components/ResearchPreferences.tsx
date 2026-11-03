import React, { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { X, Minus, Plus } from 'lucide-react';
import type { RecenciaPolitica } from '../types/api';
import { RIGOR_MAXIMO, RIGOR_MINIMO, RIGOR_PADRAO, normalizarRigor } from '../services/api';

export const ALL_PERSONAS = [
  { id: 'historiador', label: 'Historiador', desc: 'Antecedentes, precedentes e séries históricas' },
  { id: 'visionario', label: 'Visionário', desc: 'Novidades e tendências recentes' },
  { id: 'cetico', label: 'Cético', desc: 'Riscos, contra-evidências e pontos fracos' },
  { id: 'futurista', label: 'Futurista', desc: 'Cenários futuros e efeitos em cadeia' },
] as const;

export const RECENCIA_OPCOES: Array<{ id: RecenciaPolitica; label: string; desc: string }> = [
  { id: 'auto', label: 'Auto', desc: 'O que há de mais recente, sem recorte histórico' },
  { id: 'recente', label: 'Recente', desc: 'Só o que está no ar hoje' },
  { id: '24h', label: '24h', desc: 'Últimas 24 horas' },
  { id: '7d', label: '7d', desc: 'Últimos 7 dias' },
  { id: '30d', label: '30d', desc: 'Últimos 30 dias' },
  { id: '12m', label: '12m', desc: 'Últimos 12 meses' },
  { id: 'historico', label: 'Histórico', desc: 'Mantém o período que você pediu' },
];

export interface ResearchPreferencesProps {
  isOpen: boolean;
  onToggle: () => void;
  onClose: () => void;
  nPontos: number;
  onChangeNPontos: (n: number) => void;
  selectedPersonas: string[];
  onChangePersonas: (personas: string[]) => void;
  disabled?: boolean;
  currentPlanActive?: boolean;
  executionMode?: 'parallel' | 'sequential';
  onChangeExecutionMode?: (mode: 'parallel' | 'sequential') => void;
  recencia?: RecenciaPolitica;
  onChangeRecencia?: (recencia: RecenciaPolitica) => void;
  criteriosMinimos?: number;
  onChangeCriteriosMinimos?: (n: number) => void;
  asyncExecute?: boolean;
  onChangeAsyncExecute?: (async: boolean) => void;
  callbackUrl?: string;
  onChangeCallbackUrl?: (url: string) => void;
}

interface PreferencesPopoverContentProps {
  onClose: () => void;
  triggerElement: HTMLElement | null;
  nPontos: number;
  onChangeNPontos: (n: number) => void;
  selectedPersonas: string[];
  onChangePersonas: (personas: string[]) => void;
  disabled?: boolean;
  currentPlanActive?: boolean;
  executionMode?: 'parallel' | 'sequential';
  onChangeExecutionMode?: (mode: 'parallel' | 'sequential') => void;
  recencia?: RecenciaPolitica;
  onChangeRecencia?: (recencia: RecenciaPolitica) => void;
  criteriosMinimos?: number;
  onChangeCriteriosMinimos?: (n: number) => void;
  asyncExecute?: boolean;
  onChangeAsyncExecute?: (async: boolean) => void;
  callbackUrl?: string;
  onChangeCallbackUrl?: (url: string) => void;
}

const PreferencesPopoverContent: React.FC<PreferencesPopoverContentProps> = ({
  onClose,
  triggerElement,
  selectedPersonas,
  onChangePersonas,
  disabled = false,
  currentPlanActive = false,
  executionMode = 'parallel',
  onChangeExecutionMode = () => {},
  recencia = 'auto',
  onChangeRecencia = () => {},
  criteriosMinimos = RIGOR_PADRAO,
  onChangeCriteriosMinimos = () => {},
  asyncExecute = false,
  onChangeAsyncExecute = () => {},
  callbackUrl = '',
  onChangeCallbackUrl = () => {},
}) => {
  const panelRef = useRef<HTMLDivElement>(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  // Bounded panel positioning no desktop: garante que o painel e o cabeçalho nunca ultrapassem o topo do viewport
  useEffect(() => {
    const isMobile = typeof window !== 'undefined' && window.innerWidth <= 640;
    if (isMobile) return;

    const updateBounds = () => {
      if (!panelRef.current || !triggerElement) return;
      const triggerRect = triggerElement.getBoundingClientRect();
      const margin = 12;
      const maxAvailable = Math.max(160, triggerRect.top - margin - 10);
      panelRef.current.style.maxHeight = `${maxAvailable}px`;
    };
    updateBounds();
    window.addEventListener('resize', updateBounds);
    window.addEventListener('scroll', updateBounds, true);
    return () => {
      window.removeEventListener('resize', updateBounds);
      window.removeEventListener('scroll', updateBounds, true);
    };
  }, [triggerElement]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        onCloseRef.current();
        triggerElement?.focus();
      }
    };

    const handleClickOutside = (e: MouseEvent) => {
      if (
        panelRef.current &&
        !panelRef.current.contains(e.target as Node) &&
        triggerElement &&
        !triggerElement.contains(e.target as Node)
      ) {
        onCloseRef.current();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    document.addEventListener('mousedown', handleClickOutside);

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [triggerElement]);

  const togglePersona = (id: string) => {
    if (disabled || currentPlanActive) return;
    if (selectedPersonas.includes(id)) {
      if (selectedPersonas.length <= 1) return; // nunca deixa zero personas
      onChangePersonas(selectedPersonas.filter((p) => p !== id));
    } else {
      onChangePersonas([...selectedPersonas, id]);
    }
  };

  const rigorAtual = normalizarRigor(criteriosMinimos);

  return (
    <div
      ref={panelRef}
      id="preferences-popover-panel"
      className="preferences-panel"
      role="dialog"
      aria-label="Parâmetros de pesquisa"
    >
      <header className="dock-panel-head">
        <h2>Parâmetros da Pesquisa</h2>
        <button
          type="button"
          className="dock-close"
          onClick={onClose}
          aria-label="Fechar parâmetros"
        >
          <X size={14} aria-hidden="true" />
        </button>
      </header>

      <div className="dock-fields">
        {/* Campo 1: o perfil Hermes pesquisa o tema inteiro em um único ponto */}
        <div className="dock-field">
          <span className="dock-label">Pontos analíticos</span>
          <span className="dock-value" aria-label="Pontos analíticos">1 · tema único</span>
        </div>

        {/* Campo 2: Personas na busca */}
        <div className="dock-field" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: '8px' }}>
          <span className="dock-label">Personas na busca</span>
          <div className="dock-chips" style={{ width: '100%', justifyContent: 'flex-start' }} role="group" aria-label="Personas na busca">
            {ALL_PERSONAS.map(({ id, label }) => {
              const on = selectedPersonas.includes(id);
              return (
                <button
                  key={id}
                  type="button"
                  className={`dock-chip ${on ? 'is-on' : ''}`}
                  aria-pressed={on}
                  onClick={() => togglePersona(id)}
                  disabled={disabled || currentPlanActive}
                >
                  {label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Campo 3: Execução */}
        <div className="dock-field">
          <span className="dock-label">Execução da busca</span>
          <div className="dock-segment" role="group" aria-label="Modo de execução">
            <button
              type="button"
              className={executionMode === 'parallel' ? 'is-on' : ''}
              aria-pressed={executionMode === 'parallel'}
              onClick={() => !disabled && !currentPlanActive && onChangeExecutionMode('parallel')}
              disabled={disabled || currentPlanActive}
            >
              Paralelo
            </button>
            <button
              type="button"
              className={executionMode === 'sequential' ? 'is-on' : ''}
              aria-pressed={executionMode === 'sequential'}
              onClick={() => !disabled && !currentPlanActive && onChangeExecutionMode('sequential')}
              disabled={disabled || currentPlanActive}
            >
              Sequencial
            </button>
          </div>
        </div>

        {/* Campo 4: Recência da pesquisa */}
        <div className="dock-field" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: '8px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%', alignItems: 'center' }}>
            <span className="dock-label">Recência da pesquisa</span>
            <span style={{ fontSize: '0.74rem', color: 'var(--color-text-muted)' }}>
              {RECENCIA_OPCOES.find((o) => o.id === recencia)?.desc ?? 'Período aceito'}
            </span>
          </div>
          <div className="dock-chips" style={{ width: '100%', justifyContent: 'flex-start' }} role="group" aria-label="Recência da pesquisa">
            {RECENCIA_OPCOES.map((opcao) => {
              const on = recencia === opcao.id;
              return (
                <button
                  key={opcao.id}
                  type="button"
                  className={`dock-chip ${on ? 'is-on' : ''}`}
                  aria-pressed={on}
                  onClick={() => onChangeRecencia(opcao.id)}
                  disabled={disabled || currentPlanActive}
                  title={opcao.desc}
                >
                  {opcao.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Campo 5: Rigor da auditoria */}
        <div className="dock-field">
          <span className="dock-label">Rigor da auditoria</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <div className="dock-stepper" role="group" aria-label="Rigor da auditoria">
              <button
                type="button"
                onClick={() => onChangeCriteriosMinimos(Math.max(RIGOR_MINIMO, rigorAtual - 1))}
                disabled={disabled || currentPlanActive || rigorAtual <= RIGOR_MINIMO}
                aria-label="Diminuir rigor"
              >
                <Minus size={13} aria-hidden="true" />
              </button>
              <output aria-live="polite">{rigorAtual}</output>
              <button
                type="button"
                onClick={() => onChangeCriteriosMinimos(Math.min(RIGOR_MAXIMO, rigorAtual + 1))}
                disabled={disabled || currentPlanActive || rigorAtual >= RIGOR_MAXIMO}
                aria-label="Aumentar rigor"
              >
                <Plus size={13} aria-hidden="true" />
              </button>
            </div>
            <span style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)' }}>/ 12 critérios</span>
          </div>
        </div>

        {/* Campo 6: Modo de entrega */}
        <div className="dock-field" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: '8px' }}>
          <span className="dock-label">Entrega do dossiê</span>
          <div className="dock-segment" style={{ width: '100%', display: 'flex' }} role="group" aria-label="Modo de entrega">
            <button
              type="button"
              style={{ flex: 1 }}
              className={!asyncExecute ? 'is-on' : ''}
              aria-pressed={!asyncExecute}
              onClick={() => onChangeAsyncExecute(false)}
              disabled={disabled || currentPlanActive}
            >
              Stream (Sync)
            </button>
            <button
              type="button"
              style={{ flex: 1 }}
              className={asyncExecute ? 'is-on' : ''}
              aria-pressed={asyncExecute}
              onClick={() => onChangeAsyncExecute(true)}
              disabled={disabled || currentPlanActive}
            >
              Webhook (Async)
            </button>
          </div>
          {asyncExecute && (
            <div style={{ width: '100%', marginTop: '4px' }}>
              <input
                type="url"
                className="points-custom-input"
                style={{ width: '100%', boxSizing: 'border-box', height: '34px', padding: '0 10px', fontSize: '0.82rem' }}
                value={callbackUrl}
                onChange={(e) => onChangeCallbackUrl(e.target.value)}
                placeholder="https://api.exemplo.com/webhook/pesquisa"
                disabled={disabled || currentPlanActive}
                aria-label="URL de callback do webhook"
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export const ResearchPreferences: React.FC<ResearchPreferencesProps> = ({
  isOpen,
  onToggle,
  onClose,
  nPontos,
  onChangeNPontos,
  selectedPersonas,
  onChangePersonas,
  disabled = false,
  currentPlanActive = false,
  executionMode = 'parallel',
  onChangeExecutionMode = () => {},
  recencia = 'auto',
  onChangeRecencia = () => {},
  criteriosMinimos = RIGOR_PADRAO,
  onChangeCriteriosMinimos = () => {},
  asyncExecute = false,
  onChangeAsyncExecute = () => {},
  callbackUrl = '',
  onChangeCallbackUrl = () => {},
}) => {
  const triggerBtnRef = useRef<HTMLButtonElement>(null);
  const [isMobile, setIsMobile] = useState(() => {
    return typeof window !== 'undefined' ? window.innerWidth <= 640 : false;
  });

  useEffect(() => {
    const handleResize = () => {
      setIsMobile(window.innerWidth <= 640);
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Lock de rolagem do body no mobile quando a folha de preferências estiver aberta (evita duplo scroll)
  useEffect(() => {
    if (!isOpen) {
      document.body.style.overflow = '';
      document.documentElement.style.overflow = '';
      document.body.classList.remove('preferences-open');
      document.documentElement.classList.remove('preferences-open');
      return;
    }

    const updateScrollLock = () => {
      const isMobileNow = window.innerWidth <= 640 || (typeof window.matchMedia === 'function' && window.matchMedia('(max-width: 640px)').matches);
      if (isMobileNow) {
        document.body.style.overflow = 'hidden';
        document.documentElement.style.overflow = 'hidden';
        document.body.classList.add('preferences-open');
        document.documentElement.classList.add('preferences-open');
      } else {
        document.body.style.overflow = '';
        document.documentElement.style.overflow = '';
        document.body.classList.remove('preferences-open');
        document.documentElement.classList.remove('preferences-open');
      }
    };

    updateScrollLock();
    window.addEventListener('resize', updateScrollLock);
    return () => {
      document.body.style.overflow = '';
      document.documentElement.style.overflow = '';
      document.body.classList.remove('preferences-open');
      document.documentElement.classList.remove('preferences-open');
      window.removeEventListener('resize', updateScrollLock);
    };
  }, [isOpen]);

  const popoverContent = (
    <PreferencesPopoverContent
      onClose={onClose}
      triggerElement={triggerBtnRef.current}
      nPontos={nPontos}
      onChangeNPontos={onChangeNPontos}
      selectedPersonas={selectedPersonas}
      onChangePersonas={onChangePersonas}
      disabled={disabled}
      currentPlanActive={currentPlanActive}
      executionMode={executionMode}
      onChangeExecutionMode={onChangeExecutionMode}
      recencia={recencia}
      onChangeRecencia={onChangeRecencia}
      criteriosMinimos={criteriosMinimos}
      onChangeCriteriosMinimos={onChangeCriteriosMinimos}
      asyncExecute={asyncExecute}
      onChangeAsyncExecute={onChangeAsyncExecute}
      callbackUrl={callbackUrl}
      onChangeCallbackUrl={onChangeCallbackUrl}
    />
  );

  return (
    <div className="preferences-wrapper">
      <button
        ref={triggerBtnRef}
        type="button"
        id="preferences-toggle-btn"
        className={`preferences-toggle-btn ${isOpen ? 'active' : ''}`}
        onClick={onToggle}
        disabled={disabled}
        aria-label="Parâmetros de investigação (pontos, personas, execução, recência e rigor)"
        aria-expanded={isOpen}
        aria-controls="preferences-popover-panel"
        title="Configurar pontos analíticos, personas, execução, recência e rigor"
      >
        <span className="plus-icon" aria-hidden="true">+</span>
        <span className="preferences-chip-label">
          {nPontos} {nPontos === 1 ? 'ponto' : 'pontos'} • {selectedPersonas.length} {selectedPersonas.length === 1 ? 'persona' : 'personas'} • {executionMode === 'parallel' ? 'Paralelo' : 'Sequencial'}
        </span>
      </button>

      {isOpen &&
        (isMobile ? (
          createPortal(
            <div
              className="modal-backdrop preferences-modal-backdrop"
              onClick={(e) => {
                if (e.target === e.currentTarget) {
                  onClose();
                  triggerBtnRef.current?.focus();
                }
              }}
              role="presentation"
            >
              {popoverContent}
            </div>,
            document.body
          )
        ) : (
          popoverContent
        ))}
    </div>
  );
};
