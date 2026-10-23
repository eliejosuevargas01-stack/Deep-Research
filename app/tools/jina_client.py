"""Cliente HTTP assíncrono para integração com Jina Search (SERP) e Jina Reader.

Conecta a s.jina.ai para consultas SERP isolando metadados (RN-03, DT-06)
e a r.jina.ai para raspagem integral em Markdown (RN-05).
Implementa política de 1 tentativa inicial + 3 retries com backoff exponencial
e timeout de 600 segundos (RNF-02, RNF-03, DT-11).
"""

import asyncio
import os
import urllib.parse
from typing import Any, Dict, List, Optional
import httpx
from app.config import get_settings
from app.tools.errors import JinaError, classify_failure


def _normalize_base_url(url: Optional[str], default: str) -> str:
    raw = (url or "").strip()
    if not raw:
        return default.rstrip("/")
    if not raw.startswith(("http://", "https://")):
        raw = f"https://{raw}"
    return raw.rstrip("/")


class JinaClient:
    """Cliente assíncrono para os serviços Jina SERP e Jina Reader."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        search_base_url: Optional[str] = None,
        reader_base_url: Optional[str] = None,
        transport: Optional[httpx.AsyncBaseTransport] = None,
        client: Optional[httpx.AsyncClient] = None,
        timeout: float = 600.0,
        min_backoff: float = 0.01,
    ) -> None:
        settings = get_settings()
        resolved_key = (
            api_key
            or settings.jina_api_key
            or os.environ.get("Jina_API_KEY")
            or os.environ.get("JINA_API_KEY")
        )
        if not resolved_key or not str(resolved_key).strip():
            raise ValueError("Configuração ausente: JINA_API_KEY não informada no ambiente.")
        self.api_key = str(resolved_key).strip()

        # ponytail: endpoints s.jina.ai e r.jina.ai definidos nas specs SDD; altere via search_base_url/reader_base_url para proxy/gateway
        base = base_url or settings.jina_base_url or os.environ.get("JINA_BASE_URL")
        self.search_base_url = _normalize_base_url(
            search_base_url
            or (base if base else None)
            or os.environ.get("JINA_SEARCH_BASE_URL"),
            default="https://s.jina.ai",
        )

        self.reader_base_url = _normalize_base_url(
            reader_base_url
            or os.environ.get("JINA_READER_BASE_URL"),
            default="https://r.jina.ai",
        )

        self.timeout = timeout
        self.min_backoff = min_backoff
        self.transport = transport
        self._client = client or httpx.AsyncClient(
            transport=transport,
            timeout=httpx.Timeout(self.timeout),
        )

    def __repr__(self) -> str:
        return f"JinaClient(api_key='[REDACTED]', search_url='{self.search_base_url}', reader_url='{self.reader_base_url}')"

    async def aclose(self) -> None:
        """Encerra a sessão HTTP subjacente."""
        await self._client.aclose()

    async def __aenter__(self) -> "JinaClient":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.aclose()

    async def _request(self, url: str, headers: Dict[str, str]) -> httpx.Response:
        """GET com classificação de falha e retry (1+3) no modo legado.

        RF-01/RF-02: falhas HTTP classificadas em `JinaError`; billing/autenticação
        são terminais e nunca viram resultado vazio nem são retentadas.
        """
        max_attempts = 4
        res: Optional[httpx.Response] = None
        for attempt in range(1, max_attempts + 1):
            res = await self._client.get(url, headers=headers)
            if res.status_code >= 400:
                try:
                    body: Any = res.json()
                except Exception:
                    body = res.text
                erro = classify_failure(res.status_code, body)
                if not erro.terminal and attempt < max_attempts:
                    await asyncio.sleep(self.min_backoff * (2 ** (attempt - 1)))
                    continue
                raise erro
            return res

        assert res is not None  # ponytail: loop sempre retorna ou levanta
        return res

    async def search(
        self,
        query: str,
        include_content: bool = False,
    ) -> List[Dict[str, str]]:
        """Executa busca SERP retornando apenas metadados (título, url, descrição).

        Atende a RN-03: isolamento estrito de metadados, vedado download de corpo de página.
        """
        if not query or not query.strip():
            raise ValueError("A consulta de busca não pode ser vazia.")

        encoded_query = urllib.parse.quote(query.strip(), safe="")
        url = f"{self.search_base_url}/{encoded_query}"
        headers = {
            "Accept": "application/json",
            "X-Retain-Images": "none",
            "Authorization": f"Bearer {self.api_key}",
        }

        res = await self._request(url, headers)
        data = res.json()
        raw_items: List[Any] = []
        if isinstance(data, dict):
            # RF-01: a Jina sinaliza erro com HTTP 200 e corpo {"code":401,
            # "data":null}. Sem esta checagem o erro viraria lista vazia.
            codigo = data.get("code")
            if isinstance(codigo, int) and codigo >= 400:
                raise classify_failure(codigo, data)
            # .get("data", []) devolve None quando a chave existe com valor null
            # (ex.: {"code":401,"data":null}); "or []" protege o laço abaixo.
            raw_items = data.get("data") or []
        elif isinstance(data, list):
            raw_items = data

        # RN-03: filtra e sanitiza metadados, proibido corpo de página na SERP
        sanitized_results: List[Dict[str, str]] = []
        for item in raw_items:
            if isinstance(item, dict):
                entry = {
                    "title": str(item.get("title", "")),
                    "url": str(item.get("url", "")),
                    "description": str(item.get("description", "") or item.get("snippet", "")),
                }
                if include_content:
                    entry["content"] = str(item.get("content", ""))
                sanitized_results.append(entry)
        return sanitized_results

    async def read(self, target_url: str) -> str:
        """Executa raspagem integral de página web via Jina Reader sem truncamento sintático (RN-05)."""
        if not target_url or not target_url.strip():
            raise ValueError("A URL de destino para leitura não pode ser vazia.")

        url = f"{self.reader_base_url}/{target_url.strip()}"
        headers = {
            "Accept": "text/markdown",
            "Authorization": f"Bearer {self.api_key}",
        }

        # RF-01/DÚVIDA-01: mesmo defeito de classe do search() — o corpo de erro
        # (ex.: 402 InsufficientBalanceError) era devolvido como Markdown legítimo.
        res = await self._request(url, headers)

        # Retorna conteúdo integral em Markdown sem cortes (RN-05)
        return res.text
