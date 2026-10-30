"""Testes de integração para contratos de preferências por pesquisa e persistência de snapshot.

Valida:
1. Validação estrita Pydantic v2 de n_pontos (inteiro positivo estrito; rejeição de bool e float).
2. Validação estrita de personas (subconjunto não vazio e único das 4 personas de busca; rejeição de roles internos como planejador).
3. Resposta de /api/v1/plan com eco de preferências efetivas em preferencias: {n_pontos, personas}.
4. Quantidade de pontos no plano gerado respeita rigorosamente n_pontos selecionado.
5. Persistência do snapshot de preferências em metadados_planejamento JSON sem nova migração de coluna.
6. Preservação de metadados do modelo (tokens, latência, envelopes observáveis) em metadados_planejamento.
7. Execução subsequente de /api/v1/search respeita o snapshot armazenado na pesquisa quando personas não for fornecido.
8. Execução subsequente de /api/v1/search respeita subconjunto explícito válido quando fornecido.
9. Isolamento total entre pesquisas diferentes sem contaminação cruzada ou mutação de env global.
10. Proteção e mascaramento de credenciais sem vazamento de segredos em respostas JSON.
"""

import json
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from app.db.research_repository import ResearchRepository
from app.db.session import get_engine, get_sessionmaker
from app.main import app
from app.schemas.plan import PlanRequest, PlanResponse


@pytest_asyncio.fixture(autouse=True)
async def setup_integration():
    """Garante ambiente de teste isolado e banco inicializado."""
    from app.main import _setup_integration_test_env
    _setup_integration_test_env()
    from app.db.init_db import init_db
    from app.db.session import get_engine
    await init_db(get_engine())


# ==============================================================================
# 1. Validação Pydantic Unitária e Sintática de PlanRequest
# ==============================================================================

def test_plan_request_pydantic_accepts_valid_strict_integers():
    """PlanRequest aceita inteiros estritos positivos."""
    req1 = PlanRequest(tema="Impacto da Inteligência Artificial", n_pontos=1)
    assert req1.n_pontos == 1

    req3 = PlanRequest(tema="Impacto da Inteligência Artificial", n_pontos=3)
    assert req3.n_pontos == 3

    req5 = PlanRequest(tema="Impacto da Inteligência Artificial", n_pontos=5)
    assert req5.n_pontos == 5


def test_plan_request_pydantic_rejects_bool_for_n_pontos():
    """PlanRequest rejeita estritamente booleano para n_pontos (True ou False)."""
    with pytest.raises(ValidationError) as exc:
        PlanRequest(tema="Impacto da Inteligência Artificial", n_pontos=True)  # type: ignore
    assert "booleano" in str(exc.value).lower() or "n_pontos" in str(exc.value)

    with pytest.raises(ValidationError) as exc:
        PlanRequest(tema="Impacto da Inteligência Artificial", n_pontos=False)  # type: ignore
    assert "booleano" in str(exc.value).lower() or "n_pontos" in str(exc.value)


def test_plan_request_pydantic_rejects_float_for_n_pontos():
    """PlanRequest rejeita estritamente números de ponto flutuante para n_pontos."""
    with pytest.raises(ValidationError) as exc:
        PlanRequest(tema="Impacto da Inteligência Artificial", n_pontos=3.0)  # type: ignore
    assert "float" in str(exc.value).lower() or "n_pontos" in str(exc.value)

    with pytest.raises(ValidationError) as exc:
        PlanRequest(tema="Impacto da Inteligência Artificial", n_pontos=2.5)  # type: ignore
    assert "float" in str(exc.value).lower() or "n_pontos" in str(exc.value)


def test_plan_request_pydantic_rejects_non_positive_n_pontos():
    """PlanRequest rejeita valores zero ou negativos para n_pontos."""
    with pytest.raises(ValidationError):
        PlanRequest(tema="Impacto da Inteligência Artificial", n_pontos=0)

    with pytest.raises(ValidationError):
        PlanRequest(tema="Impacto da Inteligência Artificial", n_pontos=-3)


def test_plan_request_pydantic_accepts_valid_personas_subsets():
    """PlanRequest aceita subconjuntos válidos das 4 personas analíticas de busca."""
    p1 = PlanRequest(tema="Impacto da Inteligência Artificial", personas=["historiador"])
    assert p1.personas == ["historiador"]

    p2 = PlanRequest(tema="Impacto da Inteligência Artificial", personas=["visionario", "cetico"])
    assert p2.personas == ["visionario", "cetico"]

    p4 = PlanRequest(
        tema="Impacto da Inteligência Artificial",
        personas=["historiador", "visionario", "cetico", "futurista"],
    )
    assert p4.personas == ["historiador", "visionario", "cetico", "futurista"]


def test_plan_request_pydantic_rejects_invalid_personas():
    """PlanRequest rejeita lista vazia, duplicatas, persona inexistente e papéis internos do sistema."""
    # Lista vazia
    with pytest.raises(ValidationError):
        PlanRequest(tema="Impacto da Inteligência Artificial", personas=[])

    # Duplicata
    with pytest.raises(ValidationError):
        PlanRequest(tema="Impacto da Inteligência Artificial", personas=["historiador", "historiador"])

    # Persona inventada
    with pytest.raises(ValidationError):
        PlanRequest(tema="Impacto da Inteligência Artificial", personas=["alien"])

    # Papéis internos que NÃO são personas de busca
    with pytest.raises(ValidationError):
        PlanRequest(tema="Impacto da Inteligência Artificial", personas=["planejador"])

    with pytest.raises(ValidationError):
        PlanRequest(tema="Impacto da Inteligência Artificial", personas=["auditor"])

    with pytest.raises(ValidationError):
        PlanRequest(tema="Impacto da Inteligência Artificial", personas=["redator final"])


# ==============================================================================
# 2. Rejeição HTTP 422 na API FastAPI para Payloads Inválidos
# ==============================================================================

@pytest.mark.asyncio
async def test_plan_endpoint_rejects_bool_and_float_via_http_422():
    """POST /api/v1/plan rejeita n_pontos booleano ou float com HTTP 422."""
    async with AsyncClient(
        transport=ASGITransport(app=app, client=("127.0.0.1", 53001)),
        base_url="http://localhost:8000",
    ) as client:
        # Booleano True
        r1 = await client.post("/api/v1/plan", json={"tema": "Tema Válido Para Teste", "n_pontos": True})
        assert r1.status_code == 422

        # Float 2.0
        r2 = await client.post("/api/v1/plan", json={"tema": "Tema Válido Para Teste", "n_pontos": 2.0})
        assert r2.status_code == 422

        # Personas vazias
        r3 = await client.post("/api/v1/plan", json={"tema": "Tema Válido Para Teste", "personas": []})
        assert r3.status_code == 422

        # Persona interna do sistema como busca
        r4 = await client.post("/api/v1/plan", json={"tema": "Tema Válido Para Teste", "personas": ["planejador"]})
        assert r4.status_code == 422


# ==============================================================================
# 3. Execução de Plan e Persistência de Snapshot por Pesquisa
# ==============================================================================

@pytest.mark.asyncio
async def test_plan_endpoint_with_omitted_preferences_uses_server_defaults():
    """POST /api/v1/plan sem preferências explícitas retorna e persiste defaults do servidor."""
    async with AsyncClient(
        transport=ASGITransport(app=app, client=("127.0.0.1", 53002)),
        base_url="http://localhost:8000",
    ) as client:
        resp = await client.post(
            "/api/v1/plan",
            json={"tema": "Avanços em Computação Quântica e Criptografia"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "preferencias" in data
        assert data["preferencias"]["n_pontos"] == data["n_pontos"]
        assert isinstance(data["preferencias"]["personas"], list)
        assert len(data["preferencias"]["personas"]) > 0


@pytest.mark.asyncio
async def test_plan_endpoint_with_custom_n_pontos_generates_exact_point_count():
    """POST /api/v1/plan com n_pontos=2 gera exatamente 2 pontos e reflete em preferencias."""
    async with AsyncClient(
        transport=ASGITransport(app=app, client=("127.0.0.1", 53003)),
        base_url="http://localhost:8000",
    ) as client:
        resp = await client.post(
            "/api/v1/plan",
            json={
                "tema": "Avanços em Materiais Supercondutores em Temperatura Ambiente",
                "n_pontos": 2,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["n_pontos"] == 2
        assert len(data["pontos"]) == 2
        assert data["preferencias"]["n_pontos"] == 2


@pytest.mark.asyncio
async def test_preferences_snapshot_persisted_in_metadados_planejamento_json():
    """Valida que o snapshot selecionado é gravado em metadados_planejamento JSON e preserva métricas."""
    async with AsyncClient(
        transport=ASGITransport(app=app, client=("127.0.0.1", 53004)),
        base_url="http://localhost:8000",
    ) as client:
        resp = await client.post(
            "/api/v1/plan",
            json={
                "tema": "Transição Energética e Baterias de Estado Sólido",
                "n_pontos": 2,
                "personas": ["visionario", "cetico"],
            },
        )
        assert resp.status_code == 201
        id_pesquisa = resp.json()["id_pesquisa"]

    # Consulta direta na base SQLite permanente
    session_factory = get_sessionmaker()
    async with session_factory() as db:
        repo = ResearchRepository(session=db)
        pesquisa_db = await repo.get_research(id_pesquisa)
        assert pesquisa_db is not None
        assert pesquisa_db.metadados_planejamento is not None

        meta = json.loads(pesquisa_db.metadados_planejamento)
        assert "preferencias" in meta, "preferencias deve constar em metadados_planejamento JSON"
        assert meta["preferencias"]["n_pontos"] == 2
        assert meta["preferencias"]["personas"] == ["visionario", "cetico"]

        # Confirma que metadados observáveis do modelo foram preservados
        assert "model_requested" in meta
        assert "latency_seconds_total" in meta
        assert "attempts_summary" in meta


# ==============================================================================
# 4. Busca Subsequente (/search) com Respeito a Snapshot e Isolamento
# ==============================================================================

@pytest.mark.asyncio
async def test_search_honors_stored_snapshot_when_personas_omitted():
    """POST /api/v1/search sem campo personas executa rigorosamente as personas do snapshot da pesquisa."""
    async with AsyncClient(
        transport=ASGITransport(app=app, client=("127.0.0.1", 53005)),
        base_url="http://localhost:8000",
    ) as client:
        # 1. Cria pesquisa A com persona exclusiva ['cetico']
        r_plan_a = await client.post(
            "/api/v1/plan",
            json={
                "tema": "Segurança de Redes Neurais e Ataques Adversariais",
                "n_pontos": 1,
                "personas": ["cetico"],
            },
        )
        assert r_plan_a.status_code == 201
        id_a = r_plan_a.json()["id_pesquisa"]

        # 2. Cria pesquisa B com personas ['historiador', 'visionario']
        r_plan_b = await client.post(
            "/api/v1/plan",
            json={
                "tema": "História e Futuro da Exploração Espacial Comercial",
                "n_pontos": 1,
                "personas": ["historiador", "visionario"],
            },
        )
        assert r_plan_b.status_code == 201
        id_b = r_plan_b.json()["id_pesquisa"]

        # 3. Executa busca para Pesquisa A sem passar personas no payload
        r_search_a = await client.post("/api/v1/search", json={"id_pesquisa": id_a})
        assert r_search_a.status_code == 200
        coletas_a = r_search_a.json()["resumo_coletas"][0]["personas"]
        personas_executadas_a = [p["persona"] for p in coletas_a]
        assert personas_executadas_a == ["cetico"], "Pesquisa A deveria executar exclusivamente o snapshot ['cetico']!"

        # 4. Executa busca para Pesquisa B sem passar personas no payload
        r_search_b = await client.post("/api/v1/search", json={"id_pesquisa": id_b})
        assert r_search_b.status_code == 200
        coletas_b = r_search_b.json()["resumo_coletas"][0]["personas"]
        personas_executadas_b = [p["persona"] for p in coletas_b]
        assert sorted(personas_executadas_b) == sorted(["historiador", "visionario"]), (
            "Pesquisa B deveria executar o snapshot ['historiador', 'visionario']!"
        )


@pytest.mark.asyncio
async def test_search_honors_explicit_valid_requested_subset():
    """POST /api/v1/search com personas explícito honra o subconjunto solicitado."""
    async with AsyncClient(
        transport=ASGITransport(app=app, client=("127.0.0.1", 53006)),
        base_url="http://localhost:8000",
    ) as client:
        # Cria plano com 2 personas
        r_plan = await client.post(
            "/api/v1/plan",
            json={
                "tema": "Impactos Éticos da Biotecnologia CRISPR",
                "n_pontos": 1,
                "personas": ["historiador", "visionario"],
            },
        )
        assert r_plan.status_code == 201
        id_pesq = r_plan.json()["id_pesquisa"]

        # Executa busca fornecendo explicitamente apenas ['visionario']
        r_search = await client.post(
            "/api/v1/search",
            json={"id_pesquisa": id_pesq, "personas": ["visionario"]},
        )
        assert r_search.status_code == 200
        coletas = r_search.json()["resumo_coletas"][0]["personas"]
        personas_executadas = [p["persona"] for p in coletas]
        assert personas_executadas == ["visionario"]


# ==============================================================================
# 5. Segurança de Credenciais e Não Exposição de Segredos
# ==============================================================================

@pytest.mark.asyncio
async def test_no_secret_keys_or_tokens_leaked_in_json_responses():
    """Verifica que chaves de API e segredos nunca são vazados nas respostas públicas."""
    async with AsyncClient(
        transport=ASGITransport(app=app, client=("127.0.0.1", 53007)),
        base_url="http://localhost:8000",
    ) as client:
        # 1. GET /app/session
        r_sess = await client.get("/app/session")
        assert r_sess.status_code == 200
        text_sess = r_sess.text
        assert "api_secret" not in text_sess.lower()
        assert "master_key" not in text_sess.lower()
        assert "sk-" not in text_sess

        # 2. POST /api/v1/plan (autenticado pela sessão do navegador obtida em 1 com Origin da mesma origem)
        r_plan = await client.post(
            "/api/v1/plan",
            json={"tema": "Investigação com Verificação de Segurança de Envelopes"},
            headers={"Origin": "http://localhost:8000"},
        )
        assert r_plan.status_code == 201
        text_plan = r_plan.text
        assert "sk-" not in text_plan
        assert "master_key" not in text_plan.lower()
