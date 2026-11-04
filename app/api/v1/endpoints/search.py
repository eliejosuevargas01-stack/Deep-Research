import os
"""Endpoint POST /api/v1/search para busca web concorrente com 4 personas.

A coleta roda no perfil Hermes; a resposta deriva dos quatro `*_SEARCH.md`.
Atende a T034, RF-03, RF-04 e RF-05.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import hermes_adapter
from app.db.research_repository import ResearchRepository
from app.db.session import get_db
from app.schemas.search import SearchRequest, SearchResponse

print("[DR-BOOT] search.py carregado de <stdin>", flush=True)

router = APIRouter()


# ponytail: busca síncrona aguardando o processo Hermes; migrar para job assíncrono com polling/SSE se timeout > 300s
@router.post("/search", response_model=SearchResponse, status_code=status.HTTP_200_OK)
async def search_points(
    payload: SearchRequest,
    db: AsyncSession = Depends(get_db),
) -> SearchResponse:
    """Executa a varredura das 4 personas no Hermes e devolve o resumo dos arquivos."""
    repo = ResearchRepository(session=db)
    pesquisa = await repo.get_research(payload.id_pesquisa)
    if pesquisa is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pesquisa não encontrada para execução no pipeline Hermes.",
        )
    try:
        workspace = await hermes_adapter.garantir_pesquisa(payload.id_pesquisa, pesquisa.tema)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"HERMES_UNAVAILABLE: {exc}",
        ) from exc
    await hermes_adapter.marcar_inicio_etapa(repo, payload.id_pesquisa, "buscando")
    await hermes_adapter.aguardar_coletas(
        payload.id_pesquisa, timeout=float(os.environ.get("DR_SEARCH_TIMEOUT", "3600"))
    )
    return SearchResponse(**await hermes_adapter.persistir_busca(repo, pesquisa, workspace))
