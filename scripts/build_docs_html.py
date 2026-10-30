#!/usr/bin/env python3
"""Gera a versão HTML da documentação em docs/html/.

Uso:
    .venv/bin/python scripts/build_docs_html.py

Requer o pacote `markdown` (pip install markdown). Os arquivos Markdown em
README.md e docs/ são a fonte de verdade; este script só transforma e aplica
o template visual do frontend.
"""

from __future__ import annotations

import datetime as dt
import html
import json
import os
import re
import shutil
import unicodedata
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "html"
ASSETS = OUT / "assets"
FONTS = ASSETS / "fonts"


def slugify(value: str, separator: str = "-") -> str:
    """Slug próximo do GitHub: preserva acentos e remove pontuação."""
    value = unicodedata.normalize("NFKC", value).strip().lower()
    value = re.sub(r"[^\w\s-]", "", value, flags=re.UNICODE)
    value = re.sub(r"[\s_-]+", separator, value).strip(separator)
    return value or "secao"


PAGES = [
    {
        "slug": "index",
        "file": "README.md",
        "nav": "Visão geral",
        "icon": "compass",
        "source": "../../README.md",
        "description": (
            "Pipeline modular de pesquisa profunda: planejamento em N eixos, "
            "coleta por personas, auditoria em 12 critérios e dossiê final "
            "rastreável."
        ),
    },
    {
        "slug": "arquitetura",
        "file": "docs/ARCHITECTURE.md",
        "nav": "Arquitetura",
        "icon": "layers",
        "source": "../ARCHITECTURE.md",
        "description": (
            "Como o monólito FastAPI, o pipeline, o banco e o streaming se "
            "encaixam — do plano ao dossiê."
        ),
    },
    {
        "slug": "api",
        "file": "docs/API.md",
        "nav": "API",
        "icon": "code",
        "source": "../API.md",
        "description": (
            "Contratos HTTP completos: payloads, códigos de erro, eventos SSE "
            "e entrega por webhook."
        ),
    },
    {
        "slug": "operacoes",
        "file": "docs/OPERATIONS.md",
        "nav": "Operações",
        "icon": "sliders",
        "source": "../OPERATIONS.md",
        "description": (
            "Instalação, configuração, banco, testes, diagnóstico e cuidados "
            "de segurança operacional."
        ),
    },
]

PAGE_BY_SOURCE = {
    "README.md": "index.html",
    "docs/README.md": "index.html",
    "docs/ARCHITECTURE.md": "arquitetura.html",
    "docs/API.md": "api.html",
    "docs/OPERATIONS.md": "operacoes.html",
    "docs/html/index.html": "index.html",
}

STEPS = [
    (
        "compass",
        "1. Planejamento",
        "N eixos, N pontos e termos de busca estruturados.",
    ),
    (
        "search",
        "2. Coleta",
        "Historiador, visionário, cético e futurista em paralelo.",
    ),
    (
        "shield",
        "3. Auditoria",
        "12 critérios por ponto, com evidência rastreável.",
    ),
    (
        "file-text",
        "4. Dossiê",
        "Markdown final, fontes canônicas e publicação por etapa.",
    ),
]

ICON_PATHS = {
    "compass": (
        '<circle cx="12" cy="12" r="10"></circle>'
        '<polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"></polygon>'
    ),
    "book-open": (
        '<path d="M12 7v14"></path>'
        '<path d="M3 18a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h5a4 4 0 0 1 4 4 4 4 0 0 1 4-4h5a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1h-6a3 3 0 0 0-3 3 3 3 0 0 0-3-3z"></path>'
    ),
    "layers": (
        '<path d="m12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.83Z"></path>'
        '<path d="m22 17.65-9.17 4.16a2 2 0 0 1-1.66 0L2 17.65"></path>'
        '<path d="m22 12.65-9.17 4.16a2 2 0 0 1-1.66 0L2 12.65"></path>'
    ),
    "code": (
        '<polyline points="16 18 22 12 16 6"></polyline>'
        '<polyline points="8 6 2 12 8 18"></polyline>'
    ),
    "sliders": (
        '<line x1="21" x2="14" y1="4" y2="4"></line>'
        '<line x1="10" x2="3" y1="4" y2="4"></line>'
        '<line x1="21" x2="12" y1="12" y2="12"></line>'
        '<line x1="8" x2="3" y1="12" y2="12"></line>'
        '<line x1="21" x2="16" y1="20" y2="20"></line>'
        '<line x1="12" x2="3" y1="20" y2="20"></line>'
        '<line x1="14" x2="14" y1="2" y2="6"></line>'
        '<line x1="8" x2="8" y1="10" y2="14"></line>'
        '<line x1="16" x2="16" y1="18" y2="22"></line>'
    ),
    "search": (
        '<circle cx="11" cy="11" r="7"></circle>'
        '<path d="m21 21-4.3-4.3"></path>'
    ),
    "moon": '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"></path>',
    "sun": (
        '<circle cx="12" cy="12" r="4"></circle>'
        '<path d="M12 2v2"></path><path d="M12 20v2"></path>'
        '<path d="m4.93 4.93 1.41 1.41"></path>'
        '<path d="m17.66 17.66 1.41 1.41"></path>'
        '<path d="M2 12h2"></path><path d="M20 12h2"></path>'
        '<path d="m6.34 17.66-1.41 1.41"></path>'
        '<path d="m19.07 4.93-1.41 1.41"></path>'
    ),
    "menu": (
        '<line x1="4" x2="20" y1="6" y2="6"></line>'
        '<line x1="4" x2="20" y1="12" y2="12"></line>'
        '<line x1="4" x2="20" y1="18" y2="18"></line>'
    ),
    "chevron-left": '<path d="m15 18-6-6 6-6"></path>',
    "chevron-right": '<path d="m9 18 6-6-6-6"></path>',
    "arrow-up": (
        '<path d="m5 12 7-7 7 7"></path>'
        '<path d="M12 19V5"></path>'
    ),
    "file-text": (
        '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"></path>'
        '<path d="M14 2v4a2 2 0 0 0 2 2h4"></path>'
        '<path d="M10 9H8"></path><path d="M16 13H8"></path>'
        '<path d="M16 17H8"></path>'
    ),
    "folder": (
        '<path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"></path>'
    ),
    "palette": (
        '<circle cx="13.5" cy="6.5" r=".5" fill="currentColor"></circle>'
        '<circle cx="17.5" cy="10.5" r=".5" fill="currentColor"></circle>'
        '<circle cx="8.5" cy="7.5" r=".5" fill="currentColor"></circle>'
        '<circle cx="6.5" cy="12.5" r=".5" fill="currentColor"></circle>'
        '<path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.93 0 1.65-.75 1.65-1.68 0-.44-.16-.84-.44-1.15-.27-.3-.43-.7-.43-1.14a1.65 1.65 0 0 1 1.65-1.65H16c3.31 0 6-2.69 6-6 0-4.97-4.48-9-10-9Z"></path>'
    ),
    "clipboard": (
        '<rect width="8" height="4" x="8" y="2" rx="1" ry="1"></rect>'
        '<path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"></path>'
        '<path d="M9 12h6"></path><path d="M9 16h6"></path>'
    ),
    "shield": (
        '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"></path>'
        '<path d="m9 12 2 2 4-4"></path>'
    ),
    "monitor": (
        '<rect width="20" height="14" x="2" y="3" rx="2"></rect>'
        '<line x1="8" x2="16" y1="21" y2="21"></line>'
        '<line x1="12" x2="12" y1="17" y2="21"></line>'
    ),
    "clock": (
        '<circle cx="12" cy="12" r="10"></circle>'
        '<polyline points="12 6 12 12 16 14"></polyline>'
    ),
    "tag": (
        '<path d="M12.586 2.586A2 2 0 0 0 11.172 2H4a2 2 0 0 0-2 2v7.172a2 2 0 0 0 .586 1.414l8.704 8.704a2.426 2.426 0 0 0 3.42 0l6.58-6.58a2.426 2.426 0 0 0 0-3.42z"></path>'
        '<circle cx="7.5" cy="7.5" r=".5" fill="currentColor"></circle>'
    ),
}


def icon(name: str, class_name: str = "") -> str:
    cls = f' class="{class_name}"' if class_name else ""
    return (
        f'<svg{cls} viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" '
        f'aria-hidden="true">{ICON_PATHS[name]}</svg>'
    )


def esc(value: str) -> str:
    return html.escape(value, quote=True)


def strip_tags(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def extract_page(markdown_text: str) -> tuple[str, str]:
    """Separa o H1; o restante (incluindo a introdução) vira corpo."""
    match = re.match(r"^#\s+(.+?)\s*\n+", markdown_text)
    if not match:
        return "Documentação", markdown_text
    return match.group(1).strip(), markdown_text[match.end() :].lstrip()


def convert(markdown_text: str) -> tuple[str, list[dict]]:
    md = markdown.Markdown(
        extensions=["tables", "fenced_code", "sane_lists", "toc", "attr_list"],
        extension_configs={
            "toc": {
                "slugify": slugify,
                "permalink": False,
                "title": "",
            }
        },
    )
    body = md.convert(markdown_text)
    body = re.sub(
        r"<table>(.*?)</table>",
        r'<div class="table-wrap"><table>\1</table></div>',
        body,
        flags=re.S,
    )
    headings = []
    for match in re.finditer(
        r"<h([234])\s+id=\"([^\"]+)\"[^>]*>(.*?)</h\1>", body, re.S
    ):
        headings.append(
            {
                "level": int(match.group(1)),
                "id": match.group(2),
                "text": strip_tags(match.group(3)),
            }
        )
    return body, headings


def rewrite_links(body: str, source_file: str, anchors: dict[str, set[str]]) -> str:
    def repl(match: re.Match) -> str:
        attr, raw = match.group(1), html.unescape(match.group(2))
        if not raw or raw.startswith(("#", "http://", "https://", "mailto:", "tel:", "javascript:", "/")):
            return match.group(0)

        path, sep, anchor = raw.partition("#")
        if not path:
            return match.group(0)

        normalized = os.path.normpath(
            os.path.join(os.path.dirname(source_file), path)
        ).replace("\\", "/")
        if normalized.startswith("../") or normalized.startswith("/"):
            return match.group(0)

        trailing = "/" if path.endswith("/") and not normalized.endswith("/") else ""
        if normalized in PAGE_BY_SOURCE:
            target = PAGE_BY_SOURCE[normalized]
            new = target
            if anchor:
                target_slug = target[:-5]
                if anchor in anchors.get(target_slug, set()):
                    new = f"{target}#{anchor}"
                else:
                    print(f"  aviso: âncora não encontrada em {target}: #{anchor}")
                    new = target
        else:
            new = f"../../{normalized}{trailing}"
            if sep:
                new = f"{new}#{anchor}"

        return f'{attr}="{esc(new)}"'

    return re.sub(r'(href|src)="([^"]*)"', repl, body)


def build_search_index(pages: list[dict]) -> list[dict]:
    entries: list[dict] = []
    for page in pages:
        body = page["html"]
        matches = list(
            re.finditer(r"<h([23])\s+id=\"([^\"]+)\"[^>]*>(.*?)</h\1>", body, re.S)
        )
        intro = body[: matches[0].start()] if matches else body
        intro_text = strip_tags(intro)
        if intro_text:
            entries.append(
                {
                    "page": page["slug"],
                    "pageLabel": page["nav"],
                    "id": "",
                    "title": "Introdução",
                    "text": intro_text[:220],
                }
            )
        for i, match in enumerate(matches):
            if match.group(1) != "2":
                continue
            end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
            text = strip_tags(body[match.end() : end])
            if len(text) > 220:
                text = text[:220].rsplit(" ", 1)[0] + "…"
            entries.append(
                {
                    "page": page["slug"],
                    "pageLabel": page["nav"],
                    "id": match.group(2),
                    "title": strip_tags(match.group(3)),
                    "text": text,
                }
            )
    return entries


def render_sidebar(current: dict) -> str:
    docs_items = []
    for page in PAGES:
        active = page["slug"] == current["slug"]
        docs_items.append(
            '<a class="sidebar-item{active}" href="{href}"{aria}>{icon}'
            "<span>{label}</span></a>".format(
                active=" is-active" if active else "",
                href=f'{page["slug"]}.html',
                aria=' aria-current="page"' if active else "",
                icon=icon(page["icon"]),
                label=esc(page["nav"]),
            )
        )

    project_items = [
        ("../../PRODUCT.md", "file-text", "Produto"),
        ("../../DESIGN.md", "palette", "Design"),
        ("../../_reversa_sdd/prd.md", "clipboard", "PRD"),
    ]
    reference_items = [
        ("../../docs/security_audit_findings.md", "shield", "Auditoria"),
        ("../frontend/", "monitor", "Frontend"),
    ]

    def group(label: str, items: list[tuple[str, str, str]]) -> str:
        links = []
        for href, icon_name, text in items:
            badge = (
                '<span class="item-badge" aria-hidden="true">MD</span>'
                if href.endswith(".md")
                else ""
            )
            links.append(
                '<a class="sidebar-item" href="{href}">{icon}<span>{text}</span>'
                "{badge}</a>".format(
                    href=esc(href),
                    icon=icon(icon_name),
                    text=esc(text),
                    badge=badge,
                )
            )
        return f'<p class="sidebar-group">{label}</p>' + "".join(links)

    return (
        '<aside class="docs-sidebar" id="docs-sidebar" aria-label="Navegação da documentação">'
        '<a class="sidebar-brand" href="index.html">'
        f'<span class="brand-mark">{icon("compass")}</span>'
        '<span class="brand-text"><span class="brand-name">Deep Research</span>'
        '<span class="brand-sub">Documentação técnica</span></span></a>'
        '<span class="sidebar-mode"><span class="mode-dot"></span> v0.1.0 · português</span>'
        '<nav class="sidebar-nav">'
        '<p class="sidebar-group">Documentação</p>'
        + "".join(docs_items)
        + group("Projeto", project_items)
        + group("Referência", reference_items)
        + "</nav>"
        '<div class="sidebar-footer">'
        '<div class="sidebar-version"><span>Versão do projeto</span><code>0.1.0</code></div>'
        f'<div class="sidebar-version"><span>{icon("shield")} HTML offline</span>'
        "<code>sem build</code></div>"
        "</div></aside>"
    )


def render_toc(headings: list[dict]) -> str:
    links = []
    for h in headings:
        if h["level"] != 2:
            continue
        links.append(
            f'<a class="toc-link" href="#{esc(h["id"])}">{esc(h["text"])}</a>'
        )
    if not links:
        return ""
    return (
        '<aside class="docs-toc" aria-label="Nesta página">'
        '<p class="toc-title">Nesta página</p>'
        "<nav>" + "".join(links) + "</nav></aside>"
    )


def render_mobile_toc(headings: list[dict]) -> str:
    links = [
        f'<a class="toc-link" href="#{esc(h["id"])}">{esc(h["text"])}</a>'
        for h in headings
        if h["level"] == 2
    ]
    if not links:
        return ""
    return (
        '<details class="mobile-toc"><summary>Nesta página</summary>'
        "<nav>" + "".join(links) + "</nav></details>"
    )


def render_steps() -> str:
    steps = []
    for icon_name, title, text in STEPS:
        steps.append(
            '<div class="docs-step">'
            f'<div class="docs-step-icon">{icon(icon_name)}</div>'
            f"<h3>{esc(title)}</h3><p>{esc(text)}</p></div>"
        )
    return '<div class="docs-steps">' + "".join(steps) + "</div>"


def render_pager(current: dict) -> str:
    idx = next(i for i, p in enumerate(PAGES) if p["slug"] == current["slug"])
    parts = []
    if idx > 0:
        prev = PAGES[idx - 1]
        parts.append(
            '<a class="pager-link prev" href="{href}">'
            '<span class="pager-label">Anterior</span>'
            '<span class="pager-title">{icon}{label}</span></a>'.format(
                href=f'{prev["slug"]}.html',
                icon=icon("chevron-left"),
                label=esc(prev["nav"]),
            )
        )
    if idx + 1 < len(PAGES):
        nxt = PAGES[idx + 1]
        parts.append(
            '<a class="pager-link next" href="{href}">'
            '<span class="pager-label">Próximo</span>'
            '<span class="pager-title">{label}{icon}</span></a>'.format(
                href=f'{nxt["slug"]}.html',
                icon=icon("chevron-right"),
                label=esc(nxt["nav"]),
            )
        )
    return '<div class="pager">' + "".join(parts) + "</div>"


TEMPLATE = """<!DOCTYPE html>
<html lang="pt-BR" data-theme="light">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{PAGE_TITLE}}</title>
<meta name="description" content="{{DESCRIPTION}}">
<meta name="color-scheme" content="light dark">
<meta name="theme-color" content="#7c3aed">
<link rel="icon" href="assets/favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="assets/docs.css">
<script>
(function () {
  try {
    if (localStorage.getItem("dr-docs-theme") === "dark") {
      document.documentElement.setAttribute("data-theme", "dark");
    }
  } catch (e) {}
})();
</script>
</head>
<body id="top">
<a class="skip-link" href="#main-content">Pular para o conteúdo</a>
{{SIDEBAR}}
<div class="sidebar-overlay" id="sidebar-overlay"></div>
<div class="docs-main">
<header class="docs-topbar">
  <button class="menu-toggle" id="menu-toggle" type="button" aria-label="Abrir navegação" aria-controls="docs-sidebar" aria-expanded="false">
    {{ICON_MENU}}
  </button>
  <nav class="breadcrumb" aria-label="Trilha de navegação">
    <a href="index.html" class="crumb-root">Documentação</a>
    <span class="crumb-separator" aria-hidden="true">/</span>
    <strong>{{PAGE_NAV}}</strong>
  </nav>
  <div class="topbar-actions">
    <button class="search-trigger" id="search-trigger" type="button" aria-label="Buscar na documentação">
      {{ICON_SEARCH}}
      <span class="search-label">Buscar na documentação</span>
      <kbd id="search-kbd">Ctrl K</kbd>
    </button>
    <button class="theme-toggle" type="button" data-theme-toggle aria-label="Alternar tema" title="Alternar tema">
      <span class="icon-moon">{{ICON_MOON}}</span>
      <span class="icon-sun">{{ICON_SUN}}</span>
    </button>
  </div>
  <div class="scroll-progress" aria-hidden="true"><span id="scroll-progress-bar"></span></div>
</header>

<div class="docs-layout">
<main class="docs-content" id="main-content">
  <header class="page-header">
    <div class="page-eyebrow">{{ICON_BOOK}} Documentação técnica</div>
    <h1 class="page-title">{{H1}}</h1>
    <p class="page-lead">{{LEAD}}</p>
    <div class="page-meta">
      <span class="chip chip-accent">{{ICON_TAG}} v0.1.0</span>
      <span class="chip">{{ICON_CLOCK}} Atualizado em {{DATE}}</span>
      <a class="chip chip-link" href="{{SOURCE}}">{{ICON_FILE}} Ver fonte Markdown</a>
    </div>
  </header>
  {{STEPS}}
  {{MOBILE_TOC}}
  <article class="markdown-body">
{{BODY}}
  </article>
  <footer class="page-footer">
    {{PAGER}}
    <a class="back-to-top" href="#top">{{ICON_UP}} Voltar ao topo</a>
  </footer>
</main>
{{TOC}}
</div>
</div>

<div class="search-overlay" id="search-overlay" aria-hidden="true">
  <div class="search-modal" role="dialog" aria-modal="true" aria-labelledby="search-title">
    <div class="search-field">
      {{ICON_SEARCH}}
      <label class="sr-only" id="search-title" for="search-input">Buscar na documentação</label>
      <input id="search-input" type="search" placeholder="Buscar seções, endpoints, variáveis…" autocomplete="off" spellcheck="false">
      <button class="search-close" id="search-close" type="button">ESC</button>
    </div>
    <div class="search-results" id="search-results" role="listbox" aria-label="Resultados da busca"></div>
    <div class="search-footer">
      <span><kbd>↑</kbd><kbd>↓</kbd> navegar</span>
      <span><kbd>Enter</kbd> abrir</span>
      <span><kbd>Esc</kbd> fechar</span>
      <span class="search-count" id="search-count"></span>
    </div>
  </div>
</div>

<script src="assets/search-index.js"></script>
<script src="assets/docs.js"></script>
</body>
</html>
"""


def sync_fonts() -> None:
    dist = ROOT / "frontend" / "dist" / "assets"
    FONTS.mkdir(parents=True, exist_ok=True)
    patterns = {
        "inter-400.woff2": "inter-latin-400-normal-*.woff2",
        "inter-500.woff2": "inter-latin-500-normal-*.woff2",
        "inter-600.woff2": "inter-latin-600-normal-*.woff2",
        "outfit-600.woff2": "outfit-latin-600-normal-*.woff2",
        "outfit-700.woff2": "outfit-latin-700-normal-*.woff2",
        "outfit-800.woff2": "outfit-latin-800-normal-*.woff2",
        "jetbrains-mono-400.woff2": "jetbrains-mono-latin-400-normal-*.woff2",
        "jetbrains-mono-500.woff2": "jetbrains-mono-latin-500-normal-*.woff2",
    }
    if not dist.exists():
        print("aviso: frontend/dist ausente; fontes não sincronizadas")
        return
    missing = []
    for target_name, pattern in patterns.items():
        candidates = sorted(dist.glob(pattern))
        if not candidates:
            missing.append(pattern)
            continue
        shutil.copyfile(candidates[0], FONTS / target_name)
    if missing:
        print("aviso: fontes não encontradas em frontend/dist: " + ", ".join(missing))


def write_favicon() -> None:
    svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
<rect width="32" height="32" rx="9" fill="#7c3aed"/>
<circle cx="16" cy="16" r="8.5" fill="none" stroke="#ffffff" stroke-width="1.8" opacity=".9"/>
<path d="M20.1 11.9 17.7 17.7 11.9 20.1 14.3 14.3Z" fill="#ffffff"/>
</svg>
"""
    (ASSETS / "favicon.svg").write_text(svg, encoding="utf-8")


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    sync_fonts()
    write_favicon()
    date = dt.date.today().strftime("%d/%m/%Y")

    pages = []
    for config in PAGES:
        source = ROOT / config["file"]
        text = source.read_text(encoding="utf-8")
        title, content = extract_page(text)
        body, headings = convert(content)
        pages.append(
            {
                **config,
                "title": title,
                "html": body,
                "headings": headings,
            }
        )

    anchors = {
        page["slug"]: {h["id"] for h in page["headings"]} for page in pages
    }
    for page in pages:
        page["html"] = rewrite_links(page["html"], page["file"], anchors)

    search_entries = build_search_index(pages)
    (ASSETS / "search-index.js").write_text(
        "window.DOCS_SEARCH_INDEX = "
        + json.dumps(search_entries, ensure_ascii=False, indent=0).replace(
            "</", "<\\/"
        )
        + ";\n",
        encoding="utf-8",
    )

    for page in pages:
        doc = TEMPLATE
        page_title = (
            "Deep Research — Documentação técnica"
            if page["slug"] == "index"
            else page["title"]
        )
        tokens = {
            "PAGE_TITLE": esc(page_title),
            "DESCRIPTION": esc(page["description"]),
            "SIDEBAR": render_sidebar(page),
            "ICON_MENU": icon("menu"),
            "ICON_SEARCH": icon("search"),
            "ICON_MOON": icon("moon"),
            "ICON_SUN": icon("sun"),
            "PAGE_NAV": esc(page["nav"]),
            "ICON_BOOK": icon("book-open"),
            "H1": esc(page["title"]),
            "LEAD": esc(page["description"]),
            "ICON_TAG": icon("tag"),
            "ICON_CLOCK": icon("clock"),
            "DATE": date,
            "SOURCE": esc(page["source"]),
            "ICON_FILE": icon("file-text"),
            "STEPS": render_steps() if page["slug"] == "index" else "",
            "MOBILE_TOC": render_mobile_toc(page["headings"]),
            "BODY": page["html"],
            "PAGER": render_pager(page),
            "ICON_UP": icon("arrow-up"),
            "TOC": render_toc(page["headings"]),
        }
        for key, value in tokens.items():
            doc = doc.replace("{{" + key + "}}", value)
        (OUT / f'{page["slug"]}.html').write_text(doc, encoding="utf-8")
        print(
            f'gerado {page["slug"]}.html  ({len(page["html"]):,} bytes de conteúdo)'
        )

    print(f"{len(search_entries)} seções no índice de busca")


if __name__ == "__main__":
    main()
