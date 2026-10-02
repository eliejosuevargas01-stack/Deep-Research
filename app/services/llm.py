import json
import re
from typing import Any
import httpx
from litellm import acompletion
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.settings import get_record, runtime_settings


class ProviderConfigurationError(RuntimeError):
    pass


# A1: guardrail de saída — bloqueia vazamento de segredos/prompts internos nas respostas dos agentes.
_BLOCKED_OUTPUT_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9_\-\.]{12,}", re.I),
    re.compile(r"(api[_-]?key|secret|token)\s*[:=]\s*\S+", re.I),
    re.compile(r"system\s*prompt", re.I),
)


def apply_output_guardrail(text: str) -> str:
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


async def complete(role: str, system: str, user: str, db: AsyncSession) -> str:
    keys, models = await runtime_settings(db)
    record = await get_record(db)
    model = models.get(role)
    if not model:
        raise ProviderConfigurationError(f"No model configured for role '{role}'")
    provider = _provider(model)
    api_key = keys.get(provider) or keys.get("litellm")
    if not api_key:
        raise ProviderConfigurationError(f"No API key configured for model provider '{provider}'")
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "api_key": api_key,
        "timeout": 90,
    }
    if provider == "openai" and record.openai_base_url:
        kwargs["api_base"] = record.openai_base_url
    elif provider == "litellm" and keys.get("litellm"):
        from app.core.config import settings
        if settings.LITELLM_API_BASE:
            kwargs["api_base"] = settings.LITELLM_API_BASE

    response = await acompletion(**kwargs)
    text = response.choices[0].message.content
    if not text:
        raise RuntimeError("LLM returned empty content")
    return apply_output_guardrail(text)


def parse_json(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"(?:```json\s*)?(\{.*\}|\[.*\])(?:\s*```)?", text, re.S)
        if not match:
            raise ValueError("LLM response did not contain JSON")
        return json.loads(match.group(1))


async def test_provider_key(provider: str, api_key: str, base_url: str | None = None) -> tuple[bool, str]:
    """Test a provider key without logging or persisting it. Returns (success, message)."""
    clean_key = api_key.strip()
    if not clean_key:
        return False, "Chave vazia."
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            if provider == "openai":
                base = (base_url or "").strip().rstrip("/") or "https://api.openai.com/v1"
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
                base = (base_url or "").strip().rstrip("/") or (settings.LITELLM_API_BASE or "").rstrip("/") or "http://127.0.0.1:4000"
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
                if resp.status_code in {200, 422}:
                    return True, "Chave Jina validada com sucesso."
                if resp.status_code in {401, 403}:
                    return False, "Chave Jina inválida."
                return False, f"Jina retornou HTTP {resp.status_code}"

            return False, f"Provedor '{provider}' não reconhecido para teste."
    except Exception as exc:
        return False, f"Falha de conexão ao testar provedor: {type(exc).__name__}"


async def list_provider_models(provider: str, api_key: str | None = None, base_url: str | None = None) -> list[str]:
    """Dynamically discover available models from the provider catalog."""
    if not api_key:
        return []
    clean_key = api_key.strip()
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            if provider == "openai":
                base = (base_url or "").strip().rstrip("/") or "https://api.openai.com/v1"
                resp = await client.get(f"{base}/models", headers={"Authorization": f"Bearer {clean_key}"})
                if resp.status_code == 200:
                    data = resp.json()
                    models = [m["id"] for m in data.get("data", []) if isinstance(m, dict) and "id" in m]
                    # Filter chat-capable or relevant models if standard OpenAI
                    return sorted(models)
                return []

            if provider == "anthropic":
                resp = await client.get(
                    "https://api.anthropic.com/v1/models",
                    headers={"x-api-key": clean_key, "anthropic-version": "2023-06-01"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    models = [m["id"] for m in data.get("data", []) if isinstance(m, dict) and "id" in m]
                    return sorted(models)
                return []

            if provider == "gemini":
                resp = await client.get(f"https://generativelanguage.googleapis.com/v1beta/models?key={clean_key}")
                if resp.status_code == 200:
                    data = resp.json()
                    models = [
                        m["name"].replace("models/", "")
                        for m in data.get("models", [])
                        if isinstance(m, dict) and "name" in m and "generateContent" in m.get("supportedGenerationMethods", [])
                    ]
                    return sorted(models)
                return []

            if provider == "litellm":
                from app.core.config import settings
                base = (base_url or "").strip().rstrip("/") or (settings.LITELLM_API_BASE or "").rstrip("/") or "http://127.0.0.1:4000"
                resp = await client.get(f"{base}/models", headers={"Authorization": f"Bearer {clean_key}"})
                if resp.status_code == 200:
                    data = resp.json()
                    models = [m["id"] for m in data.get("data", []) if isinstance(m, dict) and "id" in m]
                    return sorted(models)
                return []

            return []
    except Exception:
        return []
