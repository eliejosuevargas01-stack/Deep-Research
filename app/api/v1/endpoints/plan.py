"""Endpoint POST /api/v1/plan para formulação de plano de investigação.

O plano é o bloco ```json``` do PLAN.md gravado pelo perfil Hermes embutido.
Atende a T033, RF-01, RF-02 e RN-02.
"""

import asyncio
import json
import uuid
from typing import Union

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from app.core import hermes_adapter
from app.db.research_repository import ResearchRepository
from app.db.session import get_db
from app.schemas.plan import (
    PlanAsyncResponse,
    PlanPontoItem,
    PlanPreferencias,
    PlanRequest,
    PlanResponse,
)

print("[DR-BOOT] plan.py carregado de <stdin>", flush=True)

router = APIRouter()


@router.post("/plan", status_code=status.HTTP_201_CREATED)
async def create_plan(
    payload: PlanRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> Union[PlanResponse, PlanAsyncResponse]:
    """Roda o perfil Hermes e devolve o plano estruturado derivado de PLAN.md."""
    repo = ResearchRepository(session=db)
    id_pesquisa = payload.id_pesquisa or str(uuid.uuid4())
    pesquisa = await repo.get_research(id_pesquisa)
    tema = pesquisa.tema if pesquisa else payload.tema

    try:
        workspace = await hermes_adapter.garantir_pesquisa(
            id_pesquisa, tema, payload.n_pontos or 1
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"HERMES_UNAVAILABLE: {exc}",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    plano = hermes_adapter.plan_payload(workspace)
    legado = not plano["valido"]
    if legado:
        # Pesquisa gravada antes do contrato DR-006: o PLAN.md antigo não valida mais.
        # Serve o que já está no banco em vez de derrubar a tela com 422.
        if pesquisa is None or not await repo.list_points(id_pesquisa):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"tipo": "PlanContractError", "diagnostico": plano["erro"]},
            )
        plano_dict = json.loads(pesquisa.plano_estruturado) if pesquisa.plano_estruturado else {}
    else:
        plano_dict = plano["plano"]
    eixos = plano_dict.get("eixos") or []

    if pesquisa is None:
        pesquisa = await repo.create_research(
            tema=tema,
            pontos_textos=hermes_adapter.pontos_do_plano(plano_dict, payload.n_pontos),
            id_pesquisa=id_pesquisa,
            plano_estruturado=plano_dict,
            eixos_estruturados=eixos,
        )
    pontos = await repo.list_points(id_pesquisa)
    hermes_adapter.registrar_pontos(id_pesquisa, [p.ponto_id for p in pontos])

    def _eixo_do_ponto(ponto, indice: int):
        bruto = getattr(ponto, "eixo_estruturado", None)
        if bruto:
            return json.loads(bruto) if isinstance(bruto, str) else bruto
        return eixos[indice - 1] if len(eixos) >= indice else None

    pontos_items = [
        PlanPontoItem(
            ponto_id=p.ponto_id,
            ponto_n=p.ponto_n,
            ponto=p.ponto,
            status=p.status,
            eixo_estruturado=_eixo_do_ponto(p, p.ponto_n),
        )
        for p in pontos
    ]
    pref_obj = PlanPreferencias(
        n_pontos=len(pontos),
        personas=sorted(plano_dict.get("personas") or hermes_adapter.PERSONA_ARQUIVOS),
        recencia=payload.recencia or "auto",
        execution_mode=payload.execution_mode,
    )
    plano_publico = None if legado else plano_dict
    reasoning_planejamento = plano_dict.get("pedido_normalizado")
    dossie_pronto = (workspace / hermes_adapter.DOSSIE_ARQUIVO).exists()
    status_servidor = getattr(pesquisa, "status_pipeline", None) or "planejado"

    if payload.async_execute:
        response.status_code = status.HTTP_202_ACCEPTED
        return PlanAsyncResponse(
            id_pesquisa=pesquisa.id_pesquisa,
            tema=pesquisa.tema,
            status="concluido" if dossie_pronto else "falha",
            status_pipeline=status_servidor,
            mensagem="Pesquisa executada pelo pipeline Hermes; dossiê disponível em /writer.",
            n_pontos=len(pontos),
            callback_url=payload.callback_url,
            pontos=pontos_items,
            plano_estruturado=plano_publico,
            preferencias=pref_obj,
            reasoning_planejamento=reasoning_planejamento,
        )

    return PlanResponse(
        id_pesquisa=pesquisa.id_pesquisa,
        tema=pesquisa.tema,
        n_pontos=len(pontos),
        criado_em=pesquisa.criado_em,
        status_pipeline=status_servidor,
        pontos=pontos_items,
        plano_estruturado=plano_publico,
        preferencias=pref_obj,
        reasoning_planejamento=reasoning_planejamento,
    )


@router.get("/plan/{id_pesquisa}/stream")
async def stream_plan_reasoning(id_pesquisa: str, request: Request) -> StreamingResponse:
    """Transmite eventos do estágio de planejamento enquanto `POST /plan` está em curso."""
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
