"""Jina Search adapter da investigação (T008, RN-05/RN-07/RN-08, RF-06/RF-07)."""

import asyncio
import html
from html.parser import HTMLParser
import math
from dataclasses import dataclass, field
from functools import lru_cache
import ipaddress
import socket
from urllib.parse import urlparse

import httpx

ENDPOINT = "https://s.jina.ai/"
MAX_ATTEMPTS = 3
_BACKOFFS = (2.0, 4.0)


class JinaSearchError(Exception):
    """Falha segura da busca Jina (sem segredos, sem URLs)."""

    def __init__(self, attempts: int):
        super().__init__(f"Busca Jina indisponível após {attempts} tentativas")
        self.attempts = attempts


@dataclass
class JinaSearchResult:
    content: str
    urls: list[str] = field(default_factory=list)


def _valid_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = urlparse(value.strip())
    except ValueError:
        return False
    return parsed.scheme in ("http", "https") and bool(parsed.hostname)


@lru_cache(maxsize=1024)
def _check_host_safe(host: str, scheme: str, port: int | None) -> bool:
    try:
        ip = ipaddress.ip_address(host)
        return not (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified)
    except ValueError:
        pass
    if host.lower() == "localhost":
        return False
    try:
        addresses = {str(item[4][0]) for item in socket.getaddrinfo(host, port or (443 if scheme == "https" else 80), type=socket.SOCK_STREAM)}
    except Exception:
        return False
    if not addresses:
        return False
    for raw in addresses:
        try:
            ip = ipaddress.ip_address(raw)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
                return False
        except ValueError:
            return False
    return True


def _is_safe_url(value: object) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    u = value.strip()
    try:
        parsed = urlparse(u)
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return False
    if parsed.username or parsed.password:
        return False
    if parsed.port and parsed.port not in (80, 443):
        return False
    return _check_host_safe(parsed.hostname, parsed.scheme, parsed.port)


class _JinaHTMLCleaner(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_lower = tag.lower()
        attr_dict = dict(attrs)
        if tag_lower in {"header", "nav", "script", "style", "footer"}:
            self._skip += 1
        elif tag_lower == "aside":
            cls = (attr_dict.get("class") or "").lower()
            aria = (attr_dict.get("aria-label") or "").lower()
            if any(k in cls or k in aria for k in ("ad", "advertisement")):
                self._skip += 1

    def handle_endtag(self, tag: str) -> None:
        tag_lower = tag.lower()
        if tag_lower in {"header", "nav", "script", "style", "footer"} and self._skip > 0:
            self._skip -= 1
        elif tag_lower == "aside" and self._skip > 0:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if self._skip == 0:
            self.parts.append(data)


def _clean_body_text(text: str) -> str:
    if "<" not in text and ">" not in text and "&" not in text:
        return text
    parser = _JinaHTMLCleaner()
    parser.feed(text)
    raw = "".join(parser.parts)
    return html.unescape(raw)


def _parse_body(body: object, query: str = "") -> JinaSearchResult:
    items: list[object] = []
    if isinstance(body, dict):
        for key in ("data", "results", "items"):
            value = body.get(key)
            if isinstance(value, list):
                items = value
                break
    elif isinstance(body, list):
        items = body

    if not isinstance(items, list) or len(items) < 10:
        raise JinaSearchError(1)

    urls: list[str] = []
    sections: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            raise JinaSearchError(1)
        status = item.get("status")
        if isinstance(status, int) and status >= 400:
            raise JinaSearchError(1)
        url = item.get("url") or item.get("link")
        if not isinstance(url, str) or not _is_safe_url(url):
            raise JinaSearchError(1)
        raw_content = item.get("content")
        if not isinstance(raw_content, str) or not raw_content.strip():
            raise JinaSearchError(1)
        if url not in urls:
            urls.append(url)
        clean = _clean_body_text(raw_content)
        title = item.get("title", "")
        sections.append(f"## {title}\nURL: {url}\n\n{clean}\n\n")

    prefix = f"Consulta: {query}\n\n" if query else ""
    full_content = prefix + "".join(sections)
    return JinaSearchResult(content=full_content, urls=urls)


class _AttemptFailed(Exception):
    def __init__(self, retry_after: float | None = None):
        super().__init__("attempt failed")
        self.retry_after = retry_after


# ponytail: Retry-After só aceita segundos numéricos (formato HTTP-date ignorado);
# tratar parsedate_to_datetime se algum provedor enviar data.
def _retry_after_s(headers: httpx.Headers) -> float | None:
    raw = headers.get("retry-after")
    if raw is None:
        return None
    try:
        value = float(raw.strip())
    except (ValueError, AttributeError):
        return None
    if not math.isfinite(value) or value <= 0:
        return None
    return min(value, 60.0)


class JinaToolAdapter:
    """Transporte POST s.jina.ai (ou proxy), timeout 90s, 3 tentativas, read_urls integral."""

    def __init__(
        self,
        api_key: str,
        proxy_url: str | None = None,
        proxy_key: str | None = None,
        timeout: float = 90.0,
        http_client: httpx.AsyncClient | None = None,
    ):
        if not isinstance(api_key, str) or not api_key:
            raise ValueError("Chave de API inválida")
        if not all(33 <= ord(ch) <= 126 for ch in api_key):
            raise ValueError("Chave de API inválida")
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
            raise ValueError("Timeout inválido")
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("Timeout inválido")
        if proxy_url is not None and (not isinstance(proxy_url, str) or not proxy_url.strip()):
            raise ValueError("URL de proxy inválida")
        self._api_key = api_key
        self._proxy_url = proxy_url.strip() if isinstance(proxy_url, str) and proxy_url else None
        self._proxy_key = proxy_key
        self._timeout = float(timeout)
        self._http_client = http_client

    async def search(self, query: str) -> JinaSearchResult:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("Query inválida")
        q = query.strip()
        url = self._proxy_url or ENDPOINT
        token = self._proxy_key or self._api_key
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Engine": "direct",
        }
        attempts = 0
        last: Exception | None = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            attempts = attempt
            try:
                return await self._single_attempt(url, q, headers)
            except asyncio.CancelledError:
                raise
            except _AttemptFailed as exc:
                last = exc
                if attempt < MAX_ATTEMPTS:
                    delay = exc.retry_after
                    if delay is None:
                        delay = _BACKOFFS[attempt - 1] if attempt - 1 < len(_BACKOFFS) else _BACKOFFS[-1]
                    await asyncio.sleep(delay)
        raise JinaSearchError(attempts) from last

    async def _single_attempt(self, url: str, query: str, headers: dict[str, str]) -> JinaSearchResult:
        owned = self._http_client is None
        client = httpx.AsyncClient() if owned else self._http_client
        assert client is not None
        try:
            try:
                async with asyncio.timeout(self._timeout):
                    response = await client.post(
                        url,
                        json={"q": query, "num": 10},
                        headers=headers,
                        timeout=self._timeout,
                        follow_redirects=False,
                    )
            except (httpx.HTTPError, TimeoutError) as exc:
                raise _AttemptFailed from exc
            try:
                if response.status_code == 429 or 500 <= response.status_code <= 599:
                    raise _AttemptFailed(_retry_after_s(response.headers))
                if not 200 <= response.status_code < 300:
                    raise JinaSearchError(1)
                try:
                    body = response.json()
                except ValueError as exc:
                    raise _AttemptFailed from exc
                return _parse_body(body, query=query)
            finally:
                try:
                    await response.aclose()
                except (AttributeError, RuntimeError):
                    pass
        except JinaSearchError:
            raise
        except asyncio.CancelledError:
            raise
        except _AttemptFailed:
            raise
        except Exception as exc:
            raise exc
        finally:
            if owned:
                await client.aclose()
