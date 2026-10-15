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

from app.main import app


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
        await engine.dispose()

    asyncio.run(_cleanup())


@pytest.fixture()
def client():
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def login(client):
    response = client.post("/api/auth/login", json={"password": "correct horse battery staple"})
    assert response.status_code == 200
    return response.json()["csrf_token"]


def test_get_settings_models_aggregated_degrades_gracefully(client, monkeypatch):
    """In aggregated mode (no provider query param), an individual provider failure degrades to []

    without failing the entire response (200 OK) and preserves models from healthy providers.
    """
    csrf = login(client)
    headers = {"X-CSRF-Token": csrf}

    up = client.put(
        "/api/settings",
        json={"provider_keys": {"openai": "valid-openai-key", "gemini": "expired-gemini-key"}, "models": {}},
        headers=headers,
    )
    assert up.status_code == 200

    async def fake_list_models(provider, api_key=None, base_url=None):
        if provider == "openai":
            return ["gpt-4o", "gpt-4o-mini"]
        if provider == "gemini":
            raise RuntimeError("Gemini API key expired (401)")
        return []

    monkeypatch.setattr("app.routers.settings.list_provider_models", fake_list_models)

    # Aggregated request (provider is None)
    res = client.get("/api/settings/models", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "models_by_provider" in data
    catalog = data["models_by_provider"]
    assert catalog["openai"] == ["gpt-4o", "gpt-4o-mini"]
    assert catalog["gemini"] == []


def test_get_settings_models_specific_provider_preserves_actionable_error(client, monkeypatch):
    """When querying a specific provider (?provider=gemini), failures must NOT be swallowed into [] + 200 OK."""
    csrf = login(client)
    headers = {"X-CSRF-Token": csrf}

    up = client.put(
        "/api/settings",
        json={"provider_keys": {"gemini": "bad-gemini-key"}, "models": {}},
        headers=headers,
    )
    assert up.status_code == 200

    async def fake_list_models(provider, api_key=None, base_url=None):
        if provider == "gemini":
            raise RuntimeError("Gemini API key invalid (401)")
        return []

    monkeypatch.setattr("app.routers.settings.list_provider_models", fake_list_models)

    # Specific provider request (?provider=gemini)
    res = client.get("/api/settings/models?provider=gemini", headers=headers)
    # Failure must not return HTTP 200 with empty list
    assert res.status_code != 200 or "models_by_provider" not in res.json() or res.json()["models_by_provider"]["gemini"] != []


def test_get_settings_models_specific_provider_success(client, monkeypatch):
    """When querying a specific provider (?provider=openai) that succeeds, return models with 200 OK."""
    csrf = login(client)
    headers = {"X-CSRF-Token": csrf}

    up = client.put(
        "/api/settings",
        json={"provider_keys": {"openai": "valid-openai-key"}, "models": {}},
        headers=headers,
    )
    assert up.status_code == 200

    async def fake_list_models(provider, api_key=None, base_url=None):
        if provider == "openai":
            return ["gpt-4o", "gpt-4o-mini"]
        return []

    monkeypatch.setattr("app.routers.settings.list_provider_models", fake_list_models)

    res = client.get("/api/settings/models?provider=openai", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["models_by_provider"]["openai"] == ["gpt-4o", "gpt-4o-mini"]
