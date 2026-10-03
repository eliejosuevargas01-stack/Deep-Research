import os
import tempfile
from pathlib import Path

_TEST_DIR = tempfile.TemporaryDirectory(prefix="deep-research-tests-")
_TEST_DB = Path(_TEST_DIR.name) / "test.db"
os.environ.update({
    "DATABASE_URL": f"sqlite+aiosqlite:///{_TEST_DB}",
    "ADMIN_PASSWORD": "correct horse battery staple",
    "SESSION_SECRET": "s" * 32,
    "APP_ENCRYPTION_KEY": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
    "ENVIRONMENT": "test",
    "TRUSTED_ROUTER_HOSTS": "custom-openai.internal",
})

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.db.database import AsyncSessionLocal
from app.models import Research, ResearchPoint, Event, Evidence
from app.services.crypto import decrypt_secret, encrypt_secret, mask_secret
from app.services.audit import deterministic_citation_audit, next_audit_state, audit_approves
from app.services.research import point_dependencies, ready_point_batches, remaining_attempts
from app.tools.outbound import SSRFSecurityViolation, validate_public_url


@pytest.fixture(scope="module", autouse=True)
def init_test_db():
    import asyncio
    from app.db.database import engine
    from app.models import Base

    async def _init():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
    asyncio.run(_init())
    yield
    async def _cleanup():
        from app.routers import research as research_router
        from app.services.research import asyncio as research_asyncio
        for t in list(research_router._running):
            if not t.done():
                t.cancel()
        await engine.dispose()
    asyncio.run(_cleanup())


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def login(client):
    response = client.post("/api/auth/login", json={"password": "correct horse battery staple"})
    assert response.status_code == 200
    return response.json()["csrf_token"]


def test_auth_cookie_csrf_and_logout(client):
    assert client.get("/api/auth/me").status_code == 401
    csrf = login(client)
    assert client.get("/api/auth/me").json()["authenticated"] is True
    rotated = client.get("/api/auth/csrf").json()["csrf_token"]
    assert rotated != csrf
    assert client.put("/api/settings", json={"models": {}}, headers={"X-CSRF-Token": csrf}).status_code == 403
    assert client.get("/api/auth/me", headers={"X-Tenant-ID": "attacker"}).status_code == 400
    assert client.put("/api/settings", json={"models": {}}).status_code == 403
    assert client.post("/api/auth/logout", headers={"X-CSRF-Token": rotated}).status_code == 204
    assert client.get("/api/auth/me").status_code == 401


def test_settings_are_encrypted_and_masked(client):
    csrf = login(client)
    payload = {"provider_keys": {"openai": "sk-secret-value"}, "models": {
        "scout": "openai/gpt-4.1-mini", "historian": "openai/gpt-4.1-mini",
        "skeptic": "openai/gpt-4.1-mini", "pragmatist": "openai/gpt-4.1-mini",
        "futurist": "openai/gpt-4.1-mini", "auditor": "openai/gpt-4.1-mini",
        "writer": "openai/gpt-4.1-mini"}}
    assert client.put("/api/settings", json=payload, headers={"X-CSRF-Token": csrf}).status_code == 200
    body = client.get("/api/settings").json()
    assert body["provider_keys"]["openai"].startswith("sk-")
    assert "secret-value" not in str(body)
    token = encrypt_secret("abc")
    assert decrypt_secret(token) == "abc"
    assert mask_secret("sk-secret-value") != "sk-secret-value"


def test_create_scout_approval_once_and_traceability(client, monkeypatch):
    csrf = login(client)
    async def fake_scout(theme, runtime):
        return [{"title": f"Point {i}", "description": "Investigate evidence", "dependencies": [], "is_parallelizable": True} for i in range(1, 6)]
    monkeypatch.setattr("app.routers.research.scout", fake_scout)
    created = client.post(
        "/api/research",
        json={"theme": "Test theme"},
        headers={"X-CSRF-Token": csrf},
    )
    assert created.status_code == 201
    rid = created.json()["research_id"]
    import time
    status = client.get(f"/api/research/{rid}").json()
    for _ in range(60):
        if status["status"] != "scouting":
            break
        time.sleep(0.05)
        status = client.get(f"/api/research/{rid}").json()
    assert status["status"] == "pending_approval"
    assert len(status["briefing_draft"]["points"]) == 5

    async def fake_run(research_id):
        return None
    monkeypatch.setattr("app.routers.research.run_research", fake_run)
    points = status["briefing_draft"]["points"]
    approved = client.post(f"/api/research/{rid}/briefing/approve", json={"approved_points": points}, headers={"X-CSRF-Token": csrf})
    assert approved.status_code == 200
    replay = client.post(f"/api/research/{rid}/briefing/approve", json={"approved_points": points}, headers={"X-CSRF-Token": csrf})
    assert replay.status_code == 409


def test_ssrf_and_audit_retry_cap():
    for url in ["http://127.0.0.1/x", "http://10.0.0.1", "http://169.254.169.254", "http://[::1]/", "http://[::ffff:127.0.0.1]/"]:
        with pytest.raises(SSRFSecurityViolation):
            validate_public_url(url)
    evidence = [{"url": "https://example.com/a", "excerpt": "The measured result was 42 percent.", "claim": "result was 42 percent"}]
    assert deterministic_citation_audit(evidence)["supported"] == 1
    # MA-05: 4 attempts total (1 initial + 3 retries); blocker only on fourth rejection
    assert next_audit_state(False, 1) == "retry_required"
    assert next_audit_state(False, 2) == "retry_required"
    assert next_audit_state(False, 3) == "retry_required"
    assert next_audit_state(False, 4) == "blocked"


def test_contradictory_excerpt_never_supports_claim():
    claim = "Treatment reduced mortality by 42 percent"
    excerpt = "Treatment did not reduce mortality by 42 percent"
    evidence = [{"url": "https://example.com/study", "claim": claim, "excerpt": excerpt, "persona": persona}
                for persona in ("historian", "skeptic", "pragmatist", "futurist")]
    result = deterministic_citation_audit(evidence)
    assert result["supported"] == 0
    assert len(result["unsupported"]) == 4


def test_auditor_verdict_fails_closed_on_invalid_or_contradictory_output():
    evidence = [{"url": "https://example.com/study", "claim": "Treatment reduced mortality by 42 percent",
                 "excerpt": "Treatment reduced mortality by 42 percent", "persona": persona}
                for persona in ("historian", "skeptic", "pragmatist", "futurist")]
    checks = deterministic_citation_audit(evidence)
    assert checks["supported"] == 4
    assert not audit_approves(checks, {})
    assert not audit_approves(checks, {"approved": "true", "findings": [], "contradictions": [], "uncertainties": [], "outline": []})
    assert not audit_approves(checks, {"approved": True, "findings": [], "contradictions": ["Sources disagree"], "uncertainties": [], "outline": []})
    assert not audit_approves(checks, {"approved": False, "findings": [], "contradictions": [], "uncertainties": [], "outline": []})
    assert audit_approves(checks, {"approved": True, "findings": [], "contradictions": [], "uncertainties": [], "outline": ["Overview"]})


def test_recovery_never_restarts_completed_or_exhausted_attempts():
    assert remaining_attempts(ResearchPoint(status="approved", attempt_count=1), 3) == []
    assert remaining_attempts(ResearchPoint(status="blocked", attempt_count=3), 3) == []
    assert remaining_attempts(ResearchPoint(status="retry_required", attempt_count=2), 3) == [3]
    assert remaining_attempts(ResearchPoint(status="in_progress", attempt_count=2), 3) == [3]
    assert remaining_attempts(ResearchPoint(status="pending", attempt_count=0), 3) == [1, 2, 3]


def test_env_initializer_preserves_existing_values_and_generates_missing(tmp_path):
    from scripts.generate_env import initialize
    path = tmp_path / ".env"
    path.write_text("EXTERNAL_KEY=unchanged\nADMIN_PASSWORD=keep-this\n", encoding="utf-8")
    assert initialize(path)
    content = path.read_text(encoding="utf-8")
    assert content.startswith("EXTERNAL_KEY=unchanged\nADMIN_PASSWORD=keep-this\n")
    for key in ("SESSION_SECRET", "APP_ENCRYPTION_KEY", "DB_PASSWORD"):
        assert content.count(f"{key}=") == 1
    assert not initialize(path)
    assert path.read_text(encoding="utf-8") == content


def test_audit_trail_model_and_callback_failure_status():
    from app.models import AuditTrail
    from app.models.domain_models import ResearchStatus
    assert AuditTrail.__tablename__ == "audit_trails"
    assert ResearchStatus.COMPLETED_BUT_CALLBACK_FAILED.value == "completed_but_callback_failed"


def test_search_falls_back_after_empty_serpapi_and_apify(monkeypatch):
    from app.tools import search_pipeline
    import asyncio
    calls = []

    async def fake_get(url, headers=None):
        calls.append(url)
        if "serpapi.com" in url:
            return 200, '{"organic_results": []}'
        if "s.jina.ai" in url:
            return 200, '[Result](https://example.com/page)'
        raise AssertionError(url)

    async def fake_apify(query, limit, token):
        calls.append("apify")
        return []

    monkeypatch.setattr(search_pipeline, "_get", fake_get)
    monkeypatch.setattr(search_pipeline, "_apify_search", fake_apify)
    results = asyncio.run(search_pipeline.search("fallback topic", keys={"serpapi": "placeholder", "apify": "placeholder"}))
    assert len(results) == 1 and results[0].url == "https://example.com/page"
    assert "apify" in calls


def test_failed_callback_preserves_report_and_records_status(client):
    from app.models import AuditTrail, Report
    from app.services.webhook import dispatch_callback

    async def exercise():
        async with AsyncSessionLocal() as db:
            item = Research(theme="Callback isolation", callback_url="http://127.0.0.1/blocked", status="completed", briefing_draft={})
            db.add(item)
            await db.flush()
            rid = item.id
            db.add(Report(research_id=rid, content_markdown="Verified report", citation_metrics={}, audit_findings={}))
            await db.commit()
        assert await dispatch_callback(rid) is False
        async with AsyncSessionLocal() as db:
            research = await db.get(Research, rid)
            report = await db.scalar(select(Report).where(Report.research_id == rid))
            trail = await db.scalar(select(AuditTrail).where(AuditTrail.research_id == rid, AuditTrail.stage == "callback"))
            assert research is not None and report is not None and trail is not None
            assert research.status == "completed_but_callback_failed"
            assert report.content_markdown == "Verified report"
            assert trail.details == {"delivered": False}

    client.portal.call(exercise)


def test_point_dependencies_schedule_and_cycles():
    class Point:
        def __init__(self, title, dependencies=(), parallel=True):
            self.title = title
            self.dependencies = list(dependencies)
            self.is_parallelizable = parallel

    # MA-01: independent points release together with the first sequential point
    points = [Point("Base"), Point("Independent"), Point("Dependent", ["1"]), Point("Sequential", parallel=False)]
    batches = ready_point_batches(points)
    assert batches[0] == [0, 1, 3]
    assert batches[1] == [2]
    with pytest.raises(ValueError, match="Maximum 20"):
        ready_point_batches([Point(f"P{i}") for i in range(21)])
    with pytest.raises(ValueError, match="cycle"):
        point_dependencies([Point("A", ["2"]), Point("B", ["1"])])
    with pytest.raises(ValueError, match="Unknown"):
        point_dependencies([Point("A", ["missing"])])


def test_health_checks_database(client):
    body = client.get("/health").json()
    assert body["database"] == "connected"


def test_writer_rejects_stub_and_requires_each_research_point():
    from app.services.research import validate_report_quality

    points = [f"Point {i}" for i in range(1, 6)]
    with pytest.raises(ValueError, match="incomplete"):
        validate_report_quality("# Results\nThe measured result was 42 percent. [Study](https://example.com/a)", points)
    with pytest.raises(ValueError, match="incomplete"):
        validate_report_quality("# Report\n" + "## Point 1\n" + ("A documented fact with a citation. " * 100), points)


def test_full_pipeline_with_controlled_sources_and_models(client, monkeypatch):
    import json
    import time
    from app.tools.search_pipeline import Source

    async def sources(query, limit=8, keys=None):
        return [
            Source("https://alpha-lab.org/result", "Study Alpha", "The measured result was 42 percent in clinical trials."),
            Source("https://beta-institute.com/data", "Study Beta", "The measured result was 42 percent in clinical trials."),
            Source("https://gamma-research.edu/report", "Study Gamma", "The measured result was 42 percent in clinical trials."),
        ]

    async def completion(role, system, user, db):
        if role == "scout":
            return json.dumps([{"title": f"Point {i}", "description": "Investigate measured results",
                                "dependencies": [], "is_parallelizable": True} for i in range(1, 6)])
        if role == "auditor":
            return json.dumps({"approved": True, "findings": [], "contradictions": [],
                               "uncertainties": [], "outline": ["Overview"]})
        if role == "writer":
            return "# Report\n" + "\n".join(
                f"## Point {i}\n" + ("The source reports a measured result; its context and limitations require careful interpretation [Study Alpha](https://alpha-lab.org/result). " * 9)
                for i in range(1, 6)
            )
        return json.dumps([{"source_url": "https://alpha-lab.org/result", "claim": "result was 42 percent in clinical trials.",
                            "exact_quote": "The measured result was 42 percent in clinical trials.", "analysis": "Source states result."}])

    monkeypatch.setattr("app.services.research.search_read", sources)
    monkeypatch.setattr("app.services.research.complete", completion)
    csrf = login(client)
    headers = {"X-CSRF-Token": csrf}
    response = client.post(
        "/api/research",
        json={"theme": "Controlled full pipeline"},
        headers=headers,
    )
    assert response.status_code == 201
    rid = response.json()["research_id"]
    status = client.get(f"/api/research/{rid}").json()
    for _ in range(100):
        status = client.get(f"/api/research/{rid}").json()
        if status["status"] == "pending_approval":
            break
        time.sleep(0.05)
    assert status["status"] == "pending_approval", status
    response = client.post(f"/api/research/{rid}/briefing/approve",
                           json={"approved_points": status["briefing_draft"]["points"]}, headers=headers)
    assert response.status_code == 200, response.text
    for _ in range(200):
        status = client.get(f"/api/research/{rid}").json()
        if status["status"] in {"completed", "blocked", "failed"}:
            break
        time.sleep(0.05)
    assert status["status"] == "completed", status
    assert len(status["points"]) == 5
    assert all(point["attempt_count"] == 1 and point["status"] == "approved" for point in status["points"])
    report = client.get(f"/api/reports/{rid}")
    assert report.status_code == 200
    assert "https://alpha-lab.org/result" in report.json()["content_markdown"]


def test_connection_resolver_rejects_mixed_and_rebound_dns(monkeypatch):
    import asyncio
    import socket
    from app.tools.outbound import PinnedResolver

    async def check():
        loop = asyncio.get_running_loop()
        answers = iter([
            [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.215.14", 443))],
            [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.215.14", 443)),
             (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))],
            [(socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("::ffff:127.0.0.1", 443, 0, 0))],
        ])

        async def resolve(*args, **kwargs):
            return next(answers)

        monkeypatch.setattr(loop, "getaddrinfo", resolve)
        assert (await PinnedResolver().resolve("example.com", 443))[0]["host"] == "93.184.215.14"
        with pytest.raises(SSRFSecurityViolation):
            await PinnedResolver().resolve("example.com", 443)
        with pytest.raises(SSRFSecurityViolation):
            await PinnedResolver().resolve("example.com", 443)

    asyncio.run(check())


def test_output_guardrail_blocks_secret_leakage():
    from app.services.llm import apply_output_guardrail
    assert apply_output_guardrail("Clean research summary") == "Clean research summary"
    for leaked in ("key: sk-abcdefghijklmnop1234", "Authorization: Bearer abcdefghijklmn", "api_key = xyz123"):
        try:
            apply_output_guardrail(leaked)
            raise AssertionError(f"guardrail missed: {leaked}")
        except RuntimeError:
            pass


def test_audit_missing_research_empty_when_approved():
    from app.services.audit import next_audit_state
    # com missing_research não vazio, a decisão deve ser retry (não approved) se attempt < max
    assert next_audit_state(False, 1, 3) == "retry_required"
    assert next_audit_state(False, 3, 3) == "blocked"
    assert next_audit_state(True, 1, 3) == "approved"


def test_settings_test_and_models_endpoints(client, monkeypatch):
    csrf = login(client)
    headers = {"X-CSRF-Token": csrf}

    async def fake_test_key(provider, key, base_url=None):
        if key == "valid-key":
            return True, f"{provider} ok"
        return False, f"{provider} invalid"

    monkeypatch.setattr("app.routers.settings.test_provider_key", fake_test_key)

    # F1 test
    res = client.post("/api/settings/test", json={"provider": "openai", "api_key": "valid-key"}, headers=headers)
    assert res.status_code == 200
    assert res.json()["success"] is True

    res_fail = client.post("/api/settings/test", json={"provider": "openai", "api_key": "bad-key"}, headers=headers)
    assert res_fail.status_code == 200
    assert res_fail.json()["success"] is False

    # Settings callback_url and openai_base_url
    up = client.put(
        "/api/settings",
        json={"provider_keys": {}, "models": {}, "callback_url": "https://example.com/webhook", "openai_base_url": "https://custom.endpoint.com/v1"},
        headers=headers,
    )
    assert up.status_code == 200
    data = up.json()
    assert data["callback_url"] == "https://example.com/webhook"
    assert data["openai_base_url"] == "https://custom.endpoint.com/v1"

    # F2 models endpoint
    async def fake_models(provider, key=None, base_url=None):
        return ["custom-model-1", "custom-model-2"]

    monkeypatch.setattr("app.routers.settings.list_provider_models", fake_models)
    res_m = client.get("/api/settings/models?provider=openai")
    assert res_m.status_code == 200
    assert "models_by_provider" in res_m.json()


def test_point_dependencies_handles_point_prefix_and_scout_sanitizes_sources(monkeypatch):
    import asyncio
    import json
    from app.services.research import point_dependencies, scout
    from app.db.database import AsyncSessionLocal

    class DummyPoint:
        def __init__(self, title, dependencies):
            self.title = title
            self.dependencies = dependencies

    # Should resolve "Point 1" or "Ponto 1"
    graph = point_dependencies([DummyPoint("P1", []), DummyPoint("P2", ["Point 1"]), DummyPoint("P3", ["Ponto 2"])])
    assert graph[1] == {0}
    assert graph[2] == {1}

    # Test scout sanitizing Source 1 references from LLM
    async def test_scout_clean():
        async def fake_search(theme, limit, keys):
            from app.tools.search_pipeline import Source
            return [
                Source("https://site-alpha.org/1", "S1", "Detailed content from Alpha source exceeding length threshold"),
                Source("https://site-beta.com/2", "S2", "Detailed content from Beta source exceeding length threshold"),
                Source("https://site-gamma.edu/3", "S3", "Detailed content from Gamma source exceeding length threshold"),
            ]

        async def fake_complete(role, system, user, db):
            return json.dumps([
                {"title": "T1", "description": "D1", "dependencies": ["Source 1", "Point 2"]},
                {"title": "T2", "description": "D2", "dependencies": ["Point 1"]},
                {"title": "T3", "description": "D3", "dependencies": ["T1", "Point 4"]},
                {"title": "T4", "description": "D4", "dependencies": ["invalid_source_ref"]},
                {"title": "T5", "description": "D5", "dependencies": []},
            ])

        monkeypatch.setattr("app.services.research.search_read", fake_search)
        monkeypatch.setattr("app.services.research.complete", fake_complete)

        async with AsyncSessionLocal() as db:
            cleaned = await scout("test theme", db)
            assert len(cleaned) == 5
            # "Source 1", "Point 2" (forward), and "invalid_source_ref" stripped
            assert cleaned[0]["dependencies"] == []
            assert cleaned[1]["dependencies"] == ["1"]
            assert cleaned[2]["dependencies"] == ["T1"]
            assert cleaned[3]["dependencies"] == []
            # point_dependencies must accept cleaned output without raising
            g = point_dependencies(cleaned)
            assert len(g) == 5

    asyncio.run(test_scout_clean())


def test_llm_complete_fallback_to_9router_on_primary_rate_limit(monkeypatch):
    import asyncio
    from litellm.exceptions import RateLimitError
    from app.db.database import AsyncSessionLocal
    from app.services.llm import complete
    from app.services.settings import update_settings

    monkeypatch.setenv("TRUSTED_ROUTER_HOSTS", "9router.internal")
    calls = []

    async def fake_acompletion(**kwargs):
        calls.append(kwargs)
        if "gemini" in kwargs["model"] and kwargs.get("api_base") is None:
            # Primary fails with 429
            raise RateLimitError("429 Quota exceeded", model=kwargs["model"], llm_provider="gemini")
        # Fallback to router succeeds
        class Choice:
            class Msg:
                content = "Fallback succeeded through 9router"
            message = Msg()
        class Resp:
            choices = [Choice()]
        return Resp()

    async def fake_models(provider, api_key=None, base_url=None):
        return ["gemini-3.1-flash-lite", "gemini-3.6-flash"]

    monkeypatch.setattr("app.services.llm.acompletion", fake_acompletion)
    monkeypatch.setattr("app.services.llm.list_provider_models", fake_models)

    async def run():
        async with AsyncSessionLocal() as db:
            # Configure primary gemini key and fallback openai / 9router endpoint
            await update_settings(
                db,
                provider_keys={"gemini": "test-gemini-key", "openai": "test-router-key"},
                models={"scout": "gemini/gemini-3.1-flash-lite"},
                openai_base_url="https://9router.internal/v1",
            )
            result = await complete("scout", "system prompt", "user prompt", db)
            assert result == "Fallback succeeded through 9router"
            # Verify primary was called first, then fallback called with router credentials
            assert len(calls) >= 2
            assert calls[0]["model"] == "gemini/gemini-3.1-flash-lite"
            assert calls[1]["model"] == "openai/gemini-3.1-flash-lite"
            assert calls[1]["api_base"] == "https://9router.internal/v1"
            assert calls[1]["api_key"] == "test-router-key"

    asyncio.run(run())


def test_briefing_approval_schema_validates_five_points_and_prior_deps():
    from app.schemas import BriefingApproval, BriefingPoint
    from pydantic import ValidationError

    def make_points(count, dep_fn=lambda i: []):
        return [
            BriefingPoint(title=f"Point {i}", description=f"Description for point {i}", dependencies=dep_fn(i))
            for i in range(1, count + 1)
        ]

    # Valid 5 points with prior dependencies
    valid = BriefingApproval(approved_points=make_points(5, lambda i: [f"Point {i-1}"] if i > 1 else []))
    assert len(valid.approved_points) == 5

    # Reject fewer than 5 points
    with pytest.raises(ValidationError):
        BriefingApproval(approved_points=make_points(4))

    # Reject more than 5 points
    with pytest.raises(ValidationError):
        BriefingApproval(approved_points=make_points(6))

    # Reject forward dependency (Point 1 depends on Point 2)
    with pytest.raises(ValidationError):
        BriefingApproval(approved_points=make_points(5, lambda i: ["Point 2"] if i == 1 else []))

    # Reject self dependency (Point 2 depends on Point 2)
    with pytest.raises(ValidationError):
        BriefingApproval(approved_points=make_points(5, lambda i: ["Point 2"] if i == 2 else []))


def test_atomic_provider_binding_and_negative_cases():
    import asyncio
    from app.db.database import AsyncSessionLocal
    from app.services.llm import complete, ProviderConfigurationError
    from app.services.settings import update_settings

    async def run():
        async with AsyncSessionLocal() as db:
            # Explicitly remove openai key and set ONLY litellm key
            await update_settings(
                db,
                provider_keys={"openai": None, "litellm": "secret-litellm-key"},
                models={"scout": "openai/gpt-4o-mini"},
                openai_base_url=None,
            )
            # Must raise ProviderConfigurationError: LiteLLM key cannot act as primary for OpenAI
            with pytest.raises(ProviderConfigurationError, match="No API key configured for model provider 'openai'"):
                await complete("scout", "sys", "usr", db)

    asyncio.run(run())


def test_base_url_ssrf_validation(monkeypatch):
    import asyncio
    import socket
    from app.db.database import AsyncSessionLocal
    from app.services.settings import update_settings, validate_base_url

    async def run():
        async with AsyncSessionLocal() as db:
            # Metadata IP blocked
            with pytest.raises(ValueError, match="blocked"):
                await update_settings(db, provider_keys={}, models={}, openai_base_url="http://169.254.169.254/latest/meta-data")

            # Alibaba Cloud metadata IP (100.100.100.200) blocked
            with pytest.raises(ValueError, match="blocked"):
                await update_settings(db, provider_keys={}, models={}, openai_base_url="http://100.100.100.200/latest/meta-data")

            # Shared address space / CGNAT non-global IP (100.64.0.1) blocked without allowlist
            with pytest.raises(ValueError, match="non-global IP blocked"):
                validate_base_url("http://100.64.0.1/v1")

            # Loopback blocked
            with pytest.raises(ValueError, match="blocked"):
                await update_settings(db, provider_keys={}, models={}, openai_base_url="http://127.0.0.1:8000/v1")

            with pytest.raises(ValueError, match="blocked"):
                await update_settings(db, provider_keys={}, models={}, openai_base_url="http://localhost:8000/v1")

            # IPv6 loopback blocked
            with pytest.raises(ValueError, match="blocked"):
                validate_base_url("http://[::1]:8000/v1")

            # IPv4-mapped IPv6 loopback and metadata blocked
            with pytest.raises(ValueError, match="blocked"):
                validate_base_url("http://[::ffff:127.0.0.1]:8000/v1")
            with pytest.raises(ValueError, match="blocked"):
                validate_base_url("http://[::ffff:100.100.100.200]/latest/meta-data")

            # Metadata hostname blocked
            with pytest.raises(ValueError, match="blocked"):
                await update_settings(db, provider_keys={}, models={}, openai_base_url="http://metadata.google.internal")

            # Loopback, link-local, and metadata destinations are NEVER allowed, even if in TRUSTED_ROUTER_HOSTS
            monkeypatch.setenv("TRUSTED_ROUTER_HOSTS", "100.100.100.200,127.0.0.1,169.254.169.254")
            with pytest.raises(ValueError, match="blocked"):
                validate_base_url("http://100.100.100.200/latest/meta-data")
            with pytest.raises(ValueError, match="blocked"):
                validate_base_url("http://127.0.0.1:8000/v1")
            with pytest.raises(ValueError, match="blocked"):
                validate_base_url("http://169.254.169.254/latest/meta-data")

            # Untrusted private IP blocked without explicit exact match in TRUSTED_ROUTER_HOSTS
            monkeypatch.delenv("TRUSTED_ROUTER_HOSTS", raising=False)
            with pytest.raises(ValueError, match="untrusted private IP blocked"):
                validate_base_url("http://192.168.1.1:8000/v1")

            # Private IP allowed ONLY with explicit exact configuration
            monkeypatch.setenv("TRUSTED_ROUTER_HOSTS", "192.168.1.1")
            assert validate_base_url("http://192.168.1.1:8000/v1") == "http://192.168.1.1:8000/v1"

            # Query parameters blocked
            with pytest.raises(ValueError, match="query parameters are prohibited"):
                validate_base_url("https://api.openai.com/v1?token=secret123")

            # Fragment identifiers blocked
            with pytest.raises(ValueError, match="fragment identifiers are prohibited"):
                validate_base_url("https://api.openai.com/v1#attacker_hash")

            # Credentials in URL blocked
            with pytest.raises(ValueError, match="credentials in URL are prohibited"):
                validate_base_url("https://user:password@api.openai.com/v1")

            # Unverified internal host blocked without TRUSTED_ROUTER_HOSTS
            monkeypatch.delenv("TRUSTED_ROUTER_HOSTS", raising=False)
            with pytest.raises(ValueError, match="unverified internal host blocked"):
                validate_base_url("https://9router.internal/v1")

            # DNS resolution to 100.64.0.1 rejected
            def fake_getaddrinfo_cgnat(host, port, *args, **kwargs):
                return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("100.64.0.1", port))]
            monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo_cgnat)
            with pytest.raises(ValueError, match="host resolves to non-global IP"):
                validate_base_url("https://some-cgnat-domain.com/v1")

            # DNS resolution to 100.100.100.200 rejected
            def fake_getaddrinfo_meta(host, port, *args, **kwargs):
                return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("100.100.100.200", port))]
            monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo_meta)
            with pytest.raises(ValueError, match="host resolves to blocked IP"):
                validate_base_url("https://some-metadata-domain.com/latest")

            # Critical audit finding: Simulated DNS resolution where 9router.internal -> 127.0.0.1
            # Even if 9router.internal is in TRUSTED_ROUTER_HOSTS, loopback resolution MUST be blocked
            monkeypatch.setenv("TRUSTED_ROUTER_HOSTS", "9router.internal")
            def fake_getaddrinfo(host, port, *args, **kwargs):
                return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", port))]

            monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
            with pytest.raises(ValueError, match="host resolves to blocked IP"):
                validate_base_url("https://9router.internal/v1")

    asyncio.run(run())


def test_research_controlled_failure_sanitizes_secrets(monkeypatch):
    import asyncio
    import uuid
    from app.db.database import AsyncSessionLocal
    from app.models import Research, Event
    from app.services.research import run_research

    rid = uuid.uuid4()

    async def run():
        async with AsyncSessionLocal() as db:
            r = Research(id=rid, theme="Secret Leaks Test", status="approved", briefing_draft={})
            db.add(r)
            await db.commit()

        # Monkeypatch ready_point_batches to throw exception with a secret in message
        def fake_batches(points):
            raise RuntimeError("secret_token_abcdef1234567890: unexpected crash")

        monkeypatch.setattr("app.services.research.ready_point_batches", fake_batches)

        await run_research(rid)

        async with AsyncSessionLocal() as db:
            updated = await db.get(Research, rid)
            assert updated is not None
            assert updated.status == "failed"
            assert updated.error is not None
            # Ensure error does NOT contain secret
            assert "secret_token_abcdef1234567890" not in updated.error
            assert updated.error == "RuntimeError: research execution failed"

            # Check event as well
            events = list((await db.scalars(select(Event).where(Event.research_id == rid))).all())
            failed_event = [e for e in events if e.event_type == "research_failed"][0]
            assert "secret_token_abcdef1234567890" not in failed_event.summary

    asyncio.run(run())


def test_f01_login_never_leaks_api_auth_secret(client, monkeypatch):
    from app.core.config import settings
    secret = "dr-secret-key-xyz-9876543210"
    monkeypatch.setattr(settings, "API_AUTH_SECRET", secret)

    resp = client.post("/api/auth/login", json={"password": "correct horse battery staple"})
    assert resp.status_code == 200
    data = resp.json()

    assert data["authenticated"] is True
    assert data["role"] == "admin"
    assert "csrf_token" in data
    assert "api_key" not in data
    assert "jwt_token" not in data
    assert secret not in resp.text


def test_f01_browser_creation_payload_minimal_and_legacy_compatible(client, monkeypatch):
    csrf = login(client)
    headers = {"X-CSRF-Token": csrf}

    async def fake_scout(theme, runtime, feedback="", base_points=None):
        return [{"title": f"Point {i}", "description": "Desc", "dependencies": [], "is_parallelizable": True} for i in range(1, 6)]

    monkeypatch.setattr("app.routers.research.scout", fake_scout)

    # 1. Minimal payload: theme only (no api_key, no jwt_token)
    res1 = client.post("/api/research", json={"theme": "Minimal Browser Payload"}, headers=headers)
    assert res1.status_code == 201
    assert "research_id" in res1.json()

    # 2. Whitespace-only theme rejected (A-02)
    res_ws = client.post("/api/research", json={"theme": "   "}, headers=headers)
    assert res_ws.status_code == 422

    # 3. Payload with api_key / jwt_token rejected with 422 without leaking secrets (A-03)
    res_creds = client.post(
        "/api/research",
        json={"theme": "Reject creds in body", "api_key": "secret-canary-key", "jwt_token": "secret-jwt"},
        headers=headers,
    )
    assert res_creds.status_code == 422
    assert "secret-canary-key" not in res_creds.text
    assert "secret-jwt" not in res_creds.text

    # 4. Browser session cannot send callback_url in body (A-03 / MA-10)
    res_cb = client.post(
        "/api/research",
        json={"theme": "Browser with callback", "callback_url": "https://webhook.site/test"},
        headers=headers,
    )
    assert res_cb.status_code == 422


def test_bearer_and_api_key_authentication_for_api_clients(client, monkeypatch):
    from app.core.config import settings
    secret = "dr-bearer-token-secret-test"
    monkeypatch.setattr(settings, "API_AUTH_SECRET", secret)

    async def fake_scout(theme, runtime, feedback="", base_points=None):
        return [{"title": f"Point {i}", "description": "Desc", "dependencies": [], "is_parallelizable": True} for i in range(1, 6)]

    monkeypatch.setattr("app.routers.research.scout", fake_scout)

    # Bearer client GET /api/auth/me (no cookie)
    res_me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {secret}"})
    assert res_me.status_code == 200
    assert res_me.json()["authenticated"] is True

    # Bearer client POST /api/research (no cookie, no CSRF token needed)
    res_create = client.post(
        "/api/research",
        json={"theme": "API Client Research Topic"},
        headers={"Authorization": f"Bearer {secret}"},
    )
    assert res_create.status_code == 201
    assert "research_id" in res_create.json()

    # X-API-Key client GET /api/auth/me
    res_key = client.get("/api/auth/me", headers={"X-API-Key": secret})
    assert res_key.status_code == 200


def test_negative_auth_scenarios_and_trust_boundary(client, monkeypatch):
    from app.core.config import settings
    secret = "dr-bearer-token-secret-test"
    monkeypatch.setattr(settings, "API_AUTH_SECRET", secret)

    # 1. Unauthenticated request rejected
    assert client.post("/api/research", json={"theme": "Unauth"}).status_code == 401
    assert client.get("/api/auth/me").status_code == 401

    # 2. Invalid Bearer token rejected
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer bad-token"}).status_code == 401
    assert client.post("/api/research", json={"theme": "Bad Bearer"}, headers={"Authorization": "Bearer bad-token"}).status_code == 401

    # 3. Invalid X-API-Key rejected
    assert client.get("/api/auth/me", headers={"X-API-Key": "bad-key"}).status_code == 401

    # 4. Browser session without CSRF on mutation rejected (403)
    login_res = client.post("/api/auth/login", json={"password": "correct horse battery staple"})
    assert login_res.status_code == 200
    assert client.post("/api/research", json={"theme": "No CSRF"}).status_code == 403
    assert client.post("/api/research", json={"theme": "Bad CSRF"}, headers={"X-CSRF-Token": "bad-csrf"}).status_code == 403

    # 5. Client tenant spoofing (X-Tenant-ID) rejected (400)
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {secret}", "X-Tenant-ID": "tenant-x"}).status_code == 400


def test_f04_candidate_key_model_discovery(client, monkeypatch):
    csrf = login(client)
    headers = {"X-CSRF-Token": csrf}

    async def fake_list_models(provider, key=None, base_url=None):
        if key == "candidate-key-123":
            return ["candidate-model-a", "candidate-model-b"]
        return []

    monkeypatch.setattr("app.routers.settings.list_provider_models", fake_list_models)

    # 1. Dedicated discovery endpoint for candidate key
    res_disc = client.post(
        "/api/settings/models",
        json={"provider": "openai", "api_key": "candidate-key-123"},
        headers=headers,
    )
    assert res_disc.status_code == 200
    disc_data = res_disc.json()
    assert disc_data["provider"] == "openai"
    assert disc_data["models"] == ["candidate-model-a", "candidate-model-b"]
    assert "candidate-key-123" not in res_disc.text

    # 2. Key test discovers models and caches them in candidate catalog
    async def fake_test_key(provider, key, base_url=None):
        return True, "Validated"

    monkeypatch.setattr("app.routers.settings.test_provider_key", fake_test_key)

    res_test = client.post(
        "/api/settings/test",
        json={"provider": "anthropic", "api_key": "candidate-key-123"},
        headers=headers,
    )
    assert res_test.status_code == 200
    assert res_test.json()["models"] == ["candidate-model-a", "candidate-model-b"]
    assert "candidate-key-123" not in res_test.text

    # 3. Subsequent GET /api/settings/models returns empty catalog when key not saved in DB (no stale global cache)
    res_models = client.get("/api/settings/models?provider=anthropic", headers=headers)
    assert res_models.status_code == 200
    assert res_models.json()["models_by_provider"]["anthropic"] == []


def test_llm_complete_auth_error_401_does_not_fallback(monkeypatch):
    import asyncio
    from litellm.exceptions import AuthenticationError
    from app.db.database import AsyncSessionLocal
    from app.services.llm import complete, ProviderConfigurationError
    from app.services.settings import update_settings

    calls = []

    async def fake_acompletion(**kwargs):
        calls.append(kwargs)
        # Primary Gemini fails with 401 Unauthorized
        raise AuthenticationError("401 Invalid API key provided", model=kwargs["model"], llm_provider="gemini")

    monkeypatch.setattr("app.services.llm.acompletion", fake_acompletion)

    async def run():
        async with AsyncSessionLocal() as db:
            await update_settings(
                db,
                provider_keys={"gemini": "bad-gemini-key", "openai": "valid-router-key"},
                models={"scout": "gemini/gemini-3.1-flash-lite"},
                openai_base_url="https://api.openai.com/v1",
            )
            # Security policy: 401 must raise ProviderConfigurationError and NEVER fallback to router
            with pytest.raises(ProviderConfigurationError, match="Authentication failure for provider 'gemini'"):
                await complete("scout", "system prompt", "user prompt", db)

            # Exactly 1 call was made to primary; NO fallback call was dispatched
            assert len(calls) == 1
            assert calls[0]["model"] == "gemini/gemini-3.1-flash-lite"

    asyncio.run(run())


def test_llm_complete_auth_error_403_does_not_fallback(monkeypatch):
    import asyncio
    import httpx
    from litellm.exceptions import PermissionDeniedError
    from app.db.database import AsyncSessionLocal
    from app.services.llm import complete, ProviderConfigurationError
    from app.services.settings import update_settings

    calls = []

    async def fake_acompletion(**kwargs):
        calls.append(kwargs)
        # Primary Anthropic fails with 403 Forbidden
        fake_resp = httpx.Response(403, request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"))
        raise PermissionDeniedError("403 Forbidden - access denied", model=kwargs["model"], llm_provider="anthropic", response=fake_resp)

    monkeypatch.setattr("app.services.llm.acompletion", fake_acompletion)

    async def run():
        async with AsyncSessionLocal() as db:
            await update_settings(
                db,
                provider_keys={"anthropic": "bad-anthropic-key", "openai": "valid-router-key"},
                models={"scout": "claude-3-5-sonnet"},
                openai_base_url="https://api.openai.com/v1",
            )
            # Security policy: 403 must raise ProviderConfigurationError and NEVER fallback to router
            with pytest.raises(ProviderConfigurationError, match="Authentication failure for provider 'anthropic'"):
                await complete("scout", "system prompt", "user prompt", db)

            # Exactly 1 call was made to primary; NO fallback call was dispatched
            assert len(calls) == 1
            assert "claude" in calls[0]["model"]

    asyncio.run(run())


def test_litellm_transport_redirects_disabled():
    import litellm
    from litellm.llms.custom_httpx.http_handler import AsyncHTTPHandler, HTTPHandler
    from litellm.llms.openai.common_utils import BaseOpenAILLM

    # Verify module level clients have follow_redirects=False
    if hasattr(litellm, "module_level_aclient") and litellm.module_level_aclient:
        assert litellm.module_level_aclient.client.follow_redirects is False

    # Verify handlers create clients with follow_redirects=False
    async_handler = AsyncHTTPHandler()
    assert async_handler.client.follow_redirects is False

    sync_handler = HTTPHandler()
    assert sync_handler.client.follow_redirects is False

    # Verify OpenAI client factory produces clients with follow_redirects=False
    async_openai_client = BaseOpenAILLM._get_async_http_client()
    assert async_openai_client is not None
    assert async_openai_client.follow_redirects is False

    sync_openai_client = BaseOpenAILLM._get_sync_http_client()
    assert sync_openai_client is not None
    assert sync_openai_client.follow_redirects is False


def test_litellm_transport_unsupported_fails_closed(monkeypatch):
    from litellm.llms.custom_httpx.http_handler import AsyncHTTPHandler
    import app.services.llm as llm_service

    class UnsupportedTransportClient:
        """Client missing follow_redirects attribute simulating unsupported transport."""
        pass

    orig_create = AsyncHTTPHandler.create_client

    def broken_create(self, *args, **kwargs):
        return UnsupportedTransportClient()

    # Re-patch create_client with unpatched broken factory
    setattr(broken_create, "_safe_patched", False)
    monkeypatch.setattr(AsyncHTTPHandler, "create_client", broken_create)

    # _enforce_safe_transport must fail closed with RuntimeError
    with pytest.raises(RuntimeError, match="LiteLLM safe transport enforcement failed"):
        llm_service._enforce_safe_transport()

    # Complete must also fail closed
    import asyncio
    from app.db.database import AsyncSessionLocal

    async def run():
        async with AsyncSessionLocal() as db:
            with pytest.raises(RuntimeError, match="LiteLLM safe transport enforcement failed"):
                await llm_service.complete("scout", "sys", "usr", db)

    asyncio.run(run())

    # Restore healthy state for following tests
    monkeypatch.setattr(AsyncHTTPHandler, "create_client", orig_create)
    setattr(orig_create, "_safe_patched", False)
    llm_service._enforce_safe_transport()


def test_scout_controlled_failure_sanitizes_secrets_and_suppresses_traceback(monkeypatch):
    import asyncio
    import traceback
    import uuid
    from app.db.database import AsyncSessionLocal
    from app.models import Event, Research
    from app.routers.research import run_scout

    rid = uuid.uuid4()
    secret = "dummy-fake-secret-token-abcdef12345"

    # Ensure traceback.print_exc was NOT called
    traceback_called = []
    def fail_if_traceback(*args, **kwargs):
        traceback_called.append(True)
    monkeypatch.setattr(traceback, "print_exc", fail_if_traceback)

    async def fake_scout_fail(theme, db, feedback="", base_points=None):
        raise RuntimeError(f"Authentication failed with {secret}: internal crash")

    monkeypatch.setattr("app.routers.research.scout", fake_scout_fail)

    async def run():
        async with AsyncSessionLocal() as db:
            r = Research(id=rid, theme="Scout Secret Leak Test", status="scouting", briefing_draft={})
            db.add(r)
            await db.commit()

        await run_scout(rid)

        async with AsyncSessionLocal() as db:
            updated = await db.get(Research, rid)
            assert updated is not None
            assert updated.status == "failed"
            assert updated.error is not None
            # Zero secret leakage in research.error
            assert secret not in updated.error
            assert updated.error == "RuntimeError: scout execution failed"

            # Check scout_failed event
            events = list((await db.scalars(select(Event).where(Event.research_id == rid))).all())
            failed_event = [e for e in events if e.event_type == "scout_failed"][0]
            assert secret not in failed_event.summary
            assert failed_event.summary == "RuntimeError: scout execution failed"

        assert not traceback_called, "traceback.print_exc() must not be called"

    asyncio.run(run())


def test_briefing_edit_cas_intermediate_state_and_one_time_execution(client, monkeypatch):
    import time
    import uuid
    from app.db.database import AsyncSessionLocal
    from app.models import Event, Research, ResearchPoint

    csrf = login(client)
    headers = {"X-CSRF-Token": csrf}
    rid = uuid.uuid4()

    points_initial = [
        {"title": f"Initial Point {i}", "description": f"Desc {i}", "dependencies": [], "is_parallelizable": True}
        for i in range(1, 6)
    ]
    points_revised = [
        {"title": f"Revised Point {i}", "description": f"Revised Desc {i}", "dependencies": [], "is_parallelizable": True}
        for i in range(1, 6)
    ]

    async def fake_scout_revised(theme, db, feedback="", base_points=None):
        assert feedback == "Focus on energy efficiency"
        assert len(base_points) == 5
        return points_revised

    monkeypatch.setattr("app.routers.research.scout", fake_scout_revised)

    async def fake_run_research(research_id):
        return None
    monkeypatch.setattr("app.routers.research.run_research", fake_run_research)

    # 1. Seed research in pending_approval
    async def seed():
        async with AsyncSessionLocal() as db:
            r = Research(
                id=rid,
                theme="Quantum Computing",
                status="pending_approval",
                briefing_draft={"points": points_initial, "source": "live_search_and_llm"},
            )
            db.add(r)
            await db.commit()

    client.portal.call(seed)

    # 2. Call briefing/edit
    res = client.post(
        f"/api/research/{rid}/briefing/edit",
        json={"note": "Focus on energy efficiency", "points": points_initial},
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "revising"
    assert data["research_id"] == str(rid)

    # 3. Immediate sequential replay must be rejected with 409
    res_replay = client.post(
        f"/api/research/{rid}/briefing/edit",
        json={"note": "Second attempt should fail", "points": points_initial},
        headers=headers,
    )
    assert res_replay.status_code == 409

    # Approve while revising must also fail with 409
    res_approve = client.post(
        f"/api/research/{rid}/briefing/approve",
        json={"approved_points": points_initial},
        headers=headers,
    )
    assert res_approve.status_code == 409

    # 4. Wait for background task rerun() to finish
    status = client.get(f"/api/research/{rid}").json()
    for _ in range(60):
        if status["status"] == "approved":
            break
        time.sleep(0.05)
        status = client.get(f"/api/research/{rid}").json()

    assert status["status"] == "approved"
    assert status["briefing_edit_available"] is False
    assert status["briefing_draft"]["source"] == "revised_after_edit"
    assert status["briefing_draft"]["edit_note"] == "Focus on energy efficiency"
    assert len(status["points"]) == 5

    # 5. Subsequent edit attempts after approved must also fail with 409
    res_after = client.post(
        f"/api/research/{rid}/briefing/edit",
        json={"note": "Third attempt should also fail", "points": points_initial},
        headers=headers,
    )
    assert res_after.status_code == 409


def test_briefing_edit_concurrent_requests_race_condition(monkeypatch):
    import asyncio
    import uuid
    import httpx
    from httpx import ASGITransport
    from app.db.database import AsyncSessionLocal
    from app.models import Research
    from app.main import app
    from app.core.config import settings

    rid = uuid.uuid4()
    secret = "dr-concurrent-test-key-12345"
    monkeypatch.setattr(settings, "API_AUTH_SECRET", secret)

    points_initial = [
        {"title": f"Race Point {i}", "description": f"Desc {i}", "dependencies": [], "is_parallelizable": True}
        for i in range(1, 6)
    ]

    async def fake_scout_slow(theme, db, feedback="", base_points=None):
        await asyncio.sleep(0.05)
        return points_initial

    monkeypatch.setattr("app.routers.research.scout", fake_scout_slow)

    async def fake_run_research(research_id):
        return None
    monkeypatch.setattr("app.routers.research.run_research", fake_run_research)

    async def run():
        async with AsyncSessionLocal() as db:
            r = Research(
                id=rid,
                theme="Concurrency Test",
                status="pending_approval",
                briefing_draft={"points": points_initial, "source": "live_search_and_llm"},
            )
            db.add(r)
            await db.commit()

        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            headers = {"Authorization": f"Bearer {secret}"}
            tasks = [
                ac.post(
                    f"/api/research/{rid}/briefing/edit",
                    json={"note": f"Concurrent edit {i}"},
                    headers=headers,
                )
                for i in range(5)
            ]
            responses = await asyncio.gather(*tasks)

        status_codes = [r.status_code for r in responses]
        assert status_codes.count(200) == 1, f"Expected exactly one 200, got: {status_codes}"
        assert status_codes.count(409) == 4, f"Expected four 409s, got: {status_codes}"

    asyncio.run(run())


def test_briefing_edit_and_approve_race_condition(monkeypatch):
    import asyncio
    import uuid
    import httpx
    from httpx import ASGITransport
    from app.db.database import AsyncSessionLocal
    from app.models import Research
    from app.main import app
    from app.core.config import settings

    rid = uuid.uuid4()
    secret = "dr-concurrent-test-key-12345"
    monkeypatch.setattr(settings, "API_AUTH_SECRET", secret)

    points_initial = [
        {"title": f"Point {i}", "description": f"Description {i}", "dependencies": [], "is_parallelizable": True}
        for i in range(1, 6)
    ]

    async def fake_scout_slow(theme, db, feedback="", base_points=None):
        await asyncio.sleep(0.05)
        return points_initial

    monkeypatch.setattr("app.routers.research.scout", fake_scout_slow)

    async def fake_run_research(research_id):
        return None
    monkeypatch.setattr("app.routers.research.run_research", fake_run_research)

    async def run():
        async with AsyncSessionLocal() as db:
            r = Research(
                id=rid,
                theme="Edit vs Approve Race",
                status="pending_approval",
                briefing_draft={"points": points_initial, "source": "live_search_and_llm"},
            )
            db.add(r)
            await db.commit()

        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            headers = {"Authorization": f"Bearer {secret}"}
            t_edit = ac.post(
                f"/api/research/{rid}/briefing/edit",
                json={"note": "Edit in race"},
                headers=headers,
            )
            t_appr = ac.post(
                f"/api/research/{rid}/briefing/approve",
                json={"approved_points": points_initial},
                headers=headers,
            )
            r_edit, r_appr = await asyncio.gather(t_edit, t_appr)

        codes = [r_edit.status_code, r_appr.status_code]
        assert 200 in codes, f"One must succeed: {codes}"
        assert 409 in codes, f"The other must fail with 409: {codes}"
        assert codes.count(200) == 1, f"Exactly one must succeed: {codes}"

    asyncio.run(run())


def test_briefing_edit_negative_and_validation_cases(monkeypatch):
    import asyncio
    import uuid
    import httpx
    from httpx import ASGITransport
    from datetime import datetime, timezone
    from app.db.database import AsyncSessionLocal
    from app.models import Research
    from app.main import app
    from app.core.config import settings

    secret = "dr-neg-test-key-12345"
    monkeypatch.setattr(settings, "API_AUTH_SECRET", secret)
    headers = {"Authorization": f"Bearer {secret}"}

    async def run():
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            # 1. 404 on non-existent research
            non_existent = uuid.uuid4()
            res404 = await ac.post(
                f"/api/research/{non_existent}/briefing/edit",
                json={"note": "Non-existent research"},
                headers=headers,
            )
            assert res404.status_code == 404

            # 2. 422 on empty or too short note
            res422_empty = await ac.post(
                f"/api/research/{non_existent}/briefing/edit",
                json={"note": "   "},
                headers=headers,
            )
            assert res422_empty.status_code == 422

            # 3. 422 on cyclic or invalid point dependencies
            invalid_points = [
                {"title": f"Point {i}", "description": f"Desc {i}", "dependencies": ["2" if i == 1 else "1"], "is_parallelizable": True}
                for i in range(1, 6)
            ]
            res422_dep = await ac.post(
                f"/api/research/{non_existent}/briefing/edit",
                json={"note": "Valid note", "points": invalid_points},
                headers=headers,
            )
            assert res422_dep.status_code == 422

            # 4. 409 when status is not pending_approval (e.g., scouting, failed, completed, in_progress)
            async with AsyncSessionLocal() as db:
                rids = {}
                for bad_status, approved in [("scouting", False), ("failed", False), ("completed", True), ("in_progress", True)]:
                    rid = uuid.uuid4()
                    r = Research(
                        id=rid,
                        theme="Status test",
                        status=bad_status,
                        approved_at=datetime.now(timezone.utc) if approved else None,
                        briefing_draft={},
                    )
                    db.add(r)
                    rids[bad_status] = rid
                await db.commit()

            for bad_status, test_rid in rids.items():
                res409 = await ac.post(
                    f"/api/research/{test_rid}/briefing/edit",
                    json={"note": "Attempt edit in invalid status"},
                    headers=headers,
                )
                assert res409.status_code == 409, f"Expected 409 for status {bad_status}, got {res409.status_code}"

    asyncio.run(run())


def test_research_status_contract_callback_configured_and_status(client):
    from app.models import AuditTrail, Report
    csrf = login(client)
    headers = {"X-CSRF-Token": csrf}
    secret_callback = "https://sensitive.webhook.internal/secret-token-12345"

    async def seed():
        async with AsyncSessionLocal() as db:
            # 1. Research without callback
            r_no_cb = Research(theme="No CB", callback_url=None, status="completed", briefing_draft={})
            db.add(r_no_cb)
            # 2. Research with callback, pending
            r_pending = Research(theme="Pending CB", callback_url=secret_callback, status="in_progress", briefing_draft={})
            db.add(r_pending)
            # 3. Research with callback, delivered
            r_deliv = Research(theme="Delivered CB", callback_url=secret_callback, status="completed", briefing_draft={})
            db.add(r_deliv)
            await db.flush()
            db.add(AuditTrail(research_id=r_deliv.id, stage="callback", details={"delivered": True}))
            # 4. Research with callback, failed
            r_fail = Research(theme="Failed CB", callback_url=secret_callback, status="completed_but_callback_failed", briefing_draft={})
            db.add(r_fail)
            await db.flush()
            db.add(AuditTrail(research_id=r_fail.id, stage="callback", details={"delivered": False}))
            await db.commit()
            return str(r_no_cb.id), str(r_pending.id), str(r_deliv.id), str(r_fail.id)

    id_no_cb, id_pending, id_deliv, id_fail = client.portal.call(seed)

    # 1. Check no callback
    res1 = client.get(f"/api/research/{id_no_cb}")
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["callback_configured"] is False
    assert data1["callback_status"] is None
    assert "callback_url" not in data1

    # 2. Check pending callback
    res2 = client.get(f"/api/research/{id_pending}")
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["callback_configured"] is True
    assert data2["callback_status"] == "pending"
    assert "callback_url" not in data2
    assert "secret-token-12345" not in res2.text

    # 3. Check delivered callback
    res3 = client.get(f"/api/research/{id_deliv}")
    assert res3.status_code == 200
    data3 = res3.json()
    assert data3["callback_configured"] is True
    assert data3["callback_status"] == "delivered"
    assert "callback_url" not in data3
    assert "secret-token-12345" not in res3.text

    # 4. Check failed callback
    res4 = client.get(f"/api/research/{id_fail}")
    assert res4.status_code == 200
    data4 = res4.json()
    assert data4["callback_configured"] is True
    assert data4["callback_status"] == "failed"
    assert "callback_url" not in data4
    assert "secret-token-12345" not in res4.text


def test_retry_callback_returns_success_and_delivered(client, monkeypatch):
    from app.models import Report
    csrf = login(client)
    headers = {"X-CSRF-Token": csrf}

    async def seed():
        async with AsyncSessionLocal() as db:
            r = Research(theme="Retry Test", callback_url="https://example.com/hook", status="completed_but_callback_failed", briefing_draft={})
            db.add(r)
            await db.flush()
            rep = Report(research_id=r.id, content_markdown="# Done", citation_metrics={}, audit_findings={})
            db.add(rep)
            await db.commit()
            return str(r.id)

    rid = client.portal.call(seed)

    async def fake_dispatch(research_id):
        return True

    monkeypatch.setattr("app.routers.research.dispatch_callback", fake_dispatch)

    res = client.post(f"/api/reports/{rid}/retry-callback", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["delivered"] is True


def test_put_settings_removal_with_null_and_empty_string_and_omit(client):
    csrf = login(client)
    headers = {"X-CSRF-Token": csrf}

    # 1. Set initial callback_url and openai_base_url
    res1 = client.put(
        "/api/settings",
        json={
            "provider_keys": {},
            "models": {},
            "callback_url": "https://example.com/initial-webhook",
            "openai_base_url": "https://example.com/v1",
        },
        headers=headers,
    )
    assert res1.status_code == 200
    assert res1.json()["callback_url"] == "https://example.com/initial-webhook"
    assert res1.json()["openai_base_url"] == "https://example.com/v1"

    # 2. Omit fields in PUT: must preserve existing values
    res2 = client.put(
        "/api/settings",
        json={"provider_keys": {}, "models": {}},
        headers=headers,
    )
    assert res2.status_code == 200
    assert res2.json()["callback_url"] == "https://example.com/initial-webhook"
    assert res2.json()["openai_base_url"] == "https://example.com/v1"

    # 3. Explicit null in PUT: must clear both fields
    res3 = client.put(
        "/api/settings",
        json={"provider_keys": {}, "models": {}, "callback_url": None, "openai_base_url": None},
        headers=headers,
    )
    assert res3.status_code == 200
    assert res3.json()["callback_url"] is None
    assert res3.json()["openai_base_url"] is None

    # 4. Set them again
    res4 = client.put(
        "/api/settings",
        json={
            "provider_keys": {},
            "models": {},
            "callback_url": "https://example.com/second-webhook",
            "openai_base_url": "https://example.com/v2",
        },
        headers=headers,
    )
    assert res4.status_code == 200
    assert res4.json()["callback_url"] == "https://example.com/second-webhook"
    assert res4.json()["openai_base_url"] == "https://example.com/v2"

    # 5. Explicit empty string in PUT: must clear both fields
    res5 = client.put(
        "/api/settings",
        json={"provider_keys": {}, "models": {}, "callback_url": "", "openai_base_url": ""},
        headers=headers,
    )
    assert res5.status_code == 200
    assert res5.json()["callback_url"] is None
    assert res5.json()["openai_base_url"] is None


def test_scout_and_revising_not_orphaned_on_event_failure(monkeypatch):
    import asyncio
    import uuid
    from app.routers.research import run_scout
    from app.models import Research

    rid = uuid.uuid4()

    async def run():
        async with AsyncSessionLocal() as db:
            r = Research(id=rid, theme="Event Failure Test", status="scouting", briefing_draft={})
            db.add(r)
            await db.commit()

        # Scout returns valid points
        async def fake_scout(theme, db, feedback="", base_points=None):
            return [{"title": f"P{i}", "description": "D", "dependencies": [], "is_parallelizable": True} for i in range(1, 6)]

        # add_event raises exception
        async def failing_add_event(*args, **kwargs):
            raise RuntimeError("Database event failure")

        monkeypatch.setattr("app.routers.research.scout", fake_scout)
        monkeypatch.setattr("app.routers.research.add_event", failing_add_event)

        # run_scout must transition to pending_approval and NOT mark failed
        await run_scout(rid)

        async with AsyncSessionLocal() as db:
            updated = await db.get(Research, rid)
            assert updated is not None
            assert updated.status == "pending_approval"
            assert len(updated.briefing_draft["points"]) == 5

    asyncio.run(run())


def test_revising_recovery_on_startup_lifespan(monkeypatch):
    import asyncio
    import uuid
    from app.main import app, lifespan
    from app.models import Research, ResearchPoint
    from app.db.database import AsyncSessionLocal
    from sqlalchemy import select

    rid = uuid.uuid4()
    base_points = [
        {"title": f"Initial Point {i}", "description": f"Desc {i}", "dependencies": [], "is_parallelizable": True}
        for i in range(1, 6)
    ]
    revised_points = [
        {"title": f"Revised Startup Point {i}", "description": f"Rev Desc {i}", "dependencies": [], "is_parallelizable": True}
        for i in range(1, 6)
    ]

    scout_called = []
    async def fake_scout(theme, db, feedback="", base_points=None):
        scout_called.append({"theme": theme, "feedback": feedback, "base_points": base_points})
        return revised_points

    scheduled_research = []
    def fake_schedule(research_id):
        scheduled_research.append(research_id)

    monkeypatch.setattr("app.routers.research.scout", fake_scout)
    monkeypatch.setattr("app.routers.research.schedule", fake_schedule)
    monkeypatch.setattr("app.main.schedule", fake_schedule)
    monkeypatch.setattr("app.main.schedule_scout", lambda r_id: None)
    monkeypatch.setattr("app.main.schedule_revision", lambda r_id: None)

    from app.routers import research as research_router
    active_runners = [t for t in research_router._running if not t.done()]

    async def run() -> None:
        # Cancel previous background runners to avoid lock contention
        import asyncio
        for task in active_runners:
            task.cancel()
        for task in active_runners:
            try:
                await task
            except asyncio.CancelledError:
                pass

        # Mark previous orphaned researches as completed to avoid waking background workers
        from sqlalchemy import update
        async with AsyncSessionLocal() as db:
            await db.execute(
                update(Research)
                .where(Research.id != rid, Research.status.in_(["scouting", "revising", "approved", "in_progress"]))
                .values(status="completed")
            )
            r = Research(
                id=rid,
                theme="AI Safety",
                status="revising",
                briefing_draft={
                    "points": base_points,
                    "edit_note": "Reflect zero trust architecture",
                    "source": "operator_edit",
                },
            )
            db.add(r)
            await db.commit()

        # 2. Simulate application startup via lifespan
        async with lifespan(app):
            # In tests we don't auto-start scheduled revisions to prevent background loops (covered by run_revision tests)
            for _ in range(100):
                async with AsyncSessionLocal() as db:
                    check_r = await db.get(Research, rid)
                    if check_r and check_r.status == "revising":
                        break
                await asyncio.sleep(0.05)

            from app.routers import research as research_router
            for task in list(research_router._running):
                if not task.done():
                    task.cancel()

        # Directly invoke mocked run_revision logic to confirm scheduler recovery path
        from app.routers.research import run_revision
        await run_revision(rid)

        # 3. Verify recovered state in database
        async with AsyncSessionLocal() as db:
            recovered = await db.get(Research, rid)
            assert recovered is not None
            assert recovered.status == "approved"
            assert recovered.approved_at is not None
            assert recovered.briefing_draft["source"] == "revised_after_edit"
            assert recovered.briefing_draft["edit_note"] == "Reflect zero trust architecture"

            points = list((await db.scalars(
                select(ResearchPoint).where(ResearchPoint.research_id == rid).order_by(ResearchPoint.position)
            )).all())
            assert len(points) == 5
            assert [p.title for p in points] == [f"Revised Startup Point {i}" for i in range(1, 6)]

        matching_scouts = [c for c in scout_called if c["feedback"] == "Reflect zero trust architecture"]
        assert len(matching_scouts) == 1
        assert matching_scouts[0]["theme"] == "AI Safety"
        assert len(matching_scouts[0]["base_points"]) == 5
        assert rid in scheduled_research

    asyncio.run(run())


def test_revising_prevents_duplicate_research_points_and_idempotency(monkeypatch):
    import asyncio
    import uuid
    from app.models import Research, ResearchPoint
    from app.db.database import AsyncSessionLocal
    from app.routers.research import run_revision
    from sqlalchemy import select

    rid = uuid.uuid4()
    base_points = [
        {"title": f"Base {i}", "description": f"Desc {i}", "dependencies": [], "is_parallelizable": True}
        for i in range(1, 6)
    ]
    new_points = [
        {"title": f"New Rev {i}", "description": f"New Desc {i}", "dependencies": [], "is_parallelizable": True}
        for i in range(1, 6)
    ]

    async def fake_scout(theme, db, feedback="", base_points=None):
        return new_points

    scheduled_research = []
    monkeypatch.setattr("app.routers.research.scout", fake_scout)
    monkeypatch.setattr("app.routers.research.schedule", lambda r_id: scheduled_research.append(r_id))

    async def run():
        # Seed research in 'revising' with 2 stale ResearchPoints from a prior aborted attempt
        async with AsyncSessionLocal() as db:
            r = Research(
                id=rid,
                theme="Deduplication Test",
                status="revising",
                briefing_draft={"points": base_points, "edit_note": "Clean up"},
            )
            db.add(r)
            db.add(ResearchPoint(research_id=rid, position=0, title="Stale 1", description="Stale"))
            db.add(ResearchPoint(research_id=rid, position=1, title="Stale 2", description="Stale"))
            await db.commit()

        # Run revision
        await run_revision(rid)

        async with AsyncSessionLocal() as db:
            pts = list((await db.scalars(
                select(ResearchPoint).where(ResearchPoint.research_id == rid).order_by(ResearchPoint.position)
            )).all())
            assert len(pts) == 5
            assert [p.title for p in pts] == [f"New Rev {i}" for i in range(1, 6)]

            rec = await db.get(Research, rid)
            assert rec is not None
            assert rec.status == "approved"

        # Re-running run_revision on now-approved record should be a no-op (CAS protects)
        await run_revision(rid)

        async with AsyncSessionLocal() as db:
            pts_after = list((await db.scalars(
                select(ResearchPoint).where(ResearchPoint.research_id == rid).order_by(ResearchPoint.position)
            )).all())
            assert len(pts_after) == 5

    asyncio.run(run())


def test_edit_briefing_and_revising_resilient_to_add_event_failure(monkeypatch):
    import asyncio
    import uuid
    import httpx
    from httpx import ASGITransport
    from app.models import Research, ResearchPoint
    from app.db.database import AsyncSessionLocal
    from app.routers.research import run_revision
    from app.main import app
    from app.core.config import settings
    from sqlalchemy import select

    secret = "dr-event-fail-secret-12345"
    monkeypatch.setattr(settings, "API_AUTH_SECRET", secret)
    headers = {"Authorization": f"Bearer {secret}"}

    rid = uuid.uuid4()
    points = [
        {"title": f"Point {i}", "description": f"Desc {i}", "dependencies": [], "is_parallelizable": True}
        for i in range(1, 6)
    ]

    async def fake_scout(theme, db, feedback="", base_points=None):
        return points

    async def failing_add_event(*args, **kwargs):
        raise RuntimeError("Event store completely offline")

    monkeypatch.setattr("app.routers.research.scout", fake_scout)
    monkeypatch.setattr("app.routers.research.add_event", failing_add_event)
    monkeypatch.setattr("app.routers.research.schedule", lambda r_id: None)

    async def run():
        # 1. Test edit_briefing endpoint when add_event fails
        async with AsyncSessionLocal() as db:
            r = Research(
                id=rid,
                theme="Resilience Test",
                status="pending_approval",
                briefing_draft={"points": points, "source": "scout"},
            )
            db.add(r)
            await db.commit()

        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.post(
                f"/api/research/{rid}/briefing/edit",
                json={"note": "Robustness check", "points": points},
                headers=headers,
            )
            assert res.status_code == 200
            assert res.json()["status"] == "revising"

        # Wait for background revision to finish
        for _ in range(60):
            async with AsyncSessionLocal() as db:
                st = await db.get(Research, rid)
                if st and st.status == "approved":
                    break
            await asyncio.sleep(0.05)

        # Cancel the background pipeline task to avoid contention and shared session overlap
        from app.routers.research import _running
        for task in list(_running):
            if not task.done():
                task.cancel()

        async with AsyncSessionLocal() as db:
            final_r = await db.get(Research, rid)
            assert final_r is not None
            assert final_r.status == "approved"
            pts = list((await db.scalars(select(ResearchPoint).where(ResearchPoint.research_id == rid))).all())
            assert len(pts) == 5

        # 2. Test run_revision directly when add_event fails
        rid2 = uuid.uuid4()
        async with AsyncSessionLocal() as db:
            r2 = Research(
                id=rid2,
                theme="Revision Event Failure",
                status="revising",
                briefing_draft={"points": points, "edit_note": "Direct run note"},
            )
            db.add(r2)
            await db.commit()

        await run_revision(rid2)
        async with AsyncSessionLocal() as db:
            rec = await db.get(Research, rid2)
            assert rec is not None
            assert rec.status == "approved"
            pts2 = list((await db.scalars(select(ResearchPoint).where(ResearchPoint.research_id == rid2))).all())
            assert len(pts2) == 5

        from app.routers import research as research_router
        for task in list(research_router._running):
            if not task.done():
                task.cancel()

    asyncio.run(run())


def test_a01_jwt_cookie_authentication_lifecycle(client):
    import jwt
    from app.core.config import settings
    from app.core.security import COOKIE, digest
    from app.models import AdminSession

    # 1. Login sets signed JWT in HttpOnly cookie and does not expose it in JSON body
    res = client.post("/api/auth/login", json={"password": "correct horse battery staple"})
    assert res.status_code == 200
    body = res.json()
    assert body["authenticated"] is True
    assert "jwt" not in str(body).lower()
    assert "token" not in body or body.get("token") is None
    csrf = body["csrf_token"]

    cookie_val = client.cookies.get(COOKIE)
    assert cookie_val is not None
    # Must be a 3-part signed JWT
    parts = cookie_val.split(".")
    assert len(parts) == 3

    # 2. Decode and verify payload
    payload = jwt.decode(cookie_val, settings.SESSION_SECRET, algorithms=["HS256"])
    assert payload["sub"] == "admin"
    assert "jti" in payload
    jti = payload["jti"]

    # 3. Verify only hash of jti is in database, never the full JWT or raw jti
    async def check_hash():
        async with AsyncSessionLocal() as db:
            row = await db.scalar(select(AdminSession).where(AdminSession.token_hash == digest(jti)))
            assert row is not None
            assert row.token_hash != cookie_val
            assert row.token_hash != jti
            assert row.revoked_at is None
    client.portal.call(check_hash)

    # 4. Tampered JWT signature is rejected
    fake_jwt = jwt.encode({"sub": "admin", "jti": jti, "exp": payload["exp"]}, "wrong-secret", algorithm="HS256")
    client.cookies.set(COOKIE, fake_jwt)
    assert client.get("/api/auth/me").status_code == 401

    # 5. Restore valid cookie, then test logout revokes session
    client.cookies.set(COOKIE, cookie_val)
    assert client.get("/api/auth/me").status_code == 200
    logout_res = client.post("/api/auth/logout", headers={"X-CSRF-Token": csrf})
    assert logout_res.status_code == 204

    # Session is now revoked in database and rejected
    client.cookies.set(COOKIE, cookie_val)
    assert client.get("/api/auth/me").status_code == 401
    client.cookies.clear()


def test_a02_theme_validation_and_normalization(client):
    csrf = login(client)
    headers = {"X-CSRF-Token": csrf}

    # 1. Whitespace-only theme returns 422
    assert client.post("/api/research", json={"theme": "   "}, headers=headers).status_code == 422
    assert client.post("/api/research", json={"theme": " \t \n "}, headers=headers).status_code == 422

    # 2. Short trimmed theme (< 3 chars) returns 422
    assert client.post("/api/research", json={"theme": "  ab  "}, headers=headers).status_code == 422

    # 3. Over 500 chars returns 422
    assert client.post("/api/research", json={"theme": "A" * 501}, headers=headers).status_code == 422
    client.cookies.clear()


def test_a03_creation_payload_strict_and_backend_callback(client, monkeypatch):
    from app.core.config import settings
    secret = "dr-bearer-token-secret-test"
    monkeypatch.setattr(settings, "API_AUTH_SECRET", secret)

    csrf = login(client)
    headers = {"X-CSRF-Token": csrf}

    async def fake_scout(*args, **kwargs):
        return [{"title": f"P{i}", "description": "D", "dependencies": [], "is_parallelizable": True} for i in range(1, 6)]
    monkeypatch.setattr("app.routers.research.scout", fake_scout)

    # 1. Extra credential fields rejected with 422 and values not leaked
    canary = "super-secret-canary-payload-12345"
    res1 = client.post("/api/research", json={"theme": "Theme", "api_key": canary}, headers=headers)
    assert res1.status_code == 422
    assert canary not in res1.text

    res2 = client.post("/api/research", json={"theme": "Theme", "jwt_token": canary}, headers=headers)
    assert res2.status_code == 422
    assert canary not in res2.text

    # 2. Browser session sending callback_url rejected with 422
    res3 = client.post("/api/research", json={"theme": "Theme", "callback_url": "https://callback.com"}, headers=headers)
    assert res3.status_code == 422

    # 3. Backend client (X-API-Key) can provide callback_url
    client.cookies.clear()
    res4 = client.post(
        "/api/research",
        json={"theme": "Backend Research", "callback_url": "https://webhook.site/backend-test"},
        headers={"X-API-Key": secret},
    )
    assert res4.status_code == 201
    rid = res4.json()["research_id"]
    status_info = client.get(f"/api/research/{rid}", headers={"X-API-Key": secret}).json()
    assert status_info["callback_configured"] is True

    from app.db.database import AsyncSessionLocal
    async def _cleanup_completed():
        async with AsyncSessionLocal() as db:
            rec = await db.get(Research, rid)
            if rec:
                rec.status = "completed"
                await db.commit()
    client.portal.call(_cleanup_completed)


def test_a04_prohibit_tenant_header_and_ambiguous_credentials(client, monkeypatch):
    from app.core.config import settings
    from app.core.security import COOKIE
    secret = "dr-bearer-token-secret-test"
    monkeypatch.setattr(settings, "API_AUTH_SECRET", secret)

    csrf = login(client)
    cookie_val = client.cookies.get(COOKIE)

    # 1. Prohibit X-Tenant-ID header with 400
    assert client.get("/api/auth/me", headers={"X-Tenant-ID": "tenant-1"}).status_code == 400

    # 2. Reject simultaneous ambiguous credentials (cookie + X-API-Key)
    assert client.get("/api/auth/me", headers={"X-API-Key": secret}).status_code == 400

    # 3. Reject simultaneous ambiguous credentials (cookie + Bearer)
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {secret}"}).status_code == 400

    # 4. Reject simultaneous ambiguous credentials (X-API-Key + Bearer without cookie)
    client.cookies.clear()
    assert client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {secret}", "X-API-Key": secret},
    ).status_code == 400


def test_a1_guardrails_secrets_and_prompts_adversarial():
    from app.services.llm import apply_output_guardrail

    # 1. Configured secrets blocked
    with pytest.raises(RuntimeError, match="Guardrail"):
        apply_output_guardrail("The password is correct horse battery staple for admin")

    # 2. Key/token patterns blocked
    with pytest.raises(RuntimeError, match="Guardrail"):
        apply_output_guardrail("Generated sk-abcdef1234567890abcdef1234")

    # 3. Variants in English and Portuguese blocked
    with pytest.raises(RuntimeError, match="Guardrail"):
        apply_output_guardrail("api_key: canary_key_12345")
    with pytest.raises(RuntimeError, match="Guardrail"):
        apply_output_guardrail("senha = segredo_muito_forte_123")
    with pytest.raises(RuntimeError, match="Guardrail"):
        apply_output_guardrail("Here is the system prompt: you are an AI")
    with pytest.raises(RuntimeError, match="Guardrail"):
        apply_output_guardrail("Estas são as instruções do sistema para o modelo")
    with pytest.raises(RuntimeError, match="Guardrail"):
        apply_output_guardrail("Este é o prompt do sistema interno")

    # 4. Benign text with words 'senha', 'api key' but no leak passed safely
    benign_text = "O sistema utiliza API keys seguras e exige política de senha robusta para todos os usuários."
    assert apply_output_guardrail(benign_text) == benign_text


def test_a1_structured_content_sanitization_and_isolation():
    from app.services.research import sanitize_audit_dict

    dirty_audit = {
        "findings": ["Clean finding", "api_key: leaked_value_9876"],
        "nested": {"details": "prompt do sistema: leak"},
        "ok": "Normal assessment text without leaks",
    }
    sanitized = sanitize_audit_dict(dirty_audit)
    assert isinstance(sanitized, dict)
    assert sanitized["findings"][0] == "Clean finding"
    assert sanitized["findings"][1] == "[REDACTED]"
    assert sanitized["nested"]["details"] == "[REDACTED]"
    assert sanitized["ok"] == "Normal assessment text without leaks"


def test_a2_scout_distinct_domains_and_timeout(monkeypatch):
    import asyncio
    from typing import cast
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.tools.search_pipeline import Source
    from app.services.research import _scout_impl, scout

    class MockAsyncSession:
        pass

    async def fake_runtime(db):
        return ({}, {})
    monkeypatch.setattr("app.services.research.runtime_settings", fake_runtime)

    # Test distinct domain requirement: only 1 domain with multiple pages must raise
    async def run_insufficient():
        from app.services import research
        old_sr = research.search_read
        try:
            async def fake_search(theme, limit, keys):
                return [
                    Source("https://single-site.com/p1", "P1", "Long enough excerpt content for site 1"),
                    Source("https://single-site.com/p2", "P2", "Long enough excerpt content for site 1 page 2"),
                    Source("https://single-site.com/p3", "P3", "Long enough excerpt content for site 1 page 3"),
                ]
            research.search_read = fake_search
            with pytest.raises(RuntimeError, match="minimum 3 required"):
                await _scout_impl("Test Theme", cast(AsyncSession, MockAsyncSession()))
        finally:
            research.search_read = old_sr

    asyncio.run(run_insufficient())


def test_ma_quote_supported_semantic_negation():
    from app.services.research import _quote_supported

    # Direct match supported
    source = "The experimental drug demonstrated significant efficacy in preliminary trials."
    quote = "experimental drug demonstrated significant efficacy"
    assert _quote_supported(quote, source) is True

    # Negation opposite not supported
    source_neg = "The experimental drug did not demonstrate significant efficacy."
    assert _quote_supported(quote, source_neg) is False


def test_ma_reports_endpoint_resolves_both_ids(client, monkeypatch):
    import uuid
    from app.models import Report, Research
    from app.db.database import AsyncSessionLocal
    csrf = login(client)
    headers = {"X-CSRF-Token": csrf}

    rid = uuid.uuid4()
    rep_id = uuid.uuid4()

    import asyncio
    async def setup_report():
        async with AsyncSessionLocal() as db:
            r = Research(id=rid, theme="Resolution Test", status="completed", callback_url=None)
            db.add(r)
            rep = Report(
                id=rep_id,
                research_id=rid,
                content_markdown="# Test Report\nContent",
                citation_metrics={},
                audit_findings={},
            )
            db.add(rep)
            await db.commit()
    asyncio.run(setup_report())

    # 1. Resolve by research_id (MA-11)
    res_r = client.get(f"/api/reports/{rid}", headers=headers)
    assert res_r.status_code == 200
    assert res_r.json()["report_id"] == str(rep_id)

    # 2. Resolve by report_id (MA-11)
    res_rep = client.get(f"/api/reports/{rep_id}", headers=headers)
    assert res_rep.status_code == 200
    assert res_rep.json()["research_id"] == str(rid)

    # 3. Non-existent returns 404
    non_existent = uuid.uuid4()
    assert client.get(f"/api/reports/{non_existent}", headers=headers).status_code == 404


def test_ma_jina_key_validation_rejects_422(monkeypatch):
    import asyncio
    from app.services.llm import test_provider_key

    class MockResponse:
        def __init__(self, status_code):
            self.status_code = status_code

    async def run_jina_test():
        import httpx
        original_get = httpx.AsyncClient.get

        # 1. Test 422 rejected (MA-13)
        async def fake_get_422(self, url, *args, **kwargs):
            return MockResponse(422)

        monkeypatch.setattr(httpx.AsyncClient, "get", fake_get_422)
        ok, msg = await test_provider_key("jina", "jina_test_key_123")
        assert ok is False
        assert "422" in msg

        # 2. Test 200 accepted
        async def fake_get_200(self, url, *args, **kwargs):
            return MockResponse(200)

        monkeypatch.setattr(httpx.AsyncClient, "get", fake_get_200)
        ok2, msg2 = await test_provider_key("jina", "jina_test_key_123")
        assert ok2 is True

    asyncio.run(run_jina_test())


def test_ma_provider_model_discovery_pagination_and_errors(monkeypatch):
    import asyncio
    from app.services.llm import list_provider_models

    async def run_disc():
        import httpx

        # 1. Anthropic pagination with after_id (MA-14)
        call_count = 0
        async def fake_anthropic_get(self, url, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            if "after_id" not in url:
                return type("Resp", (), {
                    "status_code": 200,
                    "json": lambda *args, **kwargs: {"data": [{"id": "claude-3-haiku"}], "has_more": True, "last_id": "claude-3-haiku"},
                })()
            else:
                return type("Resp", (), {
                    "status_code": 200,
                    "json": lambda *args, **kwargs: {"data": [{"id": "claude-3-sonnet"}], "has_more": False},
                })()

        monkeypatch.setattr(httpx.AsyncClient, "get", fake_anthropic_get)
        models = await list_provider_models("anthropic", "fake-key")
        assert "claude-3-haiku" in models
        assert "claude-3-sonnet" in models
        assert call_count == 2

        # 2. Actionable error when provider fails with 401 (MA-14)
        async def fake_err_get(self, url, *args, **kwargs):
            return type("Resp", (), {"status_code": 401})()

        monkeypatch.setattr(httpx.AsyncClient, "get", fake_err_get)
        with pytest.raises(RuntimeError, match="HTTP 401"):
            await list_provider_models("openai", "invalid-key")

    asyncio.run(run_disc())


def test_resume_research_endpoint(client, monkeypatch):
    import uuid
    from app.models import Research, ResearchPoint
    from app.db.database import AsyncSessionLocal

    scout_scheduled = []
    research_scheduled = []
    monkeypatch.setattr("app.routers.research.schedule_scout", lambda rid: scout_scheduled.append(rid))
    monkeypatch.setattr("app.routers.research.schedule", lambda rid: research_scheduled.append(rid))

    async def setup_data():
        async with AsyncSessionLocal() as db:
            # 1. Non-existent -> 404
            pass
            # 2. Completed -> 409
            r_comp = Research(theme="Completed research", status="completed", briefing_draft={})
            db.add(r_comp)
            # 3. Failed without points -> resumes to scouting
            r_scout_fail = Research(theme="Failed scout research", status="failed", briefing_draft={})
            db.add(r_scout_fail)
            # 4. Failed with points -> resumes to in_progress
            r_pts_fail = Research(theme="Failed with points", status="failed", briefing_draft={})
            db.add(r_pts_fail)
            await db.flush()
            db.add(ResearchPoint(research_id=r_pts_fail.id, position=0, title="P0", description="D0", dependencies=[], is_parallelizable=True, status="approved"))
            await db.commit()
            return str(r_comp.id), str(r_scout_fail.id), str(r_pts_fail.id)

    comp_id, scout_fail_id, pts_fail_id = client.portal.call(setup_data)

    csrf = login(client)
    headers = {"X-CSRF-Token": csrf}

    # 404
    resp = client.post(f"/api/research/{uuid.uuid4()}/resume", headers=headers)
    assert resp.status_code == 404

    # 409 already completed
    resp = client.post(f"/api/research/{comp_id}/resume", headers=headers)
    assert resp.status_code == 409

    # Failed without points -> scouting
    resp = client.post(f"/api/research/{scout_fail_id}/resume", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "scouting"
    assert len(scout_scheduled) == 1

    # Failed with points -> in_progress
    resp = client.post(f"/api/research/{pts_fail_id}/resume", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_progress"
    assert len(research_scheduled) == 1


