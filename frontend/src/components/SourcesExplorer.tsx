import React from 'react';
import { Globe } from 'lucide-react';
import { Favicon } from './Favicon';

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

function inicialDominio(dominio: string): string {
  const clean = dominio.replace(/^www\./, '').trim();
  if (!clean) return '?';
  const parts = clean.split('.');
  const base = parts.length >= 2 ? parts[parts.length - 2] : parts[0];
  return base.charAt(0).toUpperCase();
}

interface SourcesExplorerProps {
  items?: FonteExplorerItem[] | null;
  isActive?: boolean;
}

export const SourcesExplorer: React.FC<SourcesExplorerProps> = ({ items }) => {
  const lista = Array.isArray(items) ? items : [];

  // Group by ponto_n when exists
  const grupos: Array<{ ponto_n: number | null; itens: FonteExplorerItem[] }> = [];
  const map = new Map<string, FonteExplorerItem[]>();
  for (const item of lista) {
    const key = typeof item.ponto_n === 'number' ? `p${item.ponto_n}` : 'geral';
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(item);
  }
  // Sort keys: pontos first numerically
  const keys = Array.from(map.keys()).sort((a, b) => {
    const na = a.startsWith('p') ? parseInt(a.slice(1), 10) : 9999;
    const nb = b.startsWith('p') ? parseInt(b.slice(1), 10) : 9999;
    return na - nb;
  });
  for (const k of keys) {
    const ponto_n = k.startsWith('p') ? parseInt(k.slice(1), 10) : null;
    grupos.push({ ponto_n, itens: map.get(k)! });
  }

  return (
    <div className="right-rail__section" aria-label="Fontes exploradas">
      <div className="right-rail__header">
        <Globe size={12} aria-hidden="true" className="right-rail__header-icon" />
        <span>Fontes exploradas</span>
        <span className="right-rail__header-count">{lista.length}</span>
      </div>

      {lista.length === 0 ? (
        <p className="rr-sources__empty">Nenhuma fonte explorada ainda</p>
      ) : (
        <ul className="rr-sources__list">
          {grupos.map((grupo, gIdx) => (
            <React.Fragment key={`g-${gIdx}`}>
              {grupos.length > 1 && grupo.ponto_n !== null && (
                <li style={{ fontSize: '11px', color: 'var(--color-text-secondary)', padding: '2px 0' }}>
                  Ponto {grupo.ponto_n}
                </li>
              )}
              {grupo.itens.map((fonte, indice) => {
                const dominio = dominioDe(fonte.url, fonte.dominio);
                const titulo = fonte.titulo && fonte.titulo.trim() ? fonte.titulo.trim() : dominio;
                const seguro = isSafeUrl(fonte.url);
                const descricao = `${titulo} — ${dominio} — ${STATUS_ROTULO[fonte.status]}`;
                const init = inicialDominio(dominio);
                const conteudo = (
                  <>
                    <span className="rr-sources__favicon-wrap" aria-hidden="true">
                      <span className="rr-sources__favicon-fallback">{init}</span>
                      <Favicon dominio={dominio} size={64} className="rr-sources__favicon" />
                    </span>
                    <span className="rr-sources__title" title={titulo}>
                      {titulo}
                    </span>
                    <span className={`rr-sources__badge is-${fonte.status}`}>{STATUS_ROTULO[fonte.status]}</span>
                  </>
                );
                return (
                  <li key={`${fonte.url}-${indice}`} className="rr-sources__item">
                    {seguro ? (
                      <a
                        className="rr-sources__chip"
                        href={fonte.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        title={descricao}
                        aria-label={`Abrir fonte externa: ${descricao}`}
                      >
                        {conteudo}
                      </a>
                    ) : (
                      <span className="rr-sources__chip" title={descricao}>
                        {conteudo}
                      </span>
                    )}
                  </li>
                );
              })}
            </React.Fragment>
          ))}
        </ul>
      )}
    </div>
  );
};

import type { SearchResponse } from '../types/api';

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
        try {
          dominio = new URL(url).hostname.replace(/^www\./, '');
        } catch {
          dominio = null;
        }
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
