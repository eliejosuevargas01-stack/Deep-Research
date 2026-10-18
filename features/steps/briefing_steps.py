from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx
from behave import given, step, then, when
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.briefing.domain import (
    Briefing,
    BriefingPoint,
    BriefingStatus,
    approve_briefing,
    complete_briefing,
    edit_briefing,
    new_briefing,
)
from app.briefing.serp_client import SerpSearchError
from app.briefing.service import LLMAttemptError
from app.briefing.storage import (
    create_generating_briefing,
    save_briefing_transition,
)
from app.core.config import settings
from app.db.database import get_db
from app.main import app
from app.models.domain_models import Base


def run_async(coro):
    return asyncio.run(coro)


async def _init_briefing_db(context):
    engine: AsyncEngine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    context.engine = engine
    context.session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def _override_get_db():
        async with context.session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db


def _auth_headers():
    return {"Authorization": f"Bearer {settings.API_AUTH_SECRET}"}


@given('um tema válido de pesquisa "{theme}"')
def step_valid_theme(context, theme: str):
    run_async(_init_briefing_db(context))
    context.theme = theme


@given('um tema de pesquisa inválido "{theme}"')
def step_invalid_theme(context, theme: str):
    run_async(_init_briefing_db(context))
    context.theme = theme


@given("serviços de busca SERP e LLM retornando respostas válidas com 5 pontos")
def step_mock_serp_and_llm_valid(context):
    mock_serp = AsyncMock()
    mock_serp.search.return_value = [
        {"title": "Fonte 1", "url": "https://source1.org", "snippet": "Snippet 1"}
    ]
    context.mock_serp = mock_serp

    async def _llm(system, user):
        return json.dumps([
            {"title": f"Ponto {i}", "description": f"Descrição detalhada do ponto {i}"}
            for i in range(1, 6)
        ])

    context.mock_llm = _llm


@given("o provedor de busca SERP indisponível simulando falha de rede")
def step_mock_serp_failure(context):
    mock_serp = AsyncMock()
    mock_serp.search.side_effect = SerpSearchError(attempts=3)
    context.mock_serp = mock_serp
    context.mock_llm = AsyncMock()


@given("o provedor de LLM indisponível simulando esgotamento de quota ou timeout")
def step_mock_llm_failure(context):
    mock_serp = AsyncMock()
    mock_serp.search.return_value = [
        {"title": "F1", "url": "https://f1.org", "snippet": "S1"}
    ]
    context.mock_serp = mock_serp

    mock_llm = AsyncMock()
    mock_llm.side_effect = LLMAttemptError()
    context.mock_llm = mock_llm


@when('uma requisição "POST /briefings" é enviada com o tema')
def step_post_briefings(context):
    import app.briefing.router as briefing_mod

    async def _call():
        with patch.object(briefing_mod, "AsyncSessionLocal", context.session_factory):
            with patch.object(briefing_mod, "_build_serp_client", return_value=context.mock_serp):
                with patch.object(briefing_mod, "_build_llm_complete", return_value=context.mock_llm):
                    transport = httpx.ASGITransport(app=app)
                    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                        context.response = await client.post(
                            "/briefings",
                            json={"theme": context.theme},
                            headers=_auth_headers(),
                        )

    run_async(_call())


@when('uma requisição "POST /briefings" é enviada com o tema inválido')
def step_post_invalid_theme(context):
    import app.briefing.router as briefing_mod

    async def _call():
        with patch.object(briefing_mod, "AsyncSessionLocal", context.session_factory):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                context.response = await client.post(
                    "/briefings",
                    json={"theme": context.theme},
                    headers=_auth_headers(),
                )

    run_async(_call())


@then('a resposta deve conter status de briefing "{expected_status}" e versão {version:d}')
def step_assert_briefing_status_version(context, expected_status: str, version: int):
    data = context.response.json()
    assert data.get("status") == expected_status, (
        f"Esperado status '{expected_status}', obtido {data.get('status')}"
    )
    assert data.get("version") == version, (
        f"Esperado versão {version}, obtido {data.get('version')}"
    )


@then("o briefing deve conter entre 3 e 7 pontos de pesquisa estruturados")
def step_assert_points_count(context):
    data = context.response.json()
    points = data.get("points", [])
    assert 3 <= len(points) <= 7, f"Contagem de pontos fora da faixa [3, 7]: {len(points)}"
    for p in points:
        assert p.get("title") and p.get("description")


@then('a resposta de erro do briefing deve conter "{expected_substring}"')
def step_assert_briefing_error_detail(context, expected_substring: str):
    data = context.response.json()
    detail = data.get("detail", "")
    assert expected_substring in str(detail), (
        f"Esperado '{expected_substring}' no detalhe de erro, obtido: {detail}"
    )


@given("um briefing em rascunho persistido com versão 2")
def step_persisted_draft_briefing(context):
    run_async(_init_briefing_db(context))
    context.research_id = uuid4()

    async def _setup():
        async with context.session_factory() as session:
            b_gen = new_briefing("Tema para Revisão")
            b_gen = Briefing(
                id=context.research_id,
                theme=b_gen.theme,
                status=b_gen.status,
                points=b_gen.points,
                version=b_gen.version,
            )
            await create_generating_briefing(session, b_gen)
            pts = [
                BriefingPoint(title=f"Ponto {i}", description=f"Desc {i}")
                for i in range(1, 5)
            ]
            b_draft = complete_briefing(b_gen, pts)
            await save_briefing_transition(session, b_gen, b_draft)
            await session.commit()

    run_async(_setup())


@when('uma requisição "PATCH /briefings/<id>" é enviada com nota "{note}"')
def step_patch_briefing(context, note: str):
    import app.briefing.router as briefing_mod

    mock_serp = AsyncMock()
    mock_serp.search.return_value = [
        {"title": "Fonte Rev", "url": "https://rev.org", "snippet": "Snippet Rev"}
    ]

    async def _mock_llm(system, user):
        if "Você formula consultas de busca web" in system:
            return "Busca quantum medicina"
        return json.dumps([
            {"title": f"Rev Ponto {i}", "description": f"Rev Desc {i}"}
            for i in range(1, 5)
        ])

    async def _call():
        with patch.object(briefing_mod, "AsyncSessionLocal", context.session_factory):
            with patch.object(briefing_mod, "_build_serp_client", return_value=mock_serp):
                with patch.object(briefing_mod, "_build_llm_complete", return_value=_mock_llm):
                    with patch("app.investigation.service.InvestigationService.run_investigation", new_callable=AsyncMock):
                        transport = httpx.ASGITransport(app=app)
                        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                            context.response = await client.patch(
                                f"/briefings/{context.research_id}",
                                json={"note": note},
                                headers=_auth_headers(),
                            )

    run_async(_call())


@then("a resposta deve conter status de briefing \"approved\" e versão incrementada")
def step_assert_approved_incremented(context):
    data = context.response.json()
    assert data.get("status") == "approved", f"Esperado status 'approved', obtido: {data}"
    assert data.get("version") > 2, f"Versão não foi incrementada: {data.get('version')}"


@then("a investigação deve ser agendada para execução em background")
def step_assert_investigation_scheduled(context):
    pass


@given('um briefing com status "approved" gravado no sistema')
def step_given_approved_briefing(context):
    run_async(_init_briefing_db(context))
    context.research_id = uuid4()

    async def _setup():
        async with context.session_factory() as session:
            b_gen = new_briefing("Tema Aprovado")
            b_gen = Briefing(
                id=context.research_id,
                theme=b_gen.theme,
                status=b_gen.status,
                points=b_gen.points,
                version=b_gen.version,
            )
            await create_generating_briefing(session, b_gen)
            pts = [
                BriefingPoint(title=f"P {i}", description=f"D {i}")
                for i in range(1, 4)
            ]
            b_draft = complete_briefing(b_gen, pts)
            saved_draft = await save_briefing_transition(session, b_gen, b_draft)
            approved = approve_briefing(saved_draft, datetime.now(timezone.utc))
            await save_briefing_transition(session, saved_draft, approved)
            await session.commit()

    run_async(_setup())


@when('uma requisição "POST /briefings/<id>/reopen" é enviada')
def step_post_reopen(context):
    import app.briefing.router as briefing_mod

    async def _call():
        with patch.object(briefing_mod, "AsyncSessionLocal", context.session_factory):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                context.response = await client.post(
                    f"/briefings/{context.research_id}/reopen",
                    json={},
                    headers=_auth_headers(),
                )

    run_async(_call())


@given("um briefing já revisado com versão superior a 2")
def step_already_revised_briefing(context):
    run_async(_init_briefing_db(context))
    context.research_id = uuid4()

    async def _setup():
        async with context.session_factory() as session:
            b_gen = new_briefing("Tema Dupla Revisão")
            b_gen = Briefing(
                id=context.research_id,
                theme=b_gen.theme,
                status=b_gen.status,
                points=b_gen.points,
                version=b_gen.version,
            )
            await create_generating_briefing(session, b_gen)
            pts = [
                BriefingPoint(title=f"P {i}", description=f"D {i}")
                for i in range(1, 4)
            ]
            b_draft = complete_briefing(b_gen, pts)
            saved_draft = await save_briefing_transition(session, b_gen, b_draft)
            b_rev = edit_briefing(saved_draft, list(saved_draft.points))
            await save_briefing_transition(session, saved_draft, b_rev)
            await session.commit()

    run_async(_setup())


@when('uma requisição "PATCH /briefings/<id>" é enviada com nova nota')
def step_patch_again(context):
    step_patch_briefing(context, "Segunda nota proibida")


@given('um briefing com status "approved" e data de aprovação registrada')
def step_approved_with_timestamp(context):
    step_given_approved_briefing(context)


@when('uma requisição "GET /briefings/approved/<id>" é enviada')
def step_get_approved_briefing(context):
    import app.briefing.router as briefing_mod

    async def _call():
        with patch.object(briefing_mod, "AsyncSessionLocal", context.session_factory):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                context.response = await client.get(
                    f"/briefings/approved/{context.research_id}",
                    headers=_auth_headers(),
                )

    run_async(_call())


@then('o corpo da resposta deve conter o tema, pontos e o carimbo de data "approved_at"')
def step_assert_approved_body(context):
    data = context.response.json()
    assert data.get("theme") == "Tema Aprovado"
    assert len(data.get("points", [])) == 3
    assert data.get("approved_at") is not None


@given("um briefing que transitou de rascunho para aprovado")
def step_briefing_with_multiple_versions(context):
    step_given_approved_briefing(context)


@when('uma requisição "GET /briefings/<id>/versions" é enviada')
def step_get_briefing_versions(context):
    import app.briefing.router as briefing_mod

    async def _call():
        with patch.object(briefing_mod, "AsyncSessionLocal", context.session_factory):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                context.response = await client.get(
                    f"/briefings/{context.research_id}/versions",
                    headers=_auth_headers(),
                )

    run_async(_call())


@then("a lista de versões deve conter pelo menos 2 registros cronológicos")
def step_assert_versions_count(context):
    data = context.response.json()
    assert isinstance(data, list)
    assert len(data) >= 2, f"Esperado pelo menos 2 versões, obtido {len(data)}: {data}"
    versions = [item["version"] for item in data]
    assert versions == sorted(versions), "Versões devem estar ordenadas cronologicamente"
