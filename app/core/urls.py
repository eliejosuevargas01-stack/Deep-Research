"""Sanitização de URLs de fonte lidas dos logs e dos artefatos dos subagentes.

O log bruto do Hermes carrega HTML/JSON escapado; sem limpeza entram no SSE
`https://^`, `https:///;`, `https://{host}/w/api.php?` e
`https://epe.gov.br/relatorio\\nAirbnb`.
"""

from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urlsplit, urlunsplit

_ESCAPE_LITERAL = re.compile(r"\\[nrt]")
_PONTUACAO_FINAL = ".,;:!?)]}\"'"
_HOST_INVALIDO = re.compile(r"[\s^/{};\\<>|@]")
_TLD = re.compile(r"^[a-z]{2,24}$")
_BUSCA_INTERNA = {"duckduckgo.com", "mojeek.com", "html.duckduckgo.com"}


def sanitizar_url_fonte(raw: object) -> Optional[str]:
    """URL http(s) de fonte confiável, ou None quando o candidato é lixo."""
    if not isinstance(raw, str):
        return None
    texto = raw.strip()
    if not texto:
        return None
    # Escape literal (`\n` de JSON dentro de log) ou espaço encerram a URL.
    texto = _ESCAPE_LITERAL.split(texto, 1)[0].strip()
    if not texto:
        return None
    texto = texto.split()[0].lstrip("([{'\"<").rstrip(_PONTUACAO_FINAL)
    if not texto:
        return None
    try:
        partes = urlsplit(texto)
        porta = partes.port
    except ValueError:
        return None
    if partes.scheme.lower() not in ("http", "https"):
        return None
    host = (partes.hostname or "").strip().lower().rstrip(".")
    if not host or _HOST_INVALIDO.search(host) or "." not in host:
        return None
    if not _TLD.match(host.rsplit(".", 1)[1]):
        return None
    if host in _BUSCA_INTERNA or host.endswith(".duckduckgo.com") or host.endswith(".mojeek.com"):
        return None
    if "/w/api.php" in (partes.path or "").lower():
        return None
    autoridade = host if porta in (None, 80, 443) else f"{host}:{porta}"
    return urlunsplit((partes.scheme.lower(), autoridade, partes.path or "/", partes.query, ""))


def sanitizar_urls(brutas) -> list[str]:
    """Lista estável e sem repetição das URLs válidas de um conjunto bruto."""
    vistos: set[str] = set()
    for bruta in brutas or []:
        limpa = sanitizar_url_fonte(bruta)
        if limpa:
            vistos.add(limpa)
    return sorted(vistos)
