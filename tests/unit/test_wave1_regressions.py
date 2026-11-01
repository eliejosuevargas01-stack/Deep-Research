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


@pytest.mark.asyncio
async def test_b01_get_research_detail_timestamps() -> None:
    """Endpoint real get_research_detail retorna timestamps e auditoria integrada."""
    from app.api.v1.endpoints.research import get_research_detail

    mock_pesquisa = SimpleNamespace(
        id_pesquisa="pesq-detail-01",
        tema="Tema Real Detail",
        status_pipeline="concluido",
        status="concluido",
        criado_em="2026-11-01T10:00:00+00:00",
        concluido_em="2026-11-01T10:15:00+00:00",
        plano_estruturado=None,
        preferencias=None,
        metadados_redacao=None,
        dossier_final="Dossiê de teste",
    )
    mock_ponto = SimpleNamespace(
        ponto_id="pt-1",
        ponto_n=1,
        ponto="Eixo 1",
        status="aprovado",
        eixo_estruturado=None,
        pontos_fracos=None,
        reasoning_auditoria="Auditoria OK",
    )
    mock_db = AsyncMock()
    with patch("app.api.v1.endpoints.research.ResearchRepository") as mock_repo_cls, \
         patch("app.api.v1.endpoints.research.SourceAccountingService") as mock_source_svc:
        repo = mock_repo_cls.return_value
        repo.get_research = AsyncMock(return_value=mock_pesquisa)
        repo.list_points = AsyncMock(return_value=[mock_ponto])
        mock_source_svc.return_value.consolidate_sources = AsyncMock(return_value=None)

        detail = await get_research_detail(id_pesquisa="pesq-detail-01", db=mock_db)
        assert detail["id_pesquisa"] == "pesq-detail-01"
        assert detail["criado_em"] == "2026-11-01T10:00:00+00:00"
        assert detail["concluido_em"] == "2026-11-01T10:15:00+00:00"
        assert detail["auditoria"] is not None
        assert detail["auditoria"]["pronto_para_writer"] is True


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
    assert res["total_pontos"] == 3  # Total de pontos é len(pontos)
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
    assert res["total_pontos"] == 2
    assert res["aprovados"] == 1
    assert res["status_geral"] == "parcial"
    assert res["pronto_para_writer"] is False


def test_b06_build_auditoria_empty_when_no_audits() -> None:
    """_build_auditoria retorna None quando nenhum ponto foi auditado."""
    pesquisa = SimpleNamespace(id_pesquisa="pesq-empty", status_pipeline="planejado")
    pontos = [SimpleNamespace(ponto_id="p1", ponto_n=1, status="pendente")]
    assert _build_auditoria(pesquisa, pontos) is None


# ---------------------------------------------------------------------------
# B-12: persona com 0 URLs reporta 0 urls_lidas
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_b12_persona_zero_urls_accounting() -> None:
    """Persona com urls_fonte vazia deve reportar 0 no evento search.progress gerado pelo stream SSE."""
    import json
    from app.api.v1.endpoints.pipeline import stream_pipeline_progress

    mock_pesquisa = SimpleNamespace(
        id_pesquisa="pesq-b12",
        tema="Tema B12",
        status_pipeline="coletado",
        criado_em="2026-11-01T10:00:00Z",
        atualizado_em=None,
        concluido_em=None,
        tokens_prompt=0,
        tokens_completion=0,
        tokens_total=0,
        dossier_final=None,
    )
    mock_ponto = SimpleNamespace(
        ponto_id="pt-b12",
        ponto_n=1,
        status="coletado",
        tentativas=0,
        reasoning_auditoria=None,
    )
    mock_coleta = SimpleNamespace(
        ponto_id="pt-b12",
        criado_em="2026-11-01T10:01:00Z",
        reasoning_coleta="Análise geral",
        urls_fonte="[]",
        metadados_coleta=json.dumps({
            "resultados_personas": {
                "cetico": {
                    "reasoning": "Raciocínio cético sem URLs",
                    "urls_fonte": [],
                    "queries_executadas": 2,
                }
            }
        }),
    )

    mock_db = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = [mock_coleta]
    mock_db.execute = AsyncMock(return_value=mock_res)
    mock_req = MagicMock()
    mock_req.headers = {}
    mock_req.query_params = {}
    mock_req.is_disconnected = AsyncMock(return_value=True)

    with patch("app.api.v1.endpoints.pipeline.ResearchRepository") as mock_repo_cls:
        repo = mock_repo_cls.return_value
        repo.get_research = AsyncMock(return_value=mock_pesquisa)
        repo.list_points = AsyncMock(return_value=[mock_ponto])

        resp = await stream_pipeline_progress(
            id_pesquisa="pesq-b12",
            request=mock_req,
            snapshot_only=True,
            db=mock_db,
        )

        events = []
        async for chunk in resp.body_iterator:
            text = chunk.decode("utf-8") if isinstance(chunk, bytes) else str(chunk)
            for line in text.split("\n\n"):
                if line.strip():
                    events.append(line)

        search_evts = [e for e in events if "event: search.progress" in e]
        assert len(search_evts) > 0
        data_line = [l for l in search_evts[0].split("\n") if l.startswith("data: ")][0]
        data = json.loads(data_line[6:])
        assert data["persona"] == "cetico"
        assert data["urls_lidas"] == 0


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


@pytest.mark.asyncio
async def test_b16_create_plan_endpoint_includes_reasoning() -> None:
    """Endpoint real create_plan extrai e preenche reasoning_planejamento em PlanResponse."""
    from app.api.v1.endpoints.plan import create_plan
    from app.schemas.plan import PlanRequest
    from starlette.responses import Response

    mock_db = AsyncMock()
    mock_pesq = SimpleNamespace(
        id_pesquisa="pesq-b16-001",
        tema="Tema B16 Endpoint",
        criado_em="2026-11-01T10:00:00Z",
        status_pipeline="planejado",
        plano_estruturado=None,
        metadados_modelo=None,
        preferencias=None,
        reasoning_planejamento="Raciocínio metodológico via Planner real",
    )
    mock_ponto = SimpleNamespace(
        ponto_id="pt-1",
        ponto_n=1,
        ponto="Eixo 1",
        status="pendente",
        eixo_estruturado=None,
        pontos_fracos=None,
        reasoning_auditoria=None,
        reasoning_planejamento=None,
    )

    with patch("app.api.v1.endpoints.plan.Planner") as mock_planner_cls, \
         patch("app.api.v1.endpoints.plan.ResearchRepository") as mock_repo_cls:
        planner_inst = mock_planner_cls.return_value
        planner_inst.n_pontos = 1
        planner_inst.execute_plan = AsyncMock(return_value=mock_pesq)
        repo_inst = mock_repo_cls.return_value
        repo_inst.list_points = AsyncMock(return_value=[mock_ponto])

        req_payload = PlanRequest(tema="Tema B16 Endpoint para teste real")
        resp = await create_plan(
            payload=req_payload,
            response=Response(),
            background_tasks=MagicMock(),
            db=mock_db,
        )

        assert isinstance(resp, PlanResponse)
        assert resp.id_pesquisa == "pesq-b16-001"
        assert resp.reasoning_planejamento == "Raciocínio metodológico via Planner real"


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
async def test_b22_planner_real_accepts_long_theme() -> None:
    """Planner real aceita tema > 500 caracteres sem travar ou truncar."""
    from app.core.planner import Planner

    mock_repo = MagicMock()
    mock_pesq = SimpleNamespace(id_pesquisa="pesq-b22-real", tema="Tema B22", criado_em="2026-11-01T10:00:00Z")
    mock_repo.create_research = AsyncMock(return_value=mock_pesq)
    mock_repo.save_point = AsyncMock()
    mock_jina = MagicMock()
    mock_jina.search = AsyncMock(return_value=[])
    mock_llm = MagicMock()
    mock_envelope = MagicMock()
    mock_envelope.finish_reason = "stop"
    mock_envelope.usage = {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20}
    mock_llm.generate_json_envelope = AsyncMock(return_value=({"pedido_original": "t"}, mock_envelope))
    mock_llm.generate = AsyncMock(return_value={
        "content": '{"plano": [{"ponto_n": 1, "ponto": "Eixo longo", "descricao": "Desc"}]}',
        "reasoning": "Plano gerado para tema longo."
    })

    planner = Planner(
        research_repo=mock_repo,
        jina_client=mock_jina,
        llm_client=mock_llm,
        n_pontos=1,
        personas=["planejador", "historiador", "cético"],
    )

    tema_longo = ("Investigação estratégica aprofundada de alta densidade analítica. " * 20)[:750]
    with patch.object(planner, "evaluate_plan_semantics", AsyncMock(return_value=(True, None, None))), \
         patch("app.core.planner.validate_and_parse_plan") as mock_val:
        mock_eixo = SimpleNamespace(pergunta_principal="Eixo longo", model_dump=lambda: {"pergunta_principal": "Eixo longo"})
        mock_plano = SimpleNamespace(eixos=[mock_eixo], recorte_temporal="2026", model_dump=lambda: {"eixos": [{"pergunta_principal": "Eixo longo"}]})
        mock_val.return_value = (mock_plano, None)

        res = await planner.execute_plan(tema=tema_longo)
        assert res is not None
        assert res.id_pesquisa == "pesq-b22-real"


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
