"""Binding LiteLLM real one-attempt para a role `scout` (T023, D5).

Fábrica injetável usada pela orquestração persistida (T024): resolve
modelo/chave por requisição via `runtime_settings(db)`, faz exatamente UMA
chamada `litellm.acompletion`, sem retry/router/sleep internos. Falhas
transitórias viram `LLMAttemptError` (mensagem segura); erros de
auth/config propagam sem máscara. Não toca `app/services/llm.py`.
"""

from __future__ import annotations

import math
from collections.abc import Awaitable, Callable

import httpx
import litellm
import litellm.exceptions as litellm_exceptions
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.briefing.service import LLMAttemptError
from app.core.config import settings
from app.services.llm import (
    ProviderConfigurationError,
    _enforce_safe_transport,
    _provider,
    apply_output_guardrail,
)
from app.services.settings import get_record, runtime_settings, validate_base_url


_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


def _real_status_code(exc: Exception) -> int | None:
    """Status numérico de atributo real; bool/str/ausente viram None."""
    status = getattr(exc, "status_code", None)
    if isinstance(status, int) and not isinstance(status, bool):
        return status
    response = getattr(exc, "response", None)
    nested = getattr(response, "status_code", None)
    if isinstance(nested, int) and not isinstance(nested, bool):
        return nested
    return None


def _is_eligible_llm_error(exc: Exception) -> bool:
    """Matriz T030 por classe concreta; nunca por texto/nome/status arbitrário."""
    if isinstance(
        exc,
        (
            litellm_exceptions.APIConnectionError,
            litellm_exceptions.Timeout,
            litellm_exceptions.InternalServerError,
            litellm_exceptions.RateLimitError,
            litellm_exceptions.ServiceUnavailableError,
        ),
    ):
        return True
    if isinstance(
        exc,
        (
            httpx.ConnectError,
            httpx.ConnectTimeout,
            httpx.ReadTimeout,
            httpx.WriteTimeout,
            httpx.PoolTimeout,
        ),
    ):
        return True
    if isinstance(exc, TimeoutError):
        return True
    if isinstance(
        exc,
        (
            litellm_exceptions.AuthenticationError,
            litellm_exceptions.PermissionDeniedError,
            litellm_exceptions.BadRequestError,
            ProviderConfigurationError,
        ),
    ):
        return False
    if isinstance(exc, httpx.HTTPStatusError):
        return _real_status_code(exc) in _RETRYABLE_STATUS
    if isinstance(exc, litellm_exceptions.APIError):
        return _real_status_code(exc) in _RETRYABLE_STATUS
    return False


def _checked_timeout(value: float, *, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"Configuração de timeout LLM inválida ({name})")
    try:
        result = float(value)
    except (OverflowError, ValueError):
        raise ValueError(f"Configuração de timeout LLM inválida ({name})")
    if not math.isfinite(result) or result <= 0:
        raise ValueError(f"Configuração de timeout LLM inválida ({name})")
    return result


def make_scout_complete(
    session_factory: async_sessionmaker[AsyncSession], default_timeout_s: float = 30.0
) -> Callable[..., Awaitable[str]]:
    """Retorna `scout_complete(system, user, timeout_s=None) -> str` (one-attempt)."""
    default_timeout = _checked_timeout(default_timeout_s, name="default_timeout_s")

    async def scout_complete(system: str, user: str, timeout_s: float | None = None) -> str:
        timeout = (
            _checked_timeout(timeout_s, name="timeout_s")
            if timeout_s is not None
            else default_timeout
        )
        async with session_factory() as session:
            keys, models = await runtime_settings(session)
            record = await get_record(session)
            openai_base_url = getattr(record, "openai_base_url", None)
            keys = dict(keys)
            models = dict(models)
        model = models.get("scout")
        if not model:
            raise ProviderConfigurationError("No model configured for role 'scout'")
        provider = _provider(model)
        api_key = keys.get(provider)
        if not api_key:
            raise ProviderConfigurationError(
                f"No API key configured for model provider '{provider}'"
            )
        api_base: str | None = None
        if provider == "openai" and openai_base_url:
            validate_base_url(openai_base_url)
            api_base = openai_base_url
        elif provider == "litellm" and getattr(settings, "LITELLM_API_BASE", None):
            validate_base_url(settings.LITELLM_API_BASE)
            api_base = settings.LITELLM_API_BASE
        _enforce_safe_transport()
        kwargs: dict = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "api_key": api_key,
            "timeout": timeout,
            # F-CONTRACT-01 / RF-10: one-attempt scout. Disable internal SDK retries
            # (litellm + upstream OpenAI client) so exactly one HTTP request is made
            # per attempt; retry/loop lifecycle is owned by the orchestrator.
            "num_retries": 0,
            "max_retries": 0,
        }
        if api_base is not None:
            kwargs["api_base"] = api_base
        try:
            response = await litellm.acompletion(**kwargs)
        except ProviderConfigurationError:
            raise
        except Exception as exc:
            if _is_eligible_llm_error(exc):
                raise LLMAttemptError() from None
            raise
        msg = response.choices[0].message
        raw_text = msg.content or getattr(msg, "reasoning_content", "") or ""
        return apply_output_guardrail(
            raw_text, extra_sensitive_values=[str(v) for v in keys.values() if v]
        )

    return scout_complete
