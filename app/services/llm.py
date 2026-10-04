import asyncio
import hashlib
import json
import logging
import re
from typing import Any
import httpx
from litellm import acompletion
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.settings import get_record, runtime_settings, validate_base_url

logger = logging.getLogger(__name__)


_SAFE_TRANSPORT_ACTIVE: bool = False
_SAFE_TRANSPORT_ERROR: str | None = None


def _enforce_safe_transport() -> None:
    """Enforce SSRF defenses: disable redirects on LiteLLM HTTP clients.

    Fail-closed: Raises RuntimeError if safe transport cannot be guaranteed.
    """
    global _SAFE_TRANSPORT_ACTIVE, _SAFE_TRANSPORT_ERROR
    try:
        import litellm
        from litellm.llms.custom_httpx.http_handler import AsyncHTTPHandler, HTTPHandler
        from litellm.llms.openai.common_utils import BaseOpenAILLM

        orig_async_create = AsyncHTTPHandler.create_client
        if not getattr(orig_async_create, "_safe_patched", False):
            def _safe_async_create(self, *args, **kwargs):
                client = orig_async_create(self, *args, **kwargs)
                if not hasattr(client, "follow_redirects"):
                    raise RuntimeError("LiteLLM AsyncHTTPHandler client does not support follow_redirects (unsupported transport)")
                client.follow_redirects = False
                return client
            setattr(_safe_async_create, "_safe_patched", True)
            AsyncHTTPHandler.create_client = _safe_async_create

        orig_sync_create = HTTPHandler.create_client
        if not getattr(orig_sync_create, "_safe_patched", False):
            def _safe_sync_create(self, *args, **kwargs):
                client = orig_sync_create(self, *args, **kwargs)
                if not hasattr(client, "follow_redirects"):
                    raise RuntimeError("LiteLLM HTTPHandler client does not support follow_redirects (unsupported transport)")
                client.follow_redirects = False
                return client
            setattr(_safe_sync_create, "_safe_patched", True)
            HTTPHandler.create_client = _safe_sync_create

        orig_openai_async = BaseOpenAILLM._get_async_http_client
        if not getattr(orig_openai_async, "_safe_patched", False):
            def _safe_openai_async(*args, **kwargs):
                client = orig_openai_async(*args, **kwargs)
                if client is not None:
                    if not hasattr(client, "follow_redirects"):
                        raise RuntimeError("LiteLLM BaseOpenAILLM async client does not support follow_redirects (unsupported transport)")
                    client.follow_redirects = False
                return client
            setattr(_safe_openai_async, "_safe_patched", True)
            BaseOpenAILLM._get_async_http_client = _safe_openai_async

        orig_openai_sync = BaseOpenAILLM._get_sync_http_client
        if not getattr(orig_openai_sync, "_safe_patched", False):
            def _safe_openai_sync(*args, **kwargs):
                client = orig_openai_sync(*args, **kwargs)
                if client is not None:
                    if not hasattr(client, "follow_redirects"):
                        raise RuntimeError("LiteLLM BaseOpenAILLM sync client does not support follow_redirects (unsupported transport)")
                    client.follow_redirects = False
                return client
            setattr(_safe_openai_sync, "_safe_patched", True)
            BaseOpenAILLM._get_sync_http_client = _safe_openai_sync

        if hasattr(litellm, "module_level_aclient") and litellm.module_level_aclient:
            if not hasattr(litellm.module_level_aclient.client, "follow_redirects"):
                raise RuntimeError("LiteLLM module_level_aclient transport does not support follow_redirects (unsupported transport)")
            litellm.module_level_aclient.client.follow_redirects = False
        if hasattr(litellm, "module_level_client") and litellm.module_level_client:
            if not hasattr(litellm.module_level_client.client, "follow_redirects"):
                raise RuntimeError("LiteLLM module_level_client transport does not support follow_redirects (unsupported transport)")
            litellm.module_level_client.client.follow_redirects = False

        test_async = AsyncHTTPHandler().client
        if getattr(test_async, "follow_redirects", None) is not False:
            raise RuntimeError("LiteLLM AsyncHTTPHandler verification failed: follow_redirects is not False")
        test_sync = HTTPHandler().client
        if getattr(test_sync, "follow_redirects", None) is not False:
            raise RuntimeError("LiteLLM HTTPHandler verification failed: follow_redirects is not False")

        _SAFE_TRANSPORT_ACTIVE = True
        _SAFE_TRANSPORT_ERROR = None
    except Exception as e:
        _SAFE_TRANSPORT_ACTIVE = False
        _SAFE_TRANSPORT_ERROR = str(e)
        logger.error("Could not enforce safe LiteLLM transport redirects: %s", e)
        raise RuntimeError(f"LiteLLM safe transport enforcement failed (fail-closed): {e}") from e


_enforce_safe_transport()


# Limitation Note (SSRF & LiteLLM Transport):
# LiteLLM manages HTTP transport across heterogeneous vendor SDKs. Disabling HTTP redirects
# (follow_redirects=False) is enforced fail-closed across all LiteLLM client factories.
# Base URLs are strictly validated to reject non-global, loopback, link-local, and metadata destinations.
# Comprehensive protection against DNS rebinding (TOCTOU) across third-party vendor SDKs
# cannot be guaranteed by application-level preflight alone and requires connection-level
# IP pinning and/or infrastructure-level network egress filtering (iptables / cloud firewall).


class ProviderConfigurationError(RuntimeError):
    pass


# A1: guardrail de saída — bloqueia vazamento de segredos/prompts internos nas respostas dos agentes.
_BLOCKED_OUTPUT_PATTERNS = (
    # API key / token formats
    re.compile(r"sk-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"gsk_[A-Za-z0-9_\-]{16,}"),
    re.compile(r"gh[po]_[A-Za-z0-9_\-]{16,}"),
    re.compile(r"AIzaSy[A-Za-z0-9_\-]{30,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9_\-\.]{12,}", re.I),
    # Sensitive assignment variants in English and Portuguese
    re.compile(r"(?:api[_-]?key|secret|token|password|passwd|senha|segredo|access[_-]?token|auth[_-]?token|private[_-]?key|chave[_-]?api)\s*[:=]\s*\S+", re.I),
    # Internal system prompt and instruction disclosure in English and Portuguese
    re.compile(r"system\s*prompt", re.I),
    re.compile(r"prompt\s*do\s*sistema", re.I),
    re.compile(r"internal\s*instructions?", re.I),
    re.compile(r"core\s*instructions?", re.I),
    re.compile(r"developer\s*instructions?", re.I),
    re.compile(r"instruction\s*hierarchy", re.I),
    re.compile(r"system\s*role\s*instructions?", re.I),
    re.compile(r"instruç(?:ão|ões)\s*(?:do\s*sistema|interna[s]?)", re.I),
    re.compile(r"regras\s*internas\s*do\s*sistema", re.I),
    re.compile(r"instruções\s*confidenciais", re.I),
)


def apply_output_guardrail(text: str, extra_sensitive_values: list[str] | None = None) -> str:
    from app.core.config import settings
    configured_secrets = [
        getattr(settings, "ADMIN_PASSWORD", ""),
        getattr(settings, "SESSION_SECRET", ""),
        getattr(settings, "API_AUTH_SECRET", ""),
        getattr(settings, "APP_ENCRYPTION_KEY", ""),
    ]
    if extra_sensitive_values:
        configured_secrets.extend(extra_sensitive_values)

    text_lower = text.lower()
    for sec in configured_secrets:
        if sec and len(sec.strip()) >= 6 and sec.lower() in text_lower:
            raise RuntimeError("Guardrail: agent output contained sensitive configured secrets or credentials")

    for pattern in _BLOCKED_OUTPUT_PATTERNS:
        if pattern.search(text):
            raise RuntimeError("Guardrail: agent output contained secrets or internal prompt material")
    return text


def _provider(model: str) -> str:
    prefix = model.split("/", 1)[0].lower()
    if prefix.startswith(("gpt", "o1", "o3", "o4")):
        return "openai"
    if prefix.startswith("claude"):
        return "anthropic"
    if prefix.startswith("gemini"):
        return "gemini"
    return {"azure": "openai", "google": "gemini"}.get(prefix, prefix)


_LLM_SEMAPHORE = asyncio.Semaphore(4)


_ROUTER_MODELS_CACHE: dict[str, tuple[float, list[str]]] = {}


def _router_cache_key(provider: str, base_url: str, api_key: str) -> str:
    digest = hashlib.sha256(f"{provider}:{base_url}:{api_key}".encode("utf-8")).hexdigest()
    return f"{provider}:{digest}"


async def _get_router_models(api_key: str, base_url: str, provider: str = "openai") -> list[str]:
    import time
    validate_base_url(base_url)
    cache_key = _router_cache_key(provider, base_url, api_key)
    now = time.time()
    if cache_key in _ROUTER_MODELS_CACHE:
        ts, cached = _ROUTER_MODELS_CACHE[cache_key]
        if now - ts < 300:
            return cached
    models = await list_provider_models(provider, api_key=api_key, base_url=base_url)
    if models:
        _ROUTER_MODELS_CACHE[cache_key] = (now, models)
    return models


async def _resolve_router_fallback(model: str, router_key: str, router_base: str, router_provider: str) -> str | None:
    router_models = await _get_router_models(router_key, router_base, router_provider)
    base_model = model.split("/", 1)[1] if "/" in model else model
    if base_model in router_models:
        return f"{router_provider}/{base_model}"
    if model in router_models:
        return f"{router_provider}/{model}"
    return None


def _classify_error(exc: Exception) -> tuple[int | None, str, bool, bool]:
    """Classify exception into (status_code, error_type, is_retryable, is_auth_error)."""
    status_code = getattr(exc, "status_code", None)
    if status_code is None:
        resp = getattr(exc, "response", None)
        if resp is not None:
            status_code = getattr(resp, "status_code", None)

    err_type = type(exc).__name__
    err_type_lower = err_type.lower()
    err_msg = str(exc).lower()

    if status_code is None:
        match = re.search(r"\b(401|403|429|500|502|503|504)\b", err_msg)
        if match:
            status_code = int(match.group(1))

    is_auth_error = (
        status_code in {401, 403}
        or any(k in err_type_lower for k in ("auth", "permissiondenied"))
        or any(k in err_msg for k in ("unauthorized", "invalid_api_key", "permission_denied", "forbidden"))
    )

    is_rate_limit = (
        status_code == 429
        or "ratelimit" in err_type_lower
        or any(k in err_msg for k in ("429", "rate limit", "quota", "resource_exhausted"))
    )

    is_transient_server = (
        status_code in {502, 503, 504}
        or any(k in err_type_lower for k in ("serviceunavailable", "badgateway", "gatewaytimeout"))
        or any(k in err_msg for k in ("503", "high demand", "unavailable", "bad gateway", "service unavailable"))
    )

    is_timeout = (
        isinstance(exc, (asyncio.TimeoutError, httpx.TimeoutException))
        or "timeout" in err_type_lower
        or "timeout" in err_msg
    )

    is_retryable = (is_rate_limit or is_transient_server or is_timeout) and not is_auth_error
    return status_code, err_type, is_retryable, is_auth_error


async def complete(role: str, system: str, user: str, db: AsyncSession) -> str:
    if not _SAFE_TRANSPORT_ACTIVE:
        _enforce_safe_transport()
    keys, models = await runtime_settings(db)
    record = await get_record(db)
    model = models.get(role)
    if not model:
        raise ProviderConfigurationError(f"No model configured for role '{role}'")
    provider = _provider(model)
    # Strictly bind key atomically by provider; never use litellm key as primary for other providers
    api_key = keys.get(provider)
    if not api_key:
        raise ProviderConfigurationError(f"No API key configured for model provider '{provider}'")
    kwargs: dict[str, Any] = {
        "model": model,
        "api_key": api_key,
        "timeout": 180,
    }
    if any(k in model.lower() for k in ("kimi", "moonshot")):
        kwargs["messages"] = [{"role": "user", "content": f"INSTRUÇÕES DO SISTEMA:\n{system}\n\nDADOS E TAREFA:\n{user}"}]
        kwargs["max_tokens"] = 8000
    else:
        kwargs["messages"] = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    if provider == "openai" and record.openai_base_url:
        validate_base_url(record.openai_base_url)
        kwargs["api_base"] = record.openai_base_url
    elif provider == "litellm":
        from app.core.config import settings
        if settings.LITELLM_API_BASE:
            validate_base_url(settings.LITELLM_API_BASE)
            kwargs["api_base"] = settings.LITELLM_API_BASE

    # Atomic router gateway candidates:
    # 1. OpenAI-compatible gateway: requires both openai_base_url AND openai key
    # 2. LiteLLM gateway: requires both LITELLM_API_BASE AND litellm key
    # Key and base URL are strictly bound per provider and never mixed.
    from app.core.config import settings
    router_candidates: list[tuple[str, str, str]] = []
    if record.openai_base_url and keys.get("openai"):
        validate_base_url(record.openai_base_url)
        router_candidates.append(("openai", keys["openai"], record.openai_base_url))
    if settings.LITELLM_API_BASE and keys.get("litellm"):
        validate_base_url(settings.LITELLM_API_BASE)
        router_candidates.append(("litellm", keys["litellm"], settings.LITELLM_API_BASE))

    already_using_router = any(
        kwargs.get("api_base") == r_base and kwargs.get("api_key") == r_key
        for _, r_key, r_base in router_candidates
    )

    sensitive_keys = [str(k) for k in keys.values() if k]
    async with _LLM_SEMAPHORE:
        attempts = 5
        for attempt in range(1, attempts + 1):
            try:
                response = await acompletion(**kwargs)
                msg = response.choices[0].message
                text = msg.content or getattr(msg, "reasoning_content", "") or ""
                if not text:
                    raise RuntimeError("LLM returned empty content")
                return apply_output_guardrail(text, extra_sensitive_values=sensitive_keys)
            except Exception as exc:
                status_code, err_type, is_retryable, is_auth_error = _classify_error(exc)

                # Security policy: fail immediately on 401/403 or auth errors.
                # Never bypass auth policy or trigger router fallback on authentication failure.
                if is_auth_error:
                    raise ProviderConfigurationError(f"Authentication failure for provider '{provider}' (status={status_code})")

                # Fallback to router strictly for quota / transient errors
                if is_retryable and not already_using_router and router_candidates:
                    for router_provider, router_key, router_base in router_candidates:
                        try:
                            fallback_model = await _resolve_router_fallback(model, router_key, router_base, router_provider)
                            if fallback_model:
                                fallback_kwargs = dict(kwargs)
                                fallback_kwargs["model"] = fallback_model
                                fallback_kwargs["api_key"] = router_key
                                fallback_kwargs["api_base"] = router_base
                                fb_resp = await acompletion(**fallback_kwargs)
                                fb_msg = fb_resp.choices[0].message
                                fb_text = fb_msg.content or getattr(fb_msg, "reasoning_content", "") or ""
                                if fb_text:
                                    return apply_output_guardrail(fb_text, extra_sensitive_values=sensitive_keys)
                        except Exception as fb_exc:
                            # Safe fallback failure logging without secrets: only type and status code
                            fb_status = getattr(fb_exc, "status_code", None)
                            logger.warning(
                                "Router fallback failed: type=%s, status=%s",
                                type(fb_exc).__name__,
                                fb_status,
                            )

                # If retryable, sleep with appropriate backoff
                if attempt < attempts and is_retryable:
                    if status_code == 429:
                        # Respect enough time for the window to reset
                        backoff = min(30.0 * attempt, 120.0)
                    else:
                        backoff = min(2.0 * attempt, 10.0)
                    await asyncio.sleep(backoff)
                    continue

                if provider == "gemini" and "gemini-3.8-flash" in str(kwargs.get("model", "")).lower() and is_retryable:
                    try:
                        fallback_kwargs = dict(kwargs)
                        fallback_kwargs["model"] = "gemini/gemini-3.5-flash-lite"
                        fb_resp = await acompletion(**fallback_kwargs)
                        fb_text = fb_resp.choices[0].message.content
                        if fb_text:
                            return apply_output_guardrail(fb_text, extra_sensitive_values=sensitive_keys)
                    except Exception:
                        pass
                raise
        raise RuntimeError("All LLM retry attempts failed")


def parse_json(text: str) -> Any:
    cleaned = text.strip()
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", cleaned, re.DOTALL)
    if match:
        cleaned = match.group(1).strip()
    try:
        return json.loads(cleaned)
    except Exception:
        pass
    m = re.search(r"(\{.*\}|\[.*\])", cleaned, re.DOTALL)
    if m:
        candidate = m.group(1).strip()
        try:
            return json.loads(candidate)
        except Exception:
            pass
        try:
            import ast
            return ast.literal_eval(candidate)
        except Exception:
            pass
    try:
        import ast
        return ast.literal_eval(cleaned)
    except Exception:
        pass
    raise ValueError("LLM response did not contain JSON")


async def test_provider_key(provider: str, api_key: str, base_url: str | None = None) -> tuple[bool, str]:
    """Test a provider key without logging or persisting it. Returns (success, message)."""
    clean_key = api_key.strip()
    if not clean_key:
        return False, "Chave vazia."
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            if provider == "openai":
                base = (base_url or "").strip().rstrip("/") or "https://api.openai.com/v1"
                validate_base_url(base)
                resp = await client.get(f"{base}/models", headers={"Authorization": f"Bearer {clean_key}"})
                if resp.status_code == 200:
                    return True, "Chave OpenAI validada com sucesso."
                if resp.status_code in {401, 403}:
                    return False, f"Chave OpenAI inválida ou não autorizada (HTTP {resp.status_code})."
                return False, f"Erro do provedor OpenAI: HTTP {resp.status_code}"

            if provider == "anthropic":
                resp = await client.get(
                    "https://api.anthropic.com/v1/models",
                    headers={"x-api-key": clean_key, "anthropic-version": "2023-06-01"},
                )
                if resp.status_code == 200:
                    return True, "Chave Anthropic validada com sucesso."
                if resp.status_code in {401, 403}:
                    return False, f"Chave Anthropic inválida (HTTP {resp.status_code})."
                return False, f"Erro do provedor Anthropic: HTTP {resp.status_code}"

            if provider == "gemini":
                resp = await client.get(f"https://generativelanguage.googleapis.com/v1beta/models?key={clean_key}")
                if resp.status_code == 200:
                    return True, "Chave Gemini validada com sucesso."
                if resp.status_code in {400, 401, 403}:
                    return False, f"Chave Gemini inválida ou não autorizada (HTTP {resp.status_code})."
                return False, f"Erro do provedor Gemini: HTTP {resp.status_code}"

            if provider == "litellm":
                from app.core.config import settings
                base = (base_url or "").strip().rstrip("/") or (settings.LITELLM_API_BASE or "").rstrip("/")
                if not base:
                    return False, "Endpoint LiteLLM não configurado."
                validate_base_url(base)
                resp = await client.get(f"{base}/models", headers={"Authorization": f"Bearer {clean_key}"})
                if resp.status_code == 200:
                    return True, "Endpoint LiteLLM validado com sucesso."
                return False, f"LiteLLM retornou HTTP {resp.status_code}"

            if provider == "serpapi":
                resp = await client.get(f"https://serpapi.com/account?api_key={clean_key}")
                if resp.status_code == 200:
                    return True, "Chave SerpAPI validada com sucesso."
                if resp.status_code in {401, 403}:
                    return False, "Chave SerpAPI inválida."
                return False, f"SerpAPI retornou HTTP {resp.status_code}"

            if provider == "apify":
                resp = await client.get(f"https://api.apify.com/v2/users/me?token={clean_key}")
                if resp.status_code == 200:
                    return True, "Token Apify validado com sucesso."
                if resp.status_code in {401, 403}:
                    return False, "Token Apify inválido."
                return False, f"Apify retornou HTTP {resp.status_code}"

            if provider == "jina":
                resp = await client.get(
                    "https://r.jina.ai/https://example.com",
                    headers={"Authorization": f"Bearer {clean_key}", "Accept": "text/event-stream"},
                )
                if 200 <= resp.status_code < 300:
                    return True, "Chave Jina validada com sucesso."
                if resp.status_code in {401, 403}:
                    return False, f"Chave Jina inválida ou não autorizada (HTTP {resp.status_code})."
                if resp.status_code == 422:
                    return False, "Jina retornou erro de validação (HTTP 422). Chave não confirmada."
                if resp.status_code == 429:
                    return False, "Limite de taxa ou cota do Jina excedida (HTTP 429)."
                return False, f"Jina retornou HTTP {resp.status_code}"

            return False, f"Provedor '{provider}' não reconhecido para teste."
    except Exception as exc:
        return False, f"Falha de conexão ao testar provedor: {type(exc).__name__}"


async def list_provider_models(provider: str, api_key: str | None = None, base_url: str | None = None) -> list[str]:
    """Dynamically discover available models from the provider catalog with pagination and actionable errors."""
    if not api_key:
        return []
    clean_key = api_key.strip()
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            if provider == "openai":
                base = (base_url or "").strip().rstrip("/") or "https://api.openai.com/v1"
                validate_base_url(base)
                resp = await client.get(f"{base}/models", headers={"Authorization": f"Bearer {clean_key}"})
                if resp.status_code == 200:
                    data = resp.json()
                    models = [m["id"] for m in data.get("data", []) if isinstance(m, dict) and "id" in m]
                    return sorted(models)
                raise RuntimeError(f"OpenAI models query failed with HTTP {resp.status_code}")

            if provider == "anthropic":
                models = []
                after_id = None
                while True:
                    url = "https://api.anthropic.com/v1/models?limit=100"
                    if after_id:
                        url += f"&after_id={after_id}"
                    resp = await client.get(
                        url,
                        headers={"x-api-key": clean_key, "anthropic-version": "2023-06-01"},
                    )
                    if resp.status_code != 200:
                        raise RuntimeError(f"Anthropic models query failed with HTTP {resp.status_code}")
                    data = resp.json()
                    page_models = [m["id"] for m in data.get("data", []) if isinstance(m, dict) and "id" in m]
                    models.extend(page_models)
                    if not data.get("has_more") or not page_models:
                        break
                    after_id = data.get("last_id") or page_models[-1]
                return sorted(models)

            if provider == "gemini":
                models = []
                page_token = None
                while True:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={clean_key}&pageSize=50"
                    if page_token:
                        url += f"&pageToken={page_token}"
                    resp = await client.get(url)
                    if resp.status_code != 200:
                        raise RuntimeError(f"Gemini models query failed with HTTP {resp.status_code}")
                    data = resp.json()
                    for m in data.get("models", []):
                        if isinstance(m, dict) and "name" in m and "generateContent" in m.get("supportedGenerationMethods", []):
                            models.append(m["name"].replace("models/", ""))
                    page_token = data.get("nextPageToken")
                    if not page_token:
                        break
                    if len(models) >= 200:
                        break
                return sorted(models)

            if provider == "litellm":
                from app.core.config import settings
                base = (base_url or "").strip().rstrip("/") or (settings.LITELLM_API_BASE or "").rstrip("/")
                if not base:
                    raise RuntimeError("Endpoint LiteLLM não configurado")
                validate_base_url(base)
                resp = await client.get(f"{base}/models", headers={"Authorization": f"Bearer {clean_key}"})
                if resp.status_code == 200:
                    data = resp.json()
                    models = [m["id"] for m in data.get("data", []) if isinstance(m, dict) and "id" in m]
                    return sorted(models)
                raise RuntimeError(f"LiteLLM models query failed with HTTP {resp.status_code}")

            return []
    except Exception as exc:
        raise RuntimeError(f"Failed to query provider models for '{provider}': {str(exc)}") from exc
