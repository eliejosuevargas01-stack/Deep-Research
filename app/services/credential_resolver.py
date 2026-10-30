"""Resolução de credenciais e parâmetros seguindo a nova precedência do Adendo 002: Banco Cifrado primeiro, ambiente depois.

Atende a RF-11, RF-12, RN-10 e Adendo 002. O CREDENTIALS_MASTER_KEY permanece sempre via
ambiente (é a chave de bootstrap que decifra o próprio banco).
"""

import os
from typing import Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import get_settings
from app.db.credentials_repository import CredentialsRepository


async def resolve_key(
    db: AsyncSession,
    chave: str,
    test_transport: Optional[Any] = None,
) -> Optional[str]:
    """Resolve uma credencial/parâmetro na ordem: banco cifrado, ambiente exportado, .env.

    O uvicorn não exporta o .env para ``os.environ``; por isso o Settings entra
    como terceiro nível. Em teste, o transporte simulado assume as chaves.
    """
    if test_transport is not None:
        return None

    repo = CredentialsRepository(session=db)
    try:
        value = await repo.get_credential(chave)
        if value is not None and str(value).strip() != "":
            return str(value).strip()
    except ValueError:
        pass

    env_value = os.environ.get(chave)
    if env_value is not None and env_value.strip() != "":
        return env_value.strip()

    settings_value = getattr(get_settings(), chave.lower(), None)
    if settings_value is not None and str(settings_value).strip() != "":
        return str(settings_value).strip()

    return None


async def resolve_n_pontos(db: AsyncSession) -> Optional[int]:
    """Resolve N_PONTOS por banco cifrado, depois ENV (RN-02, RN-10, Adendo 002); None se ausente."""
    valor = await resolve_key(db, "N_PONTOS")
    if valor is None:
        return None
    try:
        n = int(str(valor).strip())
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


async def resolve_personas(db: AsyncSession) -> List[str]:
    """Resolve PERSONAS_CONFIG por banco cifrado, depois ENV, e devolve a lista limpa."""
    valor = await resolve_key(db, "PERSONAS_CONFIG")
    return [p.strip() for p in str(valor).split(",") if p.strip()] if valor else []


async def resolve_callback_webhook_url(db: AsyncSession) -> Optional[str]:
    """Resolve CALLBACK_WEBHOOK_URL por banco cifrado, depois ENV."""
    return await resolve_key(db, "CALLBACK_WEBHOOK_URL")


async def resolve_webhook_hmac_secret(db: AsyncSession) -> Optional[str]:
    """Resolve WEBHOOK_HMAC_SECRET por banco cifrado, depois ENV."""
    return await resolve_key(db, "WEBHOOK_HMAC_SECRET")


async def resolve_jina_base_url(
    db: AsyncSession,
    test_transport: Optional[Any] = None,
) -> Optional[str]:
    """Resolve JINA_BASE_URL com precedência do banco: chave dedicada, base_url do
    registro JINA_API_KEY, ambiente exportado e, por último, o .env.

    A base_url gravada junto de JINA_API_KEY no banco vence o .env — é o override
    explícito do operador para a rota Jina.
    """
    if test_transport is not None:
        return None

    repo = CredentialsRepository(session=db)
    try:
        dedicated = await repo.get_credential("JINA_BASE_URL")
        if dedicated and dedicated.strip():
            return dedicated.strip()
    except ValueError:
        pass

    record = await repo.get_credential_record("JINA_API_KEY")
    if record and record.base_url and record.base_url.strip():
        return record.base_url.strip()

    env_value = os.environ.get("JINA_BASE_URL")
    if env_value and env_value.strip():
        return env_value.strip()

    settings_value = getattr(get_settings(), "jina_base_url", None)
    if settings_value and str(settings_value).strip():
        return str(settings_value).strip()
    return None
