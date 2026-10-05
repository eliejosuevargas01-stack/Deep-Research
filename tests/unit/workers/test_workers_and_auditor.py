import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.workers.scout import ScoutWorker
from app.services.workers.personas import HistorianWorker, SkepticWorker, PragmatistWorker, FuturistWorker
from app.services.workers.writer import WriterAgent
from app.services.audit_agent import AuditorAgent, AuditVerdict
from app.services.search import Source


@pytest.fixture
def mock_session():
    return AsyncMock()


@pytest.fixture
def mock_settings():
    s = MagicMock()
    s.search_keys.return_value = {"mock": "key"}
    return s


@pytest.mark.asyncio
async def test_scout_worker(mock_session, mock_settings, monkeypatch):
    worker = ScoutWorker(session=mock_session, settings=mock_settings)
    fake_sources = [Source(url="https://example.com/1", title="Ex 1", excerpt="Some sample text")]
    monkeypatch.setattr(worker, "_search_and_read", AsyncMock(return_value=fake_sources))

    result = await worker.execute(point=None, context={"theme": "AI Agents"})
    assert result.persona == "scout"
    assert len(result.evidences) == 1
    assert result.evidences[0]["url"] == "https://example.com/1"
    assert result.metrics["sources_found"] == 1


@pytest.mark.asyncio
async def test_persona_workers(mock_session, mock_settings, monkeypatch):
    point = MagicMock(id="p-123", title="Topic A")
    fake_sources = [Source(url="https://example.com/2", title="Ex 2", excerpt="Analysis here")]

    for WorkerClass in (HistorianWorker, SkepticWorker, PragmatistWorker, FuturistWorker):
        worker = WorkerClass(session=mock_session, settings=mock_settings)
        monkeypatch.setattr(worker, "_search_and_read", AsyncMock(return_value=fake_sources))
        result = await worker.execute(point=point)
        assert result.point_id == "p-123"
        assert len(result.evidences) == 1
        assert result.persona == worker.persona_name()


@pytest.mark.asyncio
async def test_writer_agent(mock_session, mock_settings):
    writer = WriterAgent(session=mock_session, settings=mock_settings)
    context = {"theme": "Quantum Computing", "points": [{"title": "Qubits", "summary": "Superposition principles"}]}
    result = await writer.execute(point=None, context=context)
    assert result.persona == "writer"
    assert "Quantum Computing" in result.raw_response["markdown"]
    assert "Qubits" in result.raw_response["markdown"]


def test_auditor_agent_verdict():
    auditor = AuditorAgent(max_attempts=3)
    evidences = [
        {"url": "https://example.com/test", "claim": "quantum speedup", "excerpt": "achieved quantum speedup in 2026", "persona": "historian"},
        {"url": "https://example.com/test2", "claim": "error rate", "excerpt": "high error rate remains", "persona": "skeptic"},
        {"url": "https://example.com/test3", "claim": "cost", "excerpt": "cost is high", "persona": "pragmatist"},
        {"url": "https://example.com/test4", "claim": "future", "excerpt": "future scaling expected", "persona": "futurist"},
    ]
    checks = auditor.audit_evidences(evidences)
    assert checks["complete_personas"] is True
    assert checks["supported"] == 4

    verdict, msg = auditor.evaluate_verdict(checks=checks, llm_verdict={"approved": True, "findings": [], "contradictions": [], "uncertainties": [], "outline": []}, attempt=1)
    assert verdict == AuditVerdict.APPROVED
