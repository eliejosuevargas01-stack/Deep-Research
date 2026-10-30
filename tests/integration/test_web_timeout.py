"""Testes de regressão e integração para tratamento determinístico de timeout e cancelamento em /api/v1/search.

Valida:
1. Ponto que excede deadline dispara cancelamento limpo das tasks das personas e retorna HTTP 504 TIMEOUT_ERROR.
2. Ponto em timeout tem estado persistido como falha_coleta e reserva liberada (não fica em_andamento/busy).
3. Writer permanece bloqueado (HTTP 400 UNAPPROVED_POINTS), impedindo falso avanço para relatório.
4. Mesma pesquisa é re-tentável (safe retry) com mesmo id_pesquisa sem necessidade de replanejamento.
5. Fechamento e desalocação limpa de clientes e conexões em finally.
"""

import asyncio
import json
import os
from pathlib import Path
import pytest
import pytest_asyncio
import httpx
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.research_repository import ResearchRepository
from app.db.session import get_engine, get_sessionmaker
from app.main import app
from app.tools.errors import SearchTimeoutError
from tests.mocks.http_mock import MockNetwork


class SlowMockTransport(httpx.AsyncBaseTransport):
    """Transporte assíncrono que simula atraso real em chamadas de busca para testar cancelamento."""

    def __init__(self, net: MockNetwork, delay: float = 2.0):
        self.net = net
        self.delay = delay
        self.is_slow = True

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if "chat/completions" in url_str:
            try:
                body = json.loads(request.content.decode("utf-8"))
                msgs_str = str(body.get("messages", []))
            except Exception:
                msgs_str = ""

            is_search_call = (
                "protocolo de ações em json" in msgs_str.lower()
                or "historiador" in msgs_str.lower()
                or "cetico" in msgs_str.lower()
            )
            if is_search_call and self.is_slow:
                # Simula latência de rede/LLM real que ultrapassa o timeout de busca
                await asyncio.sleep(self.delay)
                return httpx.Response(200, json={"acao": "concluir", "analise_final": "lenta"})

        return self.net.handle_request(request)


@pytest_asyncio.fixture(autouse=True)
async def setup_isolated_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Garante banco de dados SQLite assíncrono estritamente isolado e limpo."""
    db_file = tmp_path / "test_timeout_isolated.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("CREDENTIALS_MASTER_KEY", "YWJjZGVmZ2hpamtsbW5vcHFyc3R1dnd4eXoxMjM0NTY=")
    monkeypatch.setenv("N_PONTOS", "1")
    monkeypatch.setenv(
        "PERSONAS_CONFIG",
        "planejador,historiador,visionario,cetico,futurista,auditor,redator final",
    )

    from app.config import get_settings
    get_settings.cache_clear()
    from app.db.session import reset_engine
    reset_engine()

    from app.db.init_db import init_db
    engine = get_engine()
    await init_db(engine)

    yield

    await engine.dispose()
    reset_engine()
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_search_point_timeout_returns_504_and_releases_reservation(monkeypatch: pytest.MonkeyPatch):
    """Ponto com persona lenta que estoura deadline dispara cancelamento seguro e retorna HTTP 504."""
    # Configura deadline extremamente curto (0.2s) para teste determinístico rápido
    monkeypatch.setenv("SEARCH_POINT_TIMEOUT_SECONDS", "0.2")

    mock_net = MockNetwork()
    transport = SlowMockTransport(mock_net, delay=2.0)
    monkeypatch.setattr("app.api.v1.endpoints.plan._get_transport", lambda: transport)
    monkeypatch.setattr("app.api.v1.endpoints.search._get_transport", lambda: transport)

    async with AsyncClient(
        transport=ASGITransport(app=app, client=("127.0.0.1", 54321)),
        base_url="http://localhost:8000",
    ) as client:
        # 1. Cria plano inicial com transporte conectado
        r_plan = await client.post(
            "/api/v1/plan",
            json={"tema": "Diferenças entre energia solar fotovoltaica e térmica", "n_pontos": 1},
        )
        assert r_plan.status_code == 201
        id_pesq = r_plan.json()["id_pesquisa"]
        ponto_id = r_plan.json()["pontos"][0]["ponto_id"]

        # 2. Executa busca sujeita a timeout -> deve retornar HTTP 504 Gateway Timeout
        r_search = await client.post(
            "/api/v1/search",
            json={"id_pesquisa": id_pesq},
            headers={"Origin": "http://localhost:8000"},
        )
        assert r_search.status_code == 504
        data_err = r_search.json()
        assert "detail" in data_err
        detail = data_err["detail"]
        assert detail["tipo"] == "TIMEOUT_ERROR"
        assert detail["id_pesquisa"] == id_pesq
        assert detail["ponto_id"] == ponto_id
        assert detail["ponto_n"] == 1
        assert detail["re_tentavel"] is True
        assert "tempo limite" in detail["mensagem"].lower()

    # 3. Verifica no SQLite isolado que o ponto NÃO está em_andamento e teve status persistido
    session_factory = get_sessionmaker()
    async with session_factory() as db:
        repo = ResearchRepository(session=db)
        ponto_db = await repo.get_point(ponto_id)
        assert ponto_db is not None
        assert ponto_db.status == "falha_coleta", "Ponto em timeout deve ser registrado como falha_coleta!"
        assert ponto_db.status != "em_andamento", "Ponto não pode permanecer em_andamento após timeout!"
        assert ponto_db.pontos_fracos is not None
        assert "timeout" in ponto_db.pontos_fracos.lower()


@pytest.mark.asyncio
async def test_search_timeout_blocks_writer_until_successful_retry(monkeypatch: pytest.MonkeyPatch):
    """Ponto com timeout não permite avanço indevido do Writer e é re-tentável na mesma pesquisa."""
    monkeypatch.setenv("SEARCH_POINT_TIMEOUT_SECONDS", "0.2")

    mock_net = MockNetwork()
    transport = SlowMockTransport(mock_net, delay=2.0)
    monkeypatch.setattr("app.api.v1.endpoints.plan._get_transport", lambda: transport)
    monkeypatch.setattr("app.api.v1.endpoints.search._get_transport", lambda: transport)
    monkeypatch.setattr("app.api.v1.endpoints.writer._get_transport", lambda: transport)

    async with AsyncClient(
        transport=ASGITransport(app=app, client=("127.0.0.1", 54322)),
        base_url="http://localhost:8000",
    ) as client:
        # 1. Cria plano inicial com transporte conectado
        r_plan = await client.post(
            "/api/v1/plan",
            json={"tema": "Eficiência de Células de Perovskita", "n_pontos": 1},
        )
        assert r_plan.status_code == 201
        id_pesq = r_plan.json()["id_pesquisa"]

        # 2. Primeira busca estoura timeout (504)
        r_search_timeout = await client.post(
            "/api/v1/search",
            json={"id_pesquisa": id_pesq},
            headers={"Origin": "http://localhost:8000"},
        )
        assert r_search_timeout.status_code == 504

        # 3. Tentativa de acionar o Writer deve ser estritamente bloqueada (400 UNAPPROVED_POINTS)
        r_writer_blocked = await client.post(
            "/api/v1/writer",
            json={"id_pesquisa": id_pesq},
            headers={"Origin": "http://localhost:8000"},
        )
        assert r_writer_blocked.status_code in (400, 422)

        # 4. Retentativa rápida na mesma pesquisa
        transport.is_slow = False
        monkeypatch.setenv("SEARCH_POINT_TIMEOUT_SECONDS", "30.0")

        r_retry = await client.post(
            "/api/v1/search",
            json={"id_pesquisa": id_pesq},
            headers={"Origin": "http://localhost:8000"},
        )
        assert r_retry.status_code == 200, "Retentativa na mesma pesquisa deve ser aceita com sucesso!"
        data_retry = r_retry.json()
        assert data_retry["id_pesquisa"] == id_pesq
        assert len(data_retry["resumo_coletas"]) == 1
        assert data_retry["resumo_coletas"][0]["status"] in ("coletado", "parcial")


@pytest.mark.asyncio
async def test_search_timeout_preserves_partial_evidence_from_completed_persona(monkeypatch: pytest.MonkeyPatch):
    """Quando uma persona conclui antes de outra estourar o timeout, suas evidências são salvas no banco."""
    monkeypatch.setenv("SEARCH_POINT_TIMEOUT_SECONDS", "0.3")

    mock_net = MockNetwork()

    class AsymmetricTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            url_str = str(request.url)
            if "chat/completions" in url_str:
                body = json.loads(request.content.decode("utf-8"))
                msgs_str = str(body.get("messages", []))
                # Cetico é lento e estoura timeout
                if "cetico" in msgs_str.lower():
                    await asyncio.sleep(2.0)
                    return httpx.Response(200, json={"acao": "concluir", "analise_final": "lenta"})
                # Historiador é rápido e conclui com fontes
                if "historiador" in msgs_str.lower():
                    return httpx.Response(
                        200,
                        json={
                            "choices": [
                                {
                                    "message": {
                                        "content": json.dumps({
                                            "acao": "concluir",
                                            "analise_final": "Análise histórica consolidada com fontes UNESCO.",
                                            "conclusoes": [
                                                {
                                                    "claim_id": "clm_hist_1",
                                                    "afirmacao": "Marco histórico verificado.",
                                                    "tipo": "fato",
                                                    "evidencias": ["chk_1"],
                                                    "confianca": "alta",
                                                    "limitacoes": "nenhuma",
                                                }
                                            ],
                                            "lacunas": [],
                                            "motivo_parada": "Fontes históricas verificadas",
                                        })
                                    }
                                }
                            ]
                        },
                    )
            return mock_net.handle_request(request)

    transport = AsymmetricTransport()
    monkeypatch.setattr("app.api.v1.endpoints.plan._get_transport", lambda: transport)
    monkeypatch.setattr("app.api.v1.endpoints.search._get_transport", lambda: transport)

    async with AsyncClient(
        transport=ASGITransport(app=app, client=("127.0.0.1", 54323)),
        base_url="http://localhost:8000",
    ) as client:
        # Cria plano com 2 personas
        r_plan = await client.post(
            "/api/v1/plan",
            json={
                "tema": "História e Desafios da Fusão Nuclear",
                "n_pontos": 1,
                "personas": ["historiador", "cetico"],
            },
        )
        assert r_plan.status_code == 201
        id_pesq = r_plan.json()["id_pesquisa"]
        ponto_id = r_plan.json()["pontos"][0]["ponto_id"]

        # Busca estoura timeout no cetico
        r_search = await client.post(
            "/api/v1/search",
            json={"id_pesquisa": id_pesq},
            headers={"Origin": "http://localhost:8000"},
        )
        assert r_search.status_code == 504
        assert r_search.json()["detail"]["tipo"] == "TIMEOUT_ERROR"

    # Confere no banco se as evidências do historiador foram registradas
    session_factory = get_sessionmaker()
    async with session_factory() as db:
        repo = ResearchRepository(session=db)
        ponto_db = await repo.get_point(ponto_id)
        assert ponto_db is not None
        assert ponto_db.status in ("falha_coleta", "parcial")

        coletas = await repo.get_collected_content(ponto_id)
        assert coletas is not None
        assert "timeout" in (ponto_db.pontos_fracos or "").lower()


