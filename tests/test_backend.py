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
        json={"api_key": "test-key", "jwt_token": "test-jwt", "theme": "Test theme"},
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
    state = None
    for attempt in range(1, 4):
        state = next_audit_state(False, attempt)
    assert state == "blocked"


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

    points = [Point("Base"), Point("Independent"), Point("Dependent", ["1"]), Point("Sequential", parallel=False)]
    batches = ready_point_batches(points)
    assert batches[0] == [3]
    assert batches[1] == [0, 1]
    assert batches[2] == [2]
    with pytest.raises(ValueError, match="cycle"):
        point_dependencies([Point("A", ["2"]), Point("B", ["1"])])
    with pytest.raises(ValueError, match="Unknown"):
        point_dependencies([Point("A", ["missing"])])


def test_health_checks_database(client):
    body = client.get("/health").json()
    assert body["database"] == "connected"


def test_full_pipeline_with_controlled_sources_and_models(client, monkeypatch):
    import json
    import time
    from app.tools.search_pipeline import Source

    async def sources(query, limit=8, keys=None):
        return [Source("https://example.com/a", "Study", "The measured result was 42 percent.")]

    async def completion(role, system, user, db):
        if role == "scout":
            return json.dumps([{"title": f"Point {i}", "description": "Investigate measured results",
                                "dependencies": [], "is_parallelizable": True} for i in range(1, 6)])
        if role == "auditor":
            return json.dumps({"approved": True, "findings": [], "contradictions": [],
                               "uncertainties": [], "outline": ["Overview"]})
        if role == "writer":
            return "# Report\nThe measured result was 42 percent. [Study](https://example.com/a)\n"
        return json.dumps([{"source_url": "https://example.com/a", "claim": "result was 42 percent",
                            "exact_quote": "The measured result was 42 percent.", "analysis": "Source states result."}])

    monkeypatch.setattr("app.services.research.search_read", sources)
    monkeypatch.setattr("app.services.research.complete", completion)
    csrf = login(client)
    headers = {"X-CSRF-Token": csrf}
    response = client.post(
        "/api/research",
        json={"api_key": "test-key", "jwt_token": "test-jwt", "theme": "Controlled full pipeline"},
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
    assert "https://example.com/a" in report.json()["content_markdown"]


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

