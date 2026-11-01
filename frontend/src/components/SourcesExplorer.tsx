import React from 'react';
import { Favicon } from './Favicon';
import { FontesResumo } from '../types/api';

export type FonteExplorerStatus = 'lendo' | 'processado' | 'invalidado' | 'consultada';

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
  consultada: 'Consultada',
  invalidado: 'Invalidado',
};

function isSafeUrl(url: string): boolean {
  const clean = url.trim().toLowerCase();
  return clean.startsWith('http://') || clean.startsWith('https://');
}

function dominioDe(url: string, explicito?: string | null): string {
  if (explicito && explicito.trim()) return explicito.trim().replace(/^www\./i, '');
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return url.replace(/^https?:\/\//i, '').replace(/^www\./i, '').replace(/\/.*$/, '');
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

/**
 * Lista de fontes do painel de contexto (DESIGN.md §7).
 *
 * Linhas abertas: favicon 16px na cor original, título truncado em 1 linha,
 * domínio em mono 11px e badge de estado. Agrupamento por ponto quando o dado
 * existe. A rolagem fica no corpo do painel — esta lista não abre um segundo
 * scroller.
 */
export const SourcesExplorer: React.FC<SourcesExplorerProps> = ({ items }) => {
  const lista = Array.isArray(items) ? items : [];

  const grupos: Array<{ ponto_n: number | null; itens: FonteExplorerItem[] }> = [];
  const map = new Map<string, FonteExplorerItem[]>();
  for (const item of lista) {
    const key = typeof item.ponto_n === 'number' ? `p${item.ponto_n}` : 'geral';
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(item);
  }
  const keys = Array.from(map.keys()).sort((a, b) => {
    const na = a.startsWith('p') ? parseInt(a.slice(1), 10) : 9999;
    const nb = b.startsWith('p') ? parseInt(b.slice(1), 10) : 9999;
    return na - nb;
  });
  for (const k of keys) {
    const ponto_n = k.startsWith('p') ? parseInt(k.slice(1), 10) : null;
    grupos.push({ ponto_n, itens: map.get(k)! });
  }
  const temPonto = grupos.some((g) => g.ponto_n !== null);

  return (
    <div className="rr-sources" aria-label="Fontes exploradas">
      {lista.length === 0 ? (
        <p className="rr-sources__empty">Nenhuma fonte explorada ainda</p>
      ) : (
        grupos.map((grupo) => {
          const rotulo = grupo.ponto_n !== null ? `Ponto ${grupo.ponto_n}` : temPonto ? 'Sem ponto' : null;
          return (
            <section
              key={grupo.ponto_n === null ? 'geral' : `ponto-${grupo.ponto_n}`}
              className="rr-sources__group"
              aria-label={rotulo ?? 'Fontes exploradas'}
            >
              {rotulo && <p className="rr-sources__group-label">{rotulo}</p>}
              <ul className="rr-sources__list">
                {grupo.itens.map((fonte, indice) => {
                  const dominio = dominioDe(fonte.url, fonte.dominio);
                  const titulo = fonte.titulo && fonte.titulo.trim() ? fonte.titulo.trim() : dominio;
                  const seguro = isSafeUrl(fonte.url);
                  const rotuloStatus = STATUS_ROTULO[fonte.status] ?? (typeof fonte.status === 'string' ? fonte.status : 'Processado');
                  const descricao = `${titulo} — ${dominio} — ${rotuloStatus}`;
                  const conteudo = (
                    <>
                      <span className="rr-source__icon" aria-hidden="true">
                        <span className="rr-source__fallback">{inicialDominio(dominio)}</span>
                        <Favicon dominio={dominio} size={32} className="rr-source__img" />
                      </span>
                      <span className="rr-source__text">
                        <span className="rr-source__title" title={titulo}>
                          {titulo}
                        </span>
                        <span className="rr-source__domain" title={dominio}>
                          {dominio}
                        </span>
                      </span>
                      <span className={`rr-source__badge is-${fonte.status}`}>{rotuloStatus}</span>
                    </>
                  );
                  return (
                    <li key={`${fonte.url}-${indice}`} className="rr-sources__row">
                      {seguro ? (
                        <a
                          className="rr-source"
                          href={fonte.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          title={descricao}
                          aria-label={`Abrir fonte externa: ${descricao}`}
                        >
                          {conteudo}
                        </a>
                      ) : (
                        <span className="rr-source" title={descricao}>
                          {conteudo}
                        </span>
                      )}
                    </li>
                  );
                })}
              </ul>
            </section>
          );
        })
      )}
    </div>
  );
};

import type { SearchResponse } from '../types/api';

export function derivarFontesParaExplorer(
  search: SearchResponse | null | undefined,
  opts?: {
    emColeta?: boolean;
    pontosReprovados?: Set<string> | null;
    reasoningItems?: Array<{
      reasoning?: string | null;
      pointNumber?: number;
      details?: { ponto_id?: string; urls_lidas?: number; [key: string]: unknown };
    }>;
  }
): FonteExplorerItem[] {
  const vistos = new Set<string>();
  const itens: FonteExplorerItem[] = [];

  // 1. Fontes estruturadas do SearchResponse (quando a coleta foi consolidada)
  if (search && Array.isArray(search.resumo_coletas)) {
    for (const coleta of search.resumo_coletas) {
      for (const p of coleta.personas ?? []) {
        for (const raw of p.urls_fonte ?? []) {
          const url = String(raw ?? '').trim();
          if (!url) continue;
          if (!/^https?:\/\//i.test(url)) continue;
          const normalizada = url.replace(/^http:\/\//i, 'https://');
          if (vistos.has(normalizada)) continue;
          vistos.add(normalizada);
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
  }

  // 2. Fontes extraídas dinamicamente do raciocínio das personas em tempo real
  if (opts?.reasoningItems && Array.isArray(opts.reasoningItems)) {
    const urlRegex = /(?:https?:\/\/)[^\s)\]"'>;,]+/gi;
    for (const item of opts.reasoningItems) {
      const texto = item.reasoning ?? '';
      const matches = texto.match(urlRegex) ?? [];
      for (const raw of matches) {
        const url = raw.trim().replace(/[.,;:)\]]+$/, '');
        if (!url || !/^https?:\/\//i.test(url)) continue;
        const normalizada = url.replace(/^http:\/\//i, 'https://');
        if (vistos.has(normalizada)) continue;
        vistos.add(normalizada);
        let dominio: string | null = null;
        try {
          dominio = new URL(url).hostname.replace(/^www\./, '');
        } catch {
          dominio = null;
        }
        itens.push({
          url,
          titulo: null,
          dominio,
          status: opts?.emColeta ? 'lendo' : 'processado',
          ponto_n: typeof item.pointNumber === 'number' ? item.pointNumber : null,
        });
      }
    }
  }

  return itens;
}

/**
 * Converte um FontesResumo retornado pelo backend em itens para o SourcesExplorer,
 * garantindo que recarregar a página preserve a listagem completa de fontes.
 */
export function converterFontesResumoParaExplorer(resumo?: FontesResumo | null): FonteExplorerItem[] {
  if (!resumo) return [];
  const items: FonteExplorerItem[] = [];
  const vistos = new Set<string>();

  const processList = (lista: unknown[] | undefined, statusPadrao: FonteExplorerStatus) => {
    if (!Array.isArray(lista)) return;
    for (const item of lista) {
      const rawUrl =
        typeof item === 'string'
          ? item
          : item && typeof item === 'object' && 'url' in item
          ? String((item as { url: unknown }).url)
          : '';
      const url = rawUrl.trim();
      if (!url || !/^https?:\/\//i.test(url)) continue;
      const normalizada = url.replace(/^http:\/\//i, 'https://');
      if (vistos.has(normalizada)) continue;
      vistos.add(normalizada);
      let dominio: string | null = null;
      try {
        dominio = new URL(url).hostname.replace(/^www\./, '');
      } catch {
        dominio = null;
      }
      const rawTitulo = item && typeof item === 'object' && 'titulo' in item ? (item as { titulo: unknown }).titulo : null;
      const titulo = typeof rawTitulo === 'string' ? rawTitulo : null;
      const rawPontoN = item && typeof item === 'object' && 'ponto_n' in item ? (item as { ponto_n: unknown }).ponto_n : null;
      const ponto_n = typeof rawPontoN === 'number' ? rawPontoN : null;
      const rawStatus = item && typeof item === 'object' && 'status' in item ? (item as { status: unknown }).status : null;
      const status: FonteExplorerStatus =
        rawStatus === 'lendo' || rawStatus === 'consultada' || rawStatus === 'processado' || rawStatus === 'invalidado'
          ? (rawStatus as FonteExplorerStatus)
          : statusPadrao;
      items.push({
        url,
        titulo,
        dominio,
        status,
        ponto_n,
      });
    }
  };

  processList(resumo.utilizadas, 'processado');
  processList(resumo.consultadas, 'consultada');

  return items;
}
