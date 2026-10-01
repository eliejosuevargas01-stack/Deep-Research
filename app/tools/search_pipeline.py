import asyncio
import html
import json
import re
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
            async with client.post(endpoint, headers={"Authorization": f"Bearer {token}"},
                                   json={"queries": query, "maxPagesPerQuery": 1, "resultsPerPage": limit},
                                   allow_redirects=False) as response:
                if response.status >= 300:
                    raise SearchProviderError(f"Apify returned HTTP {response.status}")
                payload = await response.json()
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as exc:
        raise SearchProviderError("Apify search failed") from exc
    if not isinstance(payload, list):
        raise SearchProviderError("Apify returned invalid dataset")
    return [Source(item["url"], item.get("title", ""), item.get("description", ""))
            for page in payload if isinstance(page, dict)
            for item in page.get("organicResults", []) if isinstance(item, dict)
            and isinstance(item.get("url"), str) and _safe(item["url"])][:limit]


async def search(query: str, limit: int = 8, keys: dict[str, str] | None = None) -> list[Source]:
    keys = keys or {}
    if keys.get("serpapi"):
        try:
            params = urlencode({"q": query, "engine": "google", "num": limit, "api_key": keys["serpapi"]})
            status, text = await _get(f"https://serpapi.com/search.json?{params}")
            if status >= 300:
                raise SearchProviderError(f"SerpAPI returned HTTP {status}")
            payload = json.loads(text)
            results = [Source(item["link"], item.get("title", ""), item.get("snippet", "")) for item in payload.get("organic_results", [])[:limit] if item.get("link") and _safe(item["link"])]
            if results:
                return results
        except (SearchProviderError, ValueError, KeyError, TypeError):
            pass
    if keys.get("apify"):
        try:
            results = await _apify_search(query, limit, keys["apify"])
            if results:
                return results
        except SearchProviderError:
            pass
    headers = {"Accept": "text/plain", "X-Return-Format": "markdown"}
    if keys.get("jina"):
        headers["Authorization"] = f"Bearer {keys['jina']}"
    status, text = await _get(f"https://s.jina.ai/{quote(query, safe='')}", headers)
    if status >= 300:
        raise SearchProviderError(f"Search provider returned HTTP {status}; configure SerpAPI or Jina key")
    found, seen = [], set()
    for title, url in re.findall(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", text):
        if url not in seen and _safe(url):
            seen.add(url)
            found.append(Source(url, title.strip(), ""))
        if len(found) >= limit:
            break
    return found


def _safe(url: str) -> bool:
    try:
        validate_public_url(url)
        return True
    except ValueError:
        return False


async def read_source(source: Source) -> Source | None:
    validate_public_url(source.url)
    status, body = await _get(source.url, {"User-Agent": "DeepResearchBot/1.0", "Accept": "text/html,text/plain"})
    if status >= 300:
        return None
    body = re.sub(r"(?is)<(script|style|noscript).*?>.*?</\1>", " ", body)
    text = html.unescape(re.sub(r"(?s)<[^>]+>", " ", body))
    text = re.sub(r"\s+", " ", text).strip()
    return Source(source.url, source.title, text[:8000]) if text else None


async def search_read(query: str, limit: int = 8, keys: dict[str, str] | None = None) -> list[Source]:
    results = await search(query, min(10, max(5, limit)), keys)
    pages = await asyncio.gather(*(read_source(item) for item in results), return_exceptions=True)
    return [page for page in pages if isinstance(page, Source)]
