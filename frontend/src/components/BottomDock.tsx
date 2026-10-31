import React, { useCallback, useEffect, useId, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { SlidersHorizontal, Palette, Keyboard, ShieldCheck, Minus, Plus, X } from 'lucide-react';

export interface BottomDockProps {
  theme: 'light' | 'dark';
  onToggleTheme: () => void;
  ambientOn: boolean;
  onToggleAmbient: () => void;
  nPontos: number;
  onChangeNPontos: (n: number) => void;
  personas: { id: string; label: string }[];
  selectedPersonas: string[];
  onChangePersonas: (ids: string[]) => void;
  executionMode: 'parallel' | 'sequential';
  onChangeExecutionMode: (mode: 'parallel' | 'sequential') => void;
  disabled?: boolean;
  sessionAuthenticated: boolean;
  onOpenSettings: () => void;
}

type PanelId = 'params' | 'look' | 'keys' | 'session';
type OpenPanel = PanelId | null;

const PERSONA_LABELS: Record<string, string> = {
  historiador: 'Historiador',
  visionario: 'Visionário',
  cetico: 'Cético',
  futurista: 'Futurista',
};

const PANEL_LABELS: Record<PanelId, string> = {
  params: 'Parâmetros',
  look: 'Aparência',
  keys: 'Atalhos',
  session: 'Sessão',
};

const MOBILE_QUERY = '(max-width: 640px)';

/** Sincroniza um media query sem depender de listeners duplicados. */
const useMediaQuery = (query: string): boolean => {
  const [matches, setMatches] = useState<boolean>(() =>
    typeof window !== 'undefined' && typeof window.matchMedia === 'function'
      ? window.matchMedia(query).matches
      : false
  );

  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return undefined;
    const mql = window.matchMedia(query);
    const onChange = (e: MediaQueryListEvent) => setMatches(e.matches);
    setMatches(mql.matches);
    if (typeof mql.addEventListener === 'function') {
      mql.addEventListener('change', onChange);
      return () => mql.removeEventListener('change', onChange);
    }
    // Safari < 14
    mql.addListener(onChange);
    return () => mql.removeListener(onChange);
  }, [query]);

  return matches;
};

/**
 * BottomDock — deixou de ser barra própria (DESIGN.md §8).
 *
 * Os quatro gatilhos são portados para `[data-composer-tools]`, dentro da linha
 * de acessórios do Composer, e o painel abre em fluxo no slot
 * `[data-composer-panel]`, logo abaixo da caixa — nunca por cima do input.
 * Em ≤640px os gatilhos viram um botão único que abre a folha de ferramentas.
 */
export const BottomDock: React.FC<BottomDockProps> = ({
  theme,
  onToggleTheme,
  ambientOn,
  onToggleAmbient,
  nPontos,
  onChangeNPontos,
  personas,
  selectedPersonas,
  onChangePersonas,
  executionMode,
  onChangeExecutionMode,
  disabled = false,
  sessionAuthenticated,
  onOpenSettings,
}) => {
  const [open, setOpen] = useState<OpenPanel>(null);
  const [slots, setSlots] = useState<{ tools: HTMLElement; panel: HTMLElement } | null>(null);
  const [orphan, setOrphan] = useState(false);
  const triggerHostRef = useRef<HTMLDivElement>(null);
  const triggerRefs = useRef<Record<string, HTMLButtonElement | null>>({});
  const panelRef = useRef<HTMLDivElement>(null);
  const baseId = useId();

  const isMobile = useMediaQuery(MOBILE_QUERY);

  // Os slots vivem no Composer, montado antes deste componente na mesma árvore.
  // useLayoutEffect evita um frame com os gatilhos fora do lugar.
  useLayoutEffect(() => {
    const tools = document.querySelector<HTMLElement>('[data-composer-tools]');
    const panel = document.querySelector<HTMLElement>('[data-composer-panel]');
    if (tools && panel) {
      setSlots({ tools, panel });
      setOrphan(false);
    } else {
      setOrphan(true);
    }
  }, []);

  // Se o Composer sair da tela (planejamento/execução), o painel não pode ficar
  // aberto apontando para um slot morto.
  useEffect(() => {
    if (!slots) return undefined;
    const alive = document.body.contains(slots.tools) && document.body.contains(slots.panel);
    if (!alive) setOpen(null);
    return undefined;
  }, [slots]);

  const focusTrigger = useCallback((id: OpenPanel) => {
    if (!id) return;
    triggerRefs.current[id]?.focus();
  }, []);

  const close = useCallback((refocus: boolean) => {
    if (refocus) focusTrigger(open);
    setOpen(null);
  }, [focusTrigger, open]);

  useEffect(() => {
    if (!open) return undefined;

    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        close(true);
      }
    };
    const onClick = (e: MouseEvent) => {
      const target = e.target as Node;
      if (panelRef.current?.contains(target)) return;
      if (triggerHostRef.current?.contains(target)) return;
      close(false);
    };

    document.addEventListener('keydown', onKey);
    document.addEventListener('mousedown', onClick);

    const isMobileNow = window.innerWidth <= 640;
    const prevOverflow = document.body.style.overflow;
    if (isMobileNow) {
      document.body.style.overflow = 'hidden';
    }

    const frame = window.requestAnimationFrame(() => {
      const p = panelRef.current;
      if (p) {
        // Em telas baixas o painel em fluxo cai abaixo da dobra: traz para perto
        // sem rolar o input para fora da tela.
        const r = p.getBoundingClientRect();
        if (r.bottom > window.innerHeight) {
          p.scrollIntoView({ block: 'nearest', inline: 'nearest' });
        }
      }
      const first = p?.querySelector<HTMLElement>(
        'button:not([disabled]), [href], input:not([disabled]), [tabindex]:not([tabindex="-1"])'
      );
      first?.focus({ preventScroll: true });
    });

    return () => {
      if (isMobileNow) {
        document.body.style.overflow = prevOverflow;
      }
      window.cancelAnimationFrame(frame);
      document.removeEventListener('keydown', onKey);
      document.removeEventListener('mousedown', onClick);
    };
  }, [open, close]);

  const toggle = (id: PanelId) => {
    setOpen((cur) => (cur === id ? null : id));
  };

  const personaIds = personas.map((p) => p.id);
  const togglePersona = (id: string) => {
    if (selectedPersonas.includes(id)) {
      if (selectedPersonas.length === 1) return; // nunca deixa zero personas
      onChangePersonas(selectedPersonas.filter((p) => p !== id));
    } else {
      onChangePersonas([...selectedPersonas, id]);
    }
  };

  const triggers = (
    <div
      className={`dock-triggers ${isMobile ? 'is-mobile' : ''}`}
      role="toolbar"
      aria-label="Ferramentas da investigação"
      ref={triggerHostRef}
    >
      {isMobile ? (
        <button
          type="button"
          ref={(el) => { triggerRefs.current.params = el; }}
          className={`dock-btn dock-sheet-trigger ${open ? 'is-open' : ''}`}
          aria-expanded={open !== null}
          aria-controls={`${baseId}-sheet`}
          aria-haspopup="dialog"
          onClick={() => (open ? close(true) : setOpen('params'))}
          title="Parâmetros, aparência, atalhos e sessão"
        >
          <span className="dock-btn-icon" aria-hidden="true"><SlidersHorizontal size={15} /></span>
          <span className="dock-btn-label">Ferramentas</span>
        </button>
      ) : (
        <>
          <button
            type="button"
            ref={(el) => { triggerRefs.current.params = el; }}
            className={`dock-btn ${open === 'params' ? 'is-open' : ''}`}
            aria-expanded={open === 'params'}
            aria-controls={`${baseId}-params`}
            onClick={() => toggle('params')}
            disabled={disabled}
            title="Pontos, personas e modo de execução"
          >
            <span className="dock-btn-icon" aria-hidden="true"><SlidersHorizontal size={15} /></span>
            <span className="dock-btn-label">Parâmetros</span>
          </button>
          <button
            type="button"
            ref={(el) => { triggerRefs.current.look = el; }}
            className={`dock-btn ${open === 'look' ? 'is-open' : ''}`}
            aria-expanded={open === 'look'}
            aria-controls={`${baseId}-look`}
            onClick={() => toggle('look')}
            title="Tema e ambientação"
          >
            <span className="dock-btn-icon" aria-hidden="true"><Palette size={15} /></span>
            <span className="dock-btn-label">Aparência</span>
          </button>
          <button
            type="button"
            ref={(el) => { triggerRefs.current.keys = el; }}
            className={`dock-btn ${open === 'keys' ? 'is-open' : ''}`}
            aria-expanded={open === 'keys'}
            aria-controls={`${baseId}-keys`}
            onClick={() => toggle('keys')}
            title="Atalhos"
          >
            <span className="dock-btn-icon" aria-hidden="true"><Keyboard size={15} /></span>
            <span className="dock-btn-label">Atalhos</span>
          </button>
          <button
            type="button"
            ref={(el) => { triggerRefs.current.session = el; }}
            className={`dock-btn ${open === 'session' ? 'is-open' : ''}`}
            aria-expanded={open === 'session'}
            aria-controls={`${baseId}-session`}
            onClick={() => toggle('session')}
            title="Estado da conexão"
          >
            <span className="dock-btn-icon" aria-hidden="true"><ShieldCheck size={15} /></span>
            <span className="dock-btn-label">Sessão</span>
          </button>
        </>
      )}
    </div>
  );

  const panel = open ? (
    <div
      className={`dock-panel ${isMobile ? 'dock-sheet' : ''}`}
      id={isMobile ? `${baseId}-sheet` : `${baseId}-${open}`}
      ref={panelRef}
      role="dialog"
      aria-label={PANEL_LABELS[open]}
    >
      <header className="dock-panel-head">
        <h2>{PANEL_LABELS[open]}</h2>
        <button
          type="button"
          className="dock-close"
          onClick={() => close(true)}
          aria-label="Fechar painel"
        >
          <X size={14} aria-hidden="true" />
        </button>
      </header>

      {isMobile && (
        <div className="dock-sheet-tabs" role="tablist" aria-label="Seções de ferramentas">
          {(Object.keys(PANEL_LABELS) as PanelId[]).map((id) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={open === id}
              className={`dock-sheet-tab ${open === id ? 'is-on' : ''}`}
              onClick={() => setOpen(id)}
            >
              {PANEL_LABELS[id]}
            </button>
          ))}
        </div>
      )}

      {open === 'params' && (
        <div className="dock-fields">
          <div className="dock-field">
            <span className="dock-label" id={`${baseId}-pts`}>Pontos analíticos</span>
            <div className="dock-stepper" role="group" aria-labelledby={`${baseId}-pts`}>
              <button
                type="button"
                onClick={() => onChangeNPontos(Math.max(1, nPontos - 1))}
                disabled={nPontos <= 1}
                aria-label="Diminuir pontos"
              >
                <Minus size={13} aria-hidden="true" />
              </button>
              <output aria-live="polite">{nPontos}</output>
              <button
                type="button"
                onClick={() => onChangeNPontos(Math.min(10, nPontos + 1))}
                disabled={nPontos >= 10}
                aria-label="Aumentar pontos"
              >
                <Plus size={13} aria-hidden="true" />
              </button>
            </div>
          </div>

          <div className="dock-field">
            <span className="dock-label" id={`${baseId}-per`}>Personas na busca</span>
            <div className="dock-chips" role="group" aria-labelledby={`${baseId}-per`}>
              {personaIds.map((id) => {
                const on = selectedPersonas.includes(id);
                return (
                  <button
                    key={id}
                    type="button"
                    className={`dock-chip ${on ? 'is-on' : ''}`}
                    aria-pressed={on}
                    onClick={() => togglePersona(id)}
                  >
                    {PERSONA_LABELS[id] || personas.find((p) => p.id === id)?.label || id}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="dock-field">
            <span className="dock-label" id={`${baseId}-mode`}>Execução</span>
            <div className="dock-segment" role="group" aria-labelledby={`${baseId}-mode`}>
              <button
                type="button"
                className={executionMode === 'parallel' ? 'is-on' : ''}
                aria-pressed={executionMode === 'parallel'}
                onClick={() => onChangeExecutionMode('parallel')}
              >
                Paralelo
              </button>
              <button
                type="button"
                className={executionMode === 'sequential' ? 'is-on' : ''}
                aria-pressed={executionMode === 'sequential'}
                onClick={() => onChangeExecutionMode('sequential')}
              >
                Sequencial
              </button>
            </div>
          </div>
        </div>
      )}

      {open === 'look' && (
        <div className="dock-fields">
          <div className="dock-field">
            <span className="dock-label">Tema</span>
            <div className="dock-segment">
              <button
                type="button"
                className={theme === 'light' ? 'is-on' : ''}
                aria-pressed={theme === 'light'}
                onClick={() => { if (theme !== 'light') onToggleTheme(); }}
              >
                Claro
              </button>
              <button
                type="button"
                className={theme === 'dark' ? 'is-on' : ''}
                aria-pressed={theme === 'dark'}
                onClick={() => { if (theme !== 'dark') onToggleTheme(); }}
              >
                Escuro
              </button>
            </div>
          </div>
          <label className="dock-switch">
            <input type="checkbox" checked={ambientOn} onChange={onToggleAmbient} />
            <span>
              Ambientação viva
              <small>auroras lentas no fundo; desligue para economizar bateria</small>
            </span>
          </label>
        </div>
      )}

      {open === 'keys' && (
        <ul className="dock-keys">
          <li><kbd>Enter</kbd><span>Formular o plano do tema digitado</span></li>
          <li><kbd>Shift</kbd><kbd>Enter</kbd><span>Quebrar linha sem enviar</span></li>
          <li><kbd>Esc</kbd><span>Fechar este painel</span></li>
          <li><kbd>Tab</kbd><span>Percorrer controles na ordem visível</span></li>
          <li><kbd>/</kbd><span>Focar o campo de tema de qualquer tela</span></li>
        </ul>
      )}

      {open === 'session' && (
        <div className="dock-fields">
          <p className={`dock-status ${sessionAuthenticated ? 'is-ok' : 'is-warn'}`}>
            <span className="dock-status-dot" aria-hidden="true" />
            {sessionAuthenticated ? 'Sessão sincronizada. Pode investigar.' : 'Sessão pendente: o servidor não respondeu'}
          </p>
          <p className="dock-note">As chaves ficam cifradas no servidor. Nenhum provedor é chamado sem você enviar o tema.</p>
          <button type="button" className="btn-secondary dock-action" onClick={onOpenSettings}>
            Abrir configurações
          </button>
        </div>
      )}
    </div>
  ) : null;

  // Fallback raro (slots ausentes): mantém a versão inline, sem depender do Composer.
  if (orphan || !slots) {
    if (!orphan) return null;
    return (
      <div className="dock dock-inline">
        {triggers}
        {panel}
      </div>
    );
  }

  return (
    <>
      {createPortal(triggers, slots.tools)}
      {open
        ? isMobile
          ? createPortal(
              <div
                className="modal-backdrop dock-modal-backdrop"
                onClick={(e) => {
                  if (e.target === e.currentTarget) close(true);
                }}
                role="presentation"
              >
                {panel}
              </div>,
              document.body
            )
          : createPortal(panel, slots.panel)
        : null}
    </>
  );
};
