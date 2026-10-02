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


async def _get(endpoint: str, headers: dict[str, str] | None = None) -> tuple[int, str]:
    timeout = aiohttp.ClientTimeout(total=settings.SEARCH_TIMEOUT_SECONDS)
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


async def _duckduckgo_search(query: str, limit: int = 8) -> list[Source]:
    """Free, reliable fallback search using Jina-proxied DuckDuckGo or direct DuckDuckGo."""
    timeout = aiohttp.ClientTimeout(total=settings.SEARCH_TIMEOUT_SECONDS)
    connector = aiohttp.TCPConnector(resolver=PinnedResolver(), use_dns_cache=False)

    # 1. Try Jina Reader proxy of DuckDuckGo HTML (bypasses datacenter VPS anti-bot challenges)
    try:
        q_enc = quote(query)
        jina_ddg_url = f"https://r.jina.ai/https://html.duckduckgo.com/html/?q={q_enc}"
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


async def search(query: str, limit: int = 8, keys: dict[str, str] | None = None) -> list[Source]:
    keys = keys or {}
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
        status, text = await _get(f"https://s.jina.ai/{quote(query, safe='')}", headers)
        if status < 300:
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
    ddg_results = await _duckduckgo_search(query, limit)
    return ddg_results


def _safe(url: str) -> bool:
    try:
        validate_public_url(url)
        return True
    except ValueError:
        return False


async def read_source(source: Source) -> Source | None:
    if not _safe(source.url):
        return None

    # 1. Try Jina Reader first for clean markdown extraction
    try:
        jina_url = f"https://r.jina.ai/{source.url}"
        status, text = await _get(jina_url, {"User-Agent": "Mozilla/5.0", "Accept": "text/plain"})
        if status == 200 and text and len(text.strip()) > 50:
            clean = re.sub(r"\s+", " ", text).strip()
            return Source(source.url, source.title, clean[:8000])
    except Exception:
        pass

    # 2. Fallback to direct HTML scrape
    try:
        status, body = await _get(source.url, {"User-Agent": "DeepResearchBot/1.0", "Accept": "text/html,text/plain"})
        if status < 300 and body:
            body = re.sub(r"(?is)<(script|style|noscript).*?>.*?</\1>", " ", body)
            text = html.unescape(re.sub(r"(?s)<[^>]+>", " ", body))
            text = re.sub(r"\s+", " ", text).strip()
            if text:
                return Source(source.url, source.title, text[:8000])
    except Exception:
        pass

    return None


async def search_read(query: str, limit: int = 8, keys: dict[str, str] | None = None) -> list[Source]:
    results = await search(query, min(10, max(5, limit)), keys)
    pages = await asyncio.gather(*(read_source(item) for item in results), return_exceptions=True)
    return [page for page in pages if isinstance(page, Source)]
