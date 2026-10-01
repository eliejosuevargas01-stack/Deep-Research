import json
import re
from typing import Any
from litellm import acompletion
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.settings import runtime_settings


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
    model = models.get(role)
    if not model:
        raise ProviderConfigurationError(f"No model configured for role '{role}'")
    provider = _provider(model)
    api_key = keys.get(provider) or keys.get("litellm")
    if not api_key:
        raise ProviderConfigurationError(f"No API key configured for model provider '{provider}'")
    kwargs: dict[str, Any] = {"model": model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}], "api_key": api_key, "timeout": 90}
    if provider == "litellm" and keys.get("litellm"):
        _, _ = keys, models
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
