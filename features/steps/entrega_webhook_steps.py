from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx
from behave import given, step, then, when
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.db.database import get_db
from app.main import app
from app.models.domain_models import (
    AuditTrail,
    Base,
    Event,
    Report,
    Research,
    ResearchStatus,
)
from app.services.webhook import dispatch_callback


def run_async(coro):
    return asyncio.run(coro)


async def _init_webhook_db(context):
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


@given('uma pesquisa concluída em status "DONE" com relatório gerado e callback_url pública')
def step_given_research_with_public_callback(context):
    run_async(_init_webhook_db(context))
    context.research_id = uuid4()
    context.report_id = uuid4()
    context.callback_url = "https://webhook.site/test-receiver-123"

    async def _setup():
        async with context.session_factory() as session:
            r = Research(
                id=context.research_id,
                theme="Baterias de Estado Sólido",
                status=ResearchStatus.DONE.value,
                callback_url=context.callback_url,
            )
            session.add(r)
            rep = Report(
                id=context.report_id,
                research_id=context.research_id,
                content_markdown="# Relatório: Baterias de Estado Sólido\nTexto com evidências e citações.",
                citation_metrics={"source_urls_cited": 2},
                audit_findings={"points": []},
            )
            session.add(rep)
            await session.commit()

    run_async(_setup())


@when("o serviço de despacho de webhook é executado")
def step_dispatch_webhook(context):
    import app.services.webhook as webhook_mod

    class FakeResponse:
        status = 200

    class FakeClientSession:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
        def post(self, url, **kwargs):
            class PostCtx:
                async def __aenter__(self):
                    return FakeResponse()
                async def __aexit__(self, exc_type, exc_val, exc_tb):
                    pass
            return PostCtx()

    async def _run():
        with patch.object(webhook_mod, "AsyncSessionLocal", context.session_factory):
            with patch.object(webhook_mod, "validate_public_url"):
                with patch("aiohttp.ClientSession", FakeClientSession):
                    with patch("app.services.research.add_event", new_callable=AsyncMock) as mock_evt:
                        context.mock_evt = mock_evt
                        context.delivered = await dispatch_callback(context.research_id)

    run_async(_run())


@then("a requisição POST deve ser entregue com sucesso com status 200")
def step_assert_post_delivered(context):
    assert context.delivered is True, "Despacho do webhook deveria ter retornado True"


@then('um registro de auditoria na etapa "callback" com status entregue deve ser persistido')
def step_assert_audit_trail_persisted(context):
    async def _check():
        async with context.session_factory() as session:
            rows = await session.execute(
                select(AuditTrail).where(AuditTrail.research_id == context.research_id)
            )
            return rows.scalars().first()

    trail = run_async(_check())
    assert trail is not None, "Registro AuditTrail ausente"
    assert trail.stage == "callback"
    assert trail.details.get("delivered") is True


@then('um evento de sistema "callback_delivered" deve ser emitido')
def step_assert_callback_delivered_event(context):
    assert context.mock_evt.called
    called_type = context.mock_evt.call_args[0][2]
    assert called_type == "callback_delivered", f"Esperado callback_delivered, obtido {called_type}"


@given('uma pesquisa concluída configurada com callback_url apontando para "{url}"')
def step_given_private_callback(context, url: str):
    run_async(_init_webhook_db(context))
    context.research_id = uuid4()
    context.report_id = uuid4()
    context.callback_url = url

    async def _setup():
        async with context.session_factory() as session:
            r = Research(
                id=context.research_id,
                theme="Tema SSRF",
                status=ResearchStatus.DONE.value,
                callback_url=context.callback_url,
            )
            session.add(r)
            rep = Report(
                id=context.report_id,
                research_id=context.research_id,
                content_markdown="# Relatório SSRF",
                citation_metrics={},
                audit_findings={},
            )
            session.add(rep)
            await session.commit()

    run_async(_setup())


@when("o serviço de despacho de webhook tenta validar e conectar ao destino")
def step_dispatch_webhook_with_ssrf_attempt(context):
    import app.services.webhook as webhook_mod

    async def _run():
        with patch.object(webhook_mod, "AsyncSessionLocal", context.session_factory):
            with patch("app.services.research.add_event", new_callable=AsyncMock):
                context.delivered = await dispatch_callback(context.research_id)

    run_async(_run())


@then("o envio para a URL privada deve falhar com violação de segurança SSRF")
def step_assert_ssrf_blocked(context):
    assert context.delivered is False, "Envio para IP privado não deveria ter sido entregue"


@then("o registro de auditoria deve indicar que o webhook não foi entregue")
def step_assert_audit_undelivered(context):
    async def _check():
        async with context.session_factory() as session:
            rows = await session.execute(
                select(AuditTrail).where(AuditTrail.research_id == context.research_id)
            )
            return rows.scalars().first()

    trail = run_async(_check())
    assert trail is not None
    assert trail.details.get("delivered") is False


@given('uma pesquisa concluída em status "DONE" cujo endpoint de webhook externo retorna erro 500')
def step_given_external_500_webhook(context):
    step_given_research_with_public_callback(context)


@when("o serviço de despacho de webhook processa o erro")
def step_dispatch_with_external_500(context):
    import app.services.webhook as webhook_mod

    class ErrorResponse:
        status = 500

    class FakeClientSession:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
        def post(self, url, **kwargs):
            class PostCtx:
                async def __aenter__(self):
                    return ErrorResponse()
                async def __aexit__(self, exc_type, exc_val, exc_tb):
                    pass
            return PostCtx()

    async def _run():
        with patch.object(webhook_mod, "AsyncSessionLocal", context.session_factory):
            with patch.object(webhook_mod, "validate_public_url"):
                with patch("aiohttp.ClientSession", FakeClientSession):
                    with patch("app.services.research.add_event", new_callable=AsyncMock):
                        context.delivered = await dispatch_callback(context.research_id)

    run_async(_run())


@then('o status da pesquisa deve permanecer como "DONE"')
def step_assert_status_remains_done(context):
    async def _check():
        async with context.session_factory() as session:
            r = await session.get(Research, context.research_id)
            return r.status

    status = run_async(_check())
    assert status == ResearchStatus.DONE.value, f"Status não deveria mudar de DONE, obtido: {status}"


@then("o relatório gerado deve permanecer integralmente disponível para consulta")
def step_assert_report_available(context):
    async def _check():
        async with context.session_factory() as session:
            rep = await session.scalar(
                select(Report).where(Report.research_id == context.research_id)
            )
            return rep

    report = run_async(_check())
    assert report is not None
    assert "Baterias de Estado Sólido" in report.content_markdown


@given("uma pesquisa concluída com relatório markdown estruturado")
def step_given_research_for_payload(context):
    step_given_research_with_public_callback(context)


@when("o payload de entrega do webhook é gerado")
def step_generate_webhook_payload(context):
    pass


@then('o payload deve conter "research_id", "report_id", "theme", "content_markdown" e "generated_at"')
def step_assert_payload_keys(context):
    async def _inspect():
        async with context.session_factory() as session:
            r = await session.get(Research, context.research_id)
            rep = await session.scalar(select(Report).where(Report.research_id == context.research_id))
            payload = {
                "research_id": str(r.id),
                "report_id": str(rep.id),
                "theme": r.theme,
                "content_markdown": rep.content_markdown,
                "generated_at": rep.generated_at.isoformat(),
            }
            return payload

    payload = run_async(_inspect())
    for key in ["research_id", "report_id", "theme", "content_markdown", "generated_at"]:
        assert key in payload, f"Chave {key} ausente do payload de webhook: {payload}"


@given("uma pesquisa concluída com relatório gravado no banco de dados")
def step_given_completed_research_for_frontend(context):
    step_given_research_with_public_callback(context)


@when('o cliente do frontend envia uma requisição "GET /api/research/<id>"')
def step_get_research_for_frontend(context):
    import app.routers.research as res_router

    async def _call():
        with patch.object(res_router, "AsyncSessionLocal", context.session_factory):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                context.response = await client.get(
                    f"/api/research/{context.research_id}",
                    headers=_auth_headers(),
                )

    run_async(_call())


@then("os dados retornados devem ser consistentes com o relatório gerado")
def step_assert_frontend_consistency(context):
    data = context.response.json()
    assert str(data.get("research_id")) == str(context.research_id)
    assert data.get("status") == ResearchStatus.DONE.value
    assert data.get("theme") == "Baterias de Estado Sólido"
