import os
import tempfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

_TEST_DIR = tempfile.TemporaryDirectory(prefix="bug-9d4e-tests-")
_TEST_DB = Path(_TEST_DIR.name) / "test_9d4e.db"
os.environ.update({
    "DATABASE_URL": f"sqlite+aiosqlite:///{_TEST_DB}",
    "ADMIN_PASSWORD": "correct horse battery staple",
    "SESSION_SECRET": "s" * 32,
    "APP_ENCRYPTION_KEY": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
    "ENVIRONMENT": "test",
})

from app.main import app
from app.services.settings import update_settings
from app.db.database import AsyncSessionLocal


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
    with TestClient(app) as c:
        yield c


def login(client):
    response = client.post("/api/auth/login", json={"password": "correct horse battery staple"})
    assert response.status_code == 200
    return response.json()["csrf_token"]


def test_get_provider_models_degrades_gracefully_when_one_provider_fails(client, monkeypatch):
    csrf = login(client)
    headers = {"X-CSRF-Token": csrf}

    # Set up keys for openai and gemini in settings
    async def setup_keys():
        async with AsyncSessionLocal() as db:
            await update_settings(
                db,
                provider_keys={
                    "openai": "valid-openai-key",
                    "gemini": "expired-gemini-key",
                },
                models={},
            )
    client.portal.call(setup_keys)

    # Mock list_provider_models so openai succeeds and gemini raises RuntimeError
    async def mock_list_provider_models(provider, api_key=None, base_url=None):
        if provider == "openai":
            return ["gpt-4o", "gpt-4o-mini"]
        if provider == "gemini":
            raise RuntimeError("HTTP 401 Unauthorized: Expired API Key")
        return []

    monkeypatch.setattr("app.routers.settings.list_provider_models", mock_list_provider_models)

    # 1. Test full listing without provider parameter
    response = client.get("/api/settings/models", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "models_by_provider" in data
    catalog = data["models_by_provider"]
    assert catalog["openai"] == ["gpt-4o", "gpt-4o-mini"]
    assert catalog["gemini"] == []

    # 2. Test single provider listing when that specific provider fails
    response_single = client.get("/api/settings/models?provider=gemini", headers=headers)
    assert response_single.status_code == 200
    data_single = response_single.json()
    assert data_single["models_by_provider"]["gemini"] == []
