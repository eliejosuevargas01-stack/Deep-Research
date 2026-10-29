import React from 'react';
import { Gauge } from 'lucide-react';
import type { ModeloMetadados } from '../types/api';

export function formatCompactTokens(n: unknown): string {
  if (typeof n !== 'number' || !Number.isFinite(n) || n < 0) return '—';
  if (n >= 1000) {
    return `${(n / 1000).toLocaleString('pt-BR', { maximumFractionDigits: 1 })}k`;
  }
  return n.toLocaleString('pt-BR');
}

interface TokenUsageMeterProps {
  metadados?: ModeloMetadados | null;
}

export const TokenUsageMeter: React.FC<TokenUsageMeterProps> = ({ metadados }) => {
  const usage = metadados?.usage_total ?? null;
  const prompt = typeof usage?.prompt_tokens === 'number' ? usage.prompt_tokens : 0;
  const completion = typeof usage?.completion_tokens === 'number' ? usage.completion_tokens : 0;
  const total = typeof usage?.total_tokens === 'number' ? usage.total_tokens : prompt + completion;

  if (!usage || total <= 0) {
    return (
      <div className="right-rail__section" aria-label="Consumo de tokens">
        <div className="right-rail__header">
          <Gauge size={12} aria-hidden="true" className="right-rail__header-icon" />
          <span>Tokens da sessão</span>
        </div>
        <p className="rr-token__empty">Telemetria de tokens indisponível</p>
      </div>
    );
  }

  const promptRatio = total > 0 ? prompt / total : 0;
  const completionRatio = total > 0 ? completion / total : 0;

  return (
    <div className="right-rail__section" aria-label="Consumo de tokens do planejamento">
      <div className="right-rail__header">
        <Gauge size={12} aria-hidden="true" className="right-rail__header-icon" />
        <span>Tokens da sessão</span>
      </div>

      <p className="rr-token__total">
        {formatCompactTokens(total)}
        <span className="rr-token__total-unit">tokens</span>
      </p>

      <div
        className="rr-token__bar"
        role="img"
        aria-label={`${formatCompactTokens(prompt)} tokens de entrada e ${formatCompactTokens(completion)} tokens de saída`}
      >
        <span
          className="rr-token__bar-prompt"
          style={{ transform: `scaleX(${promptRatio})` }}
          aria-hidden="true"
        />
        <span
          className="rr-token__bar-completion"
          style={{ transform: `scaleX(${completionRatio})`, left: `${promptRatio * 100}%` }}
          aria-hidden="true"
        />
      </div>

      <div className="rr-token__rows">
        <div className="rr-token__row">
          <span className="rr-token__row-label">Entrada</span>
          <span className="rr-token__row-value">{formatCompactTokens(prompt)}</span>
        </div>
        <div className="rr-token__row">
          <span className="rr-token__row-label">Saída</span>
          <span className="rr-token__row-value">{formatCompactTokens(completion)}</span>
        </div>
        <div className="rr-token__row">
          <span className="rr-token__row-label">Total</span>
          <span className="rr-token__row-value">{formatCompactTokens(total)}</span>
        </div>
      </div>

      {typeof metadados?.model_used === 'string' && metadados.model_used && (
        <div className="rr-token__model" title={metadados.model_used}>
          {metadados.model_used}
        </div>
      )}

      {metadados?.usage_complete === false && (
        <p className="rr-token__note">Telemetria parcial</p>
      )}
    </div>
  );
};
