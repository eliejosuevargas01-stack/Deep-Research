import React, { useEffect, useRef } from 'react';
import { X, SlidersHorizontal, Settings2 } from 'lucide-react';

interface QuickSheetProps {
  open: boolean;
  onClose: () => void;
  theme: 'light' | 'dark';
  onToggleTheme: () => void;
  ambientOn: boolean;
  onToggleAmbient: () => void;
  onOpenSettings: () => void;
}

/**
 * Folha inferior de ajustes rápidos: tema, ambientação e atalhos para as
 * configurações completas. Fecha por toque no fundo, Escape ou arrasto para
 * baixo no puxador.
 */
export const QuickSheet: React.FC<QuickSheetProps> = ({
  open,
  onClose,
  theme,
  onToggleTheme,
  ambientOn,
  onToggleAmbient,
  onOpenSettings,
}) => {
  const startY = useRef<number | null>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    panelRef.current?.focus();
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = prev;
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="sheet-root">
      <button type="button" className="sheet-backdrop" aria-label="Fechar ajustes rápidos" onClick={onClose} />
      <div
        className="sheet-panel"
        role="dialog"
        aria-modal="true"
        aria-label="Ajustes rápidos"
        tabIndex={-1}
        ref={panelRef}
      >
        <div
          className="sheet-handle"
          onTouchStart={(e) => { startY.current = e.touches[0].clientY; }}
          onTouchMove={(e) => {
            if (startY.current === null) return;
            const dy = e.touches[0].clientY - startY.current;
            if (dy > 0 && panelRef.current) panelRef.current.style.transform = `translateY(${dy}px)`;
          }}
          onTouchEnd={(e) => {
            if (startY.current === null) return;
            const dy = e.changedTouches[0].clientY - startY.current;
            startY.current = null;
            if (panelRef.current) panelRef.current.style.transform = '';
            if (dy > 64) onClose();
          }}
        >
          <span aria-hidden="true" />
        </div>

        <header className="sheet-head">
          <h2>Ajustes rápidos</h2>
          <button type="button" className="sheet-close" onClick={onClose} aria-label="Fechar">
            <X size={16} aria-hidden="true" />
          </button>
        </header>

        <div className="sheet-body">
          <div className="sheet-row">
            <span className="sheet-label">Tema</span>
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

          <label className="sheet-row sheet-switch">
            <span>
              Ambientação viva
              <small>Auroras lentas no fundo</small>
            </span>
            <input type="checkbox" checked={ambientOn} onChange={onToggleAmbient} />
          </label>

          <button
            type="button"
            className="sheet-link"
            onClick={() => { onClose(); onOpenSettings(); }}
          >
            <Settings2 size={17} aria-hidden="true" />
            <span>
              Configurações completas
              <small>Chaves, provedores e parâmetros do pipeline</small>
            </span>
          </button>

          <p className="sheet-note">
            <SlidersHorizontal size={14} aria-hidden="true" />
            Pontos e personas também ficam no chip de contexto do campo de tema.
          </p>
        </div>
      </div>
    </div>
  );
};
