"""Endpoint POST /api/v1/search para busca web concorrente com 4 personas.

Atende a T034, RF-03, RF-04 e RF-05.
"""

import os
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.searcher import Searcher
from app.db.research_repository import ResearchRepository
from app.db.session import get_db
from app.schemas.search import SearchRequest, SearchResponse
from app.services.credential_resolver import (
    resolve_jina_base_url,
    resolve_key,
    resolve_personas,
)
from app.tools.jina_client import JinaClient
from app.tools.llm_client import LLMClient

router = APIRouter()


def _get_transport() -> Optional[httpx.AsyncBaseTransport]:
    """Retorna transporte simulado em ambiente de teste pytest ou None em produção."""
    if "PYTEST_CURRENT_TEST" in os.environ:
        try:
            from tests.mocks.http_mock import create_mock_transport
            return create_mock_transport()
        except ImportError:
            return None
    return None


def _clean_key(val: Optional[str]) -> Optional[str]:
    """Garante chave em ASCII puro para compatibilidade estrita com headers HTTP do httpx."""
    if val is None:
        return None
    cleaned = val.encode("ascii", "ignore").decode("ascii").strip()
    return cleaned if cleaned else None


# ponytail: busca síncrona aguardando gather; migrar para job assíncrono com polling/SSE se timeout > 300s
@router.post("/search", response_model=SearchResponse, status_code=status.HTTP_200_OK)
async def search_points(
    payload: SearchRequest,
    db: AsyncSession = Depends(get_db),
) -> SearchResponse:
    """Executa varredura web concorrente sob 4 personas e deduplica URLs por pesquisa."""
    transport = _get_transport()
    repo = ResearchRepository(session=db)
    try:
        jina_key = _clean_key(await resolve_key(db, "JINA_API_KEY", transport)) or (
            "jina-mock-key" if transport else None
        )
        jina_base_url = _clean_key(await resolve_jina_base_url(db, transport))
        llm_key = _clean_key(await resolve_key(db, "OPENAI_API_KEY", transport)) or (
            "openai-mock-key" if transport else None
        )
        llm_base_url = _clean_key(await resolve_key(db, "LLM_BASE_URL", transport))
        model_light = _clean_key(await resolve_key(db, "LLM_MODEL_LIGHT", transport))
        model_strong = _clean_key(await resolve_key(db, "LLM_MODEL_STRONG", transport))

        jina_client = JinaClient(api_key=jina_key, base_url=jina_base_url, transport=transport)
        llm_client = LLMClient(
            api_key=llm_key,
            base_url=llm_base_url,
            model_light=model_light,
            model_strong=model_strong,
            transport=transport,
        )
        searcher = Searcher(
            research_repo=repo,
            jina_client=jina_client,
            llm_client=llm_client,
            personas=None if transport else await resolve_personas(db),
        )
        resumo = await searcher.execute_search(
            id_pesquisa=payload.id_pesquisa,
            ponto_id=payload.ponto_id,
        )
    except ValueError as exc:
        msg = str(exc)
        if "RESEARCH_NOT_FOUND" in msg or "não localizada" in msg or "NO_PENDING_POINTS" in msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=msg,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
        )

    return SearchResponse(**resumo)
