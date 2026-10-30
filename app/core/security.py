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
from app.ui_session import COOKIE_NAME, verify_same_origin_csrf, verify_session_token


async def verify_api_key(
    request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
    db: AsyncSession = Depends(get_db),
) -> bool:
    """Valida a chave de API externa (X-API-Key / Bearer) ou sessão de navegador local assinada.
    
    1. Se fornecida chave de API ou Bearer token, valida contra API_SECRET_KEY configurada.
    2. Se não fornecida chave externa, verifica se há cookie de sessão local assinado e válido,
       exigindo proteção de mesma origem (CSRF) para requisições mutantes.
    3. Se nenhum método for fornecido e houver API_SECRET_KEY configurada, rejeita com 401.
    4. Se nenhuma chave estiver configurada no servidor, permite passagem em modo de desenvolvimento.
    """
    settings = get_settings()
    configured_key = (
        os.environ.get("API_SECRET_KEY")
        or getattr(settings, "api_secret_key", None)
    )
    if not configured_key or not str(configured_key).strip():
        # Tenta resolver via banco cifrado
        configured_key = await resolve_key(db, "API_SECRET_KEY")

    has_configured_key = bool(configured_key and str(configured_key).strip())

    provided_key = x_api_key
    if not provided_key and authorization:
        parts = authorization.strip().split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            provided_key = parts[1]
        elif len(parts) == 1:
            provided_key = parts[0]
    if (
        not provided_key
        and hasattr(request, "query_params")
        and getattr(request, "method", "").upper() in ("GET", "HEAD")
    ):
        provided_key = request.query_params.get("token") or request.query_params.get("api_key")

    # 1. Autenticação via Chave de API externa
    if provided_key:
        if has_configured_key:
            if not secrets.compare_digest(str(provided_key).strip(), str(configured_key).strip()):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Chave de API ausente ou inválida.",
                    headers={"WWW-Authenticate": "ApiKey"},
                )
        return True

    # 2. Autenticação via Cookie de Sessão Local de Navegador
    cookie_token = request.cookies.get(COOKIE_NAME) if hasattr(request, "cookies") else None
    if cookie_token and verify_session_token(cookie_token):
        if not verify_same_origin_csrf(request):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Requisição cross-site rejeitada por segurança de mesma origem.",
            )
        return True

    # 3. Nenhuma credencial válida fornecida
    if has_configured_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Chave de API ausente ou inválida.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # Modo de desenvolvimento / aberto: sem chave exigida
    return True
