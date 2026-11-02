"""Endpoint POST /api/v1/hermes/research.

Executa a pesquisa inteira por um perfil Hermes (planner) com troca de documentos
Markdown append-only, no lugar das chamadas diretas ao modelo em cada etapa.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import hermes_adapter, hermes_planner
from app.db.research_repository import ResearchRepository
from app.db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter()


class HermesResearchRequest(BaseModel):
    tema: str = Field(..., min_length=3, max_length=2000)
    pesquisa_id: Optional[str] = None
    perfil: Optional[str] = None
    max_rodadas: int = Field(3, ge=1, le=3)
    timeout_segundos: int = Field(3600, ge=60, le=14400)


class HermesResearchResponse(BaseModel):
    pesquisa_id: str
    diretorio: str
    status: str
    dossie: Optional[str] = None
    arquivos: Dict[str, int]
    rodadas_auditoria: int
    urls_fora_do_acervo: list[str] = []
    duracao_segundos: float
    exit_code: int
    erro: Optional[str] = None
    usage: Optional[Dict[str, Any]] = None


@router.get("/hermes/research/{pesquisa_id}")
async def hermes_research_status(pesquisa_id: str, db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """Fase, plano estruturado e contratos da pesquisa — para polling da UI."""
    pesquisa = await ResearchRepository(session=db).get_research(pesquisa_id)
    if pesquisa is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pesquisa não encontrada.")
    workspace = hermes_planner.criar_workspace(pesquisa_id, pesquisa.tema)
    return hermes_adapter.detalhe(pesquisa_id, workspace)


@router.post("/hermes/research", response_model=HermesResearchResponse, status_code=status.HTTP_200_OK)
async def research_with_hermes(payload: HermesResearchRequest) -> HermesResearchResponse:
    """Roda plano, 4 searchers, auditor e redator em um único processo Hermes."""
    pesquisa_id = payload.pesquisa_id or uuid.uuid4().hex
    try:
        resultado = await hermes_planner.executar(
            payload.tema,
            pesquisa_id,
            perfil=payload.perfil,
            max_rodadas=payload.max_rodadas,
            timeout_segundos=payload.timeout_segundos,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    logger.info(
        "[DR-HERMES] pesquisa=%s status=%s rodadas=%s dur=%.1fs dir=%s",
        pesquisa_id,
        resultado["status"],
        resultado["rodadas_auditoria"],
        resultado["duracao_segundos"],
        resultado["diretorio"],
    )
    return HermesResearchResponse(**resultado)
