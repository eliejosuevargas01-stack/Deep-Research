"""Endpoint POST /api/v1/writer para redação do dossiê final e despacho de webhook.

Atende a T036, RF-08, RF-09, RF-10 e RN-07.
"""

import os
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.writer import Writer
from app.db.research_repository import ResearchRepository
from app.db.session import get_db
from app.schemas.writer import WriterRequest, WriterResponse
from app.services.credential_resolver import resolve_key, resolve_personas
from app.services.webhook_client import WebhookClient
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


# ponytail: webhook síncrono com retries integrados; delegar para fila durável/Celery quando volume escalar
@router.post("/writer", response_model=WriterResponse, status_code=status.HTTP_200_OK)
async def write_dossier(
    payload: WriterRequest,
    db: AsyncSession = Depends(get_db),
) -> WriterResponse:
    """Consolida pontos auditados, redige o dossiê final e despacha notificação assinada via webhook."""
    transport = _get_transport()
    repo = ResearchRepository(session=db)
    try:
        llm_key = _clean_key(await resolve_key(db, "OPENAI_API_KEY", transport)) or (
            "openai-mock-key" if transport else None
        )
        llm_base_url = _clean_key(await resolve_key(db, "LLM_BASE_URL", transport))
        model_light = _clean_key(await resolve_key(db, "LLM_MODEL_LIGHT", transport))
        model_strong = _clean_key(await resolve_key(db, "LLM_MODEL_STRONG", transport))

        llm_client = LLMClient(
            api_key=llm_key,
            base_url=llm_base_url,
            model_light=model_light,
            model_strong=model_strong,
            transport=transport,
        )
        webhook_secret = _clean_key(await resolve_key(db, "WEBHOOK_HMAC_SECRET", transport)) or (
            "test-secret" if transport else None
        )
        webhook_client = (
            WebhookClient(secret=webhook_secret, transport=transport, research_repo=repo)
            if webhook_secret
            else None
        )
        writer = Writer(
            research_repo=repo,
            llm_client=llm_client,
            webhook_client=webhook_client,
            personas=None if transport else await resolve_personas(db),
        )
        resumo = await writer.execute_writer(id_pesquisa=payload.id_pesquisa)
    except ValueError as exc:
        msg = str(exc)
        if "RESEARCH_NOT_FOUND" in msg or "não localizada" in msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=msg,
            )
        if "PENDING_AUDIT_POINTS" in msg or "pendente" in msg:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=msg,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
        )

    return WriterResponse(**resumo)
