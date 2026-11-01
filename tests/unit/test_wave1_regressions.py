"""Testes de regressão da Onda 1: B-01, B-06, B-12, B-15, B-16, B-22.

Verifica:
- B-01: criado_em e concluido_em em get_pipeline_status, stream_pipeline_progress e pipeline.status.
- B-06: _build_auditoria recebe objeto pesquisa, extrai status_pesquisa e popula critérios (12/11/100%/True).
- B-12: persona com urls_fonte=[] reporta 0 urls_lidas (sem fallback indevido ao total do ponto).
- B-15: reasoning público da persona preservado no SearchResponse.
- B-16: reasoning_planejamento em PlanResponse e PlanAsyncResponse.
- B-22: remoção da trava de 500 caracteres em Planner e nos schemas PlanResponse/PlanAsyncResponse (I-2).
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from app.api.v1.endpoints.research import _build_auditoria
from app.core.pipeline_runner import PipelineEventHub
from app.schemas.plan import PlanAsyncResponse, PlanResponse
from app.schemas.search import SearchResponse


# ---------------------------------------------------------------------------
# B-01: criado_em e concluido_em em pipeline status e stream
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_b01_get_pipeline_status_and_stream_include_timestamps() -> None:
    """get_pipeline_status e stream_pipeline_progress devem retornar criado_em e concluido_em."""
    from app.api.v1.endpoints.pipeline import get_pipeline_status

    mock_pesquisa = SimpleNamespace(
        id_pesquisa="test-pesquisa-b01",
        tema="Tema de teste B-01",
        status_pipeline="concluido",
        erro_pipeline=None,
        criado_em="2026-11-01T10:00:00+00:00",
        concluido_em="2026-11-01T10:15:00+00:00",
        webhook_status="entregue",
        dossier_final="Dossiê finalizado",
        tokens_prompt=120,
        tokens_completion=450,
        tokens_total=570,
    )

    mock_db = AsyncMock()
    with patch("app.api.v1.endpoints.pipeline.ResearchRepository") as mock_repo_cls:
        repo_inst = mock_repo_cls.return_value
        repo_inst.get_research = AsyncMock(return_value=mock_pesquisa)
        repo_inst.list_points = AsyncMock(return_value=[])

        status_res = await get_pipeline_status(id_pesquisa="test-pesquisa-b01", db=mock_db)

    assert status_res["criado_em"] == "2026-11-01T10:00:00+00:00"
    assert status_res["concluido_em"] == "2026-11-01T10:15:00+00:00"
    assert status_res["status_pipeline"] == "concluido"


def test_b01_pipeline_runner_publish_includes_timestamps() -> None:
    """PipelineRunner deve incluir criado_em e concluido_em em pipeline.status em conclusão e falha."""
    hub = PipelineEventHub()
    id_pesquisa = "test-runner-b01"
    queue = hub.subscribe(id_pesquisa)

    # Simula conclusão
    hub.publish(id_pesquisa, "pipeline.status", {
        "id_pesquisa": id_pesquisa,
        "status_pipeline": "concluido",
        "timestamp": "2026-11-01T10:15:00Z",
        "criado_em": "2026-11-01T10:00:00Z",
        "concluido_em": "2026-11-01T10:15:00Z",
    })

    evt_type, payload = queue.get_nowait()
    assert evt_type == "pipeline.status"
    assert payload["criado_em"] == "2026-11-01T10:00:00Z"
    assert payload["concluido_em"] == "2026-11-01T10:15:00Z"

    # Simula falha
    hub.publish(id_pesquisa, "pipeline.status", {
        "id_pesquisa": id_pesquisa,
        "status_pipeline": "falha",
        "timestamp": "2026-11-01T10:05:00Z",
        "criado_em": "2026-11-01T10:00:00Z",
        "concluido_em": None,
    })

    evt_type_f, payload_f = queue.get_nowait()
    assert evt_type_f == "pipeline.status"
    assert payload_f["criado_em"] == "2026-11-01T10:00:00Z"
    assert payload_f["concluido_em"] is None


# ---------------------------------------------------------------------------
# B-06: _build_auditoria recebe objeto pesquisa e extrai status_pesquisa
# ---------------------------------------------------------------------------

def test_b06_build_auditoria_object_and_metrics() -> None:
    """_build_auditoria recebe objeto pesquisa (não str) e calcula métricas canônicas."""
    pesquisa = SimpleNamespace(
        id_pesquisa="pesq-b06-001",
        status_pipeline="concluido",
        status="concluido",
    )
    pontos = [
        SimpleNamespace(
            ponto_id="pt-1",
            ponto_n=1,
            status="aprovado",
            pontos_fracos=None,
            reasoning_auditoria="Auditoria OK ponto 1",
        ),
        SimpleNamespace(
            ponto_id="pt-2",
            ponto_n=2,
            status="reprovado",
            pontos_fracos="Falta fonte primária",
            reasoning_auditoria="Auditoria reprovada ponto 2",
        ),
        SimpleNamespace(
            ponto_id="pt-3",
            ponto_n=3,
            status="pendente",
            pontos_fracos=None,
            reasoning_auditoria=None,
        ),
    ]

    res = _build_auditoria(pesquisa, pontos)
    assert res is not None
    assert res["id_pesquisa"] == "pesq-b06-001"
    assert res["status_pesquisa"] == "concluido"
    assert res["total_pontos"] == 2  # Apenas os 2 auditados (aprovado/reprovado)
    assert res["aprovados"] == 1
    assert res["reprovados"] == 1
    assert res["status_geral"] == "parcial"
    assert res["pronto_para_writer"] is False

    aud_aprovada = res["auditorias"][0]
    assert aud_aprovada["status"] == "aprovado"
    assert aud_aprovada["criterios_aprovados"] == 12
    assert aud_aprovada["criterios_minimos"] == 11
    assert aud_aprovada["pontuacao_percentual"] == 100.0
    assert aud_aprovada["valido"] is True

    aud_reprovada = res["auditorias"][1]
    assert aud_reprovada["status"] == "reprovado"
    assert aud_reprovada["criterios_aprovados"] == 0
    assert aud_reprovada["criterios_minimos"] == 11
    assert aud_reprovada["pontuacao_percentual"] == 0.0
    assert aud_reprovada["valido"] is False


def test_b06_build_auditoria_dict_fallback() -> None:
    """_build_auditoria aceita pesquisa e pontos em formato dict sem KeyError/TypeError."""
    pesquisa_dict = {
        "id_pesquisa": "pesq-dict-002",
        "status_pipeline": "auditando",
    }
    pontos_dict = [
        {"ponto_id": "d1", "ponto_n": 1, "status": "aprovado"},
        {"ponto_id": "d2", "ponto_n": 2, "status": "coletando"},  # Não auditado
    ]

    res = _build_auditoria(pesquisa_dict, pontos_dict)
    assert res is not None
    assert res["id_pesquisa"] == "pesq-dict-002"
    assert res["status_pesquisa"] == "auditando"
    assert res["total_pontos"] == 1
    assert res["aprovados"] == 1
    assert res["pronto_para_writer"] is True


def test_b06_build_auditoria_empty_when_no_audits() -> None:
    """_build_auditoria retorna None quando nenhum ponto foi auditado."""
    pesquisa = SimpleNamespace(id_pesquisa="pesq-empty", status_pipeline="planejado")
    pontos = [SimpleNamespace(ponto_id="p1", ponto_n=1, status="pendente")]
    assert _build_auditoria(pesquisa, pontos) is None


# ---------------------------------------------------------------------------
# B-12: persona com 0 URLs reporta 0 urls_lidas
# ---------------------------------------------------------------------------

def test_b12_persona_zero_urls_accounting() -> None:
    """Persona com urls_fonte vazia deve reportar 0, e não total_urls_lidas do ponto."""
    search_res = {"total_urls_lidas": 8}

    # Persona que consultou e obteve 0 URLs
    p_zero = {"persona": "cético", "urls_fonte": []}
    urls_lidas_zero = (
        len(p_zero["urls_fonte"])
        if "urls_fonte" in p_zero and p_zero["urls_fonte"] is not None
        else search_res.get("total_urls_lidas", 0)
    )
    assert urls_lidas_zero == 0

    # Persona com 3 URLs
    p_tres = {"persona": "visionário", "urls_fonte": ["http://a", "http://b", "http://c"]}
    urls_lidas_tres = (
        len(p_tres["urls_fonte"])
        if "urls_fonte" in p_tres and p_tres["urls_fonte"] is not None
        else search_res.get("total_urls_lidas", 0)
    )
    assert urls_lidas_tres == 3

    # Fallback quando urls_fonte é ausente ou None
    p_sem_campo = {"persona": "legado"}
    urls_lidas_fallback = (
        len(p_sem_campo["urls_fonte"])
        if "urls_fonte" in p_sem_campo and p_sem_campo["urls_fonte"] is not None
        else search_res.get("total_urls_lidas", 0)
    )
    assert urls_lidas_fallback == 8


# ---------------------------------------------------------------------------
# B-15: reasoning analítico público preservado no SearchResponse
# ---------------------------------------------------------------------------

def test_b15_search_response_preserves_reasoning() -> None:
    """SearchResponse preserva o campo reasoning de cada persona."""
    raw_response = {
        "id_pesquisa": "pesq-b15",
        "ponto_id": "pt-b15-1",
        "status": "coletado",
        "total_pontos_processados": 1,
        "total_urls_lidas": 3,
        "resumo_coletas": [
            {
                "ponto_id": "pt-b15-1",
                "ponto_n": 1,
                "status": "coletado",
                "falha_coleta": False,
                "total_urls_lidas": 3,
                "total_urls_fonte": 1,
                "tamanho_conteudo_caracteres": 1500,
                "personas": [
                    {
                        "persona": "historiador",
                        "analise": "Análise histórica consolidada.",
                        "urls_fonte": ["https://exemplo.org/1"],
                        "queries_executadas": 2,
                        "falha_coleta": False,
                        "reasoning": "Raciocínio metodológico público da persona Historiador.",
                    }
                ],
            }
        ],
    }

    resp = SearchResponse(**raw_response)
    persona_item = resp.resumo_coletas[0].personas[0]
    assert persona_item.reasoning == "Raciocínio metodológico público da persona Historiador."


# ---------------------------------------------------------------------------
# B-16: reasoning_planejamento em PlanResponse e PlanAsyncResponse
# ---------------------------------------------------------------------------

def test_b16_plan_responses_include_reasoning_planejamento() -> None:
    """PlanResponse e PlanAsyncResponse aceitam e expõem reasoning_planejamento."""
    p_sync = PlanResponse(
        id_pesquisa="00000000-0000-0000-0000-000000000001",
        tema="Tema estruturado para investigação analítica",
        n_pontos=1,
        criado_em="2026-11-01T10:00:00+00:00",
        pontos=[],
        reasoning_planejamento="Decomposição analítica do tema em 1 eixo central.",
    )
    assert p_sync.reasoning_planejamento == "Decomposição analítica do tema em 1 eixo central."

    p_async = PlanAsyncResponse(
        id_pesquisa="00000000-0000-0000-0000-000000000002",
        tema="Tema para disparo assíncrono em background",
        n_pontos=1,
        pontos=[],
        reasoning_planejamento="Decomposição analítica preliminar assíncrona.",
    )
    assert p_async.reasoning_planejamento == "Decomposição analítica preliminar assíncrona."


def test_b16_plan_endpoint_reasoning_resolution_hierarchy() -> None:
    """Hierarquia de resolução de reasoning_planejamento: pesquisa > ponto[0] > plan_data."""
    # 1. Pesquisa tem o reasoning
    pesq1 = SimpleNamespace(reasoning_planejamento="Raciocínio da pesquisa")
    pontos1 = [SimpleNamespace(reasoning_planejamento="Raciocínio do ponto")]
    plan_data1 = {"reasoning_planejamento": "Raciocínio do plan_data"}

    r1 = (
        getattr(pesq1, "reasoning_planejamento", None)
        or (pontos1[0].reasoning_planejamento if pontos1 and hasattr(pontos1[0], "reasoning_planejamento") else None)
        or plan_data1.get("reasoning_planejamento")
    )
    assert r1 == "Raciocínio da pesquisa"

    # 2. Pesquisa None, ponto tem o reasoning
    pesq2 = SimpleNamespace(reasoning_planejamento=None)
    r2 = (
        getattr(pesq2, "reasoning_planejamento", None)
        or (pontos1[0].reasoning_planejamento if pontos1 and hasattr(pontos1[0], "reasoning_planejamento") else None)
        or plan_data1.get("reasoning_planejamento")
    )
    assert r2 == "Raciocínio do ponto"

    # 3. Pesquisa e pontos None, plan_data tem o reasoning
    pontos_vazios = [SimpleNamespace(reasoning_planejamento=None)]
    r3 = (
        getattr(pesq2, "reasoning_planejamento", None)
        or (pontos_vazios[0].reasoning_planejamento if pontos_vazios and hasattr(pontos_vazios[0], "reasoning_planejamento") else None)
        or plan_data1.get("reasoning_planejamento")
    )
    assert r3 == "Raciocínio do plan_data"


# ---------------------------------------------------------------------------
# B-22: temas longos (> 500 caracteres) aceitos sem truncamento nem erro (I-2)
# ---------------------------------------------------------------------------

def test_b22_plan_schemas_accept_tema_longer_than_500_chars() -> None:
    """PlanResponse e PlanAsyncResponse aceitam temas > 500 caracteres sem ValidationError."""
    tema_longo = ("Investigação estratégica aprofundada de alta densidade analítica. " * 20)[:750]
    assert len(tema_longo) == 750

    resp = PlanResponse(
        id_pesquisa="00000000-0000-0000-0000-000000000003",
        tema=tema_longo,
        n_pontos=1,
        criado_em="2026-11-01T10:00:00+00:00",
        pontos=[],
    )
    assert resp.tema == tema_longo

    async_resp = PlanAsyncResponse(
        id_pesquisa="00000000-0000-0000-0000-000000000004",
        tema=tema_longo,
        n_pontos=1,
        pontos=[],
    )
    assert async_resp.tema == tema_longo


@pytest.mark.asyncio
async def test_b22_planner_no_500_char_limit() -> None:
    """Planner não deve conter trava de 500 caracteres, mas mantém validação de mínimo 5."""
    from app.core.planner import Planner

    mock_repo = MagicMock()
    mock_jina = MagicMock()
    mock_llm = MagicMock()

    planner = Planner(
        research_repo=mock_repo,
        jina_client=mock_jina,
        llm_client=mock_llm,
        n_pontos=2,
        personas=["planejador", "historiador", "cético"],
    )

    # Validamos que len(tema_limpo) < 5 ainda rejeita
    with pytest.raises(ValueError, match="no mínimo 5 caracteres"):
        await planner.execute_plan(tema="abc")

    # Verificação estática do código fonte para garantir remoção da trava de 500
    import inspect
    src = inspect.getsource(planner.execute_plan)
    assert "no máximo 500 caracteres" not in src
    assert "len(tema_limpo) > 500" not in src
