"""Endpoint POST /api/v1/writer para redação do dossiê final e despacho de webhook.

Atende a T036, RF-08, RF-09, RF-10 e RN-07.
"""

import asyncio
import json
import logging
import os
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
import httpx
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from app.core.writer import Writer
from app.db.research_repository import ResearchRepository
from app.db.session import get_db
from app.schemas.writer import WriterRequest, WriterResponse
from app.services.credential_resolver import (
    resolve_callback_webhook_url,
    resolve_key,
    resolve_personas,
    resolve_webhook_hmac_secret,
)
from app.services.source_accounting_service import SourceAccountingService
from app.services.webhook_client import WebhookClient
from app.tools.errors import LLMCallError
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
    llm_client: Optional[LLMClient] = None
    webhook_client: Optional[WebhookClient] = None
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
        webhook_secret = _clean_key(await resolve_webhook_hmac_secret(db)) or (
            "test-secret" if transport else None
        )
        webhook_client = (
            WebhookClient(secret=webhook_secret, transport=transport, research_repo=repo)
            if webhook_secret
            else None
        )
        callback_url = await resolve_callback_webhook_url(db)
        writer = Writer(
            research_repo=repo,
            llm_client=llm_client,
            webhook_client=webhook_client,
            callback_url=callback_url,
            personas=None,
        )
        resumo = await writer.execute_writer(id_pesquisa=payload.id_pesquisa)
        # Contabilidade pública de fontes aditiva (consultadas, utilizadas, não utilizadas)
        try:
            source_service = SourceAccountingService(research_repo=repo)
            fontes_summary = await source_service.get_source_summary(
                id_pesquisa=payload.id_pesquisa,
                dossier_override=resumo.get("dossier_final"),
            )
            if fontes_summary is not None:
                resumo["fontes"] = fontes_summary
        except Exception as src_err:
            logger.warning(f"Falha ao computar resumo de fontes para {payload.id_pesquisa}: {src_err}")
        # W07/W12 (r3): timeout TOTAL do core chega como TimeoutError TIPADO capturado
        # abaixo (HTTP 504); não há mais envelope diagnóstico nominal com 200.
        return WriterResponse(**resumo)
    except (TimeoutError, asyncio.TimeoutError) as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"TIMEOUT_ERROR: {str(exc)}",
        )
    except LLMCallError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM_PROVIDER_ERROR: {str(exc)}",
        )
    except (json.JSONDecodeError, httpx.HTTPError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"EXTERNAL_PROVIDER_ERROR: {str(exc)}",
        )
    except ValueError as exc:
        msg = str(exc)
        if "RESEARCH_NOT_FOUND" in msg or "não localizada" in msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=msg,
            )
        if any(term in msg for term in ("CONCURRENCY_CONFLICT", "CONCURRENT_EXECUTION", "outro processo", "lease", "bloqueio")):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=msg,
            )
        if any(term in msg for term in ("LLM_FAILURE", "LLM_ERROR")):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=msg,
            )
        if any(term in msg for term in ("TIMEOUT", "timed out")):
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=msg,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"WRITER_PROCESSING_ERROR: {str(exc)}",
        )
    finally:
        # W12 (r4): fecha TAMBÉM o WebhookClient criado, em qualquer caminho (erro ou
        # sucesso), sem impedir o fechamento do LLMClient — falha no aclose do webhook
        # é best-effort e nunca pula o fechamento do outro cliente.
        if webhook_client is not None:
            try:
                await webhook_client.aclose()
            except Exception:
                pass
        if llm_client is not None:
            await llm_client.aclose()
