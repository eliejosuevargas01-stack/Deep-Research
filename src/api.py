"""Superfície HTTP: POST /research e consulta do estado (PRD §2)."""

from __future__ import annotations

import asyncio
import hmac
import json
import os

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request, Security
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

import planner
from contracts import ResearchRequest
from orchestrator import Pipeline, construir_pipeline
from settings import ConfigHermes, _ler_config_remota, aplicar_config, ler_config

_INTERVALO_SSE_S = 0.5
_portador = HTTPBearer(auto_error=False)


def _chave_api() -> str:
    return os.getenv("DR_API_KEY") or os.getenv("API_KEY") or ""


def _exigir_chave(
    request: Request, credenciais: HTTPAuthorizationCredentials | None = Security(_portador)
) -> None:
    esperada = _chave_api()
    if not esperada:
        return  # sem chave configurada: aberto (só dev/testes)
    if request.url.path == "/health":
        return  # saúde sempre aberta, mesmo com chave configurada
    enviada = request.headers.get("X-API-Key") or ""
    if not enviada and credenciais is not None:
        enviada = credenciais.credentials or ""
    if not enviada:
        # EventSource não manda header: SSE aceita ?api_key=.
        enviada = request.query_params.get("api_key") or ""
    if not enviada or not hmac.compare_digest(enviada, esperada):
        raise HTTPException(status_code=401, detail="API key inválida")


def create_app(pipeline: Pipeline | None = None) -> FastAPI:
    app = FastAPI(title="Hermes Deep Research", version="0.1.0")
    app.state.pipeline = pipeline or construir_pipeline()

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/config", dependencies=[Depends(_exigir_chave)])
    @app.get("/api/v1/settings", include_in_schema=False, dependencies=[Depends(_exigir_chave)])
    def ler_configuracao() -> dict:
        return _ler_config_remota() or ler_config()

    @app.put("/config", dependencies=[Depends(_exigir_chave)])
    @app.put("/api/v1/settings", include_in_schema=False, dependencies=[Depends(_exigir_chave)])
    def gravar_configuracao(payload: ConfigHermes) -> dict:
        try:
            return aplicar_config(payload)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/research", status_code=202, dependencies=[Depends(_exigir_chave)])
    def criar(requisicao: ResearchRequest, background: BackgroundTasks) -> dict[str, str]:
        research_id = app.state.pipeline.criar(requisicao)
        background.add_task(app.state.pipeline.executar, research_id)
        return {"research_id": research_id, "status": "PROCESSING"}

    @app.get("/research/{research_id}", dependencies=[Depends(_exigir_chave)])
    def consultar(research_id: str) -> dict:
        return _consultar_run(app.state.pipeline, research_id)

    @app.get("/research/{research_id}/eventos", dependencies=[Depends(_exigir_chave)])
    @app.get("/research/{research_id}/events", dependencies=[Depends(_exigir_chave)])
    async def eventos(request: Request, research_id: str, desde: int = 0) -> StreamingResponse:
        repositorio = app.state.pipeline.repositorio
        if repositorio.obter_run(research_id) is None:
            raise HTTPException(status_code=404, detail="pesquisa não encontrada")
        cabecalho = request.headers.get("last-event-id")
        try:
            base = int(cabecalho) if cabecalho is not None else int(desde or 0)
        except ValueError:
            base = int(desde or 0)

        async def gerador():
            proximo = base
            if proximo <= 0:
                # Último id primeiro: replay depois_de=proximo pode duplicar o que o
                # snapshot já traz (at-least-once, cliente deduplica por id), nunca perde.
                proximo = await asyncio.to_thread(repositorio.ultimo_evento_id, research_id)
                retrato = await asyncio.to_thread(_consultar_run, app.state.pipeline, research_id)
                yield (
                    f"id: {proximo}\nevent: snapshot\n"
                    f"data: {json.dumps(retrato, ensure_ascii=False, default=str)}\n\n"
                )
            ociosas = 0
            while True:
                if await request.is_disconnected():
                    break
                if repositorio.obter_run(research_id) is None:
                    break
                novos = await asyncio.to_thread(repositorio.listar_eventos, research_id, proximo)
                for evento in novos:
                    yield (
                        f"id: {evento['id']}\nevent: {evento['tipo']}\n"
                        f"data: {json.dumps(evento['payload'], ensure_ascii=False, default=str)}\n\n"
                    )
                    proximo = evento["id"]
                if novos:
                    ociosas = 0
                    continue
                ociosas += 1
                if ociosas * _INTERVALO_SSE_S >= 15:
                    yield ": ping\n\n"
                    ociosas = 0
                await asyncio.sleep(_INTERVALO_SSE_S)

        return StreamingResponse(
            gerador(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return app


def _consultar_run(pipeline: Pipeline, research_id: str) -> dict:
    repositorio = pipeline.repositorio
    run = repositorio.obter_run(research_id)
    if run is None:
        raise HTTPException(status_code=404, detail="pesquisa não encontrada")
    run["pontos"] = repositorio.obter_pontos(research_id)
    auditorias = []
    for item in repositorio.obter_auditorias(research_id):
        decisao = planner.avaliar(
            perguntas_respondidas=item["perguntas_respondidas"],
            veracidade_alvo=run["veracidade_alvo"],
            tentativa_atual=item["rodada"],
            max_rodadas_auditoria=run["max_rodadas_auditoria"],
        )
        auditorias.append(
            {
                **item,
                "perguntas_true": decisao["perguntas_true"],
                "porcentagem_aprovacao": decisao["porcentagem_aprovacao"],
                "meta_veracidade_alvo": decisao["meta_veracidade_alvo"],
                "aprovado": decisao["aprovado"],
            }
        )
    run["auditorias"] = auditorias
    avaliacao = repositorio.obter_avaliacao(research_id)
    if avaliacao is not None:
        run["avaliacao_pontos"] = avaliacao
    return run
