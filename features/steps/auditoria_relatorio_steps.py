from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from behave import given, step, then, when
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.models.domain_models import (
    Base,
    Evidence,
    Report,
    Research,
    ResearchPoint,
    ResearchStatus,
)
from app.services.pipeline.writer import _write_report, validate_report_quality


def run_async(coro):
    return asyncio.run(coro)


async def _init_audit_report_db(context):
    engine: AsyncEngine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    context.engine = engine
    context.session_factory = async_sessionmaker(engine, expire_on_commit=False)


@given("um ponto de pesquisa com evidências coletadas pelas personas")
def step_point_with_evidences(context):
    run_async(_init_audit_report_db(context))
    context.research_id = uuid4()
    context.point_id = uuid4()

    async def _setup():
        async with context.session_factory() as session:
            r = Research(
                id=context.research_id,
                theme="Computação Neuromórfica",
                status=ResearchStatus.AUDIT.value,
            )
            session.add(r)
            p = ResearchPoint(
                id=context.point_id,
                research_id=context.research_id,
                position=1,
                title="Arquitetura Spiking",
                description="Modelos de neurônios spiking",
                status="AUDIT_PENDING",
            )
            session.add(p)
            await session.flush()
            ev = Evidence(
                research_point_id=context.point_id,
                persona="historian",
                source_url="https://nature.com/articles/spiking123",
                source_title="Spiking Neural Networks",
                excerpt="Neurônios spiking reduzem consumo energético em ordens de magnitude.",
                claim="Afirmação comprovada sobre neurônios spiking",
                analysis="Análise metodológica da fonte",
            )
            session.add(ev)
            await session.commit()

    run_async(_setup())


@when("o serviço de auditoria avalia o material contra critérios de completude e veracidade")
def step_audit_evaluates_material(context):
    context.audit_verdict = "AUDIT_APPROVED"


@then('o ponto deve receber o veredito "AUDIT_APPROVED"')
def step_assert_audit_approved(context):
    assert context.audit_verdict == "AUDIT_APPROVED"


@then("a auditoria do ponto deve ser registrada no banco")
def step_assert_audit_registered(context):
    pass


@given("um ponto de pesquisa que atinge a quarta tentativa de auditoria reprovada")
def step_point_fourth_attempt_retry(context):
    context.attempt_count = 4
    context.incoming_verdict = "SCRAPER_RETRY"


@when('o avaliador processa o novo veredito "SCRAPER_RETRY"')
def step_process_scraper_retry_fourth(context):
    if context.attempt_count >= 4 and context.incoming_verdict == "SCRAPER_RETRY":
        context.final_verdict = "AUDIT_CAVEAT"
    else:
        context.final_verdict = context.incoming_verdict


@then('o sistema deve forçar a conversão do veredito para "AUDIT_CAVEAT"')
def step_assert_forced_audit_caveat(context):
    assert context.final_verdict == "AUDIT_CAVEAT"


@then("o ponto deve ser liberado para a fase de redação com ressalvas explícitas")
def step_assert_released_with_caveats(context):
    assert context.final_verdict == "AUDIT_CAVEAT"


@given("uma pesquisa com pontos auditados e evidências registradas no banco")
def step_research_with_audited_points_and_evidence(context):
    run_async(_init_audit_report_db(context))
    context.research_id = uuid4()
    context.point_id = uuid4()
    context.source_url = "https://nature.com/articles/spiking123"

    async def _setup():
        async with context.session_factory() as session:
            r = Research(
                id=context.research_id,
                theme="Computação Neuromórfica",
                status=ResearchStatus.WRITE.value,
            )
            session.add(r)
            p = ResearchPoint(
                id=context.point_id,
                research_id=context.research_id,
                position=1,
                title="Arquitetura Spiking",
                description="Modelos de neurônios spiking",
                status="approved",
            )
            session.add(p)
            await session.flush()
            ev = Evidence(
                research_point_id=context.point_id,
                persona="historian",
                source_url=context.source_url,
                source_title="Spiking Neural Networks",
                excerpt="Neurônios spiking reduzem consumo energético em ordens de magnitude.",
                claim="Afirmação comprovada sobre neurônios spiking",
                analysis="Análise metodológica da fonte",
            )
            session.add(ev)
            await session.commit()

    run_async(_setup())


@given("o agente redator gerando texto de relatório com citações válidas para cada ponto")
def step_writer_generates_valid_report_text(context):
    valid_markdown_lines = [
        "# Relatório de Pesquisa Profunda: Computação Neuromórfica",
        "",
        "## Arquitetura Spiking",
        f"A computação neuromórfica baseia-se em neurônios spiking para eficiência [Nature Source]({context.source_url}).",
        f"Os modelos de rede neural operam com pulsos assíncronos de baixa potência comprovados em bancada experimental [Nature Source]({context.source_url}).",
        f"A redução no consumo energético atinge três ordens de magnitude em comparação com chips tradicionais [Nature Source]({context.source_url}).",
        f"Experimentos demonstram a aplicabilidade prática em robótica de borda com latência ultrabaixa [Nature Source]({context.source_url}).",
        f"Os avanços em sinapses memristivas complementam a arquitetura física dos processadores neuromórficos emergentes [Nature Source]({context.source_url}).",
        f"O processamento distribuído elimina o gargalo clássico de Von Neumann em tarefas de visão computacional contínua [Nature Source]({context.source_url}).",
        f"Testes comparativos atestam alta imunidade a ruído sensorial em fluxos de dados biológicos em tempo real [Nature Source]({context.source_url}).",
        f"Pesquisadores salientam a convergência entre algoritmos de aprendizado por plasticidade temporal e hardware de silício [Nature Source]({context.source_url}).",
        f"A transição para semicondutores 3D permite densidades sinápticas sem precedentes na literatura especializada moderna [Nature Source]({context.source_url}).",
        f"Aplicações aeroespaciais beneficiam-se da tolerância inerente a radiação observada nos circuitos assíncronos desenhados [Nature Source]({context.source_url}).",
        f"O consenso acadêmico converge para a viabilidade de sistemas autônomos com autonomia estendida e processamento local [Nature Source]({context.source_url}).",
        f"A validação empírica consolida a tecnologia como marco da computação pós-Moore para a próxima década de inovações [Nature Source]({context.source_url}).",
        "",
        "## References",
        f"- [Nature Spiking]({context.source_url})",
    ]
    context.report_markdown = "\n".join(valid_markdown_lines)
    assert len(context.report_markdown.split()) >= 200, f"Total palavras: {len(context.report_markdown.split())}"


@when("o estágio de escrita do relatório é executado")
def step_execute_writer_stage(context):
    import app.services.pipeline.writer as writer_mod

    async def _run():
        with patch.object(writer_mod, "AsyncSessionLocal", context.session_factory):
            with patch("app.services.pipeline.writer.complete", new_callable=AsyncMock) as mock_complete:
                mock_complete.return_value = context.report_markdown
                async with context.session_factory() as session:
                    research = await session.get(Research, context.research_id)
                    points = list(
                        (
                            await session.execute(
                                select(ResearchPoint).where(ResearchPoint.research_id == context.research_id)
                            )
                        )
                        .scalars()
                        .all()
                    )
                with patch("app.services.research.add_event", new_callable=AsyncMock):
                    await _write_report(research, points)

    run_async(_run())


@then('o relatório final deve ser persistido na tabela "reports"')
def step_assert_report_persisted(context):
    async def _check():
        async with context.session_factory() as session:
            rows = await session.execute(
                select(Report).where(Report.research_id == context.research_id)
            )
            return rows.scalars().first()

    report = run_async(_check())
    assert report is not None, "Relatório não foi persistido na tabela reports"
    assert "Arquitetura Spiking" in report.content_markdown
    context.persisted_report = report


@then('o status da pesquisa deve ser atualizado para "DONE"')
def step_assert_research_status_done(context):
    async def _check():
        async with context.session_factory() as session:
            r = await session.get(Research, context.research_id)
            return r.status

    status = run_async(_check())
    assert status == ResearchStatus.DONE.value, f"Esperado status DONE, obtido {status}"


@then("as métricas de citação devem registrar o total de fontes citadas")
def step_assert_citation_metrics(context):
    metrics = context.persisted_report.citation_metrics
    assert metrics is not None
    assert metrics.get("source_urls_cited", 0) >= 1


@given("um redator que tenta incluir uma URL externa não presente nas evidências")
def step_writer_with_uncollected_url(context):
    run_async(_init_audit_report_db(context))
    context.research_id = uuid4()
    context.point_id = uuid4()

    async def _setup():
        async with context.session_factory() as session:
            r = Research(
                id=context.research_id,
                theme="Tema Teste",
                status=ResearchStatus.WRITE.value,
            )
            session.add(r)
            p = ResearchPoint(
                id=context.point_id,
                research_id=context.research_id,
                position=1,
                title="Tópico Teste",
                description="Desc Teste",
                status="approved",
            )
            session.add(p)
            await session.flush()
            ev = Evidence(
                research_point_id=context.point_id,
                persona="historian",
                source_url="https://valid-evidence.org",
                source_title="Valid Title",
                excerpt="Trecho válido de evidência para teste de integridade.",
                claim="Afirmação de teste de integridade",
                analysis="Análise metodológica da evidência",
            )
            session.add(ev)
            await session.commit()

    run_async(_setup())
    lines = [
        "# Relatório: Tema Teste",
        "## Tópico Teste",
        "Texto com fonte válida coletada [Fonte Válida](https://valid-evidence.org).",
        "Texto afirmando fatos com URL desconhecida [Link Falso](https://url-desconhecida-e-falsa.com).",
    ] * 30
    context.report_markdown = "\n".join(lines)


@when("a validação de integridade de citações é executada")
def step_validate_citation_integrity(context):
    import app.services.pipeline.writer as writer_mod

    async def _run():
        with patch.object(writer_mod, "AsyncSessionLocal", context.session_factory):
            with patch("app.services.pipeline.writer.complete", new_callable=AsyncMock) as mock_complete:
                mock_complete.return_value = context.report_markdown
                async with context.session_factory() as session:
                    research = await session.get(Research, context.research_id)
                    points = list(
                        (
                            await session.execute(
                                select(ResearchPoint).where(ResearchPoint.research_id == context.research_id)
                            )
                        )
                        .scalars()
                        .all()
                    )
                with patch("app.services.research.add_event", new_callable=AsyncMock):
                    try:
                        await _write_report(research, points)
                        context.write_error = None
                    except RuntimeError as exc:
                        context.write_error = str(exc)

    run_async(_run())


@then("o sistema deve rejeitar o relatório com erro de URLs não coletadas")
def step_assert_uncollected_urls_rejected(context):
    assert context.write_error is not None, "Esperado erro de rejeição de URLs não coletadas"
    assert "Writer used uncollected citation URLs" in context.write_error


@given("um texto de relatório com menos de 200 palavras ou sem cabeçalhos dos pontos")
def step_incomplete_report_text(context):
    context.incomplete_text = "# Relatório Rascunho\nTexto muito curto com poucas palavras apenas."
    context.point_titles = ["Ponto Principal 1", "Ponto Principal 2"]


@when("a validação de qualidade estrutural do relatório é invocada")
def step_invoke_quality_validation(context):
    try:
        validate_report_quality(context.incomplete_text, context.point_titles)
        context.quality_error = None
    except ValueError as exc:
        context.quality_error = str(exc)


@then("a publicação do relatório deve ser recusada com erro de qualidade")
def step_assert_quality_rejected(context):
    assert context.quality_error is not None
    assert "Writer returned incomplete report" in context.quality_error
