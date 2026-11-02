import React from 'react';
import { Favicon } from './Favicon';
import { FontesResumo } from '../types/api';

export type FonteExplorerStatus = 'lendo' | 'utilizada' | 'lida_nao_utilizada';

export interface FonteExplorerItem {
  url: string;
  titulo?: string | null;
  dominio?: string | null;
  status: FonteExplorerStatus;
  ponto_n?: number | null;
}

const STATUS_ROTULO: Record<FonteExplorerStatus, string> = {
  lendo: 'Lendo',
  utilizada: 'Utilizada',
  lida_nao_utilizada: 'Lida (não utilizada)',
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
    reasoningItems?: Array<{
      reasoning?: string | null;
      pointNumber?: number;
      details?: { ponto_id?: string; urls_lidas?: number; [key: string]: unknown };
    }>;
  }
): FonteExplorerItem[] {
  const vistos = new Set<string>();
  const itens: FonteExplorerItem[] = [];

  if (search && Array.isArray(search.resumo_coletas)) {
    for (const coleta of search.resumo_coletas) {
      for (const p of coleta.personas ?? []) {
        const urlToUso = new Map<string, 'utilizada' | 'lida_nao_utilizada'>();
        if (Array.isArray((p as any).fontes)) {
          for (const f of (p as any).fontes) {
            const raw = typeof f?.url === 'string' ? f.url.trim() : '';
            if (!raw) continue;
            if (!/^https?:\/\//i.test(raw)) continue;
            const norm = raw.replace(/^http:\/\//i, 'https://');
            const uso = f?.uso === 'lida_nao_utilizada' ? 'lida_nao_utilizada' : 'utilizada';
            urlToUso.set(norm, uso);
          }
        }
        if (Array.isArray((p as any).urls_fonte)) {
          for (const raw of (p as any).urls_fonte) {
            const url = String(raw ?? '').trim();
            if (!url) continue;
            if (!/^https?:\/\//i.test(url)) continue;
            const norm = url.replace(/^http:\/\//i, 'https://');
            if (!urlToUso.has(norm)) urlToUso.set(norm, 'utilizada');
          }
        }
        if (Array.isArray((p as any).urls_lidas)) {
          for (const raw of (p as any).urls_lidas) {
            const url = String(raw ?? '').trim();
            if (!url) continue;
            if (!/^https?:\/\//i.test(url)) continue;
            const norm = url.replace(/^http:\/\//i, 'https://');
            if (!urlToUso.has(norm)) urlToUso.set(norm, 'lida_nao_utilizada');
          }
        }
        for (const [normalizada, uso] of urlToUso.entries()) {
          if (vistos.has(normalizada)) continue;
          vistos.add(normalizada);
          let dominio: string | null = null;
          try {
            dominio = new URL(normalizada).hostname.replace(/^www\./, '');
          } catch {
            dominio = null;
          }
          const status: FonteExplorerStatus = opts?.emColeta ? 'lendo' : uso;
          itens.push({
            url: normalizada.replace(/^http:\/\//i, 'https://'),
            titulo: null,
            dominio,
            status,
            ponto_n: typeof coleta.ponto_n === 'number' ? coleta.ponto_n : null,
          });
        }
      }
    }
  }

  return itens;
}

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
        rawStatus === 'lendo' || rawStatus === 'utilizada' || rawStatus === 'lida_nao_utilizada'
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

  processList(resumo.utilizadas, 'utilizada');
  processList(resumo.consultadas, 'lida_nao_utilizada');
  processList((resumo as any).nao_utilizadas, 'lida_nao_utilizada');

  return items;
}
