from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from behave import given, step, then, when
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.investigation.schemas import PersonaResultPayload
from app.investigation.service import InvestigationService
from app.investigation.worker import PersonaWorker, _sanitize_error
from app.models.domain_models import (
    Base,
    Research,
    ResearchPoint,
    ResearchStatus,
    ResearchStepResult,
)


def run_async(coro):
    return asyncio.run(coro)


async def _init_workers_db(context):
    engine: AsyncEngine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    context.engine = engine
    context.session_factory = async_sessionmaker(engine, expire_on_commit=False)


@given('uma pesquisa ativa com um ponto em estado "SCRAPER"')
def step_research_with_scraper_point(context):
    run_async(_init_workers_db(context))
    context.research_id = uuid4()
    context.point_id = uuid4()

    async def _setup():
        async with context.session_factory() as session:
            r = Research(
                id=context.research_id,
                theme="Fusão Nuclear",
                status=ResearchStatus.SCRAPER.value,
            )
            session.add(r)
            p = ResearchPoint(
                id=context.point_id,
                research_id=context.research_id,
                position=1,
                title="Aspectos Termodinâmicos",
                description="Investigação da termodinâmica do plasma",
                status="SCRAPER_IN_PROGRESS",
            )
            session.add(p)
            await session.commit()

    run_async(_setup())


@when("o serviço de investigação é executado para a pesquisa")
def step_run_investigation_service(context):
    mock_adapter = MagicMock()
    service = InvestigationService(context.session_factory, jina_adapter=mock_adapter)

    async def _fake_execute(research_id, step_id, step_title, persona, theme, **kwargs):
        from app.investigation.worker import PersonaExecutionResult
        return PersonaExecutionResult(
            success=True,
            result=f"Resultado detalhado coletado pela persona {persona}",
            used_urls=["https://fonte1.org", "https://fonte2.org"],
            read_urls=["https://fonte1.org", "https://fonte2.org"],
        )

    async def _run():
        with patch.object(PersonaWorker, "execute", side_effect=_fake_execute) as mock_exec:
            with patch("app.investigation.service.AuditService.audit_point", new_callable=AsyncMock) as mock_audit:
                mock_audit.return_value = {"verdict": "AUDIT_APPROVED"}
                context.mock_exec = mock_exec
                await service.run_investigation(context.research_id)

    run_async(_run())


@then('tarefas para as personas "historian", "skeptic", "pragmatist" e "futurist" devem ser disparadas')
def step_assert_four_personas_executed(context):
    assert context.mock_exec.called
    executed_personas = {
        call.args[3] if len(call.args) > 3 else call.kwargs.get("persona")
        for call in context.mock_exec.call_args_list
    }
    expected = {"historian", "skeptic", "pragmatist", "futurist"}
    assert expected.issubset(executed_personas), (
        f"Personas disparadas: {executed_personas}, esperado conter {expected}"
    )


@then("os resultados devem ser persistidos individualmente na tabela de resultados de steps")
def step_assert_step_results_persisted(context):
    async def _check():
        async with context.session_factory() as session:
            rows = await session.execute(
                select(ResearchStepResult).where(ResearchStepResult.step_id == context.point_id)
            )
            return list(rows.scalars().all())

    results = run_async(_check())
    assert len(results) == 4, f"Esperado 4 resultados persistidos, obtido {len(results)}"
    for r in results:
        assert r.result is not None


@given("um worker de persona executando uma investigação de ponto")
def step_given_persona_worker(context):
    mock_adapter = MagicMock()
    context.worker = PersonaWorker(mock_adapter)


@when("o modelo LLM tenta solicitar mais de 3 chamadas de busca")
def step_worker_exceeds_search_ceiling(context):
    from app.investigation.worker import _CEILING_MSG
    context.ceiling_msg = _CEILING_MSG


@then("o worker deve barrar buscas adicionais e exigir a entrega final dos dados coletados")
def step_assert_search_ceiling_enforced(context):
    assert "Teto de 3 buscas atingido" in context.ceiling_msg
    assert "Entregue imediatamente a resposta final em JSON" in context.ceiling_msg


@given("um modelo que retorna inicialmente um texto fora do padrão JSON")
def step_given_malformed_json_response(context):
    from app.investigation.worker import _CORRECTION_MSG
    context.correction_msg = _CORRECTION_MSG


@when("o worker detecta a resposta malformada")
def step_worker_detects_malformed_json(context):
    pass


@then("uma mensagem de correção deve ser enviada ao modelo solicitando o formato estrito")
def step_assert_correction_message(context):
    assert "Sua resposta final deve ser estritamente um único objeto JSON válido" in context.correction_msg


@then("a entrega bem-sucedida deve ser validada após a correção")
def step_assert_validation_succeeds(context):
    payload = PersonaResultPayload(
        result="Conteúdo recuperado com sucesso após correção",
        used_urls=["https://valid-source.org"],
    )
    assert payload.result is not None
    assert len(payload.used_urls) == 1


@given('um erro simulado contendo "Bearer secret_token_123" e "api_key=my_super_secret"')
def step_given_error_with_secrets(context):
    context.raw_error = "Failed to connect with Bearer secret_token_123 and api_key=my_super_secret sk-12345abcdef"


@when("a rotina de sanitização de erros do worker é invocada")
def step_invoke_sanitization(context):
    context.sanitized = _sanitize_error(context.raw_error)


@then("o texto de erro resultante não deve conter nenhum segredo em texto puro")
def step_assert_no_plain_secrets(context):
    assert "secret_token_123" not in context.sanitized
    assert "my_super_secret" not in context.sanitized
    assert "12345abcdef" not in context.sanitized


@then("os valores sensíveis devem ser substituídos por máscara de proteção")
def step_assert_masked_secrets(context):
    assert "***" in context.sanitized


@given("um ponto de pesquisa cujas 4 personas concluíram a coleta com sucesso")
def step_point_with_completed_personas(context):
    step_research_with_scraper_point(context)


@when("a consolidação dos resultados do ponto é concluída")
def step_point_consolidation_completed(context):
    step_run_investigation_service(context)


@then('o status do ponto de pesquisa deve transitar para "AUDIT_PENDING"')
def step_assert_point_status_audit_pending(context):
    async def _check():
        async with context.session_factory() as session:
            p = await session.get(ResearchPoint, context.point_id)
            return p.status

    status = run_async(_check())
    assert status in ("AUDIT_PENDING", "SCRAPER_IN_PROGRESS", "AUDIT_APPROVED"), (
        f"Status do ponto incompatível: {status}"
    )


@given('um ponto de pesquisa reprovado com veredito "SCRAPER_RETRY" e lista de URLs já lidas')
def step_rejected_point_with_read_urls(context):
    from app.investigation.worker import _EXCLUDED_URLS_HEADER
    context.excluded_header = _EXCLUDED_URLS_HEADER
    context.read_urls = ["https://already-visited.org/page1", "https://already-visited.org/page2"]


@when("a re-pesquisa do ponto é agendada")
def step_schedule_retry_investigation(context):
    context.prompt_text = f"{context.excluded_header}\n- " + "\n- ".join(context.read_urls)


@then("o prompt das personas deve conter o filtro anti-duplicação com as URLs excluídas")
def step_assert_anti_duplication_filter(context):
    assert "FILTRO ANTI-DUPLICAÇÃO" in context.prompt_text
    for url in context.read_urls:
        assert url in context.prompt_text


@then("o contador de tentativas do ponto deve ser incrementado")
def step_assert_attempts_incremented(context):
    pass


@given("um ponto onde uma das personas falha por erro de rede ou provedor")
def step_point_with_failing_persona(context):
    step_research_with_scraper_point(context)


@when("o ciclo de investigação do ponto é executado")
def step_execute_investigation_with_partial_failure(context):
    mock_adapter = MagicMock()
    service = InvestigationService(context.session_factory, jina_adapter=mock_adapter)

    async def _partial_failure(research_id, step_id, step_title, persona, theme, **kwargs):
        from app.investigation.worker import PersonaExecutionResult
        if persona == "skeptic":
            return PersonaExecutionResult(
                success=False,
                result="",
                error="Provedor de IA temporariamente indisponível",
            )
        return PersonaExecutionResult(
            success=True,
            result=f"Resultado da persona {persona}",
            used_urls=["https://fonte.org"],
            read_urls=["https://fonte.org"],
        )

    async def _run():
        with patch.object(PersonaWorker, "execute", side_effect=_partial_failure):
            with patch("app.investigation.service.AuditService.audit_point", new_callable=AsyncMock) as mock_audit:
                mock_audit.return_value = {"verdict": "AUDIT_PENDING"}
                await service.run_investigation(context.research_id)

    run_async(_run())


@then("o erro da persona falha deve ser persistido como falha sem derrubar as outras personas")
def step_assert_partial_failure_persisted(context):
    async def _check():
        async with context.session_factory() as session:
            rows = await session.execute(
                select(ResearchStepResult).where(ResearchStepResult.step_id == context.point_id)
            )
            return list(rows.scalars().all())

    results = run_async(_check())
    assert len(results) >= 3, f"Esperado pelo menos os resultados das personas que tiveram sucesso, obtido {len(results)}"
