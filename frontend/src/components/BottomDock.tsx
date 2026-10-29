import React, { useEffect, useId, useLayoutEffect, useRef, useState } from 'react';
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

type PanelId = 'params' | 'look' | 'keys' | 'session' | null;

const PERSONA_LABELS: Record<string, string> = {
  historiador: 'Historiador',
  visionario: 'Visionário',
  cetico: 'Cético',
  futurista: 'Futurista',
};

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
  const [open, setOpen] = useState<PanelId>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRefs = useRef<Record<string, HTMLButtonElement | null>>({});
  const panelRef = useRef<HTMLDivElement>(null);
  const baseId = useId();

  const toggle = (id: PanelId, key: string) => {
    setOpen((cur) => (cur === id ? null : id));
    triggerRefs.current[key] = triggerRefs.current[key] ?? null;
  };

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        const active = document.activeElement as HTMLElement | null;
        setOpen(null);
        const back = rootRef.current?.querySelector<HTMLButtonElement>('[aria-expanded="true"]');
        if (back) back.focus();
        else active?.blur();
      }
    };
    const onClick = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(null);
    };
    document.addEventListener('keydown', onKey);
    document.addEventListener('mousedown', onClick);
    const first = panelRef.current?.querySelector<HTMLElement>('button, [href], input, [tabindex]:not([tabindex="-1"])');
    first?.focus();
    return () => {
      document.removeEventListener('keydown', onKey);
      document.removeEventListener('mousedown', onClick);
    };
  }, [open]);

  const btn = (
    id: Exclude<PanelId, null>,
    key: string,
    label: string,
    icon: React.ReactNode,
    extra?: string
  ) => (
    <button
      type="button"
      ref={(el) => { triggerRefs.current[key] = el; }}
      className={`dock-btn ${open === id ? 'is-open' : ''}`}
      aria-expanded={open === id}
      aria-controls={`${baseId}-${id}`}
      onClick={() => toggle(id, key)}
      disabled={disabled && id === 'params'}
      title={extra || label}
    >
      <span className="dock-btn-icon" aria-hidden="true">{icon}</span>
      <span className="dock-btn-label">{label}</span>
    </button>
  );

  const personaIds = personas.map((p) => p.id);
  const togglePersona = (id: string) => {
    if (selectedPersonas.includes(id)) {
      if (selectedPersonas.length === 1) return; // nunca deixa zero personas
      onChangePersonas(selectedPersonas.filter((p) => p !== id));
    } else {
      onChangePersonas([...selectedPersonas, id]);
    }
  };

  return (
    <div className="dock" ref={rootRef}>
      <div className="dock-bar" role="toolbar" aria-label="Ferramentas da investigação">
        {btn('params', 'params', 'Parâmetros', <SlidersHorizontal size={15} />, 'Pontos, personas e modo de execução')}
        {btn('look', 'look', 'Aparência', <Palette size={15} />, 'Tema e ambientação')}
        {btn('keys', 'keys', 'Atalhos', <Keyboard size={15} />, 'Teclas de uso rápido')}
        <span className="dock-divider" aria-hidden="true" />
        {btn('session', 'session', 'Sessão', <ShieldCheck size={15} />, 'Estado da conexão com o backend')}
      </div>

      {open && (
        <div
          className="dock-panel"
          id={`${baseId}-${open}`}
          ref={panelRef}
          role="dialog"
          aria-label={
            open === 'params' ? 'Parâmetros da investigação'
            : open === 'look' ? 'Aparência'
            : open === 'keys' ? 'Atalhos'
            : 'Sessão'
          }
        >
          <header className="dock-panel-head">
            <h2>
              {open === 'params' ? 'Parâmetros'
              : open === 'look' ? 'Aparência'
              : open === 'keys' ? 'Atalhos'
              : 'Sessão'}
            </h2>
            <button type="button" className="dock-close" onClick={() => setOpen(null)} aria-label="Fechar painel">
              <X size={14} aria-hidden="true" />
            </button>
          </header>

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
                {sessionAuthenticated ? 'Backend sincronizado — pronto para investigar' : 'Sessão pendente — o backend não respondeu'}
              </p>
              <p className="dock-note">Credenciais ficam cifradas no servidor; nada de provedor é chamado sem a sua submissão.</p>
              <button type="button" className="btn-secondary dock-action" onClick={onOpenSettings}>
                Abrir configurações
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
