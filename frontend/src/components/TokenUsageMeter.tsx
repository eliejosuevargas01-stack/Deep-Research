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
  if (n >= 1_000_000) {
    return `${(n / 1_000_000).toLocaleString('pt-BR', { maximumFractionDigits: 2 })} mi`;
  }
  if (n >= 1000) {
    return `${(n / 1000).toLocaleString('pt-BR', { maximumFractionDigits: 1 })} mil`;
  }
  return n.toLocaleString('pt-BR');
}

const ROTULO_ETAPA: Record<string, string> = {
  plan: 'Planejamento',
  search: 'Busca',
  audit: 'Auditoria',
  write: 'Redação',
};

/** Rótulo da faixa: só o planejamento fala em planejamento. */
export function tituloTokensPorEtapa(status?: string | null): string {
  const s = (status ?? '').trim().toLowerCase();
  return ['idle', 'planejando', 'planejado', 'aguardando'].includes(s)
    ? 'Tokens do planejamento'
    : 'Consumo de tokens da pesquisa';
}

type UsoTokens =
  | {
      prompt_tokens?: number | null;
      completion_tokens?: number | null;
      input_tokens?: number | null;
      output_tokens?: number | null;
      total_tokens?: number | null;
    }
  | null
  | undefined;

function totalDoUso(uso: UsoTokens): number {
  if (!uso) return 0;
  const total = Number(uso.total_tokens ?? 0);
  if (Number.isFinite(total) && total > 0) return total;
  const entrada = Number(uso.prompt_tokens ?? uso.input_tokens ?? 0);
  const saida = Number(uso.completion_tokens ?? uso.output_tokens ?? 0);
  const soma = (Number.isFinite(entrada) ? entrada : 0) + (Number.isFinite(saida) ? saida : 0);
  return soma > 0 ? soma : 0;
}

/**
 * Quebra por etapa/agente do bloco expandido. O backend só manda quando
 * `usage_<etapa>.json` existe; sem isso a lista vem vazia (nada é inventado).
 */
export function linhasBreakdownTokens(
  metadados?: ModeloMetadados | null
): Array<{ rotulo: string; total: number }> {
  const linhas: Array<{ rotulo: string; total: number }> = [];
  const vistos = new Set<string>();
  const empurrar = (mapa: unknown) => {
    if (!mapa || typeof mapa !== 'object') return;
    for (const [chave, uso] of Object.entries(mapa as Record<string, UsoTokens>)) {
      const rotulo = ROTULO_ETAPA[chave] ?? chave;
      if (vistos.has(rotulo)) continue;
      const total = totalDoUso(uso);
      if (!(total > 0)) continue;
      vistos.add(rotulo);
      linhas.push({ rotulo, total });
    }
  };
  empurrar(metadados?.por_etapa);
  empurrar(metadados?.por_agente);
  return linhas.sort((a, b) => b.total - a.total);
}

interface TokenUsageMeterProps {
  metadados?: ModeloMetadados | null;
  aoVivo?: { prompt_tokens: number; completion_tokens: number; total_tokens: number } | null;
  /** Fase atual: o rótulo muda com a etapa, não fica fixo em "planejamento". */
  titulo?: string;
}

export const TokenUsageMeter: React.FC<TokenUsageMeterProps> = ({
  metadados,
  aoVivo,
  titulo = 'Consumo de tokens da pesquisa',
}) => {
  const usage =
    aoVivo && aoVivo.total_tokens > 0
      ? { prompt_tokens: aoVivo.prompt_tokens, completion_tokens: aoVivo.completion_tokens, total_tokens: aoVivo.total_tokens }
      : metadados?.usage_total ?? null;
  const total = typeof usage?.total_tokens === 'number' ? usage.total_tokens : 0;

  if (!usage || !(total > 0)) {
    return (
      <div className="rr-tokens rr-tokens--empty" aria-label={titulo}>
        <span className="rr-tokens__title">{titulo}</span>
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
  const breakdown = linhasBreakdownTokens(metadados);

  return (
    <div className="rr-tokens" aria-label={titulo}>
      <div className="rr-tokens__head">
        <span className="rr-tokens__title">{titulo}</span>
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

      <details className="rr-tokens__details">
        <summary className="rr-tokens__breakdown-toggle">Detalhes por etapa e agente</summary>
        {breakdown.length ? (
          <dl className="rr-tokens__breakdown">
            {breakdown.map((linha) => (
              <div className="rr-tokens__metric" key={linha.rotulo}>
                <dt>{linha.rotulo}</dt>
                <dd>{formatCompactTokens(linha.total)}</dd>
              </div>
            ))}
          </dl>
        ) : (
          <p className="rr-tokens__note">sem quebra por etapa disponível</p>
        )}
      </details>

      {metadados?.usage_complete === false && <p className="rr-tokens__note">dados parciais</p>}
    </div>
  );
};
