"""Cliente HTTP assíncrono para despacho assinado de Webhooks de notificação.

Calcula assinatura HMAC-SHA256 no header X-Signature sobre os raw bytes do corpo (DT-04),
valida timing-safe contra adulteração e implementa política de 1 tentativa inicial + 3 retries.
Em caso de falha definitiva, atualiza webhook_status como 'falha_definitiva' sem descartar
o dossiê nem levantar exceção não tratada (RN-09, RF-10, RNF-06).
"""

import asyncio
import hashlib
import hmac
import json
import os
from typing import Any, Dict, Optional
import httpx
from app.config import get_settings


class WebhookClient:
    """Cliente para entrega de webhooks com assinatura HMAC-SHA256 e retries 1+3."""

    def __init__(
        self,
        secret: Optional[str] = None,
        transport: Optional[httpx.AsyncBaseTransport] = None,
        client: Optional[httpx.AsyncClient] = None,
        research_repo: Optional[Any] = None,
        timeout: float = 30.0,
        min_backoff: float = 0.01,
    ) -> None:
        settings = get_settings()
        resolved_secret = (
            secret
            or settings.webhook_hmac_secret
            or os.environ.get("WEBHOOK_HMAC_SECRET")
        )
        if not resolved_secret or not str(resolved_secret).strip():
            raise ValueError("Configuração ausente: WEBHOOK_HMAC_SECRET não informado no ambiente.")
        self.secret = str(resolved_secret).strip()

        self.timeout = timeout
        self.min_backoff = min_backoff
        self.transport = transport
        self.research_repo = research_repo
        self._client = client or httpx.AsyncClient(
            transport=transport,
            timeout=httpx.Timeout(self.timeout),
        )

    def __repr__(self) -> str:
        return "WebhookClient(secret='[REDACTED]')"

    async def aclose(self) -> None:
        """Encerra a sessão HTTP subjacente."""
        await self._client.aclose()

    async def __aenter__(self) -> "WebhookClient":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.aclose()

    @staticmethod
    def compute_signature(secret: str, payload_bytes: bytes) -> str:
        """Calcula a assinatura HMAC-SHA256 sobre os bytes crus do corpo.

        Retorna no formato padronizado: 'sha256=<hex>' (DT-04).
        """
        digest = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
        return f"sha256={digest}"

    @staticmethod
    def verify_signature(secret: str, payload_bytes: bytes, signature: str) -> bool:
        """Validação timing-safe da assinatura HMAC-SHA256 para prevenir timing attacks."""
        if not signature or not isinstance(signature, str):
            return False
        prefix = "sha256="
        if not signature.startswith(prefix):
            return False

        received_hex = signature[len(prefix):]
        expected_hex = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
        return hmac.compare_digest(received_hex, expected_hex)

    async def _update_repo_status(
        self,
        repo: Optional[Any],
        id_pesquisa: str,
        status: str,
        resposta: Optional[str] = None,
    ) -> None:
        """Atualiza webhook_status na tabela pesquisa quando o repositório estiver disponível."""
        if repo is None:
            return
        try:
            pesquisa = await repo.get_research(id_pesquisa)
            if pesquisa is not None:
                pesquisa.webhook_status = status
                if resposta is not None:
                    pesquisa.webhook_resposta = resposta
                if hasattr(repo, "session") and repo.session is not None:
                    await repo.session.commit()
        except Exception:
            # ponytail: falha na persistência de telemetria não invalida o resultado do despacho
            pass

    async def send_webhook(
        self,
        url: str,
        payload: Dict[str, Any],
        id_pesquisa: str,
        research_repo: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Dispara requisição HTTP POST assinada com política de 1+3 retries.

        Calcula assinatura HMAC-SHA256 sobre raw bytes (DT-04, RN-09).
        Atualiza o status para 'entregue' ou 'falha_definitiva' sem levantar exceção em caso de exaustão.
        """
        if not url or not url.strip():
            raise ValueError("Configuração ausente: URL de webhook não informada.")

        raw_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        signature = self.compute_signature(self.secret, raw_bytes)

        headers = {
            "Content-Type": "application/json",
            "X-Signature": signature,
            "X-Event-Type": str(payload.get("evento", "research.completed")),
            "X-Research-Id": str(id_pesquisa),
        }

        repo = research_repo or self.research_repo
        max_attempts = 4  # 1 tentativa inicial + 3 retries (RNF-06)
        last_status_code: Optional[int] = None
        last_error_message: Optional[str] = None

        for attempt in range(1, max_attempts + 1):
            try:
                res = await self._client.post(
                    url=url,
                    content=raw_bytes,
                    headers=headers,
                )
                last_status_code = res.status_code

                if res.status_code in (429, 500, 502, 503, 504) or res.is_server_error:
                    res.raise_for_status()

                # BUG-20261023-EPVA: apenas 2xx confirma a entrega. Um 4xx é rejeição
                # definitiva do receptor e não pode ser gravado como 'entregue'.
                # A lista acima continua existindo só para decidir RETRY, nunca para
                # decidir que a entrega ocorreu.
                status_result = "entregue" if res.is_success else "falha_definitiva"
                await self._update_repo_status(
                    repo=repo,
                    id_pesquisa=id_pesquisa,
                    status=status_result,
                    resposta=res.text,
                )
                return {
                    "status": status_result,
                    "http_status_code": res.status_code,
                    "tentativas": attempt,
                    "resposta": res.text,
                }

            except (httpx.HTTPStatusError, httpx.TransportError) as exc:
                last_error_message = str(exc)
                if attempt == max_attempts:
                    break
                backoff = self.min_backoff * (2 ** (attempt - 1))
                if backoff > 0:
                    await asyncio.sleep(backoff)

        # Retries esgotados: registra 'falha_definitiva' preservando dados (RF-10, RN-09)
        status_result = "falha_definitiva"
        await self._update_repo_status(
            repo=repo,
            id_pesquisa=id_pesquisa,
            status=status_result,
            resposta=last_error_message,
        )
        return {
            "status": status_result,
            "http_status_code": last_status_code,
            "tentativas": max_attempts,
            "erro": last_error_message,
        }
