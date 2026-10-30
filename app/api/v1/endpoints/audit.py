"""Endpoint POST /api/v1/audit para auditoria de qualidade analítica.

Atende a T035, RF-06, RF-07 e adendo v5-audit.
"""

import os
import asyncio
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
from app.tools.errors import LLMCallError

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


@router.post("/audit", response_model=AuditResponse, status_code=status.HTTP_200_OK)
async def audit_research(
    payload: AuditRequest,
    db: AsyncSession = Depends(get_db),
) -> AuditResponse:
    """Avalia o conteúdo coletado contra o checklist das 12 perguntas de qualidade via LLM forte."""
    transport = _get_transport()
    repo = ResearchRepository(session=db)
    llm_client: Optional[LLMClient] = None
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

        personas_config = None if transport else await resolve_personas(db)

        auditor = Auditor(
            research_repo=repo,
            llm_client=llm_client,
            personas=personas_config,
        )
        resumo = await auditor.execute_audit(
            id_pesquisa=payload.id_pesquisa,
            ponto_id=payload.ponto_id,
            criterios_minimos=payload.criterios_minimos,
        )
        return AuditResponse(**resumo)

    except LLMCallError as exc:
        # Falha do provedor LLM não é erro do cliente: 502, com o motivo real
        # (ex.: content_filter) em vez de um 400 genérico de validação.
        envelope = getattr(exc, "envelope", None)
        motivo = getattr(envelope, "finish_reason", None)
        detalhe = str(exc)
        if motivo == "content_filter":
            detalhe += (
                " O provedor aplicou filtro de conteúdo sobre a evidência enviada."
                " Tente novamente; se persistir, troque o modelo da auditoria ou"
                " reduza a quantidade de fontes por ponto."
            )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AUDIT_LLM_PROVIDER_ERROR: {detalhe}",
        )

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
        if "CONCURRENT_EXECUTION" in msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=msg,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
        )
    except HTTPException:
        raise
    except (TimeoutError, asyncio.TimeoutError) as exc:
        # Sem mensagem própria, o TimeoutError virava "AUDIT_PROCESSING_ERROR: ".
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=(
                "AUDIT_TIMEOUT: a auditoria excedeu o tempo limite do ponto. "
                "A evidência foi preservada; repita a auditoria."
            ),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AUDIT_PROCESSING_ERROR: {str(exc)}",
        )
    finally:
        if llm_client is not None:
            await llm_client.aclose()
