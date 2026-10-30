import React from 'react';
import type { ModeloMetadados } from '../types/api';

/**
 * Faixa de telemetria do painel de contexto (DESIGN.md §7).
 *
 * Vive logo abaixo das abas e é a mesma nos dois modos: total em mono,
 * entrada/saída/total e modelo truncado. Quando não há telemetria o estado é
 * honesto ("telemetria indisponível") — nunca zero inventado.
 */

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
  const total = typeof usage?.total_tokens === 'number' ? usage.total_tokens : 0;

  if (!usage || !(total > 0)) {
    return (
      <div className="rr-tokens rr-tokens--empty" aria-label="Consumo de tokens">
        <span className="rr-tokens__total">Tokens</span>
        <span className="rr-tokens__empty">sem dados de tokens</span>
      </div>
    );
  }

  const prompt = typeof usage.prompt_tokens === 'number' ? usage.prompt_tokens : 0;
  const completion = typeof usage.completion_tokens === 'number' ? usage.completion_tokens : 0;
  const promptRatio = total > 0 ? Math.min(1, Math.max(0, prompt / total)) : 0;
  const completionRatio = total > 0 ? Math.min(1, Math.max(0, completion / total)) : 0;
  const modelo = typeof metadados?.model_used === 'string' && metadados.model_used ? metadados.model_used : null;

  return (
    <div className="rr-tokens" aria-label="Consumo de tokens">
      <div className="rr-tokens__head">
        <span className="rr-tokens__total">{formatCompactTokens(total)}</span>
        <span className="rr-tokens__unit">tokens</span>
        {modelo && (
          <span className="rr-tokens__model" title={modelo}>
            {modelo}
          </span>
        )}
      </div>

      <div
        className="rr-tokens__bar"
        role="img"
        aria-label={`${formatCompactTokens(prompt)} tokens de entrada e ${formatCompactTokens(completion)} tokens de saída`}
      >
        <span
          className="rr-tokens__seg rr-tokens__seg--entrada"
          style={{ transform: `scaleX(${promptRatio})` }}
          aria-hidden="true"
        />
        <span
          className="rr-tokens__seg rr-tokens__seg--saida"
          style={{ transform: `translateX(${promptRatio * 100}%) scaleX(${completionRatio})` }}
          aria-hidden="true"
        />
      </div>

      <dl className="rr-tokens__metrics">
        <div className="rr-tokens__metric">
          <dt>Entrada</dt>
          <dd>{formatCompactTokens(prompt)}</dd>
        </div>
        <div className="rr-tokens__metric">
          <dt>Saída</dt>
          <dd>{formatCompactTokens(completion)}</dd>
        </div>
        <div className="rr-tokens__metric">
          <dt>Total</dt>
          <dd>{formatCompactTokens(total)}</dd>
        </div>
      </dl>

      {metadados?.usage_complete === false && <p className="rr-tokens__note">dados parciais</p>}
    </div>
  );
};
