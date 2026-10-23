"""Endpoints administrativos POST e GET /api/v1/admin/credentials.

Atende a T037, RF-11, RF-12 e RN-10.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.credentials_repository import CredentialsRepository
from app.db.session import get_db
from app.schemas.admin import (
    CredentialCreateRequest,
    CredentialListResponse,
    CredentialResponse,
    CredentialSanitizedListItem,
)

router = APIRouter()


# ponytail: rota protegida apenas por rede interna no MVP; plugar dependência OAuth2/API Key no router admin
@router.post(
    "/admin/credentials",
    response_model=CredentialResponse,
    status_code=status.HTTP_200_OK,
)
async def create_or_update_credential(
    payload: CredentialCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> CredentialResponse:
    """Cifra com Fernet e salva/atualiza uma credencial sensível no banco relacional."""
    repo = CredentialsRepository(session=db)
    try:
        record = await repo.save_credential(
            chave=payload.chave,
            valor=payload.valor,
            tipo=payload.tipo,
            base_url=payload.base_url,
            descricao=payload.descricao,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    return CredentialResponse(
        status="salvo",
        chave=record.chave,
        tipo=record.tipo,
        base_url=record.base_url,
        criptografado=True,
        algoritmo="Fernet (AES-128-CBC + HMAC-SHA256)",
        atualizado_em=record.atualizado_em,
    )


@router.get(
    "/admin/credentials",
    response_model=CredentialListResponse,
    status_code=status.HTTP_200_OK,
)
async def list_credentials(
    db: AsyncSession = Depends(get_db),
) -> CredentialListResponse:
    """Lista metadados de credenciais sanitizadas com valores mascarados sem expor segredos."""
    repo = CredentialsRepository(session=db)
    items = await repo.list_sanitized()
    return CredentialListResponse(
        credenciais=[CredentialSanitizedListItem(**item) for item in items]
    )
