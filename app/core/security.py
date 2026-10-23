"""Módulo de segurança e controle de acesso por chave de API (X-API-Key).

Implementa validação timing-safe com secrets.compare_digest e resolução dinâmica
de API_SECRET_KEY via variáveis de ambiente ou tabela cifrada de credenciais.
"""

import os
import secrets
from typing import Optional
from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import get_settings
from app.db.session import get_db
from app.services.credential_resolver import resolve_key


async def verify_api_key(
    request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
    db: AsyncSession = Depends(get_db),
) -> bool:
    """Valida a chave de API fornecida contra a API_SECRET_KEY configurada.
    
    Se nenhuma API_SECRET_KEY estiver configurada no ambiente ou no banco,
    permite a passagem (modo aberto).
    Se estiver configurada, exige correspondência exata via secrets.compare_digest.
    """
    settings = get_settings()
    configured_key = (
        getattr(settings, "api_secret_key", None)
        or os.environ.get("API_SECRET_KEY")
    )
    if not configured_key or not str(configured_key).strip():
        # Tenta resolver via banco cifrado
        configured_key = await resolve_key(db, "API_SECRET_KEY")

    if not configured_key or not str(configured_key).strip():
        # Modo de desenvolvimento / aberto: sem chave exigida
        return True

    provided_key = x_api_key
    if not provided_key and authorization:
        parts = authorization.strip().split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            provided_key = parts[1]
        elif len(parts) == 1:
            provided_key = parts[0]

    if not provided_key or not secrets.compare_digest(str(provided_key).strip(), str(configured_key).strip()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Chave de API ausente ou inválida.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return True
