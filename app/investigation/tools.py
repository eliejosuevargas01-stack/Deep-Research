"""Jina Search adapter da investigação (T008, RN-05/RN-07/RN-08, RF-06/RF-07)."""

import asyncio
import math
from dataclasses import dataclass, field
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


def _collect_urls(node: object, out: list[str]) -> None:
    if isinstance(node, str):
        text = node.strip()
        if _valid_url(text) and text not in out:
            out.append(text)
        return
    if isinstance(node, dict):
        for key in ("url", "link", "href"):
            value = node.get(key)
            if isinstance(value, str) and _valid_url(value.strip()) and value.strip() not in out:
                out.append(value.strip())
        for value in node.values():
            _collect_urls(value, out)
        return
    if isinstance(node, (list, tuple)):
        for item in node:
            _collect_urls(item, out)


def _parse_body(body: object) -> JinaSearchResult:
    urls: list[str] = []
    _collect_urls(body, urls)
    items: list[object] = []
    if isinstance(body, dict):
        for key in ("data", "results", "items"):
            value = body.get(key)
            if isinstance(value, list):
                items = value
                break
    elif isinstance(body, list):
        items = body
    parts: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        for key in ("title", "description", "content", "text", "snippet"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                parts.append(value.strip())
    return JinaSearchResult(content="\n\n".join(parts), urls=urls)


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
                        json={"q": query},
                        headers=headers,
                        timeout=self._timeout,
                        follow_redirects=False,
                    )
            except (httpx.HTTPError, TimeoutError) as exc:
                raise _AttemptFailed from exc
            try:
                if response.status_code == 429 or 500 <= response.status_code <= 599:
                    raise _AttemptFailed(_retry_after_s(response.headers))
                if response.status_code in {401, 402, 403}:
                    from app.services.search import _duckduckgo_search
                    ddg_results = await _duckduckgo_search(query, 5)
                    if ddg_results:
                        urls = [s.url for s in ddg_results]
                        content = "\n\n".join(f"{s.title}\n{s.url}\n{s.excerpt}" for s in ddg_results)
                        return JinaSearchResult(content=content, urls=urls)
                if not 200 <= response.status_code < 300:
                    raise JinaSearchError(1)
                try:
                    body = response.json()
                except ValueError as exc:
                    raise _AttemptFailed from exc
                return _parse_body(body)
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
