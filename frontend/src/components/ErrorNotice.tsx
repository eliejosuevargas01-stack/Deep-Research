import React from 'react';
import { AlertTriangle, Info, RefreshCw, X } from 'lucide-react';
import type { FalhaApresentada } from '../utils/erros';
import '../styles/error-notice.css';

export interface ErrorNoticeProps {
  falha: FalhaApresentada;
  /** Ação de recuperação principal. Sem ela, o aviso é só informativo. */
  onRetry?: () => void;
  retrying?: boolean;
  retryLabel?: string;
  /** Ação secundária, como abrir Configurações. */
  acaoExtra?: { rotulo: string; onClick: () => void };
  onDismiss?: () => void;
  compact?: boolean;
  className?: string;
  id?: string;
}

/**
 * Aviso de falha padronizado: título com a ação que falhou, o que aconteceu
 * com o trabalho da pessoa, o próximo passo e os detalhes técnicos recolhidos.
 */
export const ErrorNotice: React.FC<ErrorNoticeProps> = ({
  falha,
  onRetry,
  retrying = false,
  retryLabel = 'Tentar de novo',
  acaoExtra,
  onDismiss,
  compact = false,
  className = '',
  id,
}) => {
  const Icone = falha.tom === 'aviso' ? Info : AlertTriangle;

  return (
    <div
      id={id}
      className={`error-notice error-notice--${falha.tom}${compact ? ' error-notice--compact' : ''}${className ? ` ${className}` : ''}`}
      role={falha.tom === 'aviso' ? 'status' : 'alert'}
      aria-live={falha.tom === 'aviso' ? 'polite' : 'assertive'}
    >
      <Icone size={compact ? 17 : 20} aria-hidden="true" className="error-notice__icon" />

      <div className="error-notice__body">
        <p className="error-notice__title">{falha.titulo}</p>
        <p className="error-notice__message">{falha.mensagem}</p>

        {falha.detalhe && (
          <details className="error-notice__details">
            <summary>Detalhes técnicos</summary>
            <code>{falha.detalhe}</code>
          </details>
        )}

        {(onRetry || acaoExtra) && (
          <div className="error-notice__actions">
            {onRetry && (
              <button
                type="button"
                className="error-notice__btn error-notice__btn--primary"
                onClick={onRetry}
                disabled={retrying}
              >
                <RefreshCw size={14} className={retrying ? 'spinner' : ''} aria-hidden="true" />
                <span>{retrying ? 'Tentando…' : retryLabel}</span>
              </button>
            )}
            {acaoExtra && (
              <button type="button" className="error-notice__btn" onClick={acaoExtra.onClick}>
                <span>{acaoExtra.rotulo}</span>
              </button>
            )}
          </div>
        )}
      </div>

      {onDismiss && (
        <button type="button" className="error-notice__close" onClick={onDismiss} aria-label="Fechar aviso">
          <X size={16} aria-hidden="true" />
        </button>
      )}
    </div>
  );
};
