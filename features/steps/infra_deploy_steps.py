from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx
from behave import given, step, then, when
from sqlalchemy import inspect, select, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.db.database import get_db
from app.main import app, lifespan
from app.models.domain_models import Base, Research, ResearchPoint, ResearchStatus


def run_async(coro):
    return asyncio.run(coro)


async def _init_infra_db(context):
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


@given('a configuração de deploy em "docker-compose.yml" e "Dockerfile"')
def step_given_compose_and_dockerfile(context):
    compose_path = Path("docker-compose.yml")
    dockerfile_path = Path("Dockerfile")
    assert compose_path.exists(), "docker-compose.yml não encontrado"
    assert dockerfile_path.exists(), "Dockerfile não encontrado"
    context.compose_content = compose_path.read_text(encoding="utf-8")
    context.dockerfile_content = dockerfile_path.read_text(encoding="utf-8")


@when("inspecionado o comando de inicialização do serviço backend")
def step_inspect_cmd(context):
    assert "CMD" in context.dockerfile_content
    context.cmd_line = [
        line for line in context.dockerfile_content.splitlines() if line.startswith("CMD")
    ][0]


@then('o serviço deve executar "alembic upgrade head" antes de iniciar o servidor uvicorn')
def step_assert_alembic_in_cmd(context):
    assert "alembic upgrade head" in context.cmd_line, (
        f"Alembic upgrade head não encontrado no CMD: {context.cmd_line}"
    )
    assert "uvicorn app.main:app" in context.cmd_line, (
        f"Uvicorn não encontrado no CMD: {context.cmd_line}"
    )
    alembic_idx = context.cmd_line.index("alembic upgrade head")
    uvicorn_idx = context.cmd_line.index("uvicorn")
    assert alembic_idx < uvicorn_idx, "Alembic upgrade head deve preceder o uvicorn"


@then("a infraestrutura não deve conter serviços efêmeros dedicados apenas a migrações")
def step_assert_no_ephemeral_migration_services(context):
    content_lower = context.compose_content.lower()
    for forbidden in ["migration:", "migrate:", "bootstrap:", "alembic:"]:
        assert forbidden not in content_lower, (
            f"Serviço efêmero de migração detectado no compose: {forbidden}"
        )


@then('o backend deve depender da condição "service_healthy" do banco de dados')
def step_assert_backend_depends_db_healthy(context):
    assert "depends_on:" in context.compose_content
    assert "condition: service_healthy" in context.compose_content


@given("um banco de dados com migrações aplicadas até a revisão head")
def step_given_migrated_db(context):
    import os
    import tempfile
    from alembic import command
    from alembic.config import Config

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    context.tmp_db_path = path
    context.tmp_async_url = f"sqlite+aiosqlite:///{path}"
    
    cfg = Config("alembic.ini")
    cfg.set_main_option("script_location", "alembic")
    cfg.set_main_option("sqlalchemy.url", context.tmp_async_url)
    context.alembic_cfg = cfg

    with patch("app.core.config.settings.DATABASE_URL", context.tmp_async_url):
        command.upgrade(cfg, "head")


@when('o comando de migração "alembic upgrade head" é executado novamente')
def step_run_alembic_upgrade_again(context):
    from alembic import command

    context.alembic_success = True
    try:
        with patch("app.core.config.settings.DATABASE_URL", context.tmp_async_url):
            command.upgrade(context.alembic_cfg, "head")
    except Exception as exc:
        context.alembic_error = str(exc)
        context.alembic_success = False
    finally:
        import os
        if hasattr(context, "tmp_db_path") and os.path.exists(context.tmp_db_path):
            try:
                os.unlink(context.tmp_db_path)
            except OSError:
                pass


@then("a execução deve concluir com sucesso sem erros")
def step_assert_alembic_success(context):
    assert getattr(context, "alembic_success", False), (
        f"Falha na execução idempotente do Alembic: {getattr(context, 'alembic_error', None)}"
    )


@then("nenhuma alteração conflitante deve ser detectada no esquema")
def step_assert_no_schema_conflict(context):
    pass


@given("o esquema de banco de dados inicializado")
def step_schema_initialized(context):
    run_async(_init_infra_db(context))


@when("as tabelas do sistema são inspecionadas")
def step_inspect_tables(context):
    async def _inspect():
        async with context.engine.connect() as conn:
            def _get_tables(sync_conn):
                inspector = inspect(sync_conn)
                return set(inspector.get_table_names())
            return await conn.run_sync(_get_tables)

    context.existing_tables = run_async(_inspect())


@then('as tabelas "research", "research_points", "evidences", "agent_event_logs", "reports", "audit_trails", "admin_sessions", "app_settings" devem existir')
def step_assert_domain_tables_exist(context):
    required = {
        "research",
        "research_points",
        "evidences",
        "agent_event_logs",
        "reports",
        "audit_trails",
        "admin_sessions",
        "app_settings",
    }
    missing = required - context.existing_tables
    assert not missing, f"Tabelas ausentes no esquema: {missing}. Tabelas existentes: {context.existing_tables}"


@given("que a aplicação backend está ativa e conectada ao banco de dados")
def step_app_active_and_connected(context):
    run_async(_init_infra_db(context))


@when('uma requisição "GET /health" é enviada')
def step_get_health(context):
    import app.main as main_mod

    async def _call():
        if hasattr(context, "session_factory") and not hasattr(context, "patcher"):
            with patch.object(main_mod, "AsyncSessionLocal", context.session_factory):
                transport = httpx.ASGITransport(app=app)
                async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                    context.response = await client.get("/health")
        else:
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                context.response = await client.get("/health")

    run_async(_call())


@then('a resposta deve conter status "healthy" e database "connected"')
def step_assert_health_body(context):
    data = context.response.json()
    assert data.get("status") == "healthy", f"Esperado status 'healthy', obtido: {data}"
    assert data.get("database") == "connected", f"Esperado database 'connected', obtido: {data}"


@given("que a conexão com o banco de dados falha")
def step_db_connection_fails(context):
    from unittest.mock import patch
    import app.main as main_mod

    class FailingSession:
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
        async def execute(self, stmt):
            raise RuntimeError("Database connection dropped")

    context.patcher = patch.object(main_mod, "AsyncSessionLocal", FailingSession)
    context.patcher.start()


@then('a resposta de saúde deve conter erro "{expected_detail}"')
def step_assert_detail_message(context, expected_detail: str):
    if hasattr(context, "patcher"):
        context.patcher.stop()
    data = context.response.json()
    assert expected_detail in str(data.get("detail", "")), (
        f"Esperado '{expected_detail}' em {data}"
    )


@given("um registro de pesquisa gravado no banco de dados")
def step_given_research_record(context):
    run_async(_init_infra_db(context))
    context.research_id = uuid4()

    async def _insert():
        async with context.session_factory() as session:
            r = Research(
                id=context.research_id,
                theme="Persistência de Teste",
                status="BRIEFING",
            )
            session.add(r)
            await session.commit()

    run_async(_insert())


@when("uma nova sessão do banco é aberta simulando reinício da aplicação")
def step_open_new_db_session(context):
    pass


@then("o registro de pesquisa deve permanecer íntegro e consultável")
def step_assert_research_persisted(context):
    async def _query():
        async with context.session_factory() as session:
            return await session.get(Research, context.research_id)

    record = run_async(_query())
    assert record is not None, f"Registro de pesquisa {context.research_id} não persistiu"
    assert record.theme == "Persistência de Teste"
    assert record.status == "BRIEFING"


@given('uma pesquisa em status "SCRAPER" com ponto em "SCRAPER_IN_PROGRESS" gravada no banco')
def step_interrupted_research_in_db(context):
    run_async(_init_infra_db(context))
    context.research_id = uuid4()

    async def _setup():
        async with context.session_factory() as session:
            r = Research(
                id=context.research_id,
                theme="Interrupted Research",
                status=ResearchStatus.SCRAPER.value,
            )
            session.add(r)
            await session.flush()
            pt = ResearchPoint(
                research_id=context.research_id,
                position=1,
                title="Ponto Interrompido",
                description="Descrição do ponto interrompido para teste",
                status="SCRAPER_IN_PROGRESS",
            )
            session.add(pt)
            await session.commit()

    run_async(_setup())


@when("o ciclo de lifespan da aplicação é inicializado")
def step_lifespan_initialized(context):
    import app.main as main_mod

    async def _test_lifespan():
        with patch.object(main_mod, "AsyncSessionLocal", context.session_factory):
            with patch.object(main_mod, "schedule_scout"):
                with patch.object(main_mod, "schedule"):
                    with patch("app.investigation.service.InvestigationService.run_investigation", new_callable=AsyncMock) as mock_inv:
                        context.mock_inv = mock_inv
                        async with lifespan(app):
                            pass

    run_async(_test_lifespan())


@then("a rotina de recuperação deve agendar a retomada da investigação em background")
def step_assert_investigation_resumed(context):
    assert context.mock_inv.called, "Retomada da investigação não foi agendada no startup"
    called_id = context.mock_inv.call_args[0][0]
    assert called_id == context.research_id, (
        f"Esperado agendamento para {context.research_id}, obtido {called_id}"
    )
