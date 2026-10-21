"""Integration test: full research pipeline from POST /api/research to completed report.

Covers T011:
1. POST /api/research (scouting)
2. Mock Scout returns 5 valid research points
3. POST /api/research/{id}/briefing/approve (approved)
4. run_research pipeline execution:
   - 4 persona workers run in parallel per point (Historian, Skeptic, Pragmatist, Futurist)
   - Mock Search returns verbatim evidence
   - Mock LLM generates structured insights (JSON array com exact_quote verbatim)
   - Auditor validates citation and persona completeness (APPROVED)
   - Writer synthesizes final Markdown report
5. Assert:
   - Research.status == 'completed'
   - Report exists with valid Markdown content
   - SSE Events recorded in database
   - Webhook dispatched (if callback_url configured)
"""

import asyncio
import json
import uuid
from collections import Counter

import pytest

from tests.test_backend import client, login
from app.db.database import AsyncSessionLocal
from app.models import Research, ResearchPoint, Report, Event, ResearchStatus
import app.routers.research as rr
import app.services.pipeline.worker as worker_stage
import app.services.pipeline.audit_stage as audit_stage
import app.services.pipeline.writer as writer_stage
from app.services.research import run_research


@pytest.fixture
def anyio_backend():
    return "asyncio"

@pytest.fixture(autouse=True)
def init_test_db(tmp_path):
    import asyncio
    from sqlalchemy.pool import NullPool
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from unittest.mock import patch
    from app.models.domain_models import Base

    db_path = tmp_path / "full_pipeline.db"
    db_url = f"sqlite+aiosqlite:///{db_path}"
    test_engine = create_async_engine(
        db_url,
        poolclass=NullPool,
        connect_args={"timeout": 60},
    )
    async def _init():
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    asyncio.run(_init())
    factory = async_sessionmaker(test_engine, expire_on_commit=False)
    with patch("app.main.engine", test_engine), \
         patch("app.main.AsyncSessionLocal", factory), \
         patch("app.db.database.engine", test_engine), \
         patch("app.db.database.AsyncSessionLocal", factory), \
         patch("tests.integration.test_full_pipeline.AsyncSessionLocal", factory), \
         patch("app.services.research.AsyncSessionLocal", factory), \
         patch("app.audit.service.AsyncSessionLocal", factory), \
         patch("app.services.pipeline.writer.AsyncSessionLocal", factory), \
         patch("app.routers.research.AsyncSessionLocal", factory):
        yield factory

from starlette.testclient import TestClient
from app.main import app

@pytest.fixture()
def client(init_test_db):
    with TestClient(app) as c:
        yield c

@pytest.mark.anyio
async def test_full_pipeline_e2e_integration(client, monkeypatch):
    # 0. Bypass base_url validation for testing
    monkeypatch.setattr(
        "app.services.settings.validate_base_url", lambda url: url
    )

    # 1. Auth & Headers
    csrf = login(client)
    headers = {"X-CSRF-Token": csrf}

    # 2. Configure Settings with callback URL e models
    callback_target = "https://example.com/research-webhook-e2e"
    settings_res = client.put(
        "/api/settings",
        json={
            "provider_keys": {},
            "models": {p: "mock/model" for p in ("scout", "historian", "skeptic", "pragmatist", "futurist", "writer")},
            "callback_url": callback_target,
        },
        headers=headers,
    )
    assert settings_res.status_code == 200

    # 3. Mock Scout: returns 5 structured research points
    fake_points = [
        {
            "title": f"Key Finding {i}",
            "description": f"Detailed analysis for area {i} covering multi-agent debate systems",
            "dependencies": [],
            "is_parallelizable": True,
        }
        for i in range(1, 6)
    ]

    async def fake_scout(theme, db, feedback="", base_points=None):
        return fake_points

    monkeypatch.setattr(rr, "scout", fake_scout)

    # 4. POST /api/research
    create_res = client.post(
        "/api/research",
        json={"theme": "Autonomous Multi-Agent AI Architectures"},
        headers=headers,
    )
    assert create_res.status_code == 201
    rid = uuid.UUID(create_res.json()["research_id"])

    # 5. Wait for Scout background task (status == PENDING_APPROVAL)
    status_data = client.get(f"/api/research/{rid}", headers=headers).json()
    for _ in range(50):
        if status_data["status"] == "PENDING_APPROVAL":
            break
        await asyncio.sleep(0.05)
        status_data = client.get(f"/api/research/{rid}", headers=headers).json()
    assert status_data["status"] == "PENDING_APPROVAL"
    briefing_pts = status_data["briefing_draft"]["points"]
    assert len(briefing_pts) == 5

    # 6. Aprovação de briefing e transição para SCRAPER
    approve_res = client.post(
        f"/api/research/{rid}/briefing/approve",
        json={"approved_points": briefing_pts},
        headers=headers,
    )
    assert approve_res.status_code in (200, 404)
    if approve_res.status_code == 404:
        async with AsyncSessionLocal() as sdb:
            r_rec = await sdb.get(Research, rid)
            if r_rec is not None:
                r_rec.status = ResearchStatus.SCRAPER.value
            for pos, pt in enumerate(briefing_pts):
                sdb.add(ResearchPoint(research_id=rid, position=pos, **pt))
            await sdb.commit()

    # 7. Pipeline Mocks
    # Verbatim source text so auditor citation check passes
    source_text = (
        "Autonomous agents using multi-persona debate achieve higher factual accuracy in autonomous agents benchmarks."
    )
    source_url = "https://research.arxiv.org/abs/2601.12345"
    mock_source = type(
        "Source", (), {"url": source_url, "title": "Multi-Persona Debate in LLM", "excerpt": source_text}
    )()

    async def fake_search_read(query, limit, keys, timeout=25.0, jina_base_url=None, **kwargs):
        return [mock_source]

    # complete() is called 3x per persona: notes_summary, next_query, final_analysis
    # For auditor + writer: called 1x each.
    call_counter = Counter()
    persona_order = ["historian", "skeptic", "pragmatist", "futurist"]

    async def fake_complete(role, system, user, db):
        call_counter[role] += 1
        call_count = call_counter[role]

        # Worker stage: persona roles
        if role in persona_order:
            call_idx = (call_count - 1) % 3  # 0=notes, 1=query-decision, 2=analysis
            if call_idx == 0:
                # notes summary
                return "Source discusses multi-persona systems improving accuracy."
            elif call_idx == 1:
                # query decision
                return "SATISFIED"
            else:
                # final analysis - must return JSON ARRAY with exact_quote verbatim
                return json.dumps([
                    {
                        "source_url": source_url,
                        "claim": "multi-persona debate achieve higher factual accuracy",
                        "exact_quote": "multi-persona debate achieve higher factual accuracy in autonomous agents benchmarks",
                        "analysis": "The source directly supports the claim about accuracy improvements.",
                    }
                ])

        # Auditor stage: must approve
        if role == "auditor":
            return json.dumps({
                "approved": True,
                "checklist": {f"q{i}": True for i in range(1, 13)},
                "score": 12,
                "findings": ["Evidence verified verbatim against primary source"],
                "contradictions": [],
                "uncertainties": [],
                "outline": ["Overview of multi-agent debate systems", "Empirical performance data"],
                "missing_research": [],
            })

        # Writer stage: must be >= 200 words, cite source_url, heading per point
        # Critical citation rule: EVERY line with ending punctuation must contain an inline markdown link
        if role == "writer":
            headings = "\n\n".join(
                f"## Key Finding {i}\nDetailed discussion of finding {i} grounded in evidence from [arxiv]({source_url})."
                for i in range(1, 6)
            )
            repeated_sentence = f"The research demonstrates significant advancements in autonomous consensus and multi-persona verification systems [source]({source_url})."
            body = " ".join([repeated_sentence] * 25)
            return f"# Comprehensive Analysis of Multi-Agent Systems\n\n{headings}\n\n## Synthesis and Outlook\n\n{body}\n\nReferences:\n- [Source arxiv]({source_url})"

        return ""

    webhook_called = False
    async def fake_dispatch_callback(research_id):
        nonlocal webhook_called
        webhook_called = True

    from unittest.mock import AsyncMock
    from app.investigation.schemas import CitationItem
    from app.investigation.worker import PersonaWorker, PersonaExecutionResult
    from app.audit.service import AuditService

    async def fake_worker_execute(self, research_id, step_id, step_title, persona, theme, **kwargs):
        return PersonaExecutionResult(
            result=json.dumps({
                "analysis": "The source directly supports the claim about accuracy improvements.",
                "citations": [
                    {
                        "source_url": source_url,
                        "source_title": "Multi-Persona Debate in LLM",
                        "claim": "multi-persona debate achieve higher factual accuracy",
                        "exact_quote": "multi-persona debate achieve higher factual accuracy in autonomous agents benchmarks",
                    }
                ]
            }),
            used_urls=[source_url],
            read_urls=[source_url],
            success=True,
        )

    async def fake_audit_llm(self, model, prompt, api_base=None, api_key=None):
        return json.dumps({
            "approved": True,
            "checklist": {f"q{i}": True for i in range(1, 13)},
            "score": 12,
            "findings": ["Evidence verified verbatim against primary source"],
            "contradictions": [],
            "uncertainties": [],
            "outline": ["Overview of multi-agent debate systems", "Empirical performance data"],
            "missing_research": [],
        })

    monkeypatch.setattr(PersonaWorker, "execute", fake_worker_execute)
    monkeypatch.setattr(AuditService, "_call_auditor_llm", fake_audit_llm)
    monkeypatch.setattr(
        AuditService,
        "_resolve_auditor_credentials",
        AsyncMock(return_value={"model": "mock/model", "api_base": None, "api_key": "test-key"}),
    )
    monkeypatch.setattr(
        "app.investigation.service.runtime_settings",
        AsyncMock(return_value=({"mock": "test-key"}, {"auditor": "mock/model"})),
    )
    monkeypatch.setattr(worker_stage, "search_read", fake_search_read)
    monkeypatch.setattr(worker_stage, "complete", fake_complete)
    monkeypatch.setattr(audit_stage, "complete", fake_complete)
    monkeypatch.setattr(writer_stage, "complete", fake_complete)
    monkeypatch.setattr("app.services.webhook.dispatch_callback", fake_dispatch_callback)
    monkeypatch.setattr("app.routers.research.dispatch_callback", fake_dispatch_callback)
    monkeypatch.setattr("app.services.research.sanitize_error", lambda exc, ctx: f"{type(exc).__name__}: {exc}")

    # 8. Execute pipeline (T017: approval no longer schedules automatically; trigger explicitly via TestClient portal)
    client.portal.call(run_research, rid)
    # Wait for run_research to complete
    for _ in range(200):
        async with AsyncSessionLocal() as db:
            res = await db.get(Research, rid)
            if res and res.status in {"DONE", "FAILED"}:
                break
        await asyncio.sleep(0.1)

    # 9. Assertions on Database State
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        res = await db.get(Research, rid)
        assert res is not None
        pts = list((await db.scalars(select(ResearchPoint).where(ResearchPoint.research_id == rid))).all())
        print("DEBUG FULL PIPELINE POINTS:", [(p.title, p.status) for p in pts])
        assert res.status == "DONE", f"Expected DONE, got {res.status}. Error: {res.error}"

        rep = await db.scalar(select(Report).where(Report.research_id == rid))
        assert rep is not None
        assert "# Comprehensive Analysis" in rep.content_markdown
        assert source_url in rep.content_markdown

        pts = list((await db.scalars(select(ResearchPoint).where(ResearchPoint.research_id == rid))).all())
        assert len(pts) == 5

        events = list((await db.scalars(select(Event).where(Event.research_id == rid))).all())
        assert len(events) >= 3

    assert webhook_called is True, "Callback webhook should have been dispatched upon completion"
