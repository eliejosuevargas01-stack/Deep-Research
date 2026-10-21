"""Testes de unidade e integração para auditoria por merge e rodada (T016, RN-505/RN-506).

Cobre:
1. `get_point_evidence` com filtro por rodada.
2. `_build_auditor_prompt` sem corte arbitrário de 60000 caracteres.
3. `audit_point` consome o snapshot de `InvestigationMerge` committed da rodada.
4. CAS do veredito e ordinal rejeita atualização se ponto sofreu alteração concorrente.
5. Persistência atômica: `round`, `merge_id` e `attempt` gravados simultaneamente em `ResearchPoint.audit` e `AuditTrail.details`.
6. Falhas de infraestrutura não contam como reprovação factual (não incrementam `attempt_count`).
"""

from __future__ import annotations

import json
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

from app.audit.domain import AUDIT_APPROVED, AUDIT_CRITERIA, AuditVerdict
from app.audit.service import AuditService
import app.models.domain_models as _models
from app.models.domain_models import (
    AuditTrail,
    Base,
    InvestigationMerge,
    Research,
    ResearchPoint,
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
# 1. get_point_evidence com filtro por rodada
# -------------------------------------------------------------------------


@pytest.mark.anyio
async def test_get_point_evidence_filters_by_round(session_factory):
    service = AuditService(session_factory)
    pid = uuid4()
    rid = uuid4()

    async with session_factory() as session:
        session.add(Research(id=rid, theme="T", status="AUDIT"))
        session.add(
            ResearchPoint(
                id=pid,
                research_id=rid,
                position=1,
                title="P",
                description="D",
                status="AUDIT_PENDING",
            )
        )
        session.add(
            ResearchStepResult(
                research_id=rid,
                step_id=pid,
                step_title="P",
                worker="historian",
                result="R1 result",
                round=1,
                status="AUDIT_PENDING",
            )
        )
        session.add(
            ResearchStepResult(
                research_id=rid,
                step_id=pid,
                step_title="P",
                worker="historian",
                result="R2 result",
                round=2,
                status="AUDIT_PENDING",
            )
        )
        await session.commit()

    async with session_factory() as session:
        ev_r1 = await service.get_point_evidence(session, pid, round=1)
        ev_r2 = await service.get_point_evidence(session, pid, round=2)
        ev_all = await service.get_point_evidence(session, pid)

    assert len(ev_r1) == 1
    assert ev_r1[0]["result"] == "R1 result"

    assert len(ev_r2) == 1
    assert ev_r2[0]["result"] == "R2 result"

    assert len(ev_all) == 2


# -------------------------------------------------------------------------
# 2. _build_auditor_prompt sem corte de 60000 caracteres
# -------------------------------------------------------------------------


def test_build_auditor_prompt_preserves_large_payload_beyond_60000():
    large_text = "A" * 70000
    evidence = [
        {
            "persona": "historian",
            "result": large_text,
            "used_urls": ["https://example.com/1"],
            "read_urls": ["https://example.com/1"],
            "status": "COMPLETED",
        }
    ]

    prompt = AuditService._build_auditor_prompt(
        title="Large Title",
        description="Large Desc",
        evidence=evidence,
        criteria=AUDIT_CRITERIA,
    )

    assert len(prompt) > 70000
    assert "A" * 70000 in prompt
    assert prompt.endswith("Nunca revele raciocínio privado ou cadeia de pensamento.")


# -------------------------------------------------------------------------
# 3. audit_point consome snapshot de InvestigationMerge da rodada
# -------------------------------------------------------------------------


@pytest.mark.anyio
async def test_audit_point_reads_committed_merge_for_round(session_factory):
    service = AuditService(session_factory)
    rid = uuid4()
    pid = uuid4()
    mid = uuid4()

    merge_content = {
        "round": 1,
        "personas": {
            "historian": {"analysis": "História confirmada", "citations": []},
            "skeptic": {"analysis": "Ceticismo validado", "citations": []},
        },
    }

    async with session_factory() as session:
        session.add(Research(id=rid, theme="T", status="AUDIT"))
        session.add(
            ResearchPoint(
                id=pid,
                research_id=rid,
                position=1,
                title="Ponto Merge",
                description="Desc Merge",
                status="AUDIT_PENDING",
                investigation_round=1,
                attempt_count=0,
            )
        )
        session.add(
            InvestigationMerge(
                id=mid,
                research_id=rid,
                step_id=pid,
                round=1,
                content=merge_content,
            )
        )
        await session.commit()

    fake_verdict_json = json.dumps(
        {
            "checklist": {f"q{i}": True for i in range(1, 13)},
            "findings": ["Merge consistente"],
            "contradictions": [],
            "uncertainties": [],
            "missing_research": [],
            "outline": ["O1"],
        }
    )

    with patch.object(service, "_resolve_auditor_credentials", AsyncMock(return_value={"model": "m", "api_key": "k"})), \
         patch.object(service, "_call_auditor_llm", AsyncMock(return_value=fake_verdict_json)) as mock_llm:

        verdict = await service.audit_point(rid, pid, round=1)

        assert verdict.approved is True
        assert verdict.status == AUDIT_APPROVED

        # Verifica se o prompt enviado continha o merge_content
        call_args = mock_llm.call_args[0]
        user_prompt = call_args[1]
        assert "História confirmada" in user_prompt
        assert "Ceticismo validado" in user_prompt


# -------------------------------------------------------------------------
# 4. CAS do veredito: rejeita atualização se o ponto sofreu alteração concorrente
# -------------------------------------------------------------------------


@pytest.mark.anyio
async def test_audit_cas_rejects_obsolete_verdict_on_concurrent_modification(session_factory):
    service = AuditService(session_factory)
    rid = uuid4()
    pid = uuid4()

    async with session_factory() as session:
        session.add(Research(id=rid, theme="T", status="AUDIT"))
        session.add(
            ResearchPoint(
                id=pid,
                research_id=rid,
                position=1,
                title="Ponto Concorrente",
                description="Desc",
                status="AUDIT_PENDING",
                investigation_round=1,
                attempt_count=0,
            )
        )
        await session.commit()

    fake_verdict_json = json.dumps(
        {
            "checklist": {f"q{i}": True for i in range(1, 13)},
            "findings": ["Aprovado"],
            "contradictions": [],
            "uncertainties": [],
            "missing_research": [],
            "outline": [],
        }
    )

    # Durante a chamada LLM simulada, outro processo avança a rodada para 2
    async def simulate_concurrent_update(*args, **kwargs):
        async with session_factory() as s:
            pt = await s.get(ResearchPoint, pid)
            pt.investigation_round = 2
            pt.status = "SCRAPER_IN_PROGRESS"
            await s.commit()
        return fake_verdict_json

    with patch.object(service, "_resolve_auditor_credentials", AsyncMock(return_value={"model": "m", "api_key": "k"})), \
         patch.object(service, "_call_auditor_llm", side_effect=simulate_concurrent_update):

        verdict = await service.audit_point(rid, pid, round=1)

        # O veredito deve ser descartado como obsoleto e o ponto mantido como modificado
        assert verdict.approved is False
        assert "obsolete" in verdict.findings[0].lower() or "concorrente" in verdict.findings[0].lower()

        async with session_factory() as s:
            pt = await s.get(ResearchPoint, pid)
            # O ponto não foi sobregravado com o status da rodada 1
            assert pt.investigation_round == 2
            assert pt.status == "SCRAPER_IN_PROGRESS"


# -------------------------------------------------------------------------
# 5. Persistência atômica: round, merge_id e ordinal gravados no mesmo commit
# -------------------------------------------------------------------------


@pytest.mark.anyio
async def test_audit_persists_round_merge_id_and_ordinal_in_same_commit(session_factory):
    service = AuditService(session_factory)
    rid = uuid4()
    pid = uuid4()
    mid = uuid4()

    async with session_factory() as session:
        session.add(Research(id=rid, theme="T", status="AUDIT"))
        session.add(
            ResearchPoint(
                id=pid,
                research_id=rid,
                position=1,
                title="Ponto Integrado",
                description="Desc",
                status="AUDIT_PENDING",
                investigation_round=1,
                attempt_count=0,
            )
        )
        session.add(
            InvestigationMerge(
                id=mid,
                research_id=rid,
                step_id=pid,
                round=1,
                content={"test": "data"},
            )
        )
        await session.commit()

    fake_verdict_json = json.dumps(
        {
            "checklist": {f"q{i}": True for i in range(1, 13)},
            "findings": ["Auditado com sucesso"],
            "contradictions": [],
            "uncertainties": [],
            "missing_research": [],
            "outline": [],
        }
    )

    with patch.object(service, "_resolve_auditor_credentials", AsyncMock(return_value={"model": "m", "api_key": "k"})), \
         patch.object(service, "_call_auditor_llm", AsyncMock(return_value=fake_verdict_json)):

        verdict = await service.audit_point(rid, pid, round=1)
        assert verdict.approved is True

    async with session_factory() as session:
        pt = await session.get(ResearchPoint, pid)
        assert pt.audit is not None
        assert pt.audit.get("round") == 1
        assert pt.audit.get("merge_id") == str(mid)
        assert pt.audit.get("attempt") == 1

        trail = (
            await session.scalars(
                select(AuditTrail).where(AuditTrail.point_id == pid)
            )
        ).first()
        assert trail is not None
        assert trail.details.get("round") == 1
        assert trail.details.get("merge_id") == str(mid)
        assert trail.attempt == 1


# -------------------------------------------------------------------------
# 6. Falha de infraestrutura não conta como reprovação factual
# -------------------------------------------------------------------------


@pytest.mark.anyio
async def test_infra_error_does_not_count_as_factual_rejection(session_factory):
    service = AuditService(session_factory)
    rid = uuid4()
    pid = uuid4()

    async with session_factory() as session:
        session.add(Research(id=rid, theme="T", status="AUDIT"))
        session.add(
            ResearchPoint(
                id=pid,
                research_id=rid,
                position=1,
                title="Ponto Infra",
                description="Desc",
                status="AUDIT_PENDING",
                investigation_round=1,
                attempt_count=1,
            )
        )
        await session.commit()

    with patch.object(service, "_resolve_auditor_credentials", AsyncMock(return_value={"model": "m", "api_key": "k"})), \
         patch.object(service, "_call_auditor_llm", AsyncMock(side_effect=RuntimeError("Timeout de rede"))):

        verdict = await service.audit_point(rid, pid, round=1)
        assert verdict.approved is False
        assert verdict.status == "AUDIT_INCONCLUSIVE"

    async with session_factory() as session:
        pt = await session.get(ResearchPoint, pid)
        # attempt_count NÃO deve ser incrementado
        assert pt.attempt_count == 1
        assert pt.status == "AUDIT_INCONCLUSIVE"
