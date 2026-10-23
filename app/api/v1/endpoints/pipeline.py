"""Endpoint para consulta de status e progresso do pipeline de pesquisa contínua.

Permite verificar o estágio corrente (planejado, buscando, auditando, redigindo, concluído, falha).
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.research_repository import ResearchRepository
from app.db.session import get_db

router = APIRouter()


@router.get("/pipeline/{id_pesquisa}/status", status_code=status.HTTP_200_OK)
async def get_pipeline_status(
    id_pesquisa: str,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Consulta o status em tempo real do processamento do pipeline."""
    repo = ResearchRepository(session=db)
    pesquisa = await repo.get_research(id_pesquisa)
    if not pesquisa:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pesquisa não localizada: {id_pesquisa}",
        )

    pontos = await repo.list_points(id_pesquisa)
    pontos_resumo = [
        {
            "ponto_id": p.ponto_id,
            "ponto_n": p.ponto_n,
            "status": p.status,
            "tentativas": p.tentativas,
            "tentativas_auditoria": p.tentativas_auditoria,
            "pontos_fracos": p.pontos_fracos,
            "reasoning_planejamento": getattr(p, "reasoning_planejamento", None),
            "reasoning_auditoria": getattr(p, "reasoning_auditoria", None),
        }
        for p in pontos
    ]

    return {
        "id_pesquisa": pesquisa.id_pesquisa,
        "tema": pesquisa.tema,
        "status_pipeline": getattr(pesquisa, "status_pipeline", "planejado"),
        "erro_pipeline": getattr(pesquisa, "erro_pipeline", None),
        "criado_em": pesquisa.criado_em,
        "concluido_em": pesquisa.concluido_em,
        "webhook_status": pesquisa.webhook_status,
        "total_pontos": len(pontos),
        "pontos": pontos_resumo,
        "tem_dossier": bool(pesquisa.dossier_final),
        "reasoning_dossier": getattr(pesquisa, "reasoning_dossier", None),
    }
