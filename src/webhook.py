"""Notificação do webhook final (PRD RF08)."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

import httpx

logger = logging.getLogger(__name__)

MAX_TENTATIVAS = 5
ESPERAS_S = (1, 2, 4, 8)


def enviar_callback(
    callback_url: str,
    payload: dict[str, Any],
    *,
    timeout_s: int = 15,
    espera: Callable[[float], None] = time.sleep,
) -> None:
    ultimo_erro: Exception | None = None
    for tentativa in range(1, MAX_TENTATIVAS + 1):
        try:
            resposta = httpx.post(callback_url, json=payload, timeout=timeout_s)
            if resposta.status_code >= 500:
                ultimo_erro = httpx.HTTPStatusError(
                    f"webhook respondeu {resposta.status_code}",
                    request=resposta.request,
                    response=resposta,
                )
            else:
                try:
                    resposta.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    raise RuntimeError(f"webhook {callback_url} falhou: {exc}") from exc
                return
        except RuntimeError:
            raise
        except httpx.HTTPError as exc:
            ultimo_erro = exc
        logger.warning(
            "webhook %s falhou na tentativa %s: %s", callback_url, tentativa, ultimo_erro
        )
        if tentativa < MAX_TENTATIVAS:
            espera(ESPERAS_S[tentativa - 1])
    raise RuntimeError(f"webhook {callback_url} falhou: {ultimo_erro}")
