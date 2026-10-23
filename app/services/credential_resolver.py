"""Resolução de credenciais e parâmetros seguindo a precedência RN-10: ENV primeiro, banco cifrado depois.

Atende a RF-11, RF-12 e RN-10. O CREDENTIALS_MASTER_KEY permanece sempre via
ambiente (é a chave de bootstrap que decifra o próprio banco).
"""

from typing import Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.credentials_repository import CredentialsRepository


async def resolve_key(
    db: AsyncSession,
    chave: str,
    test_transport: Optional[Any] = None,
) -> Optional[str]:
    """Retorna a credencial da ENV ou do banco cifrado; None se ausente em ambos.

    Em teste (PYTEST_CURRENT_TEST) retorna None para os callers aplicarem as
    chaves-mock do transporte simulado.
    """
    if test_transport is not None:
        return None
    repo = CredentialsRepository(session=db)
    try:
        return await repo.get_credential(chave)
    except ValueError:
        return None


async def resolve_n_pontos(db: AsyncSession) -> Optional[int]:
    """Resolve N_PONTOS por ENV, depois banco cifrado (RN-02, RN-10); None se ausente."""
    valor = await resolve_key(db, "N_PONTOS")
    if valor is None:
        return None
    try:
        n = int(str(valor).strip())
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


async def resolve_personas(db: AsyncSession) -> List[str]:
    """Resolve PERSONAS_CONFIG por ENV, depois banco cifrado, e devolve a lista limpa."""
    valor = await resolve_key(db, "PERSONAS_CONFIG")
    return [p.strip() for p in str(valor).split(",") if p.strip()] if valor else []


async def resolve_callback_webhook_url(db: AsyncSession) -> Optional[str]:
    """Resolve CALLBACK_WEBHOOK_URL por ENV, depois banco cifrado."""
    return await resolve_key(db, "CALLBACK_WEBHOOK_URL")


async def resolve_webhook_hmac_secret(db: AsyncSession) -> Optional[str]:
    """Resolve WEBHOOK_HMAC_SECRET por ENV, depois banco cifrado."""
    return await resolve_key(db, "WEBHOOK_HMAC_SECRET")


async def resolve_jina_base_url(
    db: AsyncSession,
    test_transport: Optional[Any] = None,
) -> Optional[str]:
    """Resolve JINA_BASE_URL via ENV ou banco; se ausente, extrai base_url do registro JINA_API_KEY."""
    if test_transport is not None:
        return None
    url = await resolve_key(db, "JINA_BASE_URL", test_transport)
    if url:
        return url
    repo = CredentialsRepository(session=db)
    record = await repo.get_credential_record("JINA_API_KEY")
    if record and record.base_url and record.base_url.strip():
        return record.base_url.strip()
    return None
