import React from 'react';
import { ExternalLink, Globe } from 'lucide-react';

export type FonteExplorerStatus = 'lendo' | 'processado' | 'invalidado';

export interface FonteExplorerItem {
  url: string;
  titulo?: string | null;
  dominio?: string | null;
  status: FonteExplorerStatus;
  ponto_n?: number | null;
}

const STATUS_ROTULO: Record<FonteExplorerStatus, string> = {
  lendo: 'Lendo',
  processado: 'Processado',
  invalidado: 'Invalidado',
};

/** Aceita somente HTTP(S) público — mesmo validador do SourceBreakdown. */
function isSafeUrl(url: string): boolean {
  const clean = url.trim().toLowerCase();
  return clean.startsWith('http://') || clean.startsWith('https://');
}

function dominioDe(url: string, explicito?: string | null): string {
  if (explicito && explicito.trim()) return explicito.trim();
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return url;
  }
}

const MAX_EXIBIDAS = 24;

interface SourcesExplorerProps {
  /** Itens reais derivados de `resumo_coletas[].personas[].urls_fonte`. */
  items?: FonteExplorerItem[] | null;
  /** Coleta em andamento: ativa o badge pulsante do cabeçalho. */
  isActive?: boolean;
}

/**
 * Painel de fontes exploradas na barra lateral (estilo Google Deep Research).
 *
 * Cada fonte é um chip compacto com favicon do domínio, título truncado,
 * badge de status real (Lendo/Processado/Invalidado) e link externo.
 * Nenhuma fonte é fabricada: sem coleta, o painel declara o estado vazio.
 */
export const SourcesExplorer: React.FC<SourcesExplorerProps> = ({ items, isActive = false }) => {
  const lista = Array.isArray(items) ? items : [];
  const visiveis = lista.slice(0, MAX_EXIBIDAS);
  const restantes = lista.length - visiveis.length;

  return (
    <div className="card gdr-sources-card" aria-label="Fontes exploradas">
      <div className="gdr-sources-head">
        <Globe size={16} aria-hidden="true" className="gdr-sources-icon" />
        <h2 className="card-title gdr-sources-title">Fontes analisadas ({lista.length})</h2>
        {isActive && (
          <span className="gdr-sources-live" role="status" aria-label="Coletando fontes" title="Coletando fontes da web" />
        )}
      </div>

      {visiveis.length === 0 ? (
        <p className="gdr-sources-empty">
          {isActive ? 'Coletando fontes da web…' : 'Nenhuma fonte coletada até o momento.'}
        </p>
      ) : (
        <ul className="gdr-sources-list">
          {visiveis.map((fonte, indice) => {
            const dominio = dominioDe(fonte.url, fonte.dominio);
            const titulo = fonte.titulo && fonte.titulo.trim() ? fonte.titulo.trim() : dominio;
            const seguro = isSafeUrl(fonte.url);
            const descricao = `${titulo} — ${dominio} — ${STATUS_ROTULO[fonte.status]}${
              typeof fonte.ponto_n === 'number' ? ` — ponto ${fonte.ponto_n}` : ''
            }`;
            const conteudo = (
              <>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={`https://www.google.com/s2/favicons?domain=${encodeURIComponent(dominio)}&sz=32`}
                  alt=""
                  width={14}
                  height={14}
                  loading="lazy"
                  aria-hidden="true"
                  className="gdr-source-favicon"
                  onError={(event) => {
                    event.currentTarget.style.display = 'none';
                  }}
                />
                <span className="gdr-source-title" title={descricao}>
                  {titulo}
                </span>
                <span className={`gdr-source-status is-${fonte.status}`}>{STATUS_ROTULO[fonte.status]}</span>
                {seguro && <ExternalLink size={12} aria-hidden="true" className="gdr-source-link-icon" />}
              </>
            );
            return (
              <li key={`${fonte.url}-${indice}`} className="gdr-source-item">
                {seguro ? (
                  <a
                    className="gdr-source-chip"
                    href={fonte.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    title={`Abrir fonte externa: ${fonte.url}`}
                    aria-label={`Abrir fonte externa: ${descricao}`}
                  >
                    {conteudo}
                  </a>
                ) : (
                  <span className="gdr-source-chip" title={descricao}>
                    {conteudo}
                  </span>
                )}
              </li>
            );
          })}
        </ul>
      )}

      {restantes > 0 && <p className="gdr-sources-more">+{restantes} outras fontes</p>}
    </div>
  );
};

import type { SearchResponse } from '../types/api';

/** Deriva itens do explorer a partir do SearchResponse real. Dedupe por URL, só http(s), sem fabricar títulos. */
export function derivarFontesParaExplorer(
  search: SearchResponse | null | undefined,
  opts?: { emColeta?: boolean; pontosReprovados?: Set<string> | null }
): FonteExplorerItem[] {
  if (!search || !Array.isArray(search.resumo_coletas)) return [];
  const vistos = new Set<string>();
  const itens: FonteExplorerItem[] = [];
  for (const coleta of search.resumo_coletas) {
    for (const p of coleta.personas ?? []) {
      for (const raw of p.urls_fonte ?? []) {
        const url = String(raw ?? '').trim();
        if (!/^https:\/\//i.test(url)) continue;
        if (vistos.has(url)) continue;
        vistos.add(url);
        let dominio: string | null = null;
        try { dominio = new URL(url).hostname.replace(/^www\./, ''); } catch { dominio = null; }
        const reprovado = Boolean(coleta.ponto_id && opts?.pontosReprovados?.has(coleta.ponto_id));
        itens.push({
          url,
          titulo: null,
          dominio,
          status: reprovado ? 'invalidado' : opts?.emColeta ? 'lendo' : 'processado',
          ponto_n: typeof coleta.ponto_n === 'number' ? coleta.ponto_n : null,
        });
      }
    }
  }
  return itens;
}
