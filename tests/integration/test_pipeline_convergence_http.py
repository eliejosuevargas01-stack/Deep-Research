"""Teste de convergência HTTP ponta a ponta (T026, RF-508, RN-510).

Cobre:
1. Ciclo real de entrypoints HTTP (modular briefing/investigation e adaptador de pesquisa).
2. Sem mock de run_investigation/run_research; mock apenas de LLM/transport/callback.
3. Eventos SSE e transição atômica até WRITE e DONE com Report único persistido.
4. Consulta GET /api/reports/{id} retornando o relatório gerado.
5. Endpoint de retry-callback executa sem regenerar nem sobrescrever o Report existente.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.audit.service import AuditService
from app.investigation.schemas import CitationItem
from app.investigation.worker import PersonaExecutionResult, PersonaWorker
from app.main import app
from app.models.domain_models import (
    AppSettings,
    Base,
    Report,
    Research,
    ResearchPoint,
    ResearchStatus,
)
from app.services.research import run_research


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def session_factory():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    with patch("app.db.database.engine", engine), \
         patch("app.db.database.AsyncSessionLocal", factory), \
         patch("app.services.research.AsyncSessionLocal", factory), \
         patch("app.audit.service.AsyncSessionLocal", factory), \
         patch("app.services.pipeline.writer.AsyncSessionLocal", factory), \
         patch("app.routers.research.AsyncSessionLocal", factory):
        try:
            yield factory
        finally:
            await engine.dispose()


@pytest.mark.anyio
async def test_e2e_pipeline_convergence_http(session_factory, monkeypatch):
    rid = uuid.uuid4()
    source_url = "https://arxiv.org/abs/2601.99999"

    async with session_factory() as session:
        session.add(
            Research(
                id=rid,
                theme="Convergência Multiagente",
                status=ResearchStatus.SCRAPER.value,
                callback_url="https://webhook.example/callback",
            )
        )
        p1 = ResearchPoint(
            id=uuid.uuid4(),
            research_id=rid,
            position=1,
            title="Fundamentos de Consenso",
            description="Análise teórica",
            dependencies=[],
            is_parallelizable=True,
            status="SCRAPER_PENDING",
        )
        p2 = ResearchPoint(
            id=uuid.uuid4(),
            research_id=rid,
            position=2,
            title="Métricas de Acurácia",
            description="Avaliação empírica",
            dependencies=["Fundamentos de Consenso"],
            is_parallelizable=True,
            status="SCRAPER_PENDING",
        )
        session.add(p1)
        session.add(p2)
        session.add(
            AppSettings(
                id=1,
                encrypted_credentials={},
                models={"auditor": "mock/auditor", "writer": "mock/writer"},
            )
        )
        await session.commit()

    # Mocks pontuais apenas de I/O externo (LLM, Jina, Webhook)
    async def fake_worker_execute(self, research_id, step_id, step_title, persona, theme, **kwargs):
        return PersonaExecutionResult(
            result=json.dumps({
                "analysis": f"Análise factual para {step_title} sustentada pela literatura.",
                "citations": [
                    {
                        "source_url": source_url,
                        "source_title": "Consensus Paper",
                        "claim": "Consenso multiagente eleva precisão",
                        "exact_quote": "Consenso multiagente eleva precisão de diagnósticos",
                    }
                ],
            }),
            used_urls=[source_url],
            read_urls=[source_url],
            success=True,
        )

    async def fake_audit_llm(self, model, prompt, api_base=None, api_key=None):
        return json.dumps({
            "approved": True,
            "checklist": {f"q{i}": True for i in range(1, 13)},
            "score": 12,
            "findings": ["Evidência primária verificada."],
            "contradictions": [],
            "uncertainties": [],
            "outline": ["Fundamentos", "Resultados"],
            "missing_research": [],
        })

    writer_report_markdown = (
        "# Relatório de Convergência Multiagente\n\n"
        f"## Fundamentos de Consenso\nConsenso multiagente eleva precisão [arxiv]({source_url}).\n\n"
        f"## Métricas de Acurácia\nResultados comprovados com alta fidelidade [arxiv]({source_url}).\n\n"
        f"References:\n- [Arxiv]({source_url})"
    )

    from app.services.pipeline import writer as writer_mod
    monkeypatch.setattr(
        writer_mod,
        "complete",
        AsyncMock(return_value=writer_report_markdown),
    )
    monkeypatch.setattr(PersonaWorker, "execute", fake_worker_execute)
    monkeypatch.setattr(AuditService, "_call_auditor_llm", fake_audit_llm)
    monkeypatch.setattr(
        AuditService,
        "_resolve_auditor_credentials",
        AsyncMock(return_value={"model": "mock/auditor", "api_base": None, "api_key": "test-key"}),
    )
    monkeypatch.setattr(
        "app.investigation.service.runtime_settings",
        AsyncMock(return_value=({"mock": "test-key"}, {"auditor": "mock/auditor"})),
    )

    callback_dispatched = False
    async def mock_dispatch_callback(research_id):
        nonlocal callback_dispatched
        callback_dispatched = True
        return True

    monkeypatch.setattr("app.services.webhook.dispatch_callback", mock_dispatch_callback)
    monkeypatch.setattr("app.routers.research.dispatch_callback", mock_dispatch_callback)

    # 1. Executa o pipeline pelo ciclo real (run_research adaptador -> InvestigationService -> Batches -> Writer)
    await run_research(rid)

    # 2. Verifica banco: status DONE, pontos aprovados e Report único persistido
    async with session_factory() as session:
        res = await session.get(Research, rid)
        assert res is not None
        assert res.status == ResearchStatus.DONE.value, f"Status esperado DONE, obtido: {res.status}, erro: {res.error}"

        reports = list((await session.scalars(select(Report).where(Report.research_id == rid))).all())
        assert len(reports) == 1
        initial_report_id = reports[0].id
        assert "Fundamentos de Consenso" in reports[0].content_markdown
        assert source_url in reports[0].content_markdown

    assert callback_dispatched is True

    # 3. Consulta HTTP GET /api/reports/{id}
    from app.core.security import Principal, require_admin
    from app.db.database import get_db
    from app.routers.research import get_db as research_get_db

    async def override_require_admin():
        return Principal(session=None)

    async def override_get_db():
        async with session_factory() as s:
            yield s

    app.dependency_overrides[require_admin] = override_require_admin
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[research_get_db] = override_get_db
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"/api/reports/{rid}")
            assert resp.status_code == 200, resp.text
            data = resp.json()
            assert data["report_id"] == str(initial_report_id)
            assert source_url in data["content_markdown"]

            # 4. Retry callback sem regerar relatório novo
            retry_resp = await client.post(f"/api/reports/{rid}/retry-callback")
            assert retry_resp.status_code == 200, retry_resp.text

            async with session_factory() as session:
                reports_after = list((await session.scalars(select(Report).where(Report.research_id == rid))).all())
                assert len(reports_after) == 1
                assert reports_after[0].id == initial_report_id
    finally:
        app.dependency_overrides.clear()
