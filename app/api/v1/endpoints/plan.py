"""Endpoint POST /api/v1/plan para formulação de plano de investigação.

Atende a T033, RF-01, RF-02 e RN-02.
"""

import os
import json
from typing import Any, Dict, List, Optional, Union
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status
import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pipeline_runner import PipelineRunner
from app.core.planner import Planner
from app.db.research_repository import ResearchRepository
from app.db.session import get_db
from app.schemas.plan import PlanAsyncResponse, PlanPontoItem, PlanRequest, PlanResponse
from app.services.credential_resolver import (
    resolve_jina_base_url,
    resolve_key,
    resolve_n_pontos,
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


@router.post("/plan", status_code=status.HTTP_201_CREATED)
async def create_plan(
    payload: PlanRequest,
    response: Response,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> Union[PlanResponse, PlanAsyncResponse]:
    """Formula N pontos focais para o tema e persiste a pesquisa no SQLite permanente."""
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
        # O plano utiliza o modelo forte (Step 5) conforme configuração operacional
        plan_model = model_strong or model_light
        llm_client = LLMClient(
            api_key=llm_key,
            base_url=llm_base_url,
            model_light=plan_model,
            model_strong=model_strong,
            transport=transport,
        )
        planner = Planner(
            research_repo=repo,
            jina_client=jina_client,
            llm_client=llm_client,
            n_pontos=None if transport else await resolve_n_pontos(db),
            personas=None if transport else await resolve_personas(db),
        )
        pesquisa = await planner.execute_plan(
            tema=payload.tema,
            id_pesquisa=payload.id_pesquisa,
        )
        pontos = await repo.list_points(pesquisa.id_pesquisa)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Falha de formatação JSON na resposta do modelo: {str(exc)}",
        )
    except ValueError as exc:
        msg = str(exc)
        if "N_PONTOS" in msg or "Configuração ausente" in msg:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"CONFIG_ERROR: {msg}",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
        )

    pontos_items = [
        PlanPontoItem(
            ponto_id=p.ponto_id,
            ponto_n=p.ponto_n,
            ponto=p.ponto,
            status=p.status,
            pontos_fracos=p.pontos_fracos,
            reasoning_planejamento=p.reasoning_planejamento,
            reasoning_auditoria=p.reasoning_auditoria,
        )
        for p in pontos
    ]

    # Se async_execute for True, agenda a execução ininterrupta em background
    if payload.async_execute:
        response.status_code = status.HTTP_202_ACCEPTED
        runner = PipelineRunner(transport=transport)
        background_tasks.add_task(runner.run, pesquisa.id_pesquisa, payload.callback_url)
        return PlanAsyncResponse(
            id_pesquisa=pesquisa.id_pesquisa,
            tema=pesquisa.tema,
            status="iniciado",
            status_pipeline="planejado",
            n_pontos=len(pontos),
            callback_url=payload.callback_url,
            pontos=pontos_items,
        )

    return PlanResponse(
        id_pesquisa=pesquisa.id_pesquisa,
        tema=pesquisa.tema,
        n_pontos=len(pontos),
        criado_em=pesquisa.criado_em,
        status_pipeline="planejado",
        pontos=pontos_items,
    )
