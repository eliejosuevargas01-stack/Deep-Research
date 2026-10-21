"""Testes de ciclo de vida de rodadas e teto inicial+3 (T017, RN-505/RN-506, RF-505).

Cobre:
1. Erro técnico de persona não incrementa `attempt_count` (RN-506).
2. Teto inicial + 3 retries (total 4 tentativas): 4ª reprovação produz `AUDIT_CAVEAT` (RF-505).
3. Ausência de 5ª rodada de investigação após a 4ª auditoria.
4. Duas pesquisas/pontos com 4 reprovações atingem `AUDIT_CAVEAT` e só então liberam `WRITE` (sem Writer prematuro).
5. Q-502: falha irrecuperável/incompleta não avança indevidamente para `AUDIT_CAVEAT` nem conclui a pesquisa.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.audit.domain import AUDIT_CAVEAT, SCRAPER_RETRY, AuditVerdict
from app.audit.service import AuditService
from app.investigation.service import InvestigationService
from app.investigation.storage import (
    STATUS_FAILED,
    check_merge_barrier,
    save_investigation_merge,
    save_step_result,
)
from app.models.domain_models import (
    Base,
    InvestigationMerge,
    Research,
    ResearchPoint,
    ResearchStatus,
    ResearchStepResult,
)


@pytest.fixture
def anyio_backend() -> str:
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
    with patch("app.services.research.AsyncSessionLocal", factory), \
         patch("app.audit.service.AsyncSessionLocal", factory):
        try:
            yield factory
        finally:
            await engine.dispose()


# -------------------------------------------------------------------------
# 1. Erro técnico de persona não incrementa attempt_count
# -------------------------------------------------------------------------


@pytest.mark.anyio
async def test_persona_technical_error_does_not_increment_attempt_count(session_factory):
    rid, pid = uuid4(), uuid4()

    async with session_factory() as session:
        session.add(Research(id=rid, theme="T", status="SCRAPER"))
        session.add(
            ResearchPoint(
                id=pid,
                research_id=rid,
                position=1,
                title="Ponto Erro",
                description="Desc",
                status="SCRAPER_IN_PROGRESS",
                investigation_round=1,
                attempt_count=0,
            )
        )
        await session.commit()

    async with session_factory() as session:
        # Persona falha tecnicamente
        await save_step_result(
            db=session,
            research_id=rid,
            step_id=pid,
            step_title="Ponto Erro",
            worker="historian",
            result="",
            used_urls=[],
            read_urls=[],
            success=False,
            round=1,
        )

    async with session_factory() as session:
        pt = await session.get(ResearchPoint, pid)
        # RN-506: Falha técnica não queima tentativa de auditoria!
        assert pt.attempt_count == 0


# -------------------------------------------------------------------------
# 2. Teto inicial + 3: 4ª reprovação produz AUDIT_CAVEAT e encerra
# -------------------------------------------------------------------------


@pytest.mark.anyio
async def test_fourth_rejection_produces_audit_caveat_without_fifth_round(session_factory):
    rid, pid = uuid4(), uuid4()

    async with session_factory() as session:
        session.add(Research(id=rid, theme="Teto 4", status="AUDIT"))
        session.add(
            ResearchPoint(
                id=pid,
                research_id=rid,
                position=1,
                title="Ponto Teto",
                description="Desc",
                status="AUDIT_PENDING",
                investigation_round=4,
                attempt_count=3,
            )
        )
        # Simula merge da rodada 4
        session.add(
            InvestigationMerge(
                id=uuid4(),
                research_id=rid,
                step_id=pid,
                round=4,
                content={"personas": {"historian": {"analysis": "A"}}},
            )
        )
        await session.commit()

    service = AuditService(session_factory)

    # 4ª auditoria reprova (score 5, sem contradições)
    fake_rejection_json = """{
        "checklist": {"q1": true, "q2": true, "q3": true, "q4": true, "q5": true, "q6": false, "q7": false, "q8": false, "q9": false, "q10": false, "q11": false, "q12": false},
        "findings": ["Insuficiente"],
        "contradictions": [],
        "uncertainties": [],
        "missing_research": ["Investigar mais fontes"],
        "outline": []
    }"""

    with patch.object(service, "_resolve_auditor_credentials", AsyncMock(return_value={"model": "m", "api_key": "k"})), \
         patch.object(service, "_call_auditor_llm", AsyncMock(return_value=fake_rejection_json)):

        verdict = await service.audit_point(rid, pid, round=4)

        assert verdict.approved is False
        assert verdict.status == AUDIT_CAVEAT
        assert verdict.is_caveat is True

    async with session_factory() as session:
        pt = await session.get(ResearchPoint, pid)
        assert pt.status == AUDIT_CAVEAT
        assert pt.attempt_count == 3  # ou registrado como 4 na tentativa


# -------------------------------------------------------------------------
# 3. Dois pontos: 4 reprovações cada -> ambos AUDIT_CAVEAT -> transição WRITE
# -------------------------------------------------------------------------


@pytest.mark.anyio
async def test_two_points_four_rejections_reach_caveat_and_transition_to_write(session_factory):
    rid = uuid4()
    p1_id, p2_id = uuid4(), uuid4()

    async with session_factory() as session:
        session.add(Research(id=rid, theme="Pesquisa 2 Pontos", status="AUDIT"))
        session.add(
            ResearchPoint(
                id=p1_id,
                research_id=rid,
                position=1,
                title="P1",
                description="Desc 1",
                status="AUDIT_PENDING",
                investigation_round=4,
                attempt_count=3,
            )
        )
        session.add(
            ResearchPoint(
                id=p2_id,
                research_id=rid,
                position=2,
                title="P2",
                description="Desc 2",
                status="AUDIT_PENDING",
                investigation_round=4,
                attempt_count=3,
            )
        )
        session.add(
            InvestigationMerge(
                id=uuid4(),
                research_id=rid,
                step_id=p1_id,
                round=4,
                content={"test": 1},
            )
        )
        session.add(
            InvestigationMerge(
                id=uuid4(),
                research_id=rid,
                step_id=p2_id,
                round=4,
                content={"test": 2},
            )
        )
        await session.commit()

    service = AuditService(session_factory)

    fake_rejection_json = """{
        "checklist": {"q1": true, "q2": false, "q3": false, "q4": false, "q5": false, "q6": false, "q7": false, "q8": false, "q9": false, "q10": false, "q11": false, "q12": false},
        "findings": ["Reprovado tentativa 4"],
        "contradictions": [],
        "uncertainties": [],
        "missing_research": ["Investigar"],
        "outline": []
    }"""

    with patch.object(service, "_resolve_auditor_credentials", AsyncMock(return_value={"model": "m", "api_key": "k"})), \
         patch.object(service, "_call_auditor_llm", AsyncMock(return_value=fake_rejection_json)):

        v1 = await service.audit_point(rid, p1_id, round=4)
        assert v1.status == AUDIT_CAVEAT

        # Apenas P1 foi auditado; P2 ainda é AUDIT_PENDING -> WRITE não pode ter transicionado
        async with session_factory() as session:
            transitioned_early = await service.check_all_points_completed(session, rid)
            assert transitioned_early is False

        v2 = await service.audit_point(rid, p2_id, round=4)
        assert v2.status == AUDIT_CAVEAT

        # Agora ambos estão conclusivos (ambos AUDIT_CAVEAT) -> WRITE é liberado!
        async with session_factory() as session:
            transitioned = await service.check_all_points_completed(session, rid)
            assert transitioned is True

            res = await session.get(Research, rid)
            assert res.status == ResearchStatus.WRITE.value


# -------------------------------------------------------------------------
# 4. Q-502: falha técnica/incompleta não avança indevidamente para AUDIT_CAVEAT
# -------------------------------------------------------------------------


@pytest.mark.anyio
async def test_q502_incomplete_investigation_does_not_conclude_or_trigger_writer(session_factory):
    rid, pid = uuid4(), uuid4()

    async with session_factory() as session:
        session.add(Research(id=rid, theme="Q502", status="SCRAPER"))
        session.add(
            ResearchPoint(
                id=pid,
                research_id=rid,
                position=1,
                title="Ponto Incompleto",
                description="Desc",
                status="SCRAPER_IN_PROGRESS",
                investigation_round=1,
                attempt_count=0,
            )
        )
        await session.commit()

    async with session_factory() as session:
        # Apenas 2 personas terminam
        await save_step_result(
            db=session,
            research_id=rid,
            step_id=pid,
            step_title="Ponto Incompleto",
            worker="historian",
            result="Parcial",
            used_urls=["https://ex.com/1"],
            read_urls=["https://ex.com/1"],
            success=True,
            round=1,
        )
        await save_step_result(
            db=session,
            research_id=rid,
            step_id=pid,
            step_title="Ponto Incompleto",
            worker="skeptic",
            result="",
            used_urls=[],
            read_urls=[],
            success=False,
            round=1,
        )

    async with session_factory() as session:
        # Barreira não foi atingida (apenas 1 com sucesso de 4)
        barrier = await check_merge_barrier(session, rid, pid, round=1)
        assert barrier is False

        service = AuditService(session_factory)
        write_ready = await service.check_all_points_completed(session, rid)
        assert write_ready is False


# -------------------------------------------------------------------------
# 5. RF-508: Ciclo único respeita ready_point_batches e run_research adaptador
# -------------------------------------------------------------------------


@pytest.mark.anyio
async def test_rf508_ready_point_batches_and_adapter(session_factory, monkeypatch):
    from app.services.research import run_research, ready_point_batches
    from app.models.domain_models import AppSettings

    rid = uuid4()
    p1_id, p2_id = uuid4(), uuid4()

    async with session_factory() as session:
        session.add(Research(id=rid, theme="Pipeline RF508", status="SCRAPER"))
        session.add(
            ResearchPoint(
                id=p1_id,
                research_id=rid,
                position=1,
                title="Ponto Independente",
                description="Desc 1",
                dependencies=[],
                is_parallelizable=True,
                status="SCRAPER_PENDING",
            )
        )
        session.add(
            ResearchPoint(
                id=p2_id,
                research_id=rid,
                position=2,
                title="Ponto Dependente",
                description="Desc 2",
                dependencies=["Ponto Independente"],
                is_parallelizable=True,
                status="SCRAPER_PENDING",
            )
        )
        session.add(AppSettings(id=1, encrypted_credentials={}, models={"scout": "openai/demo"}))
        await session.commit()

    execution_order = []

    class MockWorker:
        def __init__(self, *args, **kwargs):
            pass

        async def execute(self, research_id, step_id, step_title, persona, theme, **kwargs):
            execution_order.append((step_title, persona))
            return type("Result", (), {
                "result": f"Achado {persona}",
                "used_urls": ["https://ex.com/source"],
                "read_urls": ["https://ex.com/source"],
                "success": True,
            })()

    monkeypatch.setattr("app.investigation.service.PersonaWorker", MockWorker)
    monkeypatch.setattr(
        "app.investigation.service._resolve_credentials",
        AsyncMock(return_value=("", None, None, {"scout": "openai/demo"})),
    )
    monkeypatch.setattr(
        "app.investigation.service._resolve_persona_credentials",
        AsyncMock(return_value={}),
    )
    monkeypatch.setattr(
        "app.investigation.service.runtime_settings",
        AsyncMock(return_value=({"openai": "test-key"}, {"auditor": "openai/gpt-4o"})),
    )

    # Auditor aprova cada ponto diretamente e atualiza status para conclusivo
    approved_verdict = AuditVerdict(
        approved=True,
        status="AUDIT_APPROVED",
        score=10,
        checklist={},
        findings=["Ok"],
        contradictions=[],
        uncertainties=[],
        missing_research=[],
        outline=[],
    )

    async def mock_audit_point(self, research_id, step_id, round=1):
        async with session_factory() as session:
            pt = await session.get(ResearchPoint, step_id)
            if pt:
                pt.status = "AUDIT_APPROVED"
                await session.commit()
        return approved_verdict

    monkeypatch.setattr(
        AuditService,
        "audit_point",
        mock_audit_point,
    )
    mock_writer = AsyncMock()
    monkeypatch.setattr("app.services.pipeline.writer._write_report", mock_writer)

    # Executa pelo adaptador run_research
    await run_research(rid)

    # Verifica se Ponto Independente rodou antes de Ponto Dependente
    p1_calls = [c for c in execution_order if c[0] == "Ponto Independente"]
    p2_calls = [c for c in execution_order if c[0] == "Ponto Dependente"]
    assert len(p1_calls) == 4
    assert len(p2_calls) == 4

    # Primeiro índice de P2 deve ser posterior ao último índice de P1
    first_p2_idx = min(execution_order.index(c) for c in p2_calls)
    last_p1_idx = max(execution_order.index(c) for c in p1_calls)
    assert first_p2_idx > last_p1_idx

    # Writer foi invocado após aprovação de todos os pontos
    mock_writer.assert_awaited_once()


# -------------------------------------------------------------------------
# 6. T021: Retomada WRITE sem Report escreve; DONE + Report é no-op
# -------------------------------------------------------------------------


@pytest.mark.anyio
async def test_t021_write_resumption_and_done_noop(session_factory, monkeypatch):
    from app.investigation.service import InvestigationService
    from app.models.domain_models import Report

    rid, pid = uuid4(), uuid4()

    async with session_factory() as session:
        session.add(Research(id=rid, theme="Resumption Test", status="WRITE"))
        session.add(
            ResearchPoint(
                id=pid,
                research_id=rid,
                position=1,
                title="P1 Conclusivo",
                description="Desc",
                status="AUDIT_APPROVED",
            )
        )
        await session.commit()

    mock_writer = AsyncMock()
    monkeypatch.setattr("app.services.pipeline.writer._write_report", mock_writer)

    service = InvestigationService(session_factory)

    # 1. Status WRITE sem Report -> invoca Writer
    await service.run_investigation(rid)
    assert mock_writer.await_count == 1

    # 2. Persiste Report e marca DONE
    async with session_factory() as session:
        session.add(Report(id=uuid4(), research_id=rid, content_markdown="## Relatório Final"))
        res = await session.get(Research, rid)
        assert res is not None
        res.status = ResearchStatus.DONE.value
        await session.commit()

    # 3. Segunda invocação em DONE com Report -> no-op estrito (Writer não é chamado novamente)
    await service.run_investigation(rid)
    assert mock_writer.await_count == 1
