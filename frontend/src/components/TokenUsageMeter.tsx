import React from 'react';
import { Gauge } from 'lucide-react';
import type { ModeloMetadados } from '../types/api';

/** Formata contagem de tokens de forma compacta e localizada (ex: 45.2k). */
export function formatCompactTokens(n: unknown): string {
  if (typeof n !== 'number' || !Number.isFinite(n) || n < 0) return '—';
  if (n >= 1000) {
    return `${(n / 1000).toLocaleString('pt-BR', { maximumFractionDigits: 1 })}k`;
  }
  return n.toLocaleString('pt-BR');
}

interface TokenUsageMeterProps {
  /** Projeção pública de telemetria do planejamento (tokens reais, sem prompts). */
  metadados?: ModeloMetadados | null;
}

/**
 * Medidor de tokens no topo da barra lateral.
 *
 * Consome exclusivamente `metadados_modelo.usage_total` do plano retornado
 * pelo backend. Sem telemetria, exibe estado honesto em vez de zerar ou
 * estimar. A barra representa a proporção real entrada/saída — nenhum
 * limite máximo é inventado, pois o backend não expõe a janela de contexto.
 */
export const TokenUsageMeter: React.FC<TokenUsageMeterProps> = ({ metadados }) => {
  const usage = metadados?.usage_total ?? null;
  const prompt = typeof usage?.prompt_tokens === 'number' ? usage.prompt_tokens : 0;
  const completion = typeof usage?.completion_tokens === 'number' ? usage.completion_tokens : 0;
  const total = typeof usage?.total_tokens === 'number' ? usage.total_tokens : prompt + completion;

  if (!usage || total <= 0) {
    return (
      <div className="card gdr-token-card" aria-label="Consumo de tokens">
        <div className="gdr-token-head">
          <Gauge size={16} aria-hidden="true" className="gdr-token-icon" />
          <h2 className="card-title gdr-token-title">Tokens da sessão</h2>
        </div>
        <p className="gdr-token-empty">Telemetria de tokens indisponível para este plano.</p>
      </div>
    );
  }

  const pctPrompt = Math.min(100, Math.max(0, (prompt / total) * 100));

  return (
    <div className="card gdr-token-card" aria-label="Consumo de tokens do planejamento">
      <div className="gdr-token-head">
        <Gauge size={16} aria-hidden="true" className="gdr-token-icon" />
        <h2 className="card-title gdr-token-title">Tokens do planejamento</h2>
        {typeof metadados?.model_used === 'string' && metadados.model_used && (
          <span className="gdr-token-model" title={`Modelo utilizado: ${metadados.model_used}`}>
            {metadados.model_used}
          </span>
        )}
      </div>

      <p className="gdr-token-total">
        {formatCompactTokens(total)} <span>tokens no total</span>
      </p>

      <div
        className="gdr-token-bar"
        role="img"
        aria-label={`${formatCompactTokens(prompt)} tokens de entrada e ${formatCompactTokens(completion)} tokens de saída`}
      >
        <span className="gdr-token-bar-prompt" style={{ width: `${pctPrompt}%` }} aria-hidden="true" />
        <span className="gdr-token-bar-completion" style={{ width: `${100 - pctPrompt}%` }} aria-hidden="true" />
      </div>

      <dl className="gdr-token-rows">
        <div className="gdr-token-row">
          <dt>Entrada</dt>
          <dd>{formatCompactTokens(prompt)}</dd>
        </div>
        <div className="gdr-token-row">
          <dt>Saída</dt>
          <dd>{formatCompactTokens(completion)}</dd>
        </div>
      </dl>

      {metadados?.usage_complete === false && (
        <p className="gdr-token-note">Contagem parcial: nem todas as tentativas reportaram uso.</p>
      )}
    </div>
  );
};
