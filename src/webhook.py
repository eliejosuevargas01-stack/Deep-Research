"""Notificação do webhook final (PRD RF08)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


def enviar_callback(callback_url: str, payload: dict[str, Any], *, timeout_s: int = 15) -> None:
    ultimo_erro: Exception | None = None
    for tentativa in (1, 2):
        try:
            resposta = httpx.post(callback_url, json=payload, timeout=timeout_s)
            if resposta.status_code < 500:
                resposta.raise_for_status()
                return
            ultimo_erro = httpx.HTTPStatusError(
                f"webhook respondeu {resposta.status_code}",
                request=resposta.request,
                response=resposta,
            )
        except httpx.HTTPError as exc:
            ultimo_erro = exc
        logger.warning("webhook %s falhou na tentativa %s: %s", callback_url, tentativa, ultimo_erro)
    raise RuntimeError(f"webhook {callback_url} falhou: {ultimo_erro}")
