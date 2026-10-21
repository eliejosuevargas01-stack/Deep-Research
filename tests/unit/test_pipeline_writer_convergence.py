"""T006 author tests: real Writer, synthetic LLM/session boundaries, no DB."""
import json
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Evidence, Report, Research, ResearchPoint
from app.services.pipeline import writer


TITLES = ["Material disponível", "Lacunas da investigação"]
KNOWN_URL = "https://source.example/verified"
LIMITED = (
    "# Relatório limitado\n\n## Material disponível\n"
    "Sem evidências aproveitáveis para este ponto; não é possível concluir.\n\n"
    "## Lacunas da investigação\n"
    "Sem material verificável; conclusões permanecem indeterminadas.\n"
)
FACT = "O estudo mediu redução de custos de 37% em 2025"
CITED = f"O estudo registrou redução de custos de 12% [estudo]({KNOWN_URL})."
# Existing quality minimum must not mask Markdown guardrail assertions.
SUBSTANTIVE = "## Material disponível\n" + (CITED + "\n") * 25
PROPOSAL = "**Proposta didática: organize perguntas de diagnóstico antes de formular conclusões.**"


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def invoke_writer(monkeypatch):
    research = Research(id=uuid.uuid4(), theme="Teste sintético", status="WRITE")
    points = [
        ResearchPoint(id=uuid.uuid4(), research_id=research.id, position=i,
                      title=title, description="Ponto sintético", dependencies=[],
                      status="AUDIT_CAVEAT", audit={"limitations": ["Sem material verificável"]})
        for i, title in enumerate(TITLES, 1)
    ]
    evidence = Evidence(id=uuid.uuid4(), research_point_id=points[0].id,
                        persona="historian", source_url=KNOWN_URL,
                        source_title="Estudo sintético", excerpt="redução de custos de 12%",
                        claim="O estudo registrou redução de custos de 12%",
                        analysis="Material sintético autorizado", version=1)
    session = MagicMock(spec=AsyncSession)
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    session.get = AsyncMock(return_value=research)
    session.commit = AsyncMock()
    monkeypatch.setattr(writer, "AsyncSessionLocal", lambda: session)
    # Event persistence is separate boundary, not Writer implementation.
    from app.services import research as research_service
    monkeypatch.setattr(research_service, "add_event", AsyncMock())
    llm = AsyncMock()
    monkeypatch.setattr(writer, "complete", llm)

    async def invoke(text, *, with_evidence=True):
        rows = [evidence] if with_evidence else []
        session.scalars = AsyncMock(return_value=SimpleNamespace(all=lambda: rows))
        llm.return_value = text
        await writer._write_report(research, points)
        llm.assert_awaited_once()
        assert llm.await_args is not None
        payload = json.loads(llm.await_args.args[2])
        assert {item["point"] for item in payload["audits"]} == set(TITLES)
        assert all(item["status"] == "AUDIT_CAVEAT" for item in payload["audits"])
        assert len(payload["evidence"]) == len(rows)
        reports = [call.args[0] for call in session.add.call_args_list
                   if isinstance(call.args[0], Report)]
        assert len(reports) == 1
        assert reports[0].content_markdown == text
        session.commit.assert_awaited_once()
        return reports[0]

    return invoke


def test_rf506_quality_accepts_short_honest_sections():
    writer.validate_report_quality(LIMITED, TITLES)


def test_rf506_quality_still_requires_every_point_section():
    with pytest.raises(ValueError, match="incomplete report"):
        writer.validate_report_quality(SUBSTANTIVE, TITLES)


@pytest.mark.anyio
async def test_rf506_zero_evidence_conclusive_points(invoke_writer):
    report = await invoke_writer(LIMITED, with_evidence=False)
    assert report.citation_metrics["evidence_records"] == 0
    assert "http" not in report.content_markdown


@pytest.mark.anyio
async def test_rf506_mixed_preserves_cited_facts_and_uncited_limit(invoke_writer):
    text = SUBSTANTIVE + "\n## Lacunas da investigação\nSem evidências aproveitáveis para este ponto.\n"
    report = await invoke_writer(text)
    assert CITED in report.content_markdown
    assert "Sem evidências aproveitáveis" in report.content_markdown


@pytest.mark.anyio
async def test_rf507_bold_nonfactual_proposal_accepted(invoke_writer):
    text = SUBSTANTIVE + "\n" + PROPOSAL + "\n## Lacunas da investigação\n"
    await invoke_writer(text)


@pytest.mark.anyio
@pytest.mark.parametrize("line", [
    FACT + ".",
    "**" + FACT + ".**",
    "- " + FACT + ".",
    "| Medida | Resultado |\n| --- | --- |\n| Redução de custos | 37% em 2025 |",
    "Proposta: " + FACT + ".",
    "Limitação: " + FACT + ".",
    "**Proposta: " + FACT + ".**",
    "**Limitação: " + FACT + ".**",
    FACT + " https://unverified.example/result",
    "| Status | O estudo mediu redução de custos de 37% em 2025 |",
], ids=["prose", "bold", "list", "table", "proposal-label", "limitation-label",
        "bold-proposal-fact", "bold-limitation-fact", "arbitrary-bare-url", "status-table-fact"])
async def test_rf507_uncited_fact_rejected(invoke_writer, line):
    text = SUBSTANTIVE + "\n" + line + "\n## Lacunas da investigação\n"
    with pytest.raises(RuntimeError, match="uncited factual content"):
        await invoke_writer(text)


@pytest.mark.anyio
async def test_rn507_unknown_citation_url_rejected(invoke_writer):
    text = (SUBSTANTIVE + f"\n{FACT} [fonte](https://unverified.example/result).\n"
            "## Lacunas da investigação\n")
    with pytest.raises(RuntimeError, match="uncollected citation URLs"):
        await invoke_writer(text)


@pytest.mark.anyio
async def test_bundle_writer_incorporates_merges(monkeypatch):
    from app.models import InvestigationMerge
    research = Research(id=uuid.uuid4(), theme="Teste com Merge", status="WRITE")
    point = ResearchPoint(
        id=uuid.uuid4(),
        research_id=research.id,
        position=1,
        title=TITLES[0],
        description="Desc",
        status="AUDIT_APPROVED",
    )
    merge_url = "https://merge.example/evidence"
    merge = InvestigationMerge(
        id=uuid.uuid4(),
        research_id=research.id,
        step_id=point.id,
        round=1,
        content={
            "personas": {
                "historian": {
                    "analysis": "Análise do merge",
                    "citations": [
                        {
                            "claim": "Fato do merge comprovado",
                            "exact_quote": "comprovado",
                            "source_url": merge_url,
                            "source_title": "Fonte Merge",
                        }
                    ],
                }
            }
        },
    )

    session = MagicMock(spec=AsyncSession)
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    session.get = AsyncMock(return_value=research)
    session.commit = AsyncMock()

    # Primeiro scalars retorna Evidence vazia, segundo scalars retorna merge
    session.scalars = AsyncMock(side_effect=[
        SimpleNamespace(all=lambda: []),
        SimpleNamespace(all=lambda: [merge]),
    ])
    monkeypatch.setattr(writer, "AsyncSessionLocal", lambda: session)
    from app.services import research as research_service
    monkeypatch.setattr(research_service, "add_event", AsyncMock())

    llm = AsyncMock()
    report_text = f"## {TITLES[0]}\nFato do merge comprovado [merge]({merge_url}).\n"
    llm.return_value = report_text
    monkeypatch.setattr(writer, "complete", llm)

    await writer._write_report(research, [point])

    llm.assert_awaited_once()
    assert llm.await_args is not None
    payload = json.loads(llm.await_args.args[2])
    # Bundle deve conter o item do merge
    assert any(item.get("url") == merge_url for item in payload["evidence"])
    reports = [call.args[0] for call in session.add.call_args_list if isinstance(call.args[0], Report)]
    assert len(reports) == 1
    assert merge_url in reports[0].content_markdown
