"""Exercise full HTTP lifecycle against migrated PostgreSQL with controlled providers."""
import json
import time
import uuid

from fastapi.testclient import TestClient
import pytest

from app.core.config import settings
from app.main import app
from app.tools.search_pipeline import Source

pytestmark = pytest.mark.skipif(not settings.DATABASE_URL.startswith("postgresql+asyncpg://"),
                                reason="Requires migrated PostgreSQL; run in Compose backend")


def test_postgres_research_lifecycle(monkeypatch):
    assert settings.DATABASE_URL.startswith("postgresql+asyncpg://")
    roles_seen = []

    async def sources(query, limit=8, keys=None):
        return [Source("https://example.com/study", "Study", "The measured result was 42 percent.")]

    async def completion(role, system, user, db):
        roles_seen.append(role)
        if role == "scout":
            return json.dumps([{"title": f"Point {number}", "description": "Investigate result",
                                "dependencies": [], "is_parallelizable": True} for number in range(1, 6)])
        if role == "auditor":
            return json.dumps({"approved": True, "findings": [], "contradictions": [],
                               "uncertainties": [], "outline": ["Results"]})
        if role == "writer":
            return "# Results\nThe measured result was 42 percent. [Study](https://example.com/study)\n"
        return json.dumps([{"source_url": "https://example.com/study",
                            "claim": "result was 42 percent",
                            "exact_quote": "The measured result was 42 percent.",
                            "analysis": "The source states this result."}])

    monkeypatch.setattr("app.services.research.search_read", sources)
    monkeypatch.setattr("app.services.research.complete", completion)
    with TestClient(app, base_url="https://testserver") as client:
        health = client.get("/health")
        assert health.status_code == 200 and health.json()["database"] == "connected"
        login = client.post("/api/auth/login", json={"password": settings.ADMIN_PASSWORD})
        assert login.status_code == 200
        csrf = {"X-CSRF-Token": login.json()["csrf_token"]}
        theme = f"Postgres cycle {uuid.uuid4()}"
        created = client.post(
            "/api/research",
            json={"api_key": "test-key", "jwt_token": "test-jwt", "theme": theme},
            headers=csrf,
        )
        assert created.status_code == 201
        rid = created.json()["research_id"]
        draft = {}
        for _ in range(100):
            draft = client.get(f"/api/research/{rid}").json()
            if draft["status"] != "scouting":
                break
            time.sleep(0.05)
        assert draft["status"] == "pending_approval", draft
        points = draft["briefing_draft"]["points"]
        assert len(points) == 5
        approved = client.post(f"/api/research/{rid}/briefing/approve", json={"approved_points": points}, headers=csrf)
        assert approved.status_code == 200, approved.text
        repeat = client.post(f"/api/research/{rid}/briefing/approve", json={"approved_points": points}, headers=csrf)
        assert repeat.status_code == 409
        result = {}
        for _ in range(200):
            result = client.get(f"/api/research/{rid}").json()
            if result["status"] in {"completed", "blocked", "failed"}:
                break
            time.sleep(0.05)
        assert result["status"] == "completed", result
        assert all(point["attempt_count"] == 1 for point in result["points"])
        report = client.get(f"/api/reports/{rid}")
        assert report.status_code == 200
        assert "https://example.com/study" in report.json()["content_markdown"]
        assert {"scout", "historian", "skeptic", "pragmatist", "futurist", "auditor", "writer"} <= set(roles_seen)
