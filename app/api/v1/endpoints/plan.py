"""Endpoint POST /api/v1/plan para formulação de plano de investigação.

Atende a T033, RF-01, RF-02 e RN-02.
"""

import os
import asyncio
import json
from typing import Any, Dict, List, Optional, Union
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status
from starlette.responses import StreamingResponse
import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pipeline_runner import PipelineRunner

import asyncio as _asyncio
import logging as _logging

_pipeline_logger = _logging.getLogger(__name__)


async def _heartbeat_pipeline(id_pesquisa: str) -> None:
    """Heartbeat: se o pipeline travar, o log mostra quantas tarefas seguem vivas."""
    while True:
        await _asyncio.sleep(120)
        vivas = sorted({t.get_name() for t in _asyncio.all_tasks() if not t.done()})
        print(
            f"[DR-PIPE] heartbeat {id_pesquisa}: {len(vivas)} tarefas vivas: {vivas[:12]}",
            flush=True,
        )


async def _run_pipeline_em_background(
    runner: PipelineRunner,
    id_pesquisa: str,
    callback_url,
    execution_mode,
) -> None:
    print(f"[DR-PIPE] background iniciado para {id_pesquisa}", flush=True)
    heartbeat = _asyncio.create_task(_heartbeat_pipeline(id_pesquisa), name=f"heartbeat:{id_pesquisa}")
    try:
        resultado = await runner.run(id_pesquisa, callback_url, execution_mode)
        print(
            f"[DR-PIPE] background finalizado {id_pesquisa}: "
            f"status={(resultado or {}).get('status')} detalhe={(resultado or {}).get('detalhe')}",
            flush=True,
        )
    except BaseException as exc:
        print(f"[DR-PIPE] background FALHOU {id_pesquisa}: {exc!r}", flush=True)
        _pipeline_logger.exception("[PipelineRunner] background falhou para %s", id_pesquisa)
        raise
    finally:
        heartbeat.cancel()
from app.core.planner import PlanAmbiguityError, PlanContractError, Planner
from app.core.stream_context import stream_scope
from app.db.research_repository import ResearchRepository
from app.db.session import get_db
from app.schemas.plan import (
    PlanAsyncResponse,
    PlanPontoItem,
    PlanPreferencias,
    PlanRequest,
    PlanResponse,
    PlanoEixo,
    PlanoInvestigacao,
)
from app.services.credential_resolver import (
    resolve_jina_base_url,
    resolve_key,
    resolve_n_pontos,
    resolve_personas,
)
from app.tools.errors import JinaError, LLMCallError
from app.tools.jina_client import JinaClient
from app.tools.llm_client import LLMClient
from app.tools.llm_types import project_public_envelope, redact_sensitive_string

print("[DR-BOOT] plan.py carregado de <stdin>", flush=True)

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
    jina_client = None
    llm_client = None
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

        # Resolução de n_pontos e personas efetivos respeitando preferências por pesquisa
        plan_n_pontos = payload.n_pontos if payload.n_pontos is not None else (None if transport else await resolve_n_pontos(db))

        if payload.personas is not None:
            effective_search_personas = list(payload.personas)
        else:
            resolved_personas_raw = None if transport else await resolve_personas(db)
            if resolved_personas_raw:
                effective_search_personas = [p for p in resolved_personas_raw if p in ("historiador", "visionario", "cetico", "futurista")]
            else:
                from app.config import get_settings
                settings_p = getattr(get_settings(), "personas_config", None) or os.environ.get("PERSONAS_CONFIG")
                if settings_p:
                    effective_search_personas = [p.strip() for p in str(settings_p).split(",") if p.strip() in ("historiador", "visionario", "cetico", "futurista")]
                else:
                    effective_search_personas = ["historiador", "visionario", "cetico", "futurista"]
            if not effective_search_personas:
                effective_search_personas = ["historiador", "visionario", "cetico", "futurista"]

        planner = Planner(
            research_repo=repo,
            jina_client=jina_client,
            llm_client=llm_client,
            n_pontos=plan_n_pontos,
            personas=None,
        )

        preferencias_snapshot = {
            "n_pontos": planner.n_pontos,
            "personas": effective_search_personas,
            "recencia": payload.recencia or "auto",
        }

        with stream_scope(payload.id_pesquisa, "plan", agent="planejador"):
            pesquisa = await planner.execute_plan(
                tema=payload.tema,
                id_pesquisa=payload.id_pesquisa,
                preferencias=preferencias_snapshot,
                recencia=payload.recencia,
            )
        pontos = await repo.list_points(pesquisa.id_pesquisa)
        if len(pontos) != planner.n_pontos:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Divergência na quantidade de pontos gerados ({len(pontos)}) em relação ao solicitado ({planner.n_pontos}).",
            )
    except PlanAmbiguityError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "tipo": "ambiguidade_bloqueante",
                "pergunta_de_esclarecimento": exc.pergunta,
                "mensagem": str(exc),
                "envelopes": [project_public_envelope(e) for e in exc.envelopes],
            },
        )
    except LLMCallError as exc:
        envs = (
            [project_public_envelope(e) for e in exc.envelopes]
            if exc.envelopes
            else ([project_public_envelope(exc.envelope)] if exc.envelope else [])
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "tipo": "LLMCallError",
                "mensagem": redact_sensitive_string(str(exc)),
                "envelopes": envs,
            },
        )
    except PlanContractError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "tipo": "PlanContractError",
                "diagnostico": exc.motivo,
                "mensagem": str(exc),
                "envelopes": [project_public_envelope(e) for e in exc.envelopes],
            },
        )
    except JinaError as exc:
        status_code = (
            status.HTTP_504_GATEWAY_TIMEOUT
            if exc.http_status == 504
            else status.HTTP_502_BAD_GATEWAY
        )
        raise HTTPException(
            status_code=status_code,
            detail={
                "tipo": "JinaError",
                "categoria": exc.categoria,
                "mensagem": str(exc),
                "acao_corretiva": exc.acao_corretiva,
            },
        ) from exc
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
    finally:
        if llm_client:
            await llm_client.aclose()
        if jina_client:
            await jina_client.aclose()

    pontos_items = []
    for p in pontos:
        eixo_obj = None
        if getattr(p, "eixo_estruturado", None):
            try:
                eixo_obj = PlanoEixo.model_validate_json(p.eixo_estruturado)
            except Exception:
                pass
        pontos_items.append(
            PlanPontoItem(
                ponto_id=p.ponto_id,
                ponto_n=p.ponto_n,
                ponto=p.ponto,
                status=p.status,
                pontos_fracos=p.pontos_fracos,
                reasoning_planejamento=p.reasoning_planejamento,
                reasoning_auditoria=p.reasoning_auditoria,
                eixo_estruturado=eixo_obj,
            )
        )

    plano_estruturado = getattr(pesquisa, "_plano_estruturado", None)
    if plano_estruturado is None and getattr(pesquisa, "plano_estruturado", None):
        try:
            plano_estruturado = PlanoInvestigacao.model_validate_json(pesquisa.plano_estruturado)
        except Exception:
            pass

    metadados_modelo = getattr(pesquisa, "_metadados_modelo", None)
    if metadados_modelo is None and getattr(pesquisa, "metadados_planejamento", None):
        try:
            metadados_modelo = json.loads(pesquisa.metadados_planejamento)
        except Exception:
            pass

    # Pref snapshot para resposta
    recencia_meta = {}
    if isinstance(metadados_modelo, dict):
        recencia_meta = metadados_modelo.get("recencia") or {}
    pref_obj = PlanPreferencias(
        n_pontos=len(pontos),
        personas=effective_search_personas,
        recencia=(preferencias_snapshot.get("recencia") or "auto"),
        data_referencia=(
            (plano_estruturado.data_referencia if plano_estruturado else None)
            or recencia_meta.get("data_referencia")
        ),
        execution_mode=payload.execution_mode,
    )

    # Se async_execute for True, agenda a execução ininterrupta em background
    if payload.async_execute:
        response.status_code = status.HTTP_202_ACCEPTED
        runner = PipelineRunner(transport=transport)
        background_tasks.add_task(
            _run_pipeline_em_background,
            runner,
            pesquisa.id_pesquisa,
            payload.callback_url,
            payload.execution_mode,
        )
        return PlanAsyncResponse(
            id_pesquisa=pesquisa.id_pesquisa,
            tema=pesquisa.tema,
            status="iniciado",
            status_pipeline="planejado",
            n_pontos=len(pontos),
            callback_url=payload.callback_url,
            pontos=pontos_items,
            plano_estruturado=plano_estruturado,
            metadados_modelo=metadados_modelo,
            preferencias=pref_obj,
        )

    return PlanResponse(
        id_pesquisa=pesquisa.id_pesquisa,
        tema=pesquisa.tema,
        n_pontos=len(pontos),
        criado_em=pesquisa.criado_em,
        status_pipeline="planejado",
        pontos=pontos_items,
        plano_estruturado=plano_estruturado,
        metadados_modelo=metadados_modelo,
        preferencias=pref_obj,
    )


@router.get("/plan/{id_pesquisa}/stream")
async def stream_plan_reasoning(id_pesquisa: str, request: Request) -> StreamingResponse:
    """Transmite o raciocínio do Planejador enquanto `POST /plan` ainda está em curso.

    O `Planner` roda dentro de `stream_scope(id_pesquisa, "plan")`, então cada token do
    provedor chega ao hub antes de a resposta HTTP existir. Este canal permite abrir a
    tela intermediária de planejamento sem esperar o plano completo.
    """
    from app.core.pipeline_runner import get_pipeline_event_hub

    async def event_generator():
        hub = get_pipeline_event_hub()
        queue = hub.subscribe(id_pesquisa)
        try:
            yield ": conectado\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event_name, payload = await asyncio.wait_for(queue.get(), timeout=15)
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                yield f"event: {event_name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
        finally:
            hub.unsubscribe(id_pesquisa, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )
