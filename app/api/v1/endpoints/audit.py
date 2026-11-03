import os
"""Endpoint POST /api/v1/audit para auditoria de qualidade analítica.

A auditoria roda no perfil Hermes; a resposta deriva das seções de AUDITORIA.md.
Atende a T035, RF-06, RF-07 e adendo v5-audit.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import hermes_adapter, hermes_planner
from app.db.research_repository import ResearchRepository
from app.db.session import get_db
from app.schemas.audit import AuditRequest, AuditResponse

router = APIRouter()


@router.post("/audit", response_model=AuditResponse, status_code=status.HTTP_200_OK)
async def audit_research(
    payload: AuditRequest,
    db: AsyncSession = Depends(get_db),
) -> AuditResponse:
    """Avalia as rodadas do auditor Hermes contra o checklist das 12 perguntas."""
    repo = ResearchRepository(session=db)
    pesquisa = await repo.get_research(payload.id_pesquisa)
    if pesquisa is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pesquisa não encontrada para auditoria no pipeline Hermes.",
        )
    workspace = await hermes_adapter.aguardar_arquivo(
        payload.id_pesquisa, "AUDITORIA.md", timeout=float(os.environ.get("DR_AUDIT_TIMEOUT", "3600"))
    )
    return AuditResponse(
        **hermes_adapter.audit_payload(
            payload.id_pesquisa, workspace, payload.criterios_minimos or 11
        )
    )
