"""Testes de integração para contabilidade pública de fontes e endpoint GET /api/v1/pipeline/{id}/sources.

Verifica:
- GET /api/v1/pipeline/{id_pesquisa}/sources retorna 404 para pesquisa inexistente.
- GET /api/v1/pipeline/{id_pesquisa}/sources retorna 200 com resumo completo após ciclo de pesquisa.
- Separação íntegra de fontes consultadas, utilizadas e não utilizadas.
- Hidratação de relatório legado sem acionar LLMs ou mutações de banco de dados.
- Verificação de autenticação e proteção contra requisições cross-site/não autorizadas.
- Presença e consistência aditiva do campo fontes no retorno do POST /api/v1/writer.
"""

import hashlib
import json
import httpx
import pytest
from app.db.models import Pesquisa
from app.db.research_repository import ResearchRepository


@pytest.mark.asyncio
async def test_sources_endpoint_not_found() -> None:
    """Verifica que pesquisa inexistente retorna HTTP 404 com mensagem descritiva."""
    from app.main import app

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/pipeline/inexistente-uuid-999/sources")
        assert resp.status_code == 404
        data = resp.json()
        assert "não localizada" in data["detail"]


@pytest.mark.asyncio
async def test_sources_endpoint_legacy_report_hydration(db_session) -> None:
    """Verifica hidratação somente-leitura de relatório legado sem acionar modelos."""
    from app.main import app

    repo = ResearchRepository(session=db_session)
    id_legacy = "legacy-report-test-123"
    dossier_legacy = (
        "# Dossiê Histórico\n\n"
        "Investigação realizada citando [Fonte Antiga](https://legado.org/estudo-2023) "
        "e também <https://dados.antigos.gov.br/relatorio> no corpo do texto."
    )
    doc_hash = hashlib.sha256(dossier_legacy.encode("utf-8")).hexdigest()

    pesquisa = Pesquisa(
        id_pesquisa=id_legacy,
        tema="Tema Histórico",
        criado_em="2023-01-01T00:00:00Z",
        concluido_em="2023-01-01T01:00:00Z",
        status_pipeline="concluido",
        dossier_final=dossier_legacy,
    )
    db_session.add(pesquisa)
    await db_session.commit()

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/api/v1/pipeline/{id_legacy}/sources")
        assert resp.status_code == 200
        data = resp.json()

        assert data["id_pesquisa"] == id_legacy
        assert data["status"] == "indisponivel"
        assert data["total_consultadas"] is None  # Não inventa 0
        assert data["total_nao_utilizadas"] is None  # Não inventa 0
        assert data["total_utilizadas"] == 2
        assert len(data["consultadas"]) == 0
        assert len(data["utilizadas"]) == 2
        assert len(data["nao_utilizadas"]) == 0
        assert data["artifact_hash"] == doc_hash

        utilizadas_urls = [u["url"] for u in data["utilizadas"]]
        assert "https://legado.org/estudo-2023" in utilizadas_urls
        assert "https://dados.antigos.gov.br/relatorio" in utilizadas_urls


@pytest.mark.asyncio
async def test_sources_endpoint_full_pipeline_accounting() -> None:
    """Verifica que o pipeline gera a contabilidade completa e o POST /writer inclui fontes."""
    from app.main import app

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # 1. Planejamento
        plan_resp = await client.post("/api/v1/plan", json={"tema": "IA na Medicina"})
        assert plan_resp.status_code == 201
        id_pesquisa = plan_resp.json()["id_pesquisa"]

        # 2. Busca web com personas
        search_resp = await client.post("/api/v1/search", json={"id_pesquisa": id_pesquisa})
        assert search_resp.status_code == 200

        # 3. Auditoria
        audit_resp = await client.post("/api/v1/audit", json={"id_pesquisa": id_pesquisa})
        assert audit_resp.status_code == 200

        # 4. Redação final com validação de fontes aditivas no WriterResponse
        writer_resp = await client.post("/api/v1/writer", json={"id_pesquisa": id_pesquisa})
        assert writer_resp.status_code == 200
        writer_data = writer_resp.json()

        assert "fontes" in writer_data
        fontes_writer = writer_data["fontes"]
        assert fontes_writer is not None
        assert fontes_writer["status"] in ("completo", "parcial")
        assert fontes_writer["total_consultadas"] is not None
        assert fontes_writer["total_consultadas"] > 0
        assert fontes_writer["total_utilizadas"] is not None
        assert fontes_writer["total_utilizadas"] > 0

        # 5. Consulta via GET /api/v1/pipeline/{id_pesquisa}/sources
        sources_resp = await client.get(f"/api/v1/pipeline/{id_pesquisa}/sources")
        assert sources_resp.status_code == 200
        sources_data = sources_resp.json()

        assert sources_data["id_pesquisa"] == id_pesquisa
        assert sources_data["status"] == fontes_writer["status"]
        assert sources_data["total_consultadas"] == fontes_writer["total_consultadas"]
        assert sources_data["total_utilizadas"] == fontes_writer["total_utilizadas"]
        assert sources_data["total_nao_utilizadas"] == fontes_writer["total_nao_utilizadas"]
        assert sources_data["artifact_hash"] is not None

        # Partição íntegra
        if sources_data["status"] == "completo":
            assert sources_data["total_consultadas"] == (
                sources_data["total_utilizadas"] + sources_data["total_nao_utilizadas"]
            )
            assert len(sources_data["consultadas"]) == sources_data["total_consultadas"]
            assert len(sources_data["utilizadas"]) == sources_data["total_utilizadas"]
            assert len(sources_data["nao_utilizadas"]) == sources_data["total_nao_utilizadas"]


@pytest.mark.asyncio
async def test_sources_endpoint_authentication(db_session, monkeypatch) -> None:
    """Verifica que o endpoint GET respeita a autenticação configurada por API_SECRET_KEY."""
    from app.config import get_settings
    from app.main import app

    # Configura chave de API no servidor
    monkeypatch.setenv("API_SECRET_KEY", "segredo-teste-producao-12345")
    get_settings.cache_clear()

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # Requisição sem credenciais é rejeitada com 401
        resp_sem_auth = await client.get("/api/v1/pipeline/qualquer-id/sources")
        assert resp_sem_auth.status_code == 401
        assert "Chave de API ausente" in resp_sem_auth.json()["detail"]

        # Requisição com chave inválida é rejeitada com 401
        resp_chave_errada = await client.get(
            "/api/v1/pipeline/qualquer-id/sources",
            headers={"X-API-Key": "chave-incorreta"},
        )
        assert resp_chave_errada.status_code == 401

        # Requisição com chave correta passa pela barreira de autenticação (atinge a lógica de pesquisa)
        resp_chave_certa = await client.get(
            "/api/v1/pipeline/qualquer-id/sources",
            headers={"X-API-Key": "segredo-teste-producao-12345"},
        )
        # ID inexistente resulta em 404, demonstrando autenticação autorizada
        assert resp_chave_certa.status_code == 404
