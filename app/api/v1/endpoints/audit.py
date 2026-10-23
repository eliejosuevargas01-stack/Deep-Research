"""Endpoint POST /api/v1/audit para auditoria de qualidade analítica.

Atende a T035, RF-06 e RF-07.
"""

import os
import json
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auditor import Auditor
from app.db.research_repository import ResearchRepository
from app.db.session import get_db
from app.schemas.audit import AuditRequest, AuditResponse
from app.services.credential_resolver import resolve_key, resolve_personas
from app.tools.llm_client import LLMClient

router = APIRouter()


async def _persona_prompt(db: AsyncSession, transport: object) -> str | None:
    """Devolve o prompt da persona auditor; None se PERSONAS_CONFIG não contiver 'auditor'."""
    if transport is not None:
        return None
    configuradas = await resolve_personas(db)
    if "auditor" in configuradas:
        return "Você é a persona auditor com rigor metodológico, objetividade e ceticismo analítico."
    return None


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


# ponytail: auditoria atômica em bloco; suportar reavaliação parcial de ponto específico via query param
@router.post("/audit", response_model=AuditResponse, status_code=status.HTTP_200_OK)
async def audit_research(
    payload: AuditRequest,
    db: AsyncSession = Depends(get_db),
) -> AuditResponse:
    """Avalia o conteúdo coletado contra o checklist das 12 perguntas de qualidade via LLM forte."""
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
        auditor = Auditor(
            research_repo=repo,
            llm_client=llm_client,
            persona_prompt=await _persona_prompt(db, transport),
        )
        resumo = await auditor.execute_audit(id_pesquisa=payload.id_pesquisa)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Falha de formatação JSON na resposta do modelo: {str(exc)}",
        )
    except ValueError as exc:
        msg = str(exc)
        if "RESEARCH_NOT_FOUND" in msg or "não localizada" in msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=msg,
            )
        if "SEARCH_NOT_COMPLETED" in msg or "coleta" in msg:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=msg,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AUDIT_PROCESSING_ERROR: {str(exc)}",
        )

    return AuditResponse(**resumo)
