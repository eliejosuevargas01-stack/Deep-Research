"""Superfície HTTP: POST /research e consulta do estado (PRD §2)."""

from __future__ import annotations

from fastapi import BackgroundTasks, FastAPI, HTTPException

from contracts import ResearchRequest
from orchestrator import Pipeline, construir_pipeline


def create_app(pipeline: Pipeline | None = None) -> FastAPI:
    app = FastAPI(title="Hermes Deep Research", version="0.1.0")
    app.state.pipeline = pipeline or construir_pipeline()

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/research", status_code=202)
    def criar(requisicao: ResearchRequest, background: BackgroundTasks) -> dict[str, str]:
        research_id = app.state.pipeline.criar(requisicao)
        background.add_task(app.state.pipeline.executar, research_id)
        return {"research_id": research_id, "status": "PROCESSING"}

    @app.get("/research/{research_id}")
    def consultar(research_id: str) -> dict:
        repositorio = app.state.pipeline.repositorio
        run = repositorio.obter_run(research_id)
        if run is None:
            raise HTTPException(status_code=404, detail="pesquisa não encontrada")
        run["pontos"] = repositorio.obter_pontos(research_id)
        return run

    return app
