"""LiteLLM binding with async retries for investigation agent (T009)."""

from __future__ import annotations

import asyncio
from typing import Any

import litellm
import litellm.exceptions as litellm_exceptions


class LLMCallError(Exception):
    """Error after exhausting all retry attempts."""

    def __init__(self, attempts: int, message: str):
        self.attempts = attempts
        self.message = message
        super().__init__(f"LLM call failed after {attempts} attempts: {message}")


async def call_llm_with_retries(
    model: str,
    messages: list[dict],
    tools: list[dict] | None = None,
    tool_choice: str | dict | None = "auto",
    timeout: float = 90.0,
    api_base: str | None = None,
    api_key: str | None = None,
    max_attempts: int = 3,
) -> Any:
    """
    Call LiteLLM acompletion with retries on transient failures.

    Retries on: RateLimitError / 429, APIConnectionError, TimeoutError / asyncio.TimeoutError, 5xx.
    Waits Retry-After header or retry_after attribute if present; else 2s then 4s backoff.
    Returns native LiteLLM completion object. Does not expose keys in exceptions.
    """
    last_exc: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            response = await litellm.acompletion(
                model=model,
                messages=messages,
                tools=tools,
                tool_choice=tool_choice,
                timeout=timeout,
                api_base=api_base,
                api_key=api_key,
                num_retries=0,  # RN-07: harness owns the 3 attempts; disable SDK retries
            )
            return response
        except (
            litellm_exceptions.RateLimitError,
            litellm_exceptions.APIConnectionError,
            asyncio.TimeoutError,
            TimeoutError,
        ) as exc:
            last_exc = exc
            if attempt == max_attempts:
                break

            # Check for Retry-After header or retry_after attribute
            wait_time = _get_retry_after(exc)
            if wait_time is None:
                wait_time = 2.0 if attempt == 1 else 4.0

            await asyncio.sleep(wait_time)

        except litellm_exceptions.APIError as exc:
            # Check for 5xx status codes
            status_code = getattr(exc, "status_code", None)
            if status_code is None:
                response = getattr(exc, "response", None)
                if response:
                    status_code = getattr(response, "status_code", None)

            if isinstance(status_code, int) and 500 <= status_code < 600:
                last_exc = exc
                if attempt == max_attempts:
                    break

                wait_time = _get_retry_after(exc)
                if wait_time is None:
                    wait_time = 2.0 if attempt == 1 else 4.0

                await asyncio.sleep(wait_time)
            else:
                # Non-retryable API error - propagate immediately
                raise

        except Exception as exc:
            # Any other exception - propagate immediately
            raise

    # All attempts exhausted
    raise LLMCallError(max_attempts, str(last_exc) if last_exc else "Unknown error")


def _get_retry_after(exc: Exception) -> float | None:
    """Extract Retry-After value from exception if present."""
    # Check retry_after attribute (litellm RateLimitError)
    retry_after = getattr(exc, "retry_after", None)
    if retry_after is not None:
        try:
            return float(retry_after)
        except (ValueError, TypeError):
            pass

    # Check Retry-After header in response
    response = getattr(exc, "response", None)
    if response:
        headers = getattr(response, "headers", None)
        if headers:
            retry_after_header = headers.get("Retry-After") or headers.get("retry-after")
            if retry_after_header:
                try:
                    return float(retry_after_header)
                except (ValueError, TypeError):
                    pass

    return None