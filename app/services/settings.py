from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.models import AppSettings
from app.schemas import PROVIDERS, ROLES
from app.services.crypto import decrypt_secret, encrypt_secret, mask_secret

ENV_KEYS = {
    "openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY", "gemini": "GEMINI_API_KEY",
    "litellm": "LITELLM_API_KEY", "jina": "JINA_API_KEY", "serpapi": "SERPAPI_API_KEY",
    "apify": "APIFY_API_TOKEN",
}


async def get_record(db: AsyncSession) -> AppSettings:
    record = await db.get(AppSettings, 1)
    if not record:
        record = AppSettings(id=1, encrypted_credentials={}, models={}, callback_url=None, openai_base_url=None)
        db.add(record)
        await db.flush()
    return record


async def runtime_settings(db: AsyncSession) -> tuple[dict[str, str], dict[str, str]]:
    record = await get_record(db)
    keys = {}
    for provider in PROVIDERS:
        encrypted = record.encrypted_credentials.get(provider)
        env_value = getattr(settings, ENV_KEYS[provider], None)
        if encrypted:
            keys[provider] = decrypt_secret(encrypted)
        elif env_value:
            keys[provider] = env_value
    models = {role: record.models.get(role) or getattr(settings, f"{role.upper()}_MODEL", None) for role in ROLES}
    return keys, {role: model for role, model in models.items() if model}


async def public_settings(db: AsyncSession) -> dict:
    record = await get_record(db)
    keys, models = await runtime_settings(db)
    return {
        "provider_keys": {p: mask_secret(keys[p]) if p in keys else None for p in PROVIDERS},
        "provider_configured": {p: p in keys for p in PROVIDERS},
        "models": {role: models.get(role) for role in ROLES},
        "callback_url": record.callback_url,
        "openai_base_url": record.openai_base_url,
    }


async def update_settings(
    db: AsyncSession,
    provider_keys: dict,
    models: dict,
    callback_url: str | None = None,
    openai_base_url: str | None = None,
) -> dict:
    record = await get_record(db)
    encrypted = dict(record.encrypted_credentials)
    for provider, value in provider_keys.items():
        if value is None or value == "":
            encrypted.pop(provider, None)
        elif "*" not in value:
            encrypted[provider] = encrypt_secret(value)
    merged_models = dict(record.models)
    merged_models.update(models)
    record.encrypted_credentials = encrypted
    record.models = merged_models
    if callback_url is not None:
        cleaned_callback = callback_url.strip() if callback_url else ""
        if cleaned_callback:
            from app.tools.outbound import validate_public_url
            validate_public_url(cleaned_callback)
            record.callback_url = cleaned_callback
        else:
            record.callback_url = None
    if openai_base_url is not None:
        cleaned_base = openai_base_url.strip() if openai_base_url else ""
        record.openai_base_url = cleaned_base if cleaned_base else None
    await db.commit()
    return await public_settings(db)
