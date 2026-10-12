"""Adapter SERP Jina isolado (T009, RF-02/RF-10)."""

import asyncio
import math
from urllib.parse import urlparse

import httpx

from app.briefing.domain import validate_theme

ENDPOINT = "https://s.jina.ai/"
MAX_ATTEMPTS = 4

# ponytail: sem backoff entre tentativas (intervalo não decidido); introduzir
# espera/jitter somente se RF-10 definir intervalo, sem mudar assinatura search.


class SerpSearchError(Exception):
    """Falha segura da busca SERP (mensagem fixa, sem segredos)."""

    def __init__(self, attempts: int):
        super().__init__(f"Busca SERP indisponível após {attempts} tentativas")
        self.attempts = attempts


class _AttemptFailed(Exception):
    pass


def _valid_url(value: str) -> bool:
    try:
        parsed = urlparse(value.strip())
    except ValueError:
        return False
    return parsed.scheme in ("http", "https") and bool(parsed.hostname)


class JinaSerpClient:
    """Client reutilizável Jina SERP. Lock por instância (não cross-process).

    Fronteira: instância compartilhada será ligada em T011; T010 consome
    search(theme). Cliente httpx injetado pertence ao caller (nunca fechado
    aqui); cliente próprio é fechado ao fim da operação.
    """

    def __init__(self, api_key: str, timeout: float = 30, http_client=None):
        if not isinstance(api_key, str) or not api_key:
            raise ValueError("Chave de API inválida")
        if not all(33 <= ord(ch) <= 126 for ch in api_key):
            raise ValueError("Chave de API inválida")
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
            raise ValueError("Timeout inválido")
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("Timeout inválido")
        self._api_key = api_key
        self._timeout = float(timeout)
        self._http_client = http_client
        self._lock = asyncio.Lock()

    async def search(self, theme: str) -> list[dict]:
        async with self._lock:
            query = validate_theme(theme)
            attempts = 0
            last_failure: Exception | None = None
            for attempt in range(1, MAX_ATTEMPTS + 1):
                attempts = attempt
                try:
                    return await self._single_attempt(query)
                except asyncio.CancelledError:
                    raise
                except _AttemptFailed as exc:
                    last_failure = exc
                    continue
            raise SerpSearchError(attempts) from last_failure

    async def _single_attempt(self, query: str) -> list[dict]:
        owned = self._http_client is None
        client = httpx.AsyncClient() if owned else self._http_client
        try:
            try:
                async with asyncio.timeout(self._timeout):
                    response = await client.post(
                        ENDPOINT,
                        json={"q": query},
                        headers={
                            "Authorization": f"Bearer {self._api_key}",
                            "Accept": "application/json",
                            "Content-Type": "application/json",
                            "X-Respond-With": "no-content",
                        },
                        timeout=self._timeout,
                        follow_redirects=False,
                    )
            except (httpx.HTTPError, TimeoutError) as exc:
                raise _AttemptFailed from exc
            try:
                if not 200 <= response.status_code < 300:
                    raise _AttemptFailed
                try:
                    body = response.json()
                except ValueError as exc:
                    raise _AttemptFailed from exc
                results = self._parse(body)
                if not results:
                    raise _AttemptFailed
                return results
            finally:
                try:
                    await response.aclose()
                except (AttributeError, RuntimeError):
                    pass
        except _AttemptFailed:
            raise
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            # Erro de programação: propaga sem converter em retry externo.
            raise exc
        finally:
            if owned:
                await client.aclose()

    @staticmethod
    def _parse(body) -> list[dict]:
        # Regra técnica: filtra itens inválidos, mantém válidos; vazio = falha.
        if not isinstance(body, dict) or not isinstance(body.get("data"), list):
            return []
        results = []
        for item in body["data"]:
            if not isinstance(item, dict):
                continue
            title, url, description = item.get("title"), item.get("url"), item.get("description")
            if not isinstance(title, str) or not title.strip():
                continue
            if not isinstance(url, str) or not _valid_url(url):
                continue
            if not isinstance(description, str) or not description.strip():
                continue
            results.append({
                "title": title.strip(),
                "url": url.strip(),
                "description": description.strip(),
            })
        return results
