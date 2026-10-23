"""Testes de integração para a feature 002: Pipeline Autônomo Seguro.

Valida autenticação global por API Key e execução ininterrupta assíncrona.
"""

import pytest
import httpx
from app.main import app


@pytest.mark.asyncio
async def test_api_key_protection_on_endpoints(monkeypatch: pytest.MonkeyPatch):
    """Verifica proteção 401 em rotas /api/v1 quando API_SECRET_KEY está ativa."""
    monkeypatch.setenv("API_SECRET_KEY", "chave-secreta-forte-123")

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # 1. Rota /health permanece pública (200 OK sem header)
        health_resp = await client.get("/health")
        assert health_resp.status_code == 200

        # 2. Rota /api/v1/plan sem header deve falhar com 401
        unauth_resp = await client.post("/api/v1/plan", json={"tema": "Tema Qualquer"})
        assert unauth_resp.status_code == 401
        assert "Chave de API ausente ou inválida" in unauth_resp.json()["detail"]

        # 3. Rota /api/v1/plan com header inválido deve falhar com 401
        wrong_resp = await client.post(
            "/api/v1/plan",
            json={"tema": "Tema Qualquer"},
            headers={"X-API-Key": "chave-errada"},
        )
        assert wrong_resp.status_code == 401

        # 4. Rota /api/v1/plan com header válido é autorizada
        auth_resp = await client.post(
            "/api/v1/plan",
            json={"tema": "Inteligência Artificial no Varejo"},
            headers={"X-API-Key": "chave-secreta-forte-123"},
        )
        assert auth_resp.status_code == 201
        assert "id_pesquisa" in auth_resp.json()


@pytest.mark.asyncio
async def test_async_pipeline_execution_and_status(monkeypatch: pytest.MonkeyPatch):
    """Verifica disparo de pipeline contínuo com async_execute=True retornando HTTP 202."""
    monkeypatch.delenv("API_SECRET_KEY", raising=False)

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # Disparo com async_execute
        resp = await client.post(
            "/api/v1/plan",
            json={
                "tema": "Inovações em Robótica Médica",
                "async_execute": True,
                "callback_url": "https://meu-webhook.site/callback",
            },
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "iniciado"
        assert data["status_pipeline"] == "planejado"
        assert "id_pesquisa" in data
        id_pesquisa = data["id_pesquisa"]

        # Consulta de status da pesquisa
        status_resp = await client.get(f"/api/v1/pipeline/{id_pesquisa}/status")
        assert status_resp.status_code == 200
        status_data = status_resp.json()
        assert status_data["id_pesquisa"] == id_pesquisa
        assert "status_pipeline" in status_data
        assert status_data["total_pontos"] >= 1
