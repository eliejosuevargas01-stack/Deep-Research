import React, { useEffect, useRef } from 'react';
import { Sliders, X, Info, Minus, Plus } from 'lucide-react';
import type { RecenciaPolitica } from '../types/api';
import { RIGOR_MAXIMO, RIGOR_MINIMO, RIGOR_PADRAO, normalizarRigor, validarCallbackUrl } from '../services/api';

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
  /** Passo 1: política temporal enviada em PlanRequest.recencia. */
  recencia?: RecenciaPolitica;
  onChangeRecencia?: (recencia: RecenciaPolitica) => void;
  /** Passo 4: limiar de aprovação (10..12, padrão 11). */
  criteriosMinimos?: number;
  onChangeCriteriosMinimos?: (n: number) => void;
  /** Passo 5: entrega síncrona (stream) ou assíncrona (webhook). */
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
  disabled: boolean;
  currentPlanActive: boolean;
  executionMode: 'parallel' | 'sequential';
  onChangeExecutionMode: (mode: 'parallel' | 'sequential') => void;
  recencia: RecenciaPolitica;
  onChangeRecencia: (recencia: RecenciaPolitica) => void;
  criteriosMinimos: number;
  onChangeCriteriosMinimos: (n: number) => void;
  asyncExecute: boolean;
  onChangeAsyncExecute: (async: boolean) => void;
  callbackUrl: string;
  onChangeCallbackUrl: (url: string) => void;
}

const PreferencesPopoverContent: React.FC<PreferencesPopoverContentProps> = ({
  onClose,
  triggerElement,
  nPontos,
  onChangeNPontos,
  selectedPersonas,
  onChangePersonas,
  disabled,
  currentPlanActive,
  executionMode,
  onChangeExecutionMode,
  recencia,
  onChangeRecencia,
  criteriosMinimos,
  onChangeCriteriosMinimos,
  asyncExecute,
  onChangeAsyncExecute,
  callbackUrl,
  onChangeCallbackUrl,
}) => {
  const panelRef = useRef<HTMLDivElement>(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  // Bounded panel positioning: garante que o painel e o cabeçalho nunca ultrapassem o topo do viewport (isTopClipped: false)
  useEffect(() => {
    const updateBounds = () => {
      if (!panelRef.current || !triggerElement) return;
      const triggerRect = triggerElement.getBoundingClientRect();
      const margin = 12; // margem de segurança mínima do topo do viewport
      // Usa todo o espaço acima do gatilho: o teto fixo de 520px cortava a
      // última persona em telas onde havia espaço de sobra.
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

  // Abertura animada em CSS (keyframe `prefs-enter`), uma vez na montagem.
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

  const togglePersona = (personaId: string) => {
    if (selectedPersonas.includes(personaId)) {
      if (selectedPersonas.length <= 1) return;
      onChangePersonas(selectedPersonas.filter((p) => p !== personaId));
    } else {
      onChangePersonas([...selectedPersonas, personaId]);
    }
  };

  const handlePointSelect = (p: number) => {
    if (p >= 1 && p <= 20) {
      onChangeNPontos(p);
    }
  };

  const handleCustomPointChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value.trim();
    if (!val) return;
    const num = parseInt(val, 10);
    if (!isNaN(num) && num >= 1 && num <= 20) {
      onChangeNPontos(num);
    }
  };

  // Navegação por teclado nos botões de preset de pontos (ArrowLeft/ArrowRight)
  const handlePointKeyDown = (e: React.KeyboardEvent<HTMLButtonElement>, current: number) => {
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
      e.preventDefault();
      const next = current < 5 ? current + 1 : 1;
      onChangeNPontos(next);
      const btn = panelRef.current?.querySelector<HTMLButtonElement>(`button[data-point="${next}"]`);
      btn?.focus();
    } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
      e.preventDefault();
      const prev = current > 1 ? current - 1 : 5;
      onChangeNPontos(prev);
      const btn = panelRef.current?.querySelector<HTMLButtonElement>(`button[data-point="${prev}"]`);
      btn?.focus();
    }
  };

  return (
    <div
      ref={panelRef}
      id="preferences-popover-panel"
      className="preferences-panel preferences-panel-enter"
      role="dialog"
      aria-labelledby="preferences-panel-title"
    >
      <header className="preferences-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Sliders size={16} className="preferences-icon" aria-hidden="true" />
          <h2 id="preferences-panel-title" className="preferences-title">
            Preferências de Pesquisa
          </h2>
        </div>
        <button
          type="button"
          className="preferences-close-btn"
          onClick={() => {
            onClose();
            triggerElement?.focus();
          }}
          aria-label="Fechar painel de preferências"
        >
          <X size={16} aria-hidden="true" />
        </button>
      </header>

      {currentPlanActive && (
        <div className="preferences-notice" role="note">
          <Info size={14} aria-hidden="true" style={{ flexShrink: 0, marginTop: '2px' }} />
          <span>
            Existe um plano ativo. Alterações feitas aqui serão aplicadas na formulação do <strong>próximo plano</strong>, sem alterar a pesquisa em andamento.
          </span>
        </div>
      )}

      {/* Seletor de Pontos (Presets 1..5 + Campo customizado até 20) */}
      <section className="preferences-section">
        <label className="preferences-label" id="points-selector-label">
          Número de pontos analíticos:
        </label>
        <div className="points-selector-row">
          <div
            className="points-selector-group"
            role="group"
            aria-labelledby="points-selector-label"
            style={{ flex: 1 }}
          >
            {[1, 2, 3, 4, 5].map((num) => (
              <button
                key={num}
                type="button"
                data-point={num}
                aria-pressed={nPontos === num}
                className={`point-option-btn ${nPontos === num ? 'selected' : ''}`}
                onClick={() => handlePointSelect(num)}
                onKeyDown={(e) => handlePointKeyDown(e, num)}
                disabled={disabled}
              >
                {num} {num === 1 ? 'ponto' : 'pontos'}
              </button>
            ))}
          </div>

          <div className="points-custom-wrapper">
            <label htmlFor="custom-points-input" style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)' }}>
              Quantidade:
            </label>
            <div className="points-stepper" role="group" aria-label="Ajustar quantidade de pontos">
              <button
                type="button"
                className="point-stepper-btn point-stepper-btn-minus"
                onClick={() => handlePointSelect(Math.max(1, nPontos - 1))}
                disabled={disabled || nPontos <= 1}
                aria-label="Diminuir pontos"
              >
                <Minus size={14} aria-hidden="true" />
              </button>
              <input
                id="custom-points-input"
                type="number"
                min={1}
                max={20}
                className="points-custom-input"
                value={nPontos}
                onChange={handleCustomPointChange}
                disabled={disabled}
                title="Digite a quantidade exata de pontos desejada (1 a 20)"
                aria-label="Quantidade exata de pontos analíticos (1 a 20)"
              />
              <button
                type="button"
                className="point-stepper-btn point-stepper-btn-plus"
                onClick={() => handlePointSelect(Math.min(20, nPontos + 1))}
                disabled={disabled || nPontos >= 20}
                aria-label="Aumentar pontos"
              >
                <Plus size={14} aria-hidden="true" />
              </button>
            </div>
          </div>
        </div>
        <p className="preferences-helper">
          Define a quantidade de eixos falseáveis estruturados pelo planejador antes da busca (1 a 20).
        </p>
      </section>

      {/* Modo de execução da busca */}
      <section className="preferences-section">
        <label className="preferences-label" id="execution-mode-label">
          Modo de execução da busca:
        </label>
        <div className="points-selector-row">
          <div className="points-selector-group" role="group" aria-labelledby="execution-mode-label" style={{ flex: 1 }}>
            {(['parallel', 'sequential'] as const).map((modo) => (
              <button
                key={modo}
                type="button"
                className={`point-option-btn ${executionMode === modo ? 'selected' : ''}`}
                aria-pressed={executionMode === modo}
                disabled={disabled}
                onClick={() => onChangeExecutionMode(modo)}
              >
                {modo === 'parallel' ? 'Paralelo' : 'Sequencial'}
              </button>
            ))}
          </div>
        </div>
        <p className="preferences-hint" id="execution-mode-hint">
          {executionMode === 'parallel'
            ? 'Personas consultam a web ao mesmo tempo: mais rápido, mais chamadas simultâneas.'
            : 'Personas consultam a web uma após a outra: mais lento, mais estável com limite de taxa.'}
        </p>
      </section>

      {/* Recência da pesquisa (Passo 1) */}
      <section className="preferences-section">
        <label className="preferences-label" id="recencia-label">
          Recência da pesquisa:
        </label>
        <div className="points-selector-row">
          <div className="points-selector-group" role="group" aria-labelledby="recencia-label" style={{ flex: 1 }}>
            {RECENCIA_OPCOES.map((opcao) => (
              <button
                key={opcao.id}
                type="button"
                className={`point-option-btn ${recencia === opcao.id ? 'selected' : ''}`}
                aria-pressed={recencia === opcao.id}
                disabled={disabled}
                onClick={() => onChangeRecencia(opcao.id)}
                title={opcao.desc}
              >
                {opcao.label}
              </button>
            ))}
          </div>
        </div>
        <p className="preferences-hint">
          {RECENCIA_OPCOES.find((o) => o.id === recencia)?.desc ?? 'Período aceito para as fontes.'}
        </p>
      </section>

      {/* Rigor da auditoria (Passo 4): 10..12, padrão 11 */}
      <section className="preferences-section">
        <label className="preferences-label" id="rigor-label" htmlFor="rigor-input">
          Rigor da auditoria:
        </label>
        <div className="points-selector-row">
          <input
            id="rigor-input"
            type="number"
            className="points-custom-input"
            min={RIGOR_MINIMO}
            max={RIGOR_MAXIMO}
            step={1}
            value={criteriosMinimos}
            disabled={disabled}
            onChange={(e) => onChangeCriteriosMinimos(normalizarRigor(e.target.value))}
            aria-describedby="rigor-hint"
            style={{ maxWidth: '88px' }}
          />
          <span className="preferences-hint" aria-hidden="true">/ 12 critérios</span>
        </div>
        <p className="preferences-hint" id="rigor-hint">
          Limiar de aprovação por ponto. 11 é o padrão do backend; 12 exige unanimidade, 10 tolera uma lacuna.
        </p>
      </section>

      {/* Modo de entrega (Passo 5): stream síncrono ou webhook assíncrono */}
      <section className="preferences-section">
        <label className="preferences-label" id="delivery-mode-label">
          Entrega do dossiê:
        </label>
        <div className="points-selector-row">
          <div className="points-selector-group" role="group" aria-labelledby="delivery-mode-label" style={{ flex: 1 }}>
            <button
              type="button"
              className={`point-option-btn ${!asyncExecute ? 'selected' : ''}`}
              aria-pressed={!asyncExecute}
              disabled={disabled}
              onClick={() => onChangeAsyncExecute(false)}
              title="Acompanha o pipeline ao vivo nesta tela"
            >
              Stream (Sync)
            </button>
            <button
              type="button"
              className={`point-option-btn ${asyncExecute ? 'selected' : ''}`}
              aria-pressed={asyncExecute}
              disabled={disabled}
              onClick={() => onChangeAsyncExecute(true)}
              title="Agenda no servidor e entrega via webhook"
            >
              Webhook (Async)
            </button>
          </div>
        </div>
        {asyncExecute && (
          <>
            <label className="preferences-label" htmlFor="callback-url-input" style={{ marginTop: '8px' }}>
              URL de callback:
            </label>
            <input
              id="callback-url-input"
              type="url"
              className="points-custom-input"
              value={callbackUrl}
              disabled={disabled}
              onChange={(e) => onChangeCallbackUrl(e.target.value)}
              placeholder="https://sua-api.exemplo.com/webhook/pesquisa"
              inputMode="url"
              autoComplete="url"
              aria-describedby="callback-url-hint"
              style={{ width: '100%' }}
            />
            {(() => {
              if (!callbackUrl.trim()) {
                return (
                  <p className="preferences-hint" id="callback-url-hint">
                    O servidor chama esta URL com o dossiê pronto. Sem ela, o plano cria mas nada é entregue.
                  </p>
                );
              }
              const check = validarCallbackUrl(callbackUrl);
              if (!check.valida) {
                return (
                  <p className="preferences-helper warning" id="callback-url-hint" role="alert">
                    {check.motivo}
                  </p>
                );
              }
              if (check.avisoLocal) {
                return (
                  <p className="preferences-helper warning" id="callback-url-hint" role="alert">
                    Host local: o servidor não alcança localhost/127.0.0.1. Use uma URL pública.
                  </p>
                );
              }
              return (
                <p className="preferences-hint" id="callback-url-hint">
                  Callback válido. O job roda no servidor; consulte o andamento com o status do pipeline.
                </p>
              );
            })()}
          </>
        )}
      </section>

      {/* Seleção de Personas Analíticas */}
      <section className="preferences-section">
        <label className="preferences-label" id="personas-selector-label">
          Personas ativas na busca web:
        </label>
        <div className="personas-list" role="group" aria-labelledby="personas-selector-label">
          {ALL_PERSONAS.map((persona) => {
            const isSelected = selectedPersonas.includes(persona.id);
            const isOnlyOne = isSelected && selectedPersonas.length === 1;
            return (
              <label
                key={persona.id}
                className={`persona-checkbox-label ${isSelected ? 'checked' : ''} ${isOnlyOne ? 'locked' : ''}`}
              >
                <input
                  type="checkbox"
                  className="persona-checkbox-input"
                  checked={isSelected}
                  disabled={disabled || isOnlyOne}
                  onChange={() => togglePersona(persona.id)}
                  aria-describedby={`persona-desc-${persona.id}`}
                />
                <div className="persona-checkbox-info">
                  <span className="persona-name">{persona.label}</span>
                  <span id={`persona-desc-${persona.id}`} className="persona-desc">
                    {persona.desc}
                  </span>
                </div>
              </label>
            );
          })}
        </div>
        {selectedPersonas.length === 1 && (
          <p className="preferences-helper warning">
            Pelo menos uma persona analítica deve permanecer ativa para a varredura web.
          </p>
        )}
      </section>
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
      const isMobile = window.innerWidth <= 640 || (typeof window.matchMedia === 'function' && window.matchMedia('(max-width: 640px)').matches);
      if (isMobile) {
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

  return (
    <div className="preferences-wrapper">
      <button
        ref={triggerBtnRef}
        type="button"
        id="preferences-toggle-btn"
        className={`preferences-toggle-btn ${isOpen ? 'active' : ''}`}
        onClick={onToggle}
        disabled={disabled}
        aria-label="Preferências de investigação (pontos, personas, recência, rigor e entrega)"
        aria-expanded={isOpen}
        aria-controls="preferences-popover-panel"
        title="Configurar pontos, personas, recência, rigor e entrega"
      >
        <span className="plus-icon" aria-hidden="true">+</span>
        <span className="preferences-chip-label">
          {nPontos} {nPontos === 1 ? 'ponto' : 'pontos'} • {selectedPersonas.length} {selectedPersonas.length === 1 ? 'persona' : 'personas'} • {RECENCIA_OPCOES.find((o) => o.id === recencia)?.label ?? recencia} • Rigor {normalizarRigor(criteriosMinimos)}/12{asyncExecute ? ' • Async' : ''}
        </span>
      </button>

      {isOpen && (
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
          criteriosMinimos={normalizarRigor(criteriosMinimos)}
          onChangeCriteriosMinimos={onChangeCriteriosMinimos}
          asyncExecute={asyncExecute}
          onChangeAsyncExecute={onChangeAsyncExecute}
          callbackUrl={callbackUrl}
          onChangeCallbackUrl={onChangeCallbackUrl}
        />
      )}
    </div>
  );
};
