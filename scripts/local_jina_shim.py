#!/usr/bin/env python3
"""Shim local compatível com a Jina (busca + leitura) para desenvolvimento.

Por que existe: os endpoints do Deep Research constroem um ``JinaClient`` que
exige ``JINA_API_KEY`` e usa duas rotas:

  * busca   -> ``GET {JINA_BASE_URL}/<query>``    (Accept: application/json)
  * leitura -> ``GET {JINA_READER_BASE_URL}/<url>`` (Accept: text/markdown)

Sem uma chave Jina válida nada roda localmente. Este shim expõe as duas rotas
no mesmo host, sem dependências externas:

  * ``/search/<query>`` -> SERP real (DuckDuckGo HTML; fallback para a API de
    busca da Wikipedia, que não tem rate-limit agressivo), com cache em disco
  * ``/read/<url>``     -> conteúdo real da página por extração própria de
    HTML; ``r.jina.ai`` (sem chave) só entra como reserva

O cache em ``scripts/.shim_cache/`` evita repetir consultas: o pipeline emite
dezenas de buscas por execução e o DuckDuckGo bloqueia rajadas com uma página
de desafio (HTTP 202). Quando isso acontece o provider entra em cooldown e as
consultas passam a ser resolvidas pela Wikipedia.

Uso:
    python3 scripts/local_jina_shim.py --port 8899

E no .env:
    JINA_API_KEY=shim-local
    JINA_BASE_URL=http://127.0.0.1:8899/search
    JINA_READER_BASE_URL=http://127.0.0.1:8899/read

Quando houver uma chave Jina real, basta remover as três linhas acima.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import pathlib
import re
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
DDG = "https://html.duckduckgo.com/html/?q="
SEZNAM = "https://search.seznam.cz/?q="
WIKI = "https://{lang}.wikipedia.org/w/api.php"
READER = "https://r.jina.ai/"

# Feeds usados como índice de notícias quando os buscadores bloqueiam a origem.
FEEDS = (
    "https://g1.globo.com/rss/g1/",
    "https://g1.globo.com/rss/g1/politica/",
    "https://g1.globo.com/rss/g1/tecnologia/",
    "https://g1.globo.com/rss/g1/economia/",
    "https://feeds.folha.uol.com.br/poder/rss.xml",
    "https://agenciabrasil.ebc.com.br/rss/geral/feed.xml",
    "https://rss.uol.com.br/feed/noticias.xml",
    "https://www.nexojornal.com.br/rss.xml",
    "https://www.poder360.com.br/feed/",
)
FEED_TTL = 20 * 60
# Hosts que não rendem texto jornalístico/utilizável para o reader.
HOSTS_DESCARTADOS = (
    "play.google", "books.google", "youtube.com", "youtu.be", "facebook.com",
    "instagram.com", "twitter.com", "x.com", "linkedin.com", "pinterest.",
    "tiktok.com", "amazon.", "mercadolivre.com", "shopee.", "ebay.",
)


def _url_util(url: str) -> bool:
    """Descarta URLs que o reader não consegue transformar em texto útil."""
    partes = urllib.parse.urlparse(url)
    if partes.scheme not in ("http", "https"):
        return False
    if partes.path.lower().endswith((".pdf", ".zip", ".rar", ".mp3", ".mp4", ".xls", ".xlsx")):
        return False
    return not any(chave in partes.netloc for chave in HOSTS_DESCARTADOS)
STOPWORDS = {
    "a", "o", "as", "os", "de", "da", "do", "das", "dos", "e", "ou", "em", "no", "na",
    "nos", "nas", "um", "uma", "para", "por", "com", "sobre", "que", "se", "ao", "aos",
    "como", "mais", "menos", "entre", "the", "of", "and", "to", "in", "on", "for",
}

CACHE_DIR = pathlib.Path(__file__).resolve().parent / ".shim_cache"
SEARCH_TTL = 24 * 3600
READ_TTL = 6 * 3600
MIN_INTERVAL = {"ddg": 2.0, "seznam": 1.5}
MIN_INTERVAL_HOST = 1.2  # espaçamento padrão por host

_LOCK = threading.Lock()
_LAST_CALL: dict[str, float] = {}
_COOLDOWN: dict[str, float] = {}


def _cached(kind: str, key: str, ttl: int, producer):
    CACHE_DIR.mkdir(exist_ok=True)
    digest = hashlib.sha1(f"{kind}:{key}".encode()).hexdigest()[:20]
    path = CACHE_DIR / f"{kind}-{digest}.json"
    if path.exists() and (time.time() - path.stat().st_mtime) < ttl:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # cache corrompido: refaz
            path.unlink(missing_ok=True)
    value = producer()
    if value:
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return value


def _throttle(host: str) -> None:
    """Espaça as chamadas por host e respeita o cooldown de quem bloqueou."""
    with _LOCK:
        limite = _COOLDOWN.get(host, 0.0)
        if limite > time.time():
            raise RuntimeError(f"{host} em cooldown")
        intervalo = MIN_INTERVAL.get(host, MIN_INTERVAL_HOST)
        espera = intervalo - (time.time() - _LAST_CALL.get(host, 0.0))
        if espera > 0:
            time.sleep(espera)
        _LAST_CALL[host] = time.time()


def _bloquear(host: str, segundos: float = 600.0) -> None:
    with _LOCK:
        _COOLDOWN[host] = time.time() + segundos


def _get(url: str, timeout: float, accept: str, extra: dict | None = None) -> tuple[int, str]:
    headers = {"User-Agent": UA, "Accept": accept}
    if extra:
        headers.update(extra)
    req = urllib.request.Request(url, headers=headers)
    for tentativa in (1, 2):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as res:
                return res.status, res.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 503) and tentativa == 1:
                time.sleep(3.0)  # rate-limit: uma pausa costuma bastar
                continue
            return exc.code, exc.read().decode("utf-8", "replace")
        except Exception:  # timeout, DNS, TLS: degrada para o próximo provider
            return 599, ""
    return 599, ""


def _clean(fragment: str) -> str:
    text = re.sub(r"<[^>]+>", "", fragment)
    return html.unescape(text).strip()


def _unwrap_ddg(href: str) -> str:
    if href.startswith("//"):
        href = "https:" + href
    parsed = urllib.parse.urlparse(href)
    if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
        target = urllib.parse.parse_qs(parsed.query).get("uddg", [""])[0]
        if target:
            return urllib.parse.unquote(target)
    return href


def _simplify(query: str) -> str:
    """Reduz consultas com operadores (site:, OR, aspas) a termos que o DDG aceita."""
    cleaned = re.sub(r"site:\S+", " ", query)
    cleaned = re.sub(r"\bOR\b", " ", cleaned)
    cleaned = cleaned.replace('"', " ").replace("(", " ").replace(")", " ")
    words = [w for w in cleaned.split() if w.strip(" -")]
    return " ".join(words[:12])


def _dedupe(items: list[dict], limit: int, por_dominio_max: int = 3) -> list[dict]:
    vistos_url: set[str] = set()
    por_dominio: dict[str, int] = {}
    saida: list[dict] = []
    for item in items:
        url = item.get("url", "")
        parsed = urllib.parse.urlparse(url)
        if not url.startswith("http") or parsed.path in ("", "/"):
            continue  # home de portal: pouco texto útil para o pipeline
        if "duckduckgo.com" in parsed.netloc:
            continue
        if url in vistos_url or por_dominio.get(parsed.netloc, 0) >= por_dominio_max:
            continue
        vistos_url.add(url)
        por_dominio[parsed.netloc] = por_dominio.get(parsed.netloc, 0) + 1
        saida.append(item)
        if len(saida) >= limit:
            break
    return saida


def _ddg(query: str, limit: int) -> list[dict]:
    try:
        _throttle("ddg")
    except RuntimeError:
        return []
    status, body = _get(DDG + urllib.parse.quote(query), 25, "text/html")
    if status >= 400 or not body:
        return []
    if "result__a" not in body:
        # página de desafio (202) ou nenhum resultado: libera o host por 10 min
        if "anomaly" in body or status in (202, 403):
            _bloquear("ddg")
        return []
    pattern = re.compile(
        r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>'
        r'.*?(?:<a[^>]+class="result__snippet"[^>]*>(.*?)</a>)?',
        re.S,
    )
    itens = [
        {"title": _clean(title), "url": _unwrap_ddg(href), "description": _clean(snippet or "")}
        for href, title, snippet in pattern.findall(body)
    ]
    return _dedupe(itens, limit)


def _wikipedia(query: str, limit: int) -> list[dict]:
    """Fallback sem chave e sem rate-limit: acha verbetes relacionados ao tema."""
    termo = _simplify(query) or query
    for lang in ("pt", "en"):
        try:
            _throttle("wiki")
        except RuntimeError:
            continue
        url = (
            f"{WIKI.format(lang=lang)}?action=query&list=search&format=json&srlimit={limit}"
            f"&srsearch={urllib.parse.quote(termo)}"
        )
        status, body = _get(url, 20, "application/json")
        if status >= 400 or not body.strip().startswith("{"):
            continue
        try:
            hits = json.loads(body).get("query", {}).get("search", [])
        except json.JSONDecodeError:
            continue
        itens = [
            {
                "title": hit.get("title", ""),
                "url": f"https://{lang}.wikipedia.org/wiki/{urllib.parse.quote(hit.get('title', '').replace(' ', '_'))}",
                "description": _clean(hit.get("snippet", "")),
            }
            for hit in hits
        ]
        if itens:
            # a Wikipedia concentra tudo no mesmo domínio: não limitar por domínio
            return _dedupe(itens, limit, por_dominio_max=limit)
    return []


def _fold(text: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFD", text.lower()) if unicodedata.category(ch) != "Mn"
    )


def _tokens(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]{3,}", _fold(text)) if w not in STOPWORDS]


def _feed_items(feed: str) -> list[dict]:
    try:
        _throttle(urllib.parse.urlparse(feed).netloc)
    except RuntimeError:
        return []
    status, body = _get(feed, 12, "application/rss+xml, application/xml;q=0.9, */*;q=0.8")
    if status >= 400 or "<item" not in body:
        return []
    itens: list[dict] = []
    for bloco in re.findall(r"<item>(.*?)</item>", body, re.S):
        titulo = re.search(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", bloco, re.S)
        link = re.search(r"<link>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</link>", bloco, re.S)
        desc = re.search(r"<description>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</description>", bloco, re.S)
        if not titulo or not link:
            continue
        if not _url_util(link.group(1).strip()):
            continue
        itens.append(
            {
                "title": _clean(titulo.group(1)),
                "url": link.group(1).strip(),
                "description": _clean(desc.group(1))[:400] if desc else "",
            }
        )
    return itens


def _seznam(query: str, limit: int) -> list[dict]:
    """Buscador server-rendered (Seznam) — funciona quando o DDG bloqueia a origem."""
    try:
        _throttle("seznam")
    except RuntimeError:
        return []
    status, body = _get(SEZNAM + urllib.parse.quote(query), 20, "text/html")
    if status >= 400 or "<h3" not in body:
        return []
    itens: list[dict] = []
    blocos = re.split(r"<h3", body)
    for bloco in blocos[1:]:
        achado = re.search(r'<a[^>]+href="(https?://[^"]+)"[^>]*>(.*?)</a>', bloco, re.S)
        if not achado:
            continue
        url = html.unescape(achado.group(1))
        host = urllib.parse.urlparse(url).netloc
        if "seznam.cz" in host or host.endswith("seznam.cz"):
            continue
        titulo = _clean(achado.group(2))
        if not titulo:
            continue
        resto = re.sub(r"<[^>]+>", " ", bloco[achado.end(): achado.end() + 900])
        if not _url_util(url):
            continue
        itens.append({"title": titulo, "url": url, "description": re.sub(r"\s+", " ", html.unescape(resto)).strip()[:400]})
        if len(itens) >= limit * 2:
            break
    return _dedupe(itens, limit)


def _noticias(query: str, limit: int) -> list[dict]:
    """Índice de notícias por palavra-chave (feeds RSS), para quando não há SERP."""
    alvo = set(_tokens(query))
    if not alvo:
        return []
    candidatos: list[tuple[int, dict]] = []
    for feed in FEEDS:
        for item in _cached("feed", feed, FEED_TTL, lambda f=feed: _feed_items(f)):
            titulo = set(_tokens(item["title"]))
            corpo = set(_tokens(item["description"]))
            casados = alvo & (titulo | corpo)
            score = 3 * len(alvo & titulo) + len(alvo & corpo)
            if score >= 3 and len(casados) >= 2:
                candidatos.append((score, item))
    candidatos.sort(key=lambda par: par[0], reverse=True)
    vistos: set[str] = set()
    saida: list[dict] = []
    for _, item in candidatos:
        if item["url"] in vistos:
            continue
        vistos.add(item["url"])
        saida.append(item)
        if len(saida) >= limit:
            break
    return saida


def serp(query: str, limit: int = 8) -> list[dict]:
    def produzir() -> list[dict]:
        for provider in (_ddg, _seznam, _noticias, _wikipedia):
            itens = provider(query, limit)
            if itens:
                return itens
        simples = _simplify(query)
        if simples and simples != query:
            for provider in (_seznam, _ddg, _noticias, _wikipedia):
                itens = provider(simples, limit)
                if itens:
                    return itens
        return []

    return _cached("search", f"{limit}:{query}", SEARCH_TTL, produzir)


def _html_to_text(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", raw)
    raw = re.sub(r"(?i)<br\s*/?>", "\n", raw)
    raw = re.sub(r"(?i)</(p|div|li|h[1-6]|tr)>", "\n", raw)
    text = html.unescape(re.sub(r"<[^>]+>", " ", raw))
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def _read_direct(target: str) -> str:
    try:
        _throttle(urllib.parse.urlparse(target).netloc)
    except RuntimeError:
        return ""
    status, raw = _get(target, 2.0, "text/html")
    if status < 400 and raw and len(raw) > 500:
        return _html_to_text(raw)
    return ""


def _read_reader(target: str) -> str:
    status, body = _get(READER + target, 12.0, "text/markdown")
    if status < 400 and body.strip():
        return body
    return ""


def read(target: str) -> tuple[int, str]:
    # r.jina.ai direto para resposta rápida e Markdown limpo; fallback rápido com _read_direct (2s).
    texto = _cached("read", target, READ_TTL, lambda: _read_reader(target) or _read_direct(target))
    if texto:
        return 200, texto
    return 502, f"falha ao ler {target}"


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args) -> None:  # noqa: A002, N802
        print(f"[shim] {self.command} {self.path[:110]} -> {args[1] if len(args) > 1 else ''}", flush=True)

    def _send(self, status: int, payload: str, content_type: str) -> None:
        data = payload.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        path = self.path
        if path.startswith("/search/"):
            query = urllib.parse.unquote(path[len("/search/"):])
            items = serp(query)
            body = json.dumps({"code": 200, "status": 20000, "data": items}, ensure_ascii=False)
            self._send(200, body, "application/json")
            return
        if path.startswith("/read/"):
            target = urllib.parse.unquote(path[len("/read/"):])
            if not target.startswith("http"):
                self._send(400, "url inválida", "text/plain")
                return
            status, text = read(target)
            self._send(status if status < 400 else 502, text, "text/markdown")
            return
        if path in ("/health", "/"):
            self._send(200, json.dumps({"status": "shim-ok"}), "application/json")
            return
        self._send(404, "not found", "text/plain")


def main() -> None:
    parser = argparse.ArgumentParser(description="Shim local Jina (search + reader)")
    parser.add_argument("--port", type=int, default=8899)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"shim Jina em http://127.0.0.1:{args.port}  (/search/<q>, /read/<url>)", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
