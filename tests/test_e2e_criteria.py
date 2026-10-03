import time
import pytest
from tests.test_backend import client, login
import app.routers.research as rr


def test_criteria_full_flow(client):
    # 1. Login (A4)
    csrf = login(client)
    headers = {"X-CSRF-Token": csrf}
    api_key = "session-admin"
    jwt_token = csrf

    # 2. Settings: Test Key (F1)
    test_key_res = client.post(
        "/api/settings/test",
        json={"provider": "openai", "api_key": "sk-test-key"},
        headers=headers,
    )
    assert test_key_res.status_code == 200
    assert "success" in test_key_res.json()

    # 3. Settings: Configure Webhook & OpenAI Base URL (A7, F3, D)
    settings_res = client.put(
        "/api/settings",
        json={
            "provider_keys": {},
            "models": {"scout": "openai/gpt-4o-mini"},
            "callback_url": "https://example.com/research-webhook",
            "openai_base_url": "https://custom-openai.internal/v1",
        },
        headers=headers,
    )
    assert settings_res.status_code == 200
    cfg = settings_res.json()
    assert cfg["callback_url"] == "https://example.com/research-webhook"
    assert cfg["openai_base_url"] == "https://custom-openai.internal/v1"

    # 4. Settings: Dynamic Model Catalog (F2)
    models_res = client.get("/api/settings/models?provider=openai", headers=headers)
    assert models_res.status_code == 200
    assert "models_by_provider" in models_res.json()

    # 5. Create Research without callback in payload (A, A2)
    async def fake_scout(theme, db, feedback="", base_points=None):
        return [
            {"title": f"Aspecto {i}", "description": f"Investigação {i}", "dependencies": [], "is_parallelizable": True}
            for i in range(1, 6)
        ]

    original_scout = rr.scout
    rr.scout = fake_scout

    try:
        create_res = client.post(
            "/api/research",
            json={"theme": "Avanços em Computação Quântica"},
            headers=headers,
        )
        assert create_res.status_code == 201
        rid = create_res.json()["research_id"]

        # Wait for scout
        status = client.get(f"/api/research/{rid}", headers=headers).json()
        for _ in range(60):
            if status["status"] == "pending_approval":
                break
            time.sleep(0.05)
            status = client.get(f"/api/research/{rid}", headers=headers).json()

        assert status["status"] == "pending_approval"
        points = status["briefing_draft"]["points"]
        assert len(points) == 5

        # 6. Approve Briefing (A3, A4)
        approve_res = client.post(
            f"/api/research/{rid}/briefing/approve",
            json={"approved_points": points},
            headers=headers,
        )
        assert approve_res.status_code == 200
        assert approve_res.json()["status"] == "approved"

    finally:
        rr.scout = original_scout
