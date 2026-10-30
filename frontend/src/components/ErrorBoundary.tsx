import React from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

interface Props {
  children: React.ReactNode;
}

interface State {
  falha: Error | null;
}

/**
 * Última barreira: uma exceção de render não pode deixar a tela em branco.
 * Mostra o que quebrou, o que continua salvo e como recomeçar.
 */
export class ErrorBoundary extends React.Component<Props, State> {
  state: State = { falha: null };

  static getDerivedStateFromError(falha: Error): State {
    return { falha };
  }

  componentDidCatch(falha: Error, info: React.ErrorInfo): void {
    // Fica no console para diagnóstico; a pessoa nunca vê stack cru.
    console.error('[ErrorBoundary] render falhou:', falha, info.componentStack);
  }

  private recarregar = (): void => {
    window.location.reload();
  };

  render(): React.ReactNode {
    const { falha } = this.state;
    if (!falha) return this.props.children;

    return (
      <div className="error-crash" role="alert">
        <div className="error-crash__card">
          <AlertTriangle size={22} aria-hidden="true" className="error-crash__icon" />
          <h1 className="error-crash__title">Esta tela quebrou</h1>
          <p className="error-crash__message">
            O app encontrou um erro que não sabe resolver sozinho. Suas pesquisas continuam salvas neste navegador.
            Recarregue para voltar ao início.
          </p>
          <button type="button" className="error-notice__btn error-notice__btn--primary" onClick={this.recarregar}>
            <RefreshCw size={14} aria-hidden="true" />
            <span>Recarregar o app</span>
          </button>
          <details className="error-notice__details">
            <summary>Detalhes técnicos</summary>
            <code>{`${falha.name}: ${falha.message}`}</code>
          </details>
        </div>
      </div>
    );
  }
}
