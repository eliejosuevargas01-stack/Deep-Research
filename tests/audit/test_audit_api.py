"""Testes de integração para os endpoints administrativos de auditoria (T045, T050).

Cobre:
- Autenticação de administrador (Bearer token, x-api-key, rejeição 401/400).
- POST /api/audit/{research_id}/run (200, 404, 409, transição WRITE, bump attempt em retry).
- POST /api/audit/{research_id}/points/{point_id}/run (200, 404, 409).
"""

from __future__ import annotations

from typing import AsyncGenerator
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx
import pytest
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.audit.domain import (
    AUDIT_APPROVED,
    CRITERIA_KEYS,
    SCRAPER_RETRY,
    AuditVerdict,
)
from app.audit.router import NO_PENDING_DETAIL
from app.core.config import settings
from app.db.database import get_db
from app.main import app
from app.models.domain_models import Base, Research, ResearchPoint, ResearchStatus

AUTH_HEADERS = {"Authorization": f"Bearer {settings.API_AUTH_SECRET}"}
API_KEY_HEADERS = {"x-api-key": settings.API_AUTH_SECRET}


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def sqlite_engine() -> AsyncGenerator[AsyncEngine, None]:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
def session_factory(sqlite_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(sqlite_engine, expire_on_commit=False)


@pytest.fixture
async def client(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[httpx.AsyncClient, None]:
    app.dependency_overrides.clear()
    async def db_override() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = db_override
    with patch("app.audit.router.AsyncSessionLocal", session_factory):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as http_client:
            yield http_client
    app.dependency_overrides.clear()


# =========================================================================
# 1. Testes de Autenticação Admin (401, 400, API-Key)
# =========================================================================


@pytest.mark.anyio
async def test_auth_missing_credentials(client: httpx.AsyncClient):
    r_id = uuid4()
    p_id = uuid4()
    res1 = await client.post(f"/api/audit/{r_id}/run")
    assert res1.status_code == 401
    assert "Authentication required" in res1.text

    res2 = await client.post(f"/api/audit/{r_id}/points/{p_id}/run")
    assert res2.status_code == 401
    assert "Authentication required" in res2.text


@pytest.mark.anyio
async def test_auth_invalid_credentials(client: httpx.AsyncClient):
    r_id = uuid4()
    res_bearer = await client.post(
        f"/api/audit/{r_id}/run",
        headers={"Authorization": "Bearer invalid_secret_token"},
    )
    assert res_bearer.status_code == 401

    res_key = await client.post(
        f"/api/audit/{r_id}/run",
        headers={"x-api-key": "invalid_api_key"},
    )
    assert res_key.status_code == 401


@pytest.mark.anyio
async def test_auth_ambiguous_credentials(client: httpx.AsyncClient):
    r_id = uuid4()
    res = await client.post(
        f"/api/audit/{r_id}/run",
        headers={
            "Authorization": f"Bearer {settings.API_AUTH_SECRET}",
            "x-api-key": settings.API_AUTH_SECRET,
        },
    )
    assert res.status_code == 400
    assert "Ambiguous authentication" in res.text


@pytest.mark.anyio
async def test_auth_client_tenant_header_prohibited(client: httpx.AsyncClient):
    r_id = uuid4()
    res = await client.post(
        f"/api/audit/{r_id}/run",
        headers={
            **AUTH_HEADERS,
            "x-tenant-id": "tenant-123",
        },
    )
    assert res.status_code == 400
    assert "Client tenant headers are prohibited" in res.text


@pytest.mark.anyio
async def test_auth_via_api_key_accepted(
    client: httpx.AsyncClient, session_factory: async_sessionmaker[AsyncSession]
):
    # API key válida é autenticada com sucesso (cai no 404 da pesquisa ausente, não em 401)
    r_id = uuid4()
    res = await client.post(
        f"/api/audit/{r_id}/run",
        headers=API_KEY_HEADERS,
    )
    assert res.status_code == 404
    assert "Pesquisa não encontrada" in res.json().get("detail", "")


# =========================================================================
# 2. Endpoint POST /api/audit/{research_id}/run
# =========================================================================


@pytest.mark.anyio
async def test_run_research_audit_404_not_found(client: httpx.AsyncClient):
    res = await client.post(f"/api/audit/{uuid4()}/run", headers=AUTH_HEADERS)
    assert res.status_code == 404
    assert res.json()["detail"] == "Pesquisa não encontrada"


@pytest.mark.anyio
async def test_run_research_audit_409_no_points(
    client: httpx.AsyncClient, session_factory: async_sessionmaker[AsyncSession]
):
    async with session_factory() as session:
        r = Research(theme="Pesquisa Vazia", status="AUDIT")
        session.add(r)
        await session.commit()
        r_id = r.id

    res = await client.post(f"/api/audit/{r_id}/run", headers=AUTH_HEADERS)
    assert res.status_code == 409
    assert res.json()["detail"] == NO_PENDING_DETAIL


@pytest.mark.anyio
async def test_run_research_audit_409_no_pending_points(
    client: httpx.AsyncClient, session_factory: async_sessionmaker[AsyncSession]
):
    async with session_factory() as session:
        r = Research(theme="Pesquisa Sem Pendências", status="AUDIT")
        session.add(r)
        await session.flush()
        p = ResearchPoint(
            research_id=r.id,
            position=1,
            title="P1",
            description="Desc",
            status="AUDIT_APPROVED",
            attempt_count=1,
        )
        session.add(p)
        await session.commit()
        r_id = r.id

    res = await client.post(f"/api/audit/{r_id}/run", headers=AUTH_HEADERS)
    assert res.status_code == 409
    assert res.json()["detail"] == NO_PENDING_DETAIL


@pytest.mark.anyio
async def test_run_research_audit_200_all_approved_transitions_to_write(
    client: httpx.AsyncClient, session_factory: async_sessionmaker[AsyncSession]
):
    async with session_factory() as session:
        r = Research(theme="Pesquisa Aprovação Total", status="AUDIT")
        session.add(r)
        await session.flush()
        p1 = ResearchPoint(
            research_id=r.id,
            position=1,
            title="P1",
            description="Desc 1",
            status="AUDIT_PENDING",
            attempt_count=0,
        )
        p2 = ResearchPoint(
            research_id=r.id,
            position=2,
            title="P2",
            description="Desc 2",
            status="AUDIT_PENDING",
            attempt_count=0,
        )
        session.add_all([p1, p2])
        await session.commit()
        r_id = r.id
        p1_id = p1.id
        p2_id = p2.id

    approved_verdict = AuditVerdict(
        approved=True,
        score=11,
        checklist={k: (i < 11) for i, k in enumerate(CRITERIA_KEYS)},
        findings=["Ponto consistente"],
        contradictions=[],
        uncertainties=[],
        missing_research=[],
        outline=[],
        status=AUDIT_APPROVED,
        attempt=1,
    )

    async def fake_audit_point(research_id, point_id, attempt_count=None):
        async with session_factory() as s:
            p = await s.get(ResearchPoint, point_id)
            p.status = AUDIT_APPROVED
            await s.commit()
        return approved_verdict

    with patch("app.audit.router.AuditService") as mock_cls:
        instance = mock_cls.return_value
        instance.audit_point = AsyncMock(side_effect=fake_audit_point)
        # check_all_points_completed real usando a session_factory
        from app.audit.service import AuditService

        real_service = AuditService(session_factory)
        instance.check_all_points_completed = real_service.check_all_points_completed

        res = await client.post(f"/api/audit/{r_id}/run", headers=AUTH_HEADERS)
        assert res.status_code == 200
        data = res.json()
        assert data["research_id"] == str(r_id)
        assert data["requested_points"] == 2
        assert len(data["outcomes"]) == 2
        assert data["research_status"] == "WRITE"
        assert data["write_transitioned"] is True

        # Verifica persistência no banco
        async with session_factory() as session:
            refreshed_r = await session.get(Research, r_id)
            assert refreshed_r.status == ResearchStatus.WRITE.value


@pytest.mark.anyio
async def test_run_research_audit_200_scraper_retry_bumps_attempt(
    client: httpx.AsyncClient, session_factory: async_sessionmaker[AsyncSession]
):
    async with session_factory() as session:
        r = Research(theme="Pesquisa com Reprovação", status="AUDIT")
        session.add(r)
        await session.flush()
        p = ResearchPoint(
            research_id=r.id,
            position=1,
            title="P1 Retry",
            description="Desc",
            status="AUDIT_PENDING",
            attempt_count=0,
        )
        session.add(p)
        await session.commit()
        r_id = r.id
        p_id = p.id

    retry_verdict = AuditVerdict(
        approved=False,
        score=6,
        checklist={k: (i < 6) for i, k in enumerate(CRITERIA_KEYS)},
        findings=["Lacunas encontradas"],
        contradictions=[],
        uncertainties=[],
        missing_research=["Investigar ponto com citação verbatim e URL de origem"],
        outline=[],
        status=SCRAPER_RETRY,
        attempt=1,
    )

    from app.audit.service import AuditService

    real_service = AuditService(session_factory)

    async def fake_audit_point(research_id, point_id, attempt_count=None):
        async with session_factory() as s:
            pt = await s.get(ResearchPoint, point_id)
            pt.status = SCRAPER_RETRY
            await s.commit()
        return retry_verdict

    with patch("app.audit.router.AuditService") as mock_cls:
        instance = mock_cls.return_value
        instance.audit_point = AsyncMock(side_effect=fake_audit_point)
        instance.bump_retry_attempt = real_service.bump_retry_attempt
        instance.check_all_points_completed = real_service.check_all_points_completed

        res = await client.post(f"/api/audit/{r_id}/run", headers=AUTH_HEADERS)
        assert res.status_code == 200
        data = res.json()
        assert data["requested_points"] == 1
        assert data["outcomes"][0]["state"] == SCRAPER_RETRY
        assert data["outcomes"][0]["attempt"] == 1
        assert data["write_transitioned"] is False

        # Verifica se attempt_count foi incrementado no banco
        async with session_factory() as session:
            refreshed_p = await session.get(ResearchPoint, p_id)
            assert refreshed_p.attempt_count == 1


# =========================================================================
# 3. Endpoint POST /api/audit/{research_id}/points/{point_id}/run
# =========================================================================


@pytest.mark.anyio
async def test_run_point_audit_404_research_not_found(client: httpx.AsyncClient):
    res = await client.post(
        f"/api/audit/{uuid4()}/points/{uuid4()}/run",
        headers=AUTH_HEADERS,
    )
    assert res.status_code == 404
    assert res.json()["detail"] == "Pesquisa não encontrada"


@pytest.mark.anyio
async def test_run_point_audit_404_point_not_found(
    client: httpx.AsyncClient, session_factory: async_sessionmaker[AsyncSession]
):
    async with session_factory() as session:
        r = Research(theme="Pesquisa Teste", status="AUDIT")
        session.add(r)
        await session.commit()
        r_id = r.id

    res = await client.post(
        f"/api/audit/{r_id}/points/{uuid4()}/run",
        headers=AUTH_HEADERS,
    )
    assert res.status_code == 404
    assert res.json()["detail"] == "Ponto de pesquisa não encontrado"


@pytest.mark.anyio
async def test_run_point_audit_404_point_belongs_to_other_research(
    client: httpx.AsyncClient, session_factory: async_sessionmaker[AsyncSession]
):
    async with session_factory() as session:
        r1 = Research(theme="Pesquisa 1", status="AUDIT")
        r2 = Research(theme="Pesquisa 2", status="AUDIT")
        session.add_all([r1, r2])
        await session.flush()
        p = ResearchPoint(
            research_id=r2.id,
            position=1,
            title="Ponto de R2",
            description="Desc",
            status="AUDIT_PENDING",
            attempt_count=0,
        )
        session.add(p)
        await session.commit()
        r1_id = r1.id
        p_id = p.id

    res = await client.post(
        f"/api/audit/{r1_id}/points/{p_id}/run",
        headers=AUTH_HEADERS,
    )
    assert res.status_code == 404
    assert res.json()["detail"] == "Ponto de pesquisa não encontrado"


@pytest.mark.anyio
async def test_run_point_audit_409_research_already_in_write_or_done(
    client: httpx.AsyncClient, session_factory: async_sessionmaker[AsyncSession]
):
    async with session_factory() as session:
        r = Research(theme="Pesquisa no Redator", status=ResearchStatus.WRITE.value)
        session.add(r)
        await session.flush()
        p = ResearchPoint(
            research_id=r.id,
            position=1,
            title="P1",
            description="Desc",
            status="AUDIT_PENDING",
            attempt_count=0,
        )
        session.add(p)
        await session.commit()
        r_id = r.id
        p_id = p.id

    res = await client.post(
        f"/api/audit/{r_id}/points/{p_id}/run",
        headers=AUTH_HEADERS,
    )
    assert res.status_code == 409
    assert "Pesquisa já liberada para o Redator" in res.json()["detail"]


@pytest.mark.anyio
async def test_run_point_audit_409_point_status_not_auditable(
    client: httpx.AsyncClient, session_factory: async_sessionmaker[AsyncSession]
):
    async with session_factory() as session:
        r = Research(theme="Pesquisa Ponto Inelegivel", status="AUDIT")
        session.add(r)
        await session.flush()
        p = ResearchPoint(
            research_id=r.id,
            position=1,
            title="Ponto em Coleta",
            description="Desc",
            status="SCRAPER_IN_PROGRESS",
            attempt_count=0,
        )
        session.add(p)
        await session.commit()
        r_id = r.id
        p_id = p.id

    res = await client.post(
        f"/api/audit/{r_id}/points/{p_id}/run",
        headers=AUTH_HEADERS,
    )
    assert res.status_code == 409
    assert "Estado do ponto não permite auditoria" in res.json()["detail"]


@pytest.mark.anyio
async def test_run_point_audit_200_success(
    client: httpx.AsyncClient, session_factory: async_sessionmaker[AsyncSession]
):
    async with session_factory() as session:
        r = Research(theme="Pesquisa Ponto Sucesso", status="AUDIT")
        session.add(r)
        await session.flush()
        p = ResearchPoint(
            research_id=r.id,
            position=1,
            title="Ponto Elegível",
            description="Desc",
            status="AUDIT_PENDING",
            attempt_count=0,
        )
        session.add(p)
        await session.commit()
        r_id = r.id
        p_id = p.id

    verdict = AuditVerdict(
        approved=True,
        score=11,
        checklist={k: (i < 11) for i, k in enumerate(CRITERIA_KEYS)},
        findings=["Evidências sólidas"],
        contradictions=[],
        uncertainties=["Leve incerteza residual"],
        missing_research=[],
        outline=["Tópico 1", "Tópico 2"],
        status=AUDIT_APPROVED,
        attempt=1,
    )

    with patch("app.audit.router.AuditService") as mock_cls:
        instance = mock_cls.return_value
        instance.audit_point = AsyncMock(return_value=verdict)

        res = await client.post(
            f"/api/audit/{r_id}/points/{p_id}/run",
            headers=AUTH_HEADERS,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["approved"] is True
        assert data["score"] == 11
        assert data["findings"] == ["Evidências sólidas"]
        assert data["uncertainties"] == ["Leve incerteza residual"]
        assert data["missing_research"] == []
        assert data["checklist"]["q1"] is True
        assert data["checklist"]["q12"] is False
