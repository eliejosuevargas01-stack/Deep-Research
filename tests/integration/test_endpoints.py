"""Testes de integração para os endpoints da API (fluxos felizes ponta a ponta).

Cobre os endpoints operacionais /api/v1/plan, /api/v1/search, /api/v1/audit,
/api/v1/writer e administrativos /api/v1/admin/credentials via httpx.AsyncClient.
Atende a RF-01 até RF-12.
"""

import httpx
import pytest
from tests.mocks.http_mock import MockNetwork, create_mock_transport


@pytest.mark.asyncio
async def test_admin_credentials_endpoints() -> None:
    """Verifica cadastro (POST) e consulta sanitizada (GET) em /api/v1/admin/credentials."""
    from app.main import app

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # 1. Cadastro de credencial
        payload = {
            "chave": "OPENAI_API_KEY",
            "valor": "sk-proj-test1234567890",
            "tipo": "llm",
            "base_url": "https://api.openai.com/v1",
            "descricao": "Chave OpenAI mock",
        }
        resp_post = await client.post("/api/v1/admin/credentials", json=payload)
        assert resp_post.status_code == 200
        dados_post = resp_post.json()
        assert dados_post["status"] == "salvo"
        assert dados_post["chave"] == "OPENAI_API_KEY"

        # 2. Listagem sanitizada
        resp_get = await client.get("/api/v1/admin/credentials")
        assert resp_get.status_code == 200
        dados_get = resp_get.json()
        assert "credenciais" in dados_get
        item = next((c for c in dados_get["credenciais"] if c["chave"] == "OPENAI_API_KEY"), None)
        assert item is not None
        assert "sk-proj-test1234567890" not in item["mascarado"]
        assert item["origem_ativa"] in ("ambiente", "banco_cifrado")


@pytest.mark.asyncio
async def test_plan_endpoint_happy_path() -> None:
    """Verifica geração de pesquisa e N pontos via POST /api/v1/plan (RF-01, RF-02)."""
    from app.main import app

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        payload = {"tema": "Impacto da Inteligência Artificial Generativa na Educação Básica"}
        resp = await client.post("/api/v1/plan", json=payload)

        assert resp.status_code == 201
        data = resp.json()
        assert "id_pesquisa" in data
        assert data["n_pontos"] == 5
        assert len(data["pontos"]) == 5
        for p in data["pontos"]:
            assert p["status"] == "pendente"


@pytest.mark.asyncio
async def test_search_endpoint_happy_path() -> None:
    """Verifica coleta concorrente via POST /api/v1/search (RF-03, RF-04, RF-05)."""
    from app.main import app

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # Primeiro cria o plano
        plan_resp = await client.post(
            "/api/v1/plan",
            json={"tema": "Impacto da IA na Educação"},
        )
        id_pesquisa = plan_resp.json()["id_pesquisa"]

        # Executa a busca
        search_resp = await client.post("/api/v1/search", json={"id_pesquisa": id_pesquisa})
        assert search_resp.status_code == 200
        data = search_resp.json()
        assert data["id_pesquisa"] == id_pesquisa
        assert data["total_pontos_processados"] == 5
        assert data["status_pesquisa"] == "coletado"


@pytest.mark.asyncio
async def test_audit_endpoint_happy_path() -> None:
    """Verifica auditoria analítica via POST /api/v1/audit com checklist das 12 perguntas (RF-06)."""
    from app.main import app

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # Prepara plano e busca
        plan_resp = await client.post("/api/v1/plan", json={"tema": "IA na Educação"})
        id_pesquisa = plan_resp.json()["id_pesquisa"]
        await client.post("/api/v1/search", json={"id_pesquisa": id_pesquisa})

        # Dispara auditoria
        audit_resp = await client.post("/api/v1/audit", json={"id_pesquisa": id_pesquisa})
        assert audit_resp.status_code == 200
        data = audit_resp.json()
        assert data["id_pesquisa"] == id_pesquisa
        assert data["total_pontos"] == 5
        assert data["status_geral"] == "auditado"
        assert len(data["auditorias"]) == 5


@pytest.mark.asyncio
async def test_writer_endpoint_happy_path() -> None:
    """Verifica redação e despacho de webhook via POST /api/v1/writer (RF-08, RF-10)."""
    from app.main import app

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # Ciclo preparatório completo: plan -> search -> audit
        plan_resp = await client.post("/api/v1/plan", json={"tema": "IA na Educação"})
        id_pesquisa = plan_resp.json()["id_pesquisa"]
        await client.post("/api/v1/search", json={"id_pesquisa": id_pesquisa})
        await client.post("/api/v1/audit", json={"id_pesquisa": id_pesquisa})

        # Redação final
        writer_resp = await client.post("/api/v1/writer", json={"id_pesquisa": id_pesquisa})
        assert writer_resp.status_code == 200
        data = writer_resp.json()
        assert data["id_pesquisa"] == id_pesquisa
        assert data["status"] == "concluido"
        assert data["total_caracteres_dossier"] > 0
        assert data["webhook_entrega"]["status"] in ("entregue", "falha_definitiva")


@pytest.mark.asyncio
async def test_full_pipeline_end_to_end() -> None:
    """Valida o ciclo sequencial completo das 4 etapas de investigação em sequência única."""
    from app.main import app

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # 1. Planejamento
        r1 = await client.post("/api/v1/plan", json={"tema": "Transição Energética Global"})
        assert r1.status_code == 201
        id_pesquisa = r1.json()["id_pesquisa"]

        # 2. Busca com Personas
        r2 = await client.post("/api/v1/search", json={"id_pesquisa": id_pesquisa})
        assert r2.status_code == 200

        # 3. Auditoria de Qualidade
        r3 = await client.post("/api/v1/audit", json={"id_pesquisa": id_pesquisa})
        assert r3.status_code == 200

        # 4. Redação do Dossier
        r4 = await client.post("/api/v1/writer", json={"id_pesquisa": id_pesquisa})
        assert r4.status_code == 200
        assert r4.json()["status"] == "concluido"
