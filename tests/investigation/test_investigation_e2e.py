"""Testes de integração E2E da Feature 002 (T020, RN-01 a RN-10, Seção 8 requirements.md).

Cobre o fluxo completo de ponta a ponta:
1. Fluxo E2E Completo:
   - Briefing aprovado, pesquisa em status SCRAPER com 5 pontos em SCRAPER_PENDING.
   - Disparo via POST /briefings/{research_id}/investigate autenticado como admin -> HTTP 202.
   - Transição atômica dos 5 pontos para SCRAPER_IN_PROGRESS.
   - Re-disparo imediato rejeitado com HTTP 409 Conflict.
   - Execução assíncrona dos 20 workers (4 personas x 5 pontos) com mocks Jina e LiteLLM.
   - Persistência de 20 registros em research_step_results com status AUDIT_PENDING,
     used_urls populado e read_urls contendo as fontes Jina.
   - Transição dos 5 pontos para AUDIT_PENDING e pesquisa para status AUDIT.
2. Cenário de Resiliência Parcial:
   - 1 worker de 1 ponto falha após esgotar tentativas externas.
   - Registro de falha em research_step_results com status FAILED e erro sanitizado.
   - Sucesso dos outros 19 workers e avanço da pesquisa para AUDIT.
3. Cenário de Falha Total:
   - Todos os 4 workers de todos os 5 pontos falham.
   - Todos os pontos transitam para SCRAPER_FAILED e pesquisa para status FAILED.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, AsyncGenerator, Callable
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool
from starlette.background import BackgroundTasks

from app.db.database import get_db
from app.investigation.llm_binding import LLMCallError
from app.investigation.prompts import PERSONA_NAMES
from app.investigation.service import InvestigationService
from app.investigation.storage import get_step_results
from app.investigation.tools import JinaSearchResult, JinaToolAdapter
from app.main import app
from app.models.domain_models import (
    Base,
    BriefingRecord,
    Research,
    ResearchPoint,
    ResearchStatus,
)

E2E_ADMIN_SECRET = "test-api-secret-0123456789"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def e2e_db(tmp_path, monkeypatch) -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    """Cria banco SQLite em arquivo temporário com WAL mode para concorrência de 20 workers."""
    db_file = tmp_path / "test_investigation_e2e.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"
    engine: AsyncEngine = create_async_engine(
        db_url,
        poolclass=NullPool,
        connect_args={"timeout": 60},
    )

    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=60000")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            finally:
                try:
                    await session.rollback()
                except Exception:
                    pass
                await session.close()

    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr("app.investigation.router.AsyncSessionLocal", session_factory)
    monkeypatch.setattr("app.db.database.AsyncSessionLocal", session_factory)
    monkeypatch.setattr("app.core.config.settings.API_AUTH_SECRET", E2E_ADMIN_SECRET)
    monkeypatch.setattr("app.core.security.settings.API_AUTH_SECRET", E2E_ADMIN_SECRET)

    try:
        yield session_factory
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()


@pytest.fixture
def intercept_background_tasks(monkeypatch) -> list[tuple[Any, tuple, dict]]:
    """Intercepta BackgroundTasks.add_task para desacoplar resposta HTTP da execução dos workers."""
    recorded_tasks: list[tuple[Any, tuple, dict]] = []

    def _fake_add_task(self, func, *args, **kwargs):
        recorded_tasks.append((func, args, kwargs))

    monkeypatch.setattr(BackgroundTasks, "add_task", _fake_add_task)
    return recorded_tasks


async def _seed_approved_research_with_5_points(
    session_factory: async_sessionmaker[AsyncSession],
    theme: str = "Impacto da IA Generativa na Medicina Diagnóstica",
) -> tuple[UUID, list[UUID]]:
    """Gera pesquisa e briefing aprovado com 5 pontos em SCRAPER_PENDING e pesquisa em SCRAPER."""
    research_id = uuid4()
    points_data = [
        ("Precisão em Imagens", "Investigar acurácia de diagnósticos por imagem."),
        ("Decisão Clínica", "Examinar ferramentas de apoio ao médico."),
        ("Desafios Regulatórios", "Mapear conformidade com FDA e Anvisa."),
        ("Custos e Adoção", "Análise de custo-benefício em redes hospitalares."),
        ("Ética e Privacidade", "Examinar segurança e anonimização de prontuários."),
    ]
    point_ids: list[UUID] = []
    async with session_factory() as session:
        research = Research(
            id=research_id,
            theme=theme,
            status=ResearchStatus.SCRAPER.value,
            briefing_draft={"points": [{"title": t, "description": d} for t, d in points_data]},
            approved_at=datetime.now(timezone.utc),
        )
        briefing = BriefingRecord(
            id=research_id,
            theme=theme,
            status="approved",
            version=1,
            points_json=[{"title": t, "description": d} for t, d in points_data],
            approved_at=datetime.now(timezone.utc),
        )
        session.add(research)
        session.add(briefing)
        for idx, (title, desc) in enumerate(points_data):
            pid = uuid4()
            point_ids.append(pid)
            point = ResearchPoint(
                id=pid,
                research_id=research_id,
                position=idx + 1,
                title=title,
                description=desc,
                status="SCRAPER_PENDING",
                attempt_count=0,
            )
            session.add(point)
        await session.commit()
    return research_id, point_ids


@pytest.mark.anyio
async def test_investigation_e2e_full_flow(
    e2e_db: async_sessionmaker[AsyncSession],
    intercept_background_tasks: list[tuple[Any, tuple, dict]],
    make_litellm_tool_call_response: Callable[[str, str], Any],
    make_litellm_final_response: Callable[[str, list[str]], Any],
    monkeypatch,
):
    """
    Cenário 1: Fluxo E2E Completo.
    - POST /briefings/{research_id}/investigate retorna 202 com status SCRAPER.
    - 5 pontos passam para SCRAPER_IN_PROGRESS.
    - Re-disparo retorna 409 Conflict ("Investigação já iniciada ou em andamento para esta pesquisa").
    - Execução do run_investigation gera 20 registros AUDIT_PENDING com used_urls e read_urls.
    - Ao término, todos os 5 pontos ficam em AUDIT_PENDING e a pesquisa transita para AUDIT.
    """
    session_factory = e2e_db
    research_id, point_ids = await _seed_approved_research_with_5_points(session_factory)

    headers = {"Authorization": f"Bearer {E2E_ADMIN_SECRET}"}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # 1. Disparo inicial autenticado como admin -> HTTP 202
        response = await client.post(f"/briefings/{research_id}/investigate", headers=headers)
        assert response.status_code == 202
        data = response.json()
        assert data["research_id"] == str(research_id)
        assert data["status"] == "SCRAPER"
        assert data["message"] == "Investigação iniciada em background"

        # 2. Valida transição atômica dos 5 pontos para SCRAPER_IN_PROGRESS
        async with session_factory() as session:
            rows = await session.execute(
                select(ResearchPoint).where(ResearchPoint.research_id == research_id)
            )
            points_after_dispatch = list(rows.scalars().all())
            assert len(points_after_dispatch) == 5
            assert all(p.status == "SCRAPER_IN_PROGRESS" for p in points_after_dispatch)

        # 3. Valida re-disparo imediato -> HTTP 409 Conflict
        conflict_res = await client.post(f"/briefings/{research_id}/investigate", headers=headers)
        assert conflict_res.status_code == 409
        assert conflict_res.json()["detail"] == (
            "Investigação já iniciada ou em andamento para esta pesquisa"
        )

    # 4. Valida agendamento da tarefa em background
    assert len(intercept_background_tasks) == 1
    task_func, task_args, _ = intercept_background_tasks[0]
    assert task_args == (research_id,)

    # 5. Configura mocks para Jina e LiteLLM
    jina_sources = [
        "https://example.com/artigo-medicina-ia",
        "https://example.com/estudo-clinico-diagnostico",
    ]
    used_source = ["https://example.com/artigo-medicina-ia"]

    mock_jina_adapter = AsyncMock(spec=JinaToolAdapter)
    mock_jina_adapter.search.return_value = JinaSearchResult(
        content="Evidências clínicas consolidadas de algoritmos diagnósticos com sensibilidade > 95%.",
        urls=jina_sources,
    )

    async def fake_llm(model: str, messages: list[dict], tools: list[dict] | None = None, **kwargs):
        # Se última mensagem for resposta da ferramenta, entrega JSON final analítico
        if messages and messages[-1].get("role") == "tool":
            return make_litellm_final_response(
                "Síntese analítica consistente integrando dados factuais de diagnóstico clínico.",
                used_source,
            )
        # Primeira iteração emite chamada de busca na Jina
        return make_litellm_tool_call_response("diagnostico por imagem acuracia")

    monkeypatch.setattr("app.investigation.worker.call_llm_with_retries", fake_llm)

    # 6. Executa run_investigation da InvestigationService
    service = InvestigationService(session_factory, jina_adapter=mock_jina_adapter)
    await service.run_investigation(research_id)

    # 7. Valida 20 registros em research_step_results (4 por ponto)
    async with session_factory() as session:
        step_results = await get_step_results(session, research_id)
        assert len(step_results) == 20

        # Mapeia resultados por ponto
        results_by_point: dict[UUID, list[Any]] = {}
        for r in step_results:
            results_by_point.setdefault(r.step_id, []).append(r)
            assert r.status == "AUDIT_PENDING"
            assert r.used_urls == used_source
            assert r.read_urls == jina_sources
            assert len(r.result) >= 10

        assert len(results_by_point) == 5
        for pid in point_ids:
            point_workers = [r.worker for r in results_by_point[pid]]
            assert sorted(point_workers) == sorted(PERSONA_NAMES)

        # 8. Valida que todos os 5 pontos transitaram para AUDIT_PENDING
        rows = await session.execute(
            select(ResearchPoint).where(ResearchPoint.research_id == research_id)
        )
        final_points = list(rows.scalars().all())
        assert len(final_points) == 5
        assert all(p.status == "AUDIT_PENDING" for p in final_points)

        # 9. Valida que a pesquisa transita para status AUDIT
        final_research = await session.get(Research, research_id)
        assert final_research is not None
        assert final_research.status == ResearchStatus.AUDIT.value
        assert final_research.status == "AUDIT"


@pytest.mark.anyio
async def test_investigation_e2e_partial_resilience(
    e2e_db: async_sessionmaker[AsyncSession],
    make_litellm_tool_call_response: Callable[[str, str], Any],
    make_litellm_final_response: Callable[[str, list[str]], Any],
    monkeypatch,
):
    """
    Cenário 2: Resiliência Parcial.
    - 1 worker de 1 ponto falha esgotando tentativas com erro contendo segredo.
    - Valida registro em research_step_results com status FAILED e erro sanitizado (sem segredo).
    - Valida que os outros 19 workers concluem com status AUDIT_PENDING.
    - Valida que o ponto do worker com falha mantém AUDIT_PENDING e tem attempt_count=1.
    - Valida avanço da pesquisa para o status AUDIT.
    """
    session_factory = e2e_db
    research_id, point_ids = await _seed_approved_research_with_5_points(session_factory)
    target_point_id = point_ids[0]

    # Prepara adapter Jina mockado
    jina_sources = ["https://example.com/artigo-resiliencia-1"]
    mock_jina_adapter = AsyncMock(spec=JinaToolAdapter)
    mock_jina_adapter.search.return_value = JinaSearchResult(
        content="Evidências sobre resiliência operacional.",
        urls=jina_sources,
    )

    failed_worker_executed = False

    async def fake_llm(model: str, messages: list[dict], tools: list[dict] | None = None, **kwargs):
        nonlocal failed_worker_executed
        # Identifica o worker da persona 'skeptic' no primeiro ponto para falhar
        system_content = messages[0].get("content", "") if messages else ""
        is_first_point = "Precisão em Imagens" in system_content
        is_skeptic = "Cético Analítico" in system_content

        if is_first_point and is_skeptic:
            failed_worker_executed = True
            raise LLMCallError(
                attempts=3,
                message="RateLimit 429 com credencial Bearer sk-secret-token-do-not-leak-12345",
            )

        if messages and messages[-1].get("role") == "tool":
            return make_litellm_final_response(
                "Síntese analítica robusta para o cenário de resiliência.",
                jina_sources,
            )
        return make_litellm_tool_call_response("resiliencia operacional")

    monkeypatch.setattr("app.investigation.worker.call_llm_with_retries", fake_llm)

    service = InvestigationService(session_factory, jina_adapter=mock_jina_adapter)
    await service.run_investigation(research_id)

    assert failed_worker_executed is True

    async with session_factory() as session:
        step_results = await get_step_results(session, research_id)
        assert len(step_results) == 20

        failed_results = [r for r in step_results if r.status == "FAILED"]
        success_results = [r for r in step_results if r.status == "AUDIT_PENDING"]

        assert len(failed_results) == 1
        assert len(success_results) == 19

        failed_r = failed_results[0]
        assert failed_r.worker == "skeptic"
        assert failed_r.step_id == target_point_id
        # Valida erro sanitizado: segredo ocultado, sem vazamento do token
        assert "sk-secret-token-do-not-leak-12345" not in failed_r.result
        assert "Bearer ***" in failed_r.result

        # Ponto do worker falho deve permanecer em AUDIT_PENDING e ter attempt_count incrementado
        point_record = await session.get(ResearchPoint, target_point_id)
        assert point_record is not None
        assert point_record.attempt_count == 1
        assert point_record.status == "AUDIT_PENDING"

        # Demais 4 pontos devem estar em AUDIT_PENDING com attempt_count=0
        other_points = list((await session.execute(
            select(ResearchPoint).where(
                ResearchPoint.research_id == research_id,
                ResearchPoint.id != target_point_id,
            )
        )).scalars().all())
        assert len(other_points) == 4
        assert all(p.status == "AUDIT_PENDING" and p.attempt_count == 0 for p in other_points)

        # Pesquisa deve avançar para AUDIT mesmo com 1 falha parcial
        research = await session.get(Research, research_id)
        assert research is not None
        assert research.status == "AUDIT"


@pytest.mark.anyio
async def test_investigation_e2e_total_failure(
    e2e_db: async_sessionmaker[AsyncSession],
    monkeypatch,
):
    """
    Cenário 3: Falha Total.
    - Todos os 4 workers de todos os 5 pontos falham.
    - Valida que todos os 20 resultados em research_step_results ficam em FAILED.
    - Valida que todos os 5 pontos transitam para SCRAPER_FAILED e attempt_count=4.
    - Valida que a pesquisa transita atomicamente para o status FAILED.
    """
    session_factory = e2e_db
    research_id, point_ids = await _seed_approved_research_with_5_points(session_factory)

    mock_jina_adapter = AsyncMock(spec=JinaToolAdapter)

    async def failing_llm(*args, **kwargs):
        raise LLMCallError(attempts=3, message="Falha irreversível no provedor upstream LLM")

    monkeypatch.setattr("app.investigation.worker.call_llm_with_retries", failing_llm)

    service = InvestigationService(session_factory, jina_adapter=mock_jina_adapter)
    await service.run_investigation(research_id)

    async with session_factory() as session:
        step_results = await get_step_results(session, research_id)
        assert len(step_results) == 20
        assert all(r.status == "FAILED" for r in step_results)

        # Valida que todos os 5 pontos ficaram em SCRAPER_FAILED
        rows = await session.execute(
            select(ResearchPoint).where(ResearchPoint.research_id == research_id)
        )
        final_points = list(rows.scalars().all())
        assert len(final_points) == 5
        assert all(p.status == "SCRAPER_FAILED" for p in final_points)
        # Cada ponto teve 4 workers falhando, logo attempt_count deve ser 4
        assert all(p.attempt_count == 4 for p in final_points)

        # Valida que a pesquisa transita atomicamente para o status FAILED
        final_research = await session.get(Research, research_id)
        assert final_research is not None
        assert final_research.status == ResearchStatus.FAILED.value
        assert final_research.status == "FAILED"
