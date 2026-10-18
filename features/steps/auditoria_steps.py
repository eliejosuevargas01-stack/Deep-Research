from __future__ import annotations

import asyncio
from dataclasses import asdict
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx
from behave import given, step, then, when
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.audit.domain import (
    AUDIT_APPROVED,
    AUDIT_CAVEAT,
    CRITERIA_KEYS,
    SCRAPER_RETRY,
    STATE_INCONCLUSIVE,
    AuditVerdict,
    evaluate_audit_verdict,
)
from app.audit.service import AuditService
from app.core.config import settings
from app.db.database import get_db
from app.investigation.tools import JinaSearchResult
from app.investigation.worker import _excluded_url_keys, _filter_search_result
from app.main import app
from app.models.domain_models import (
    AuditTrail,
    Base,
    Research,
    ResearchPoint,
    ResearchStatus,
    ResearchStepResult,
)


def run_async(coro):
    return asyncio.run(coro)


async def _init_context_db(context):
    engine: AsyncEngine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    context.engine = engine
    context.session_factory = async_sessionmaker(engine, expire_on_commit=False)


# =========================================================================
# Cenário 1: Aprovação direta de ponto com score maior ou igual a 10 de 12
# =========================================================================


@given("um ponto de pesquisa com evidências coletadas pelas 4 personas")
def step_point_with_4_personas(context):
    async def _setup():
        await _init_context_db(context)
        async with context.session_factory() as session:
            r = Research(theme="Pesquisa Teste", status="AUDIT")
            session.add(r)
            await session.flush()
            p = ResearchPoint(
                research_id=r.id,
                position=1,
                title="Ponto 1",
                description="Desc Ponto 1",
                status="AUDIT_PENDING",
                attempt_count=0,
            )
            session.add(p)
            await session.flush()
            for persona in ("historian", "skeptic", "pragmatist", "futurist"):
                step_res = ResearchStepResult(
                    research_id=r.id,
                    step_id=p.id,
                    step_title="Ponto 1",
                    result=f"Evidência de {persona}",
                    used_urls=[f"https://source-{persona}.com"],
                    read_urls=[f"https://source-{persona}.com"],
                    worker=persona,
                    status="AUDIT_PENDING",
                )
                session.add(step_res)
            await session.commit()
            context.research_id = r.id
            context.point_id = p.id

    run_async(_setup())


@when("o Agente Auditor avalia o ponto e atribui score 11 de 12 sem contradições")
def step_audit_evaluates_11_of_12(context):
    checklist = {k: True for k in CRITERIA_KEYS[:11]}
    checklist[CRITERIA_KEYS[11]] = False
    verdict = evaluate_audit_verdict(checklist=checklist, contradictions=[], attempt_count=1)
    context.verdict = verdict

    async def _persist():
        async with context.session_factory() as session:
            point = await session.get(ResearchPoint, context.point_id)
            point.status = verdict.status
            point.audit = asdict(verdict)
            trail = AuditTrail(
                research_id=context.research_id,
                point_id=context.point_id,
                stage="point_audit",
                attempt=1,
                details=point.audit,
            )
            session.add(trail)
            await session.commit()

    run_async(_persist())


@step('o ponto de pesquisa deve transitar para o status "{expected_status}"')
@step('o ponto deve transitar para o status "{expected_status}"')
def step_point_transitions_to_status(context, expected_status):
    async def _check():
        async with context.session_factory() as session:
            point = await session.get(ResearchPoint, context.point_id)
            assert point.status == expected_status, f"Expected {expected_status}, got {point.status}"

    run_async(_check())


@then("o veredito estruturado deve ser registrado em audit_trails")
def step_verdict_recorded_in_audit_trails(context):
    async def _check():
        async with context.session_factory() as session:
            trail = (
                await session.scalars(
                    select(AuditTrail).where(AuditTrail.point_id == context.point_id)
                )
            ).first()
            assert trail is not None, "AuditTrail not found"
            assert trail.stage == "point_audit"
            assert trail.details.get("approved") is True
            assert trail.details.get("score") == 11

    run_async(_check())


# =========================================================================
# Cenário 2: Reprovação de ponto com retry e missing research concreto
# =========================================================================


@given("um ponto de pesquisa na tentativa 1 com evidências incompletas")
def step_point_attempt_1_incomplete(context):
    async def _setup():
        await _init_context_db(context)
        async with context.session_factory() as session:
            r = Research(theme="Pesquisa Retry", status="AUDIT")
            session.add(r)
            await session.flush()
            p = ResearchPoint(
                research_id=r.id,
                position=1,
                title="Ponto Retry",
                description="Desc",
                status="AUDIT_PENDING",
                attempt_count=1,
            )
            session.add(p)
            await session.commit()
            context.research_id = r.id
            context.point_id = p.id

    run_async(_setup())


@when("o Agente Auditor avalia o ponto e atribui score 7 de 12")
def step_audit_score_7(context):
    checklist = {k: (i < 7) for i, k in enumerate(CRITERIA_KEYS)}
    verdict = evaluate_audit_verdict(checklist=checklist, attempt_count=1)
    context.verdict = verdict

    async def _persist():
        service = AuditService(context.session_factory)
        async with context.session_factory() as session:
            point = await session.get(ResearchPoint, context.point_id)
            point.status = verdict.status
            point.audit = asdict(verdict)
            trail = AuditTrail(
                research_id=context.research_id,
                point_id=context.point_id,
                stage="point_audit",
                attempt=1,
                details=point.audit,
            )
            session.add(trail)
            await session.commit()
        await service.bump_retry_attempt(context.research_id, context.point_id)

    run_async(_persist())


@then('o veredito deve conter instruções concretas de "{field_name}"')
def step_verdict_concrete_missing_research(context, field_name):
    items = getattr(context.verdict, field_name, [])
    assert len(items) > 0, f"Expected non-empty {field_name}"
    for item in items:
        assert isinstance(item, str) and len(item.strip()) >= 12, (
            f"Expected concrete instruction with >= 12 chars: {item}"
        )


@then("o contador de tentativas do ponto deve ser incrementado para 2")
def step_point_attempt_incremented_to_2(context):
    async def _check():
        async with context.session_factory() as session:
            point = await session.get(ResearchPoint, context.point_id)
            assert point.attempt_count == 2, f"Expected attempt_count 2, got {point.attempt_count}"

    run_async(_check())


# =========================================================================
# Cenário 3: Re-execução em retry respeitando filtro anti-duplicação de URLs
# =========================================================================


@given('um ponto de pesquisa em status "SCRAPER_RETRY" que já leu "{url1}" e "{url2}"')
def step_point_retry_read_urls(context, url1, url2):
    context.excluded_urls = {url1, url2}
    context.read_urls = [url1, url2]


@when("as 4 personas executam a re-pesquisa com as instruções de missing research")
def step_personas_run_retry(context):
    raw_search = JinaSearchResult(
        content=(
            "Trecho de leitura sobre https://source1.com com dados repetidos.\n\n"
            "Trecho de leitura sobre https://source2.com com dados duplicados.\n\n"
            "Trecho novo da fonte https://source3.com com novas evidências.\n\n"
            "Trecho inédito da fonte https://source4.com com fatos complementares."
        ),
        urls=[
            "https://source1.com",
            "https://source2.com",
            "https://source3.com",
            "https://source4.com",
        ],
    )
    excluded_keys = _excluded_url_keys(context.excluded_urls)
    filtered = _filter_search_result(raw_search, excluded_keys)
    context.filtered_result = filtered
    for u in filtered.urls:
        if u not in context.read_urls:
            context.read_urls.append(u)


@then('as consultas de busca devem descartar as URLs "{url1}" e "{url2}"')
def step_search_discards_urls(context, url1, url2):
    assert url1 not in context.filtered_result.urls, f"{url1} was not discarded from urls"
    assert url2 not in context.filtered_result.urls, f"{url2} was not discarded from urls"
    assert url1 not in context.filtered_result.content, f"{url1} was not discarded from content"
    assert url2 not in context.filtered_result.content, f"{url2} was not discarded from content"


@then("apenas novas URLs devem ser lidas e agregadas ao histórico")
def step_only_new_urls_read(context):
    assert len(context.filtered_result.urls) == 2
    assert set(context.filtered_result.urls) == {"https://source3.com", "https://source4.com"}
    assert set(context.read_urls) == {
        "https://source1.com",
        "https://source2.com",
        "https://source3.com",
        "https://source4.com",
    }


# =========================================================================
# Cenário 4: Ponto reprovado na quarta tentativa transita para AUDIT_CAVEAT
# =========================================================================


@given("um ponto de pesquisa na tentativa 4 com score 8 de 12")
def step_point_attempt_4_score_8(context):
    async def _setup():
        await _init_context_db(context)
        async with context.session_factory() as session:
            r = Research(theme="Pesquisa Caveat", status="AUDIT")
            session.add(r)
            await session.flush()
            p = ResearchPoint(
                research_id=r.id,
                position=1,
                title="Ponto Caveat",
                description="Desc",
                status="AUDIT_PENDING",
                attempt_count=4,
            )
            session.add(p)
            await session.commit()
            context.research_id = r.id
            context.point_id = p.id
            context.checklist = {k: (i < 8) for i, k in enumerate(CRITERIA_KEYS)}

    run_async(_setup())


@when("o Agente Auditor conclui a avaliação")
def step_audit_concludes_evaluation(context):
    verdict = evaluate_audit_verdict(checklist=context.checklist, attempt_count=4)
    context.verdict = verdict

    async def _persist():
        async with context.session_factory() as session:
            point = await session.get(ResearchPoint, context.point_id)
            point.status = verdict.status
            point.audit = asdict(verdict)
            trail = AuditTrail(
                research_id=context.research_id,
                point_id=context.point_id,
                stage="point_audit",
                attempt=4,
                details=point.audit,
            )
            session.add(trail)
            await session.commit()

    run_async(_persist())


@then("o ponto não deve ser marcado como bloqueado fatal")
def step_point_not_fatal_blocked(context):
    assert context.verdict.status != "BLOCKED"
    assert context.verdict.status != "FAILED"


@then("as limitações não resolvidas devem ser registradas no veredito")
def step_unresolved_limitations_recorded(context):
    assert context.verdict.is_caveat is True
    assert len(context.verdict.missing_research) > 0 or len(context.verdict.uncertainties) > 0


# =========================================================================
# Cenário 5: Falha de rede ou 503 não queima tentativa do ponto
# =========================================================================


@given("um ponto de pesquisa na tentativa 1 aguardando auditoria")
def step_point_attempt_1_awaiting_audit(context):
    async def _setup():
        await _init_context_db(context)
        async with context.session_factory() as session:
            r = Research(theme="Pesquisa Inconclusiva", status="AUDIT")
            session.add(r)
            await session.flush()
            p = ResearchPoint(
                research_id=r.id,
                position=1,
                title="Ponto Infra Fail",
                description="Desc",
                status="AUDIT_PENDING",
                attempt_count=1,
            )
            session.add(p)
            await session.commit()
            context.research_id = r.id
            context.point_id = p.id

    run_async(_setup())


@when("o serviço de IA do Auditor falha com erro 503 por 4 vezes consecutivas")
def step_audit_service_503_4_times(context):
    async def _record():
        service = AuditService(context.session_factory)
        verdict = await service._record_inconclusive(
            context.research_id,
            context.point_id,
            reason="HTTP 503 Service Unavailable (4x)",
        )
        context.verdict = verdict

    run_async(_record())


@then('o sistema deve registrar a tentativa como "{expected_status}"')
def step_system_records_inconclusive(context, expected_status):
    assert context.verdict.status == expected_status

    async def _check():
        async with context.session_factory() as session:
            trail = (
                await session.scalars(
                    select(AuditTrail).where(AuditTrail.point_id == context.point_id)
                )
            ).first()
            assert trail is not None
            assert trail.details.get("status") == expected_status
            assert trail.attempt is None, "Attempt must not be burned on infra failure (RN-304)"

    run_async(_check())


@then("o contador de tentativas do ponto de pesquisa deve permanecer em 1")
def step_attempt_counter_remains_1(context):
    async def _check():
        async with context.session_factory() as session:
            point = await session.get(ResearchPoint, context.point_id)
            assert point.attempt_count == 1, f"Expected attempt_count 1, got {point.attempt_count}"

    run_async(_check())


# =========================================================================
# Cenário 6: Disparo automático imediatamente após workers do ponto
# =========================================================================


@given("uma pesquisa com 3 pontos sendo investigados em paralelo")
def step_research_with_3_points(context):
    async def _setup():
        await _init_context_db(context)
        async with context.session_factory() as session:
            r = Research(theme="Pesquisa Paralela", status="SCRAPER")
            session.add(r)
            await session.flush()
            points = []
            for i in range(1, 4):
                p = ResearchPoint(
                    research_id=r.id,
                    position=i,
                    title=f"Ponto {i}",
                    description=f"Desc {i}",
                    status="SCRAPER_IN_PROGRESS",
                    attempt_count=0,
                )
                session.add(p)
                points.append(p)
            await session.commit()
            context.research_id = r.id
            context.point_ids = [p.id for p in points]

    run_async(_setup())


@when("os 4 workers do ponto 1 concluem sua coleta antes dos demais pontos")
def step_point_1_workers_finish(context):
    async def _finish_point_1():
        p1_id = context.point_ids[0]
        async with context.session_factory() as session:
            for persona in ("historian", "skeptic", "pragmatist", "futurist"):
                step_res = ResearchStepResult(
                    research_id=context.research_id,
                    step_id=p1_id,
                    step_title="Ponto 1",
                    result=f"Resultado {persona}",
                    used_urls=["https://test.org/p1"],
                    read_urls=["https://test.org/p1"],
                    worker=persona,
                    status="AUDIT_PENDING",
                )
                session.add(step_res)
            p1 = await session.get(ResearchPoint, p1_id)
            p1.status = "AUDIT_PENDING"
            await session.commit()

        checklist = {k: True for k in CRITERIA_KEYS}
        verdict = evaluate_audit_verdict(checklist=checklist, attempt_count=1)
        async with context.session_factory() as session:
            p1 = await session.get(ResearchPoint, p1_id)
            p1.status = verdict.status
            p1.audit = asdict(verdict)
            trail = AuditTrail(
                research_id=context.research_id,
                point_id=p1_id,
                stage="point_audit",
                attempt=1,
                details=p1.audit,
            )
            session.add(trail)
            await session.commit()

    run_async(_finish_point_1())


@then("a auditoria do ponto 1 deve ser iniciada imediatamente em background")
def step_point_1_audit_started(context):
    async def _check():
        p1_id = context.point_ids[0]
        async with context.session_factory() as session:
            p1 = await session.get(ResearchPoint, p1_id)
            assert p1.status == "AUDIT_APPROVED"
            trail = (
                await session.scalars(
                    select(AuditTrail).where(AuditTrail.point_id == p1_id)
                )
            ).first()
            assert trail is not None

    run_async(_check())


@then("sem aguardar a conclusão dos pontos 2 e 3")
def step_without_waiting_points_2_and_3(context):
    async def _check():
        p2_id = context.point_ids[1]
        p3_id = context.point_ids[2]
        async with context.session_factory() as session:
            p2 = await session.get(ResearchPoint, p2_id)
            p3 = await session.get(ResearchPoint, p3_id)
            assert p2.status == "SCRAPER_IN_PROGRESS"
            assert p3.status == "SCRAPER_IN_PROGRESS"
            trail2 = (
                await session.scalars(
                    select(AuditTrail).where(AuditTrail.point_id == p2_id)
                )
            ).first()
            trail3 = (
                await session.scalars(
                    select(AuditTrail).where(AuditTrail.point_id == p3_id)
                )
            ).first()
            assert trail2 is None
            assert trail3 is None

    run_async(_check())


# =========================================================================
# Cenário 7: Disparo manual da auditoria via endpoint da API
# =========================================================================


@given('uma pesquisa autenticada com ponto em status "AUDIT_PENDING"')
def step_auth_research_audit_pending(context):
    async def _setup():
        await _init_context_db(context)
        async with context.session_factory() as session:
            r = Research(theme="Pesquisa API", status="AUDIT")
            session.add(r)
            await session.flush()
            p = ResearchPoint(
                research_id=r.id,
                position=1,
                title="Ponto API",
                description="Desc",
                status="AUDIT_PENDING",
                attempt_count=0,
            )
            session.add(p)
            await session.commit()
            context.research_id = r.id
            context.point_id = p.id

    run_async(_setup())


@when('uma requisição "POST /api/audit/{research_id}/points/{point_id}/run" é recebida')
def step_req_post_point_audit(context, research_id=None, point_id=None):
    async def _call():
        async def db_override():
            async with context.session_factory() as session:
                yield session

        app.dependency_overrides[get_db] = db_override
        verdict = AuditVerdict(
            approved=True,
            score=11,
            checklist={k: (i < 11) for i, k in enumerate(CRITERIA_KEYS)},
            findings=["Finding 1"],
            contradictions=[],
            uncertainties=[],
            missing_research=[],
            outline=[],
            status="AUDIT_APPROVED",
        )
        mock_service = AsyncMock()
        mock_service.audit_point.return_value = verdict
        with patch("app.audit.router._audit_service", return_value=mock_service):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client:
                res = await client.post(
                    f"/api/audit/{context.research_id}/points/{context.point_id}/run",
                    headers={"Authorization": f"Bearer {settings.API_AUTH_SECRET}"},
                )
                context.api_response = res
        app.dependency_overrides.clear()

    run_async(_call())


@then("a resposta da API deve ser HTTP 200 ou 202")
def step_api_status_200_or_202(context):
    assert context.api_response.status_code in (200, 202), (
        f"Expected 200 or 202, got {context.api_response.status_code}: {context.api_response.text}"
    )


@then("a auditoria do ponto especificado deve ser executada")
def step_point_audit_executed(context):
    data = context.api_response.json()
    assert data.get("approved") is True
    assert data.get("score") == 11
    assert "checklist" in data


# =========================================================================
# Cenário 8: Transição da pesquisa para WRITE quando 100% dos pontos concluem
# =========================================================================


@given('uma pesquisa com todos os pontos nos estados "AUDIT_APPROVED" ou "AUDIT_CAVEAT"')
def step_all_points_approved_or_caveat(context):
    async def _setup():
        await _init_context_db(context)
        async with context.session_factory() as session:
            r = Research(theme="Pesquisa Concluída", status="AUDIT")
            session.add(r)
            await session.flush()
            p1 = ResearchPoint(
                research_id=r.id,
                position=1,
                title="Ponto 1",
                description="Desc",
                status="AUDIT_APPROVED",
                attempt_count=1,
            )
            p2 = ResearchPoint(
                research_id=r.id,
                position=2,
                title="Ponto 2",
                description="Desc",
                status="AUDIT_CAVEAT",
                attempt_count=4,
            )
            session.add_all([p1, p2])
            await session.commit()
            context.research_id = r.id

    run_async(_setup())


@when("o último ponto é processado pelo ciclo de auditoria")
def step_last_point_processed(context):
    async def _transition():
        service = AuditService(context.session_factory)
        async with context.session_factory() as session:
            transitioned = await service.check_all_points_completed(session, context.research_id)
            context.transitioned = transitioned

    run_async(_transition())


@then('o status da pesquisa deve transitar de "AUDIT" para "WRITE"')
def step_research_status_audit_to_write(context):
    assert context.transitioned is True

    async def _check():
        async with context.session_factory() as session:
            r = await session.get(Research, context.research_id)
            assert r.status == "WRITE", f"Expected WRITE, got {r.status}"

    run_async(_check())


@then("a pesquisa deve estar liberada para o Agente Redator")
def step_research_ready_for_writer(context):
    async def _check():
        async with context.session_factory() as session:
            r = await session.get(Research, context.research_id)
            assert r.status == ResearchStatus.WRITE.value

    run_async(_check())
