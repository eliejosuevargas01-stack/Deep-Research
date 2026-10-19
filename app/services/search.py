import asyncio
import html
import json
import re
import urllib.parse
from dataclasses import dataclass
from urllib.parse import quote, urlencode
import aiohttp
from app.core.config import settings
from app.tools.outbound import PinnedResolver, validate_public_url


@dataclass
class Source:
    url: str
    title: str
    excerpt: str


class SearchProviderError(RuntimeError):
    pass


async def _get(endpoint: str, headers: dict[str, str] | None = None, timeout_seconds: int | None = None) -> tuple[int, str]:
    timeout_val = timeout_seconds or settings.SEARCH_TIMEOUT_SECONDS
    timeout = aiohttp.ClientTimeout(total=timeout_val)
    connector = aiohttp.TCPConnector(resolver=PinnedResolver(), use_dns_cache=True)
    try:
        async with aiohttp.ClientSession(timeout=timeout, connector=connector, headers=headers, trust_env=False) as client:
            async with client.get(endpoint, allow_redirects=False) as response:
                return response.status, await response.text(errors="replace")
    except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
        raise SearchProviderError("Outbound provider request failed") from exc


async def _apify_search(query: str, limit: int, token: str) -> list[Source]:
    endpoint = "https://api.apify.com/v2/acts/apify~google-search-scraper/run-sync-get-dataset-items"
    timeout = aiohttp.ClientTimeout(total=settings.SEARCH_TIMEOUT_SECONDS)
    connector = aiohttp.TCPConnector(resolver=PinnedResolver(), use_dns_cache=False)
    try:
        async with aiohttp.ClientSession(timeout=timeout, connector=connector, trust_env=False) as client:
            async with client.post(
                endpoint,
                headers={"Authorization": f"Bearer {token}"},
                json={"queries": query, "maxPagesPerQuery": 1, "resultsPerPage": limit},
                allow_redirects=False,
            ) as response:
                if response.status >= 300:
                    raise SearchProviderError(f"Apify returned HTTP {response.status}")
                payload = await response.json()
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as exc:
        raise SearchProviderError("Apify search failed") from exc
    if not isinstance(payload, list):
        raise SearchProviderError("Apify returned invalid dataset")
    return [
        Source(item["url"], item.get("title", ""), item.get("description", ""))
        for page in payload
        if isinstance(page, dict)
        for item in page.get("organicResults", [])
        if isinstance(item, dict) and isinstance(item.get("url"), str) and _safe(item["url"])
    ][:limit]


async def _duckduckgo_search(query: str, limit: int = 8, jina_base_url: str | None = None) -> list[Source]:
    """Free, reliable fallback search using Jina-proxied DuckDuckGo or direct DuckDuckGo."""
    timeout = aiohttp.ClientTimeout(total=settings.SEARCH_TIMEOUT_SECONDS)
    connector = aiohttp.TCPConnector(resolver=PinnedResolver(), use_dns_cache=False)
    jina_base = (jina_base_url or DEFAULT_JINA_BASE_URL).rstrip("/")

    # 1. Try Jina Reader proxy of DuckDuckGo HTML (bypasses datacenter VPS anti-bot challenges)
    try:
        q_enc = quote(query)
        jina_ddg_url = f"{jina_base}/https://html.duckduckgo.com/html/?q={q_enc}"
        headers = {"User-Agent": "Mozilla/5.0", "Accept": "text/plain"}
        async with aiohttp.ClientSession(timeout=timeout, connector=connector, trust_env=False) as client:
            async with client.get(jina_ddg_url, headers=headers, allow_redirects=False) as resp:
                if resp.status == 200:
                    text = await resp.text(errors="replace")
                    items = re.findall(r"##\s*\[(.*?)\]\((https?://duckduckgo\.com/l/\?uddg=[^\s\)]+)", text)
                    results = []
                    seen = set()
                    for title, ddg_url in items:
                        real_url = urllib.parse.unquote(ddg_url.split("uddg=")[1].split("&")[0])
                        if not real_url.startswith(("http://", "https://")) or not _safe(real_url):
                            continue
                        if real_url in seen:
                            continue
                        seen.add(real_url)
                        clean_title = re.sub(r"<[^>]+>", "", title).strip()
                        results.append(Source(real_url, clean_title, ""))
                        if len(results) >= limit:
                            break
                    if results:
                        return results
    except Exception:
        pass

    # 2. Direct DuckDuckGo HTML POST fallback
    try:
        endpoint = "https://html.duckduckgo.com/html/"
        data = {"q": query}
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }
        async with aiohttp.ClientSession(timeout=timeout, connector=connector, trust_env=False) as client:
            async with client.post(endpoint, data=data, headers=headers, allow_redirects=False) as response:
                if response.status < 300:
                    text = await response.text(errors="replace")
                    matches = re.findall(
                        r'<a[^>]+class=[\'"][^\'"]*result__a[^\'"]*[\'"][^>]+href=[\'"]([^\'"]+)[\'"][^>]*>(.*?)</a>',
                        text,
                        re.S,
                    )
                    snippets = re.findall(r'<a[^>]+class=[\'"][^\'"]*result__snippet[^\'"]*[\'"][^>]*>(.*?)</a>', text, re.S)
                    results = []
                    seen = set()
                    for i, (href, title) in enumerate(matches):
                        real_url = href
                        if "uddg=" in href:
                            real_url = urllib.parse.unquote(href.split("uddg=")[1].split("&")[0])
                        if not real_url.startswith(("http://", "https://")) or not _safe(real_url):
                            continue
                        if real_url in seen:
                            continue
                        seen.add(real_url)
                        snip = re.sub(r"<[^>]+>", "", snippets[i]).strip() if i < len(snippets) else ""
                        clean_title = re.sub(r"<[^>]+>", "", title).strip()
                        results.append(Source(real_url, clean_title, snip))
                        if len(results) >= limit:
                            break
                    if results:
                        return results
    except Exception:
        pass

    return []


DEFAULT_JINA_BASE_URL = "https://r.jina.ai"


def _parse_search_payload(text: str) -> list[tuple[str, str]]:
    """Parse worker/jina search response: JSON array or markdown links."""
    stripped = text.strip()
    if stripped.startswith(("{", "[")):
        try:
            payload = json.loads(stripped)
            items = payload if isinstance(payload, list) else payload.get("results", payload.get("data", []))
            pairs = []
            for item in items if isinstance(items, list) else []:
                if not isinstance(item, dict):
                    continue
                url = item.get("url") or item.get("link") or ""
                title = item.get("title") or ""
                if isinstance(url, str) and url.startswith(("http://", "https://")):
                    pairs.append((title, url))
            return pairs
        except (ValueError, TypeError):
            pass
    return re.findall(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", text)


async def _proxy_get(
    proxy_url: str,
    path: str,
    proxy_auth: str | None = None,
    timeout_seconds: int = 20,
) -> tuple[int, str]:
    headers = {"Accept": "text/plain"}
    if proxy_auth:
        headers["Authorization"] = f"Bearer {proxy_auth}"
    endpoint = f"{proxy_url.rstrip('/')}/{path}"
    return await _get(endpoint, headers, timeout_seconds=timeout_seconds)


async def search(
    query: str,
    limit: int = 8,
    keys: dict[str, str] | None = None,
    jina_base_url: str | None = None,
    jina_proxy_url: str | None = None,
    jina_proxy_auth: str | None = None,
    jina_proxy_timeout: int = 20,
) -> list[Source]:
    keys = keys or {}
    jina_base = (jina_base_url or DEFAULT_JINA_BASE_URL).rstrip("/")

    # 0. Jina Proxy Worker (Cloudflare): single static endpoint, search + read
    if jina_proxy_url:
        try:
            q_enc = quote(query, safe="")
            status, text = await _proxy_get(jina_proxy_url, f"?q={q_enc}", jina_proxy_auth, jina_proxy_timeout)
            if status < 300 and text.strip():
                found, seen = [], set()
                for title, url in _parse_search_payload(text):
                    if url not in seen and _safe(url):
                        seen.add(url)
                        found.append(Source(url, title.strip(), ""))
                    if len(found) >= limit:
                        break
                if found:
                    return found
        except Exception:
            pass  # graceful degradation: fall through to direct Jina

    if keys.get("serpapi"):
        try:
            params = urlencode({"q": query, "engine": "google", "num": limit, "api_key": keys["serpapi"]})
            status, text = await _get(f"https://serpapi.com/search.json?{params}")
            if status < 300:
                payload = json.loads(text)
                results = [
                    Source(item["link"], item.get("title", ""), item.get("snippet", ""))
                    for item in payload.get("organic_results", [])[:limit]
                    if item.get("link") and _safe(item["link"])
                ]
                if results:
                    return results
        except Exception:
            pass

    if keys.get("apify"):
        try:
            results = await _apify_search(query, limit, keys["apify"])
            if results:
                return results
        except Exception:
            pass

    # 3. Try Jina Search (with key if available, or free endpoint)
    try:
        headers = {"Accept": "text/plain", "X-Return-Format": "markdown"}
        if keys.get("jina"):
            headers["Authorization"] = f"Bearer {keys['jina']}"
        status, text = await _get(f"{jina_base}/{quote(query, safe='')}", headers)
        if status in {401, 402, 403} and keys.get("jina"):
            pass
        elif status < 300:
            found, seen = [], set()
            for title, url in re.findall(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", text):
                if url not in seen and _safe(url):
                    seen.add(url)
                    found.append(Source(url, title.strip(), ""))
                if len(found) >= limit:
                    break
            if found:
                return found
    except Exception:
        pass

    # 4. Free fallback when no search API key is provided or paid providers return errors:
    ddg_results = await _duckduckgo_search(query, limit, jina_base_url=jina_base_url)
    return ddg_results


def _safe(url: str) -> bool:
    try:
        validate_public_url(url)
        return True
    except ValueError:
        return False


MAX_SOURCE_CHARS = 50000  # full page cap; LLM selects the relevant verbatim excerpt (decision LACUNA 3)


async def read_source(
    source: Source,
    jina_base_url: str | None = None,
    jina_api_key: str | None = None,
    jina_proxy_url: str | None = None,
    jina_proxy_auth: str | None = None,
    jina_proxy_timeout: int = 20,
) -> Source | None:
    if not _safe(source.url):
        return None

    # 0. Jina Proxy Worker (Cloudflare): path /r/{url}
    if jina_proxy_url:
        try:
            status, text = await _proxy_get(
                jina_proxy_url,
                f"r/{source.url}",
                jina_proxy_auth,
                jina_proxy_timeout,
            )
            if status == 200 and text and len(text.strip()) > 50:
                clean = re.sub(r"\s+", " ", text).strip()
                return Source(source.url, source.title, clean[:MAX_SOURCE_CHARS])
        except Exception:
            pass  # graceful degradation: fallback to direct Jina reader / scrape

    # 1. Try Jina Reader first for clean markdown extraction
    try:
        jina_base = (jina_base_url or DEFAULT_JINA_BASE_URL).rstrip("/")
        jina_url = f"{jina_base}/{source.url}"
        headers = {"User-Agent": "Mozilla/5.0", "Accept": "text/plain"}
        if jina_api_key:
            headers["Authorization"] = f"Bearer {jina_api_key}"
        status, text = await _get(jina_url, headers)
        if status in {401, 402, 403} and jina_api_key:
            headers.pop("Authorization", None)
            status, text = await _get(jina_url, headers)
        if status == 200 and text and len(text.strip()) > 50:
            clean = re.sub(r"\s+", " ", text).strip()
            return Source(source.url, source.title, clean[:MAX_SOURCE_CHARS])
    except Exception:
        pass

    # 2. Fallback to direct HTML scrape
    try:
        status, body = await _get(source.url, {"User-Agent": "DeepResearchBot/1.0", "Accept": "text/html,text/plain"})
        if status < 300 and body:
            body = re.sub(r"(?is)<(script|style|noscript).*?>.*?</\\1>", " ", body)
            text = html.unescape(re.sub(r"(?s)<[^>]+>", " ", body))
            text = re.sub(r"\s+", " ", text).strip()
            if text:
                return Source(source.url, source.title, text[:MAX_SOURCE_CHARS])
    except Exception:
        pass

    return None


async def search_read(
    query: str,
    limit: int = 8,
    keys: dict[str, str] | None = None,
    jina_base_url: str | None = None,
    jina_proxy_url: str | None = None,
    jina_proxy_auth: str | None = None,
    jina_proxy_timeout: int = 20,
) -> list[Source]:
    keys = keys or {}
    results = await search(
        query,
        min(10, max(5, limit)),
        keys,
        jina_base_url=jina_base_url,
        jina_proxy_url=jina_proxy_url,
        jina_proxy_auth=jina_proxy_auth,
        jina_proxy_timeout=jina_proxy_timeout,
    )
    pages = await asyncio.gather(
        *(
            asyncio.wait_for(
                read_source(
                    item,
                    jina_base_url=jina_base_url,
                    jina_api_key=keys.get("jina"),
                    jina_proxy_url=jina_proxy_url,
                    jina_proxy_auth=jina_proxy_auth,
                    jina_proxy_timeout=jina_proxy_timeout,
                ),
                timeout=20.0,
            )
            for item in results
        ),
        return_exceptions=True,
    )
    return [page for page in pages if isinstance(page, Source)]
