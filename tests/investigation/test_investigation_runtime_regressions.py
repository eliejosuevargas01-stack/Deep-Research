from __future__ import annotations

import asyncio
from uuid import uuid4

import anyio
from fastapi import BackgroundTasks, HTTPException

from app.investigation import service as service_module
from app.investigation.router import investigate_briefing
from app.investigation.service import InvestigationService
from app.models.domain_models import AppSettings, Research, ResearchPoint, ResearchStepResult


async def _noop_save(*args, **kwargs):
    return None


async def _async_result(value):
    return value


async def _session_factory():
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import StaticPool
    from app.models.domain_models import Base
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool, connect_args={"check_same_thread": False})
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


def test_resume_dispatches_only_missing_worker_results(monkeypatch):
    async def run():
        engine, session_factory = await _session_factory()
        research_id, step_id = uuid4(), uuid4()
        async with session_factory() as db:
            db.add(Research(id=research_id, theme="topic", status="SCRAPER"))
            db.add(ResearchPoint(id=step_id, research_id=research_id, position=1, title="point", description="", status="SCRAPER_IN_PROGRESS"))
            db.add(ResearchStepResult(id=uuid4(), research_id=research_id, step_id=step_id, step_title="point", result="saved", used_urls=[], read_urls=[], worker="historian", status="AUDIT_PENDING"))
            db.add(AppSettings(id=1, encrypted_credentials={}, models={"scout": "openai/demo"}, openai_base_url="https://llm.example/v1"))
            await db.commit()

        calls = []

        class Worker:
            def __init__(self, adapter, app_settings_models=None, api_base=None, api_key=None):
                assert api_base == "https://llm.example/v1"
                assert api_key == "test-key"

            async def execute(self, research_id, step_id, step_title, persona, theme):
                calls.append((step_id, step_title, persona))
                return type("Result", (), {"result": "ok", "used_urls": [], "read_urls": [], "success": True})()

        async def resolve(db):
            return "", None, None, {"scout": "openai/demo", "_provider_base_url": "https://llm.example/v1", "_provider_key": "test-key"}

        monkeypatch.setattr(service_module, "PersonaWorker", Worker)
        monkeypatch.setattr(service_module, "_resolve_credentials", resolve)
        monkeypatch.setattr(service_module, "save_step_result", _noop_save)

        await InvestigationService(session_factory, jina_adapter=object()).run_investigation(research_id)
        assert calls == [(step_id, "point", p) for p in ("skeptic", "pragmatist", "futurist")]
        calls.clear()
        async with session_factory() as db:
            db.add_all([ResearchStepResult(id=uuid4(), research_id=research_id, step_id=step_id, step_title="point", result="saved", used_urls=[], read_urls=[], worker=p, status="AUDIT_PENDING") for p in ("skeptic", "pragmatist", "futurist")])
            await db.commit()
        await InvestigationService(session_factory, jina_adapter=object()).run_investigation(research_id)
        assert calls == []

    anyio.run(run)


def test_credentials_resolve_model_provider_key_and_base_url(monkeypatch):
    async def run():
        engine, session_factory = await _session_factory()
        from app.services.crypto import encrypt_secret
        async with session_factory() as db:
            db.add(AppSettings(id=1, encrypted_credentials={"openai": encrypt_secret("test-key")}, models={"scout": "openai/demo"}, openai_base_url="https://llm.example/v1"))
            await db.commit()
            monkeypatch.setattr("app.services.settings.runtime_jina_proxy", lambda db: _async_result((None, None, 20)))
            monkeypatch.setattr("app.services.settings.decrypt_secret", lambda value: "test-key")
            monkeypatch.setattr("app.services.crypto.decrypt_secret", lambda value: "test-key")
            _jina, _proxy, _proxy_key, models = await service_module._resolve_credentials(db)
        assert models["_provider_base_url"] == "https://llm.example/v1"
        assert models["_provider_key"] == "test-key"
        assert models["scout"] == "openai/demo"

    anyio.run(run)


def test_concurrent_dispatch_reservation_returns_conflict(monkeypatch):
    async def run():
        engine, session_factory = await _session_factory()
        research_id, step_id = uuid4(), uuid4()
        async with session_factory() as db:
            db.add(Research(id=research_id, theme="topic", status="SCRAPER"))
            db.add(ResearchPoint(id=step_id, research_id=research_id, position=1, title="point", description="", status="SCRAPER_PENDING"))
            await db.commit()

        async def invoke():
            async with session_factory() as db:
                return await investigate_briefing(research_id, BackgroundTasks(), db=db, principal=object())

        results = await asyncio.gather(invoke(), invoke(), return_exceptions=True)
        assert sum(isinstance(r, HTTPException) and r.status_code == 409 for r in results) == 1

    anyio.run(run)


def test_persona_credentials_follow_each_models_provider(monkeypatch):
    async def run():
        engine, session_factory = await _session_factory()
        from app.services.crypto import encrypt_secret
        async with session_factory() as db:
            db.add(AppSettings(id=1, encrypted_credentials={"openai": encrypt_secret("synthetic-A"), "anthropic": encrypt_secret("synthetic-B")}, models={"scout": "openai/scout", "historian": "openai/hist", "skeptic": "anthropic/skeptic"}, openai_base_url="https://a.example/v1"))
            await db.commit()
            monkeypatch.setattr("app.services.settings.decrypt_secret", lambda value: "synthetic-A" if value.endswith("A") else "synthetic-B")
            monkeypatch.setattr("app.services.crypto.decrypt_secret", lambda value: "synthetic-A" if value.endswith("A") else "synthetic-B")
            credentials = await service_module._resolve_persona_credentials(db, {"scout": "openai/scout", "historian": "openai/hist", "skeptic": "anthropic/skeptic"})
        assert credentials["historian"] == {"api_key": "synthetic-A", "api_base": "https://a.example/v1"}
        assert credentials["skeptic"]["api_key"] == "synthetic-B"
        assert credentials["skeptic"]["api_base"] is None
        assert "synthetic-A" not in str(credentials["skeptic"])

    anyio.run(run)

import httpx

def test_approval_does_not_schedule_run_research(monkeypatch):
    async def run():
        engine, session_factory = await _session_factory()
        research_id = uuid4()
        async with session_factory() as db:
            db.add(Research(id=research_id, theme="topic", status="PENDING_APPROVAL"))
            from app.models.domain_models import AdminSession
            from datetime import datetime, timezone, timedelta
            db.add(AdminSession(id=uuid4(), token_hash="fake", csrf_hash="fake", expires_at=datetime.now(timezone.utc) + timedelta(days=1)))
            await db.commit()

        calls = []
        def mock_schedule(r_id):
            calls.append(r_id)

        monkeypatch.setattr("app.routers.research.schedule", mock_schedule)
        from app.main import app

        def override_get_db():
            return session_factory()

        async def override_require_admin():
            from app.core.security import Principal
            return Principal(session=None)

        app.dependency_overrides["app.db.database.get_db"] = override_get_db
        app.dependency_overrides["app.core.security.require_admin"] = override_require_admin

        from app.db.database import get_db
        from app.core.security import require_admin
        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[require_admin] = override_require_admin

        try:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(
                    f"/api/research/{research_id}/briefing/approve",
                    json={"approved_points": [{"title": f"title{i}", "description": f"description{i}", "dependencies": [], "is_parallelizable": True} for i in range(5)]}
                )
                assert resp.status_code == 200, resp.text
        finally:
            app.dependency_overrides.clear()

        assert calls == [research_id]

    anyio.run(run)

def test_revision_does_not_schedule_run_research(monkeypatch):
    async def run():
        engine, session_factory = await _session_factory()
        research_id = uuid4()
        async with session_factory() as db:
            db.add(Research(id=research_id, theme="topic", status="BRIEFING", briefing_draft={"edit_note": "test", "points": [{"title": "title", "description": "desc", "dependencies": [], "is_parallelizable": True}]}))
            await db.commit()

        calls = []
        def mock_schedule(r_id):
            calls.append(r_id)

        monkeypatch.setattr("app.routers.research.schedule", mock_schedule)

        async def mock_scout(*args, **kwargs):
            return [{"title": f"title{i}", "description": f"desc{i}", "dependencies": [], "is_parallelizable": True} for i in range(5)]

        monkeypatch.setattr("app.routers.research.scout", mock_scout)

        from app.routers.research import run_revision

        monkeypatch.setattr("app.routers.research.AsyncSessionLocal", session_factory)

        await run_revision(research_id)

        assert calls == []

    anyio.run(run)
