"""Endpoint para consulta de status e progresso do pipeline de pesquisa contínua.

Permite verificar o estágio corrente (planejado, buscando, auditando, redigindo, concluído, falha).
"""

import asyncio
import json
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from starlette.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.pipeline_runner import _format_iso_utc, get_pipeline_event_hub
from app.db.models import ConteudoColetado
from app.db.research_repository import ResearchRepository
from app.db.session import get_db
from app.schemas.sources import FontesResumo
from app.services.source_accounting_service import SourceAccountingService

router = APIRouter()


def _format_sse(event: str, data: Dict[str, Any]) -> str:
    """Serializa evento canônico no formato W3C Server-Sent Events."""
    payload_str = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload_str}\n\n"


def _delta_key(payload: Dict[str, Any]) -> tuple:
    return (
        payload.get("stage"),
        payload.get("agent"),
        payload.get("ponto_id"),
        payload.get("kind"),
    )


def _drain_deltas(
    first: Dict[str, Any],
    queue: "asyncio.Queue",
    max_batch: int = 400,
) -> tuple:
    """Agrupa deltas consecutivos do mesmo agente/estágio em um único evento SSE.

    Sem isso, cada token do provedor vira um frame SSE (centenas por resposta).
    Eventos de outro tipo encontrados na fila são devolvidos para o chamador
    processar na próxima iteração (asyncio.Queue não tem put_front).
    """
    merged = dict(first)
    merged["text"] = first.get("text") or ""
    key = _delta_key(first)
    pending = None

    for _ in range(max_batch):
        try:
            event_type, payload = queue.get_nowait()
        except asyncio.QueueEmpty:
            break

        if event_type == "agent.delta" and _delta_key(payload) == key:
            merged["text"] += payload.get("text") or ""
            continue

        pending = (event_type, payload)
        break

    return merged, pending


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
        "tokens_prompt": int(getattr(pesquisa, "tokens_prompt", 0) or 0),
        "tokens_completion": int(getattr(pesquisa, "tokens_completion", 0) or 0),
        "tokens_total": int(getattr(pesquisa, "tokens_total", 0) or 0),
    }


@router.get(
    "/pipeline/{id_pesquisa}/sources",
    response_model=FontesResumo,
    status_code=status.HTTP_200_OK,
)
async def get_pipeline_sources(
    id_pesquisa: str,
    db: AsyncSession = Depends(get_db),
) -> FontesResumo:
    """Retorna o resumo contábil de fontes consultadas, utilizadas e não utilizadas.

    Endpoint estritamente somente-leitura para hidratação de relatórios sem acionar
    modelos LLM, leituras web ou mutações de banco de dados.
    """
    repo = ResearchRepository(session=db)
    service = SourceAccountingService(research_repo=repo)
    summary = await service.get_source_summary(id_pesquisa)
    if summary is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pesquisa não localizada: {id_pesquisa}",
        )
    return summary


@router.get("/pipeline/{id_pesquisa}/stream")
async def stream_pipeline_progress(
    id_pesquisa: str,
    request: Request,
    snapshot_only: bool = False,
    max_events: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Canal Server-Sent Events (SSE) transmitindo status, progresso e raciocínios em tempo real.

    1. Autenticação e integridade validadas via dependências (API key ou cookie de sessão).
    2. Envia snapshot inicial do banco de dados (estado atual, pontos, coletas, auditorias, dossiê).
    3. Transmite eventos do hub em memória em tempo real.
    4. Emite keep-alive ': keep-alive\\n\\n' a cada 15 segundos.
    5. Monitora cancelamento na desconexão com request.is_disconnected().
    """
    repo = ResearchRepository(session=db)
    pesquisa = await repo.get_research(id_pesquisa)
    if not pesquisa:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pesquisa não localizada: {id_pesquisa}",
        )

    pontos = await repo.list_points(id_pesquisa)
    stmt_coletas = (
        select(ConteudoColetado)
        .where(ConteudoColetado.id_pesquisa == id_pesquisa)
        .order_by(ConteudoColetado.criado_em.asc())
    )
    coletas_res = (await db.execute(stmt_coletas)).scalars().all()

    async def event_generator():
        hub = get_pipeline_event_hub()
        queue = hub.subscribe(id_pesquisa)
        emitted_count = 0

        def emit(evt_name: str, evt_payload: Dict[str, Any]) -> str:
            nonlocal emitted_count
            emitted_count += 1
            return _format_sse(evt_name, evt_payload)

        try:
            # 1. Snapshot inicial do banco de dados
            status_pipe = getattr(pesquisa, "status_pipeline", "planejado") or "planejado"
            yield emit("pipeline.status", {
                "id_pesquisa": id_pesquisa,
                "status_pipeline": status_pipe,
                "timestamp": getattr(pesquisa, "atualizado_em", None) or getattr(pesquisa, "criado_em", None) or _format_iso_utc(),
                "criado_em": pesquisa.criado_em,
                "tokens_prompt": int(getattr(pesquisa, "tokens_prompt", 0) or 0),
                "tokens_completion": int(getattr(pesquisa, "tokens_completion", 0) or 0),
                "tokens_total": int(getattr(pesquisa, "tokens_total", 0) or 0),
            })

            # Pontos e suas auditorias
            for p in pontos:
                yield emit("point.status", {
                    "id_pesquisa": id_pesquisa,
                    "ponto_id": p.ponto_id,
                    "ponto_n": p.ponto_n,
                    "status": p.status,
                    "tentativas": p.tentativas or 0,
                })
                if p.reasoning_auditoria or p.status in ("aprovado", "reprovado"):
                    yield emit("audit.result", {
                        "id_pesquisa": id_pesquisa,
                        "ponto_id": p.ponto_id,
                        "ponto_n": p.ponto_n,
                        "status": p.status,
                        "pontuacao_percentual": 100.0 if p.status == "aprovado" else 0.0,
                        "criterios_aprovados": 12 if p.status == "aprovado" else 0,
                        "reasoning_auditoria": p.reasoning_auditoria,
                        "pontos_fracos": p.pontos_fracos,
                    })

            # Coletas e seus raciocínios
            for c in coletas_res:
                if c.reasoning_coleta:
                    urls_list = []
                    if c.urls_fonte:
                        try:
                            urls_list = json.loads(c.urls_fonte)
                        except Exception:
                            urls_list = []

                    meta = {}
                    if getattr(c, "metadados_coleta", None):
                        try:
                            raw_meta = c.metadados_coleta
                            meta = json.loads(raw_meta) if isinstance(raw_meta, str) else raw_meta
                        except Exception:
                            meta = {}

                    res_personas = meta.get("resultados_personas") if isinstance(meta, dict) else None
                    if res_personas and isinstance(res_personas, dict):
                        emitted_personas = False
                        for p_name, p_val in res_personas.items():
                            p_reasoning = p_val.get("reasoning") if isinstance(p_val, dict) else None
                            if p_reasoning:
                                emitted_personas = True
                                p_urls = p_val.get("urls_fonte", []) if isinstance(p_val, dict) else []
                                yield emit("search.progress", {
                                    "id_pesquisa": id_pesquisa,
                                    "ponto_id": c.ponto_id,
                                    "persona": p_name,
                                    "queries_executadas": p_val.get("queries_executadas", 1) if isinstance(p_val, dict) else 1,
                                    "urls_lidas": len(p_urls) if isinstance(p_urls, list) else len(urls_list),
                                    "falha_coleta": bool(p_val.get("falha_coleta", False)) if isinstance(p_val, dict) else False,
                                    "reasoning_coleta": p_reasoning,
                                })
                        if not emitted_personas:
                            p_persona = (meta.get("persona") if isinstance(meta, dict) else None)
                            if not p_persona and c.reasoning_coleta:
                                lower_r = c.reasoning_coleta.lower()
                                for cand in ("historiador", "visionario", "cetico", "futurista"):
                                    if cand in lower_r:
                                        p_persona = cand
                                        break
                            p_persona = p_persona or "historiador"
                            yield emit("search.progress", {
                                "id_pesquisa": id_pesquisa,
                                "ponto_id": c.ponto_id,
                                "persona": p_persona,
                                "queries_executadas": 1,
                                "urls_lidas": len(urls_list),
                                "falha_coleta": False,
                                "reasoning_coleta": c.reasoning_coleta,
                            })
                    else:
                        p_persona = (meta.get("persona") if isinstance(meta, dict) else None)
                        if not p_persona and c.reasoning_coleta:
                            lower_r = c.reasoning_coleta.lower()
                            for cand in ("historiador", "visionario", "cetico", "futurista"):
                                if cand in lower_r:
                                    p_persona = cand
                                    break
                        p_persona = p_persona or "historiador"
                        yield emit("search.progress", {
                            "id_pesquisa": id_pesquisa,
                            "ponto_id": c.ponto_id,
                            "persona": p_persona,
                            "queries_executadas": 1,
                            "urls_lidas": len(urls_list),
                            "falha_coleta": False,
                            "reasoning_coleta": c.reasoning_coleta,
                        })

            # Dossiê final se já existente
            if pesquisa.dossier_final:
                yield emit("writer.progress", {
                    "id_pesquisa": id_pesquisa,
                    "status": "concluido",
                    "reasoning_dossier": getattr(pesquisa, "reasoning_dossier", None),
                    "total_caracteres": len(pesquisa.dossier_final),
                })
                yield emit("report.final", {
                    "id_pesquisa": id_pesquisa,
                    "status": "concluido",
                    "dossier_final": pesquisa.dossier_final,
                    "total_caracteres": len(pesquisa.dossier_final),
                    "concluido_em": pesquisa.concluido_em or _format_iso_utc(),
                })

            # Interrupção precoce configurada para snapshot_only ou limite de eventos
            if snapshot_only or (max_events is not None and emitted_count >= max_events):
                return

            # Se o pipeline já estiver em status terminal no banco e a fila estiver vazia:
            if status_pipe in ("concluido", "falha", "reprovado") and queue.empty():
                return

            # 2. Transmissão em tempo real do hub
            pending_event: Optional[tuple] = None
            while True:
                if await request.is_disconnected():
                    break
                try:
                    if pending_event is not None:
                        event_type, payload = pending_event
                        pending_event = None
                    else:
                        event_type, payload = await asyncio.wait_for(queue.get(), timeout=15.0)

                    if event_type == "agent.delta":
                        merged_delta, pending_event = _drain_deltas(payload, queue)
                        yield emit("agent.delta", merged_delta)
                        if max_events is not None and emitted_count >= max_events:
                            break
                        continue

                    yield emit(event_type, payload)
                    if max_events is not None and emitted_count >= max_events:
                        break
                    if event_type == "report.final" or (
                        event_type == "pipeline.status"
                        and payload.get("status_pipeline") in ("concluido", "falha", "reprovado")
                    ):
                        break
                except asyncio.TimeoutError:
                    if await request.is_disconnected():
                        break
                    yield ": keep-alive\n\n"
        finally:
            hub.unsubscribe(id_pesquisa, queue)

    headers = {
        "Content-Type": "text/event-stream; charset=utf-8",
        "Cache-Control": "no-cache, no-transform",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers=headers,
    )
