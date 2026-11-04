import os
"""Endpoint POST /api/v1/writer para entrega do dossiê final.

O dossiê é o DOSSIE.md gravado pelo redator Hermes.
Atende a T036, RF-08, RF-09, RF-10 e RN-07.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import hermes_adapter, hermes_planner
from app.db.research_repository import ResearchRepository
from app.db.session import get_db
from app.schemas.writer import WriterRequest, WriterResponse

router = APIRouter()


# ponytail: entrega síncrona do dossiê; delegar para fila durável/Celery quando volume escalar
@router.post("/writer", response_model=WriterResponse, status_code=status.HTTP_200_OK)
async def write_dossier(
    payload: WriterRequest,
    db: AsyncSession = Depends(get_db),
) -> WriterResponse:
    """Consolida o DOSSIE.md produzido pelo redator Hermes e persiste o texto final."""
    repo = ResearchRepository(session=db)
    pesquisa = await repo.get_research(payload.id_pesquisa)
    if pesquisa is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pesquisa não encontrada para redação no pipeline Hermes.",
        )
    await hermes_adapter.marcar_inicio_etapa(repo, payload.id_pesquisa, "redigindo")
    workspace = await hermes_adapter.aguardar_arquivo(
        payload.id_pesquisa, "DOSSIE.json", tema=pesquisa.tema, timeout=float(os.environ.get("DR_WRITER_TIMEOUT", "3600"))
    )
    dados = await hermes_adapter.persistir_dossie(repo, pesquisa, workspace)
    return WriterResponse(**dados)
