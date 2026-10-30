"""Testes de aceitação para o canal de streaming SSE e propagação de reasoning em tempo real.

Atende ao Entregável 2 / Checkpoint 2:
- Validação de formato W3C SSE (event, data, keep-alive)
- Validação de headers HTTP específicos para streaming (text/event-stream, no-cache, keep-alive, no-buffering)
- Autenticação e autorização por chave de API (header X-API-Key, Authorization Bearer e query param token) e cookie
- Emissão de snapshot inicial do banco de dados (status, pontos, auditoria, coletas, dossiê)
- Propagação em tempo real de eventos e reasonings (search, audit, writer, report)
- Desconexão limpa e cancelamento seguro
"""

import asyncio
import json
import pytest
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import get_settings
from app.core.pipeline_runner import get_pipeline_event_hub
from app.db.research_repository import ResearchRepository
from app.main import app


def parse_sse_events(raw_text: str):
    """Auxiliar para converter bloco de texto SSE em lista de tuplas (event, data)."""
    events = []
    current_event = None
    current_data = []

    for line in raw_text.splitlines():
        line = line.strip()
        if not line:
            if current_event and current_data:
                events.append((current_event, "\n".join(current_data)))
            current_event = None
            current_data = []
        elif line.startswith("event:"):
            current_event = line.replace("event:", "", 1).strip()
        elif line.startswith("data:"):
            current_data.append(line.replace("data:", "", 1).strip())

    if current_event and current_data:
        events.append((current_event, "\n".join(current_data)))

    return events


@pytest.mark.asyncio
async def test_sse_stream_endpoint_404_when_research_not_found(db_session: AsyncSession):
    """Garante retorno HTTP 404 quando o id_pesquisa não existe."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get("/api/v1/pipeline/pesquisa-inexistente-1234/stream")
        assert resp.status_code == 404
        assert "Pesquisa não localizada" in resp.json().get("detail", "")


@pytest.mark.asyncio
async def test_sse_stream_headers_and_snapshot(db_session: AsyncSession):
    """Verifica cabeçalhos HTTP estritos de SSE e entrega do snapshot inicial."""
    repo = ResearchRepository(session=db_session)
    pesquisa = await repo.create_research(
        tema="Impacto da Inteligência Artificial em Saúde",
        pontos_textos=["Diagnóstico por imagem e acurácia clínica"],
        reasoning_planejamento="Raciocínio inicial do planejamento de saúde",
    )
    pontos = await repo.list_points(pesquisa.id_pesquisa)
    p_id = pontos[0].ponto_id

    # Atualiza ponto com auditoria preliminar
    await repo.update_point_status(
        ponto_id=p_id,
        status="aprovado",
        reasoning_auditoria="Auditoria confirmou robustez diagnóstica frente aos 12 critérios.",
    )
    await db_session.commit()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get(f"/api/v1/pipeline/{pesquisa.id_pesquisa}/stream?snapshot_only=true")
        assert resp.status_code == 200

        # Validação de Headers Canônicos W3C SSE
        assert "text/event-stream" in resp.headers.get("content-type", "")
        assert "no-cache" in resp.headers.get("cache-control", "")
        assert resp.headers.get("connection") == "keep-alive"
        assert resp.headers.get("x-accel-buffering") == "no"

        events = parse_sse_events(resp.text)
        event_types = [e[0] for e in events]
        assert "pipeline.status" in event_types
        assert "point.status" in event_types

        # Valida payload do pipeline.status
        status_evt = next(e for e in events if e[0] == "pipeline.status")
        status_data = json.loads(status_evt[1])
        assert status_data["id_pesquisa"] == pesquisa.id_pesquisa
        assert status_data["status_pipeline"] == "planejado"

        # Valida payload do point.status
        pt_evt = next(e for e in events if e[0] == "point.status")
        pt_data = json.loads(pt_evt[1])
        assert pt_data["ponto_id"] == p_id
        assert pt_data["status"] == "aprovado"

        # Valida payload de audit.result do snapshot
        audit_evt = next(e for e in events if e[0] == "audit.result")
        audit_data = json.loads(audit_evt[1])
        assert audit_data["ponto_id"] == p_id
        assert audit_data["status"] == "aprovado"
        assert "Auditoria confirmou robustez" in audit_data["reasoning_auditoria"]


@pytest.mark.asyncio
async def test_sse_stream_authentication(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    """Valida bloqueio sem chave e aceitação via Header X-API-Key, Bearer ou query param token."""
    monkeypatch.setenv("API_SECRET_KEY", "segredo-super-restrito-123")
    get_settings.cache_clear()

    repo = ResearchRepository(session=db_session)
    pesquisa = await repo.create_research(
        tema="Tema Seguro",
        pontos_textos=["Ponto Único"],
    )
    await db_session.commit()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        # 1. Sem credenciais: HTTP 401
        res_unauth = await client.get(f"/api/v1/pipeline/{pesquisa.id_pesquisa}/stream?snapshot_only=true")
        assert res_unauth.status_code == 401

        # 2. Com chave incorreta: HTTP 401
        res_wrong = await client.get(
            f"/api/v1/pipeline/{pesquisa.id_pesquisa}/stream?snapshot_only=true",
            headers={"X-API-Key": "chave-errada"},
        )
        assert res_wrong.status_code == 401

        # 3. Com X-API-Key válida: HTTP 200
        res_valid = await client.get(
            f"/api/v1/pipeline/{pesquisa.id_pesquisa}/stream?snapshot_only=true",
            headers={"X-API-Key": "segredo-super-restrito-123"},
        )
        assert res_valid.status_code == 200

        # 4. Com Authorization Bearer válida: HTTP 200
        res_bearer = await client.get(
            f"/api/v1/pipeline/{pesquisa.id_pesquisa}/stream?snapshot_only=true",
            headers={"Authorization": "Bearer segredo-super-restrito-123"},
        )
        assert res_bearer.status_code == 200

        # 5. Com query param token (vital para navegadores): HTTP 200
        res_token = await client.get(
            f"/api/v1/pipeline/{pesquisa.id_pesquisa}/stream?snapshot_only=true&token=segredo-super-restrito-123",
        )
        assert res_token.status_code == 200


@pytest.mark.asyncio
async def test_sse_stream_live_events_propagation_with_reasonings(db_session: AsyncSession):
    """Testa a propagação em tempo real de eventos emitidos via PipelineEventHub."""
    repo = ResearchRepository(session=db_session)
    pesquisa = await repo.create_research(
        tema="Fusão Nuclear e Energia Limpa",
        pontos_textos=["Confinamento Magnético vs Inercial"],
    )
    await db_session.commit()
    p_id = (await repo.list_points(pesquisa.id_pesquisa))[0].ponto_id

    hub = get_pipeline_event_hub()
    hub.clear(pesquisa.id_pesquisa)

    async def pusher():
        # Aguarda conexão do cliente ser estabelecida
        await asyncio.sleep(0.05)

        # Publica eventos progressivos com reasonings analíticos
        hub.publish(pesquisa.id_pesquisa, "search.progress", {
            "id_pesquisa": pesquisa.id_pesquisa,
            "ponto_id": p_id,
            "persona": "visionario",
            "queries_executadas": 3,
            "urls_lidas": 5,
            "falha_coleta": False,
            "reasoning_coleta": "Raciocínio Visionário: Investigação de reatores estelares e avanços recentes do SPARC.",
        })

        await asyncio.sleep(0.02)
        hub.publish(pesquisa.id_pesquisa, "audit.result", {
            "id_pesquisa": pesquisa.id_pesquisa,
            "ponto_id": p_id,
            "ponto_n": 1,
            "status": "aprovado",
            "pontuacao_percentual": 91.67,
            "criterios_aprovados": 11,
            "reasoning_auditoria": "Raciocínio Auditor: 11 de 12 critérios aprovados com forte embasamento empírico.",
            "pontos_fracos": None,
        })

        await asyncio.sleep(0.02)
        hub.publish(pesquisa.id_pesquisa, "writer.progress", {
            "id_pesquisa": pesquisa.id_pesquisa,
            "status": "redigindo",
            "reasoning_dossier": "Raciocínio Redator: Estruturando síntese comparativa com notas de rodapé canônicas.",
            "total_caracteres": 1500,
        })

        await asyncio.sleep(0.02)
        hub.publish(pesquisa.id_pesquisa, "report.final", {
            "id_pesquisa": pesquisa.id_pesquisa,
            "status": "concluido",
            "dossier_final": "# Dossiê Completo de Fusão Nuclear\nConteúdo rico em evidências.",
            "total_caracteres": 4200,
            "concluido_em": "2026-10-27T14:30:00Z",
        })

    push_task = asyncio.create_task(pusher())

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        # A conexão SSE fecha automaticamente quando recebe report.final
        response = await client.get(f"/api/v1/pipeline/{pesquisa.id_pesquisa}/stream")
        assert response.status_code == 200

    await push_task

    events = parse_sse_events(response.text)
    event_map = {e[0]: json.loads(e[1]) for e in events}

    # 1. search.progress
    assert "search.progress" in event_map
    sp = event_map["search.progress"]
    assert sp["persona"] == "visionario"
    assert sp["queries_executadas"] == 3
    assert "Raciocínio Visionário" in sp["reasoning_coleta"]

    # 2. audit.result
    assert "audit.result" in event_map
    ar = event_map["audit.result"]
    assert ar["status"] == "aprovado"
    assert ar["criterios_aprovados"] == 11
    assert "Raciocínio Auditor" in ar["reasoning_auditoria"]

    # 3. writer.progress
    assert "writer.progress" in event_map
    wp = event_map["writer.progress"]
    assert wp["status"] == "redigindo"
    assert "Raciocínio Redator" in wp["reasoning_dossier"]

    # 4. report.final
    assert "report.final" in event_map
    rf = event_map["report.final"]
    assert rf["status"] == "concluido"
    assert rf["total_caracteres"] == 4200
    assert "# Dossiê Completo" in rf["dossier_final"]


@pytest.mark.asyncio
async def test_pipeline_runner_dispatches_canonical_events_to_hub(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    """Comprova que o PipelineRunner emite todos os eventos canônicos ao hub com seus respectivos reasonings."""
    from app.core.pipeline_runner import PipelineRunner
    from app.core.searcher import Searcher
    from app.core.auditor import Auditor
    from app.core.writer import Writer

    repo = ResearchRepository(session=db_session)
    pesquisa = await repo.create_research(
        tema="Cenários Climáticos e Transição Energética",
        pontos_textos=["Modelagem hidrológica da bacia do Paraná"],
    )
    await db_session.commit()
    p_id = (await repo.list_points(pesquisa.id_pesquisa))[0].ponto_id

    hub = get_pipeline_event_hub()
    hub.clear(pesquisa.id_pesquisa)

    # Mock dos 3 estágios com emissão de reasonings estruturados
    async def mock_execute_search(*args, **kwargs):
        return {
            "ponto_id": p_id,
            "ponto_n": 1,
            "status": "coletado",
            "tentativas": 1,
            "total_urls_lidas": 4,
            "personas": [
                {
                    "persona": "historiador",
                    "queries_executadas": 2,
                    "urls_fonte": ["https://exemplo.org/clima"],
                    "falha_coleta": False,
                    "reasoning": "Raciocínio Historiador: análise retrospectiva das secas de 1944 a 2021.",
                }
            ],
        }

    async def mock_execute_audit(*args, **kwargs):
        return {
            "id_pesquisa": pesquisa.id_pesquisa,
            "pronto_para_writer": True,
            "auditorias": [
                {
                    "ponto_id": p_id,
                    "ponto_n": 1,
                    "status": "aprovado",
                    "pontuacao_percentual": 100.0,
                    "criterios_aprovados": 12,
                    "reasoning_auditoria": "Raciocínio Auditor: 12 critérios validados com corroboração primária.",
                    "pontos_fracos": None,
                }
            ],
        }

    async def mock_execute_writer(*args, **kwargs):
        return {
            "id_pesquisa": pesquisa.id_pesquisa,
            "status": "concluido",
            "dossier_final": "# Dossiê Climático Completo",
            "reasoning_dossier": "Raciocínio Redator: Síntese rigorosa das vazões e impacto tarifário.",
            "concluido_em": "2026-10-27T15:00:00Z",
        }

    monkeypatch.setattr(Searcher, "execute_search", mock_execute_search)
    monkeypatch.setattr(Auditor, "execute_audit", mock_execute_audit)
    monkeypatch.setattr(Writer, "execute_writer", mock_execute_writer)

    runner = PipelineRunner()
    res = await runner.run(id_pesquisa=pesquisa.id_pesquisa)
    assert res.get("status") == "concluido"

    # Inspeciona histórico de eventos despachados no hub
    history = hub.get_history(pesquisa.id_pesquisa)
    events_recorded = [h[0] for h in history]

    # Valida presença dos eventos canônicos obrigatórios
    assert "pipeline.status" in events_recorded
    assert "point.status" in events_recorded
    assert "search.progress" in events_recorded
    assert "audit.result" in events_recorded
    assert "writer.progress" in events_recorded
    assert "report.final" in events_recorded

    # Valida reasonings em cada evento despachado
    search_evt = next(h[1] for h in history if h[0] == "search.progress")
    assert "Raciocínio Historiador" in search_evt["reasoning_coleta"]

    audit_evt = next(h[1] for h in history if h[0] == "audit.result")
    assert "Raciocínio Auditor" in audit_evt["reasoning_auditoria"]

    writer_evt = next(h[1] for h in history if h[0] == "writer.progress" and h[1].get("status") == "concluido")
    assert "Raciocínio Redator" in writer_evt["reasoning_dossier"]

    report_evt = next(h[1] for h in history if h[0] == "report.final")
    assert report_evt["dossier_final"] == "# Dossiê Climático Completo"


def test_pipeline_event_hub_fifo_eviction_bounded_memory():
    """Valida limitação estrita de histórico no hub a no máximo 50 pesquisas (FIFO eviction)."""
    from collections import OrderedDict
    from app.core.pipeline_runner import PipelineEventHub

    hub = PipelineEventHub(max_history_per_research=10, max_researches=50)
    assert isinstance(hub._history, OrderedDict)

    # Publica eventos em 60 pesquisas sequenciais
    for i in range(1, 61):
        p_id = f"pesquisa-{i:03d}"
        hub.publish(p_id, "pipeline.status", {"status": "iniciado"})
        hub.publish(p_id, "pipeline.status", {"status_pipeline": "concluido"})

    # Limite estrito de 50 pesquisas mantido
    assert len(hub._history) == 50

    # As primeiras 10 foram descartadas em FIFO
    for i in range(1, 11):
        assert hub.get_history(f"pesquisa-{i:03d}") == []

    # As 50 mais recentes (11 a 60) continuam presentes
    for i in range(11, 61):
        hist = hub.get_history(f"pesquisa-{i:03d}")
        assert len(hist) == 2


@pytest.mark.asyncio
async def test_sse_stream_snapshot_extracts_real_persona_from_metadata(db_session: AsyncSession):
    """Valida que o snapshot SSE extrai a persona real de metadados_coleta em vez do placeholder 'coleta'."""
    repo = ResearchRepository(session=db_session)
    pesquisa = await repo.create_research(
        tema="Inteligência Artificial e Mercado de Trabalho",
        pontos_textos=["Impacto na produtividade e substituição cognitiva"],
    )
    p_id = (await repo.list_points(pesquisa.id_pesquisa))[0].ponto_id

    # Salva coleta com metadados estruturados contendo persona
    meta_obj = {
        "versao": 1,
        "resultados_personas": {
            "futurista": {
                "persona": "futurista",
                "reasoning": "Raciocínio Futurista: Cenários de automação em 2030.",
                "sucesso": True,
                "queries_executadas": 2,
                "urls_fonte": ["https://exemplo.org/ia-futuro"],
            }
        }
    }
    await repo.save_collected_content(
        id_pesquisa=pesquisa.id_pesquisa,
        ponto_id=p_id,
        tema="Inteligência Artificial e Mercado de Trabalho",
        ponto="Impacto na produtividade e substituição cognitiva",
        conteudo_coletado="Resumo da coleta",
        urls_lidas=["https://exemplo.org/ia-futuro"],
        urls_fonte=["https://exemplo.org/ia-futuro"],
        reasoning_coleta="Raciocínio Futurista: Cenários de automação em 2030.",
        metadados_coleta=meta_obj,
    )
    await db_session.commit()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get(f"/api/v1/pipeline/{pesquisa.id_pesquisa}/stream?snapshot_only=true")
        assert resp.status_code == 200

    events = parse_sse_events(resp.text)
    search_events = [json.loads(e[1]) for e in events if e[0] == "search.progress"]
    assert len(search_events) >= 1
    sp = search_events[0]
    # Persona extraída dos metadados
    assert sp["persona"] == "futurista"
    assert sp["ponto_id"] == p_id
    assert "Raciocínio Futurista" in sp["reasoning_coleta"]




@pytest.mark.asyncio
async def test_sse_stream_delivers_live_agent_deltas_coalesced(db_session: AsyncSession):
    """Deltas do LLM (stream_context) chegam ao cliente coalescidos, sem perda nem truncamento."""
    from app.core.stream_context import publish_delta, publish_stage_event, stream_scope

    repo = ResearchRepository(session=db_session)
    pesquisa = await repo.create_research(
        tema="Redes Neurais Espaçofasdas",
        pontos_textos=["Arquiteturas esparsas eficientes"],
    )
    await db_session.commit()
    p_id = (await repo.list_points(pesquisa.id_pesquisa))[0].ponto_id

    hub = get_pipeline_event_hub()
    hub.clear(pesquisa.id_pesquisa)

    partes = ["O ponto exige ", "evidência primária ", "sobre eficiência energética."]

    async def pusher():
        await asyncio.sleep(0.05)
        publish_stage_event(pesquisa.id_pesquisa, "stage.start", "search", agent="historiador", ponto_id=p_id)
        with stream_scope(pesquisa.id_pesquisa, "search", agent="historiador", ponto_id=p_id):
            for parte in partes:
                publish_delta("reasoning", parte)
        publish_stage_event(pesquisa.id_pesquisa, "stage.end", "search", agent="historiador", ponto_id=p_id)
        await asyncio.sleep(0.02)
        hub.publish(pesquisa.id_pesquisa, "report.final", {
            "id_pesquisa": pesquisa.id_pesquisa,
            "status": "concluido",
            "dossier_final": "# Dossiê\nConteúdo.",
            "total_caracteres": 20,
            "concluido_em": "2026-10-28T10:00:00Z",
        })

    push_task = asyncio.create_task(pusher())

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(f"/api/v1/pipeline/{pesquisa.id_pesquisa}/stream")
        assert response.status_code == 200

    await push_task

    events = parse_sse_events(response.text)
    nomes = [e[0] for e in events]
    assert nomes[0] == "pipeline.status" or nomes[0] == "point.status", "Snapshot inicial ausente"
    assert "stage.start" in nomes
    assert "stage.end" in nomes
    assert "report.final" in nomes
    assert nomes.index("stage.start") < nomes.index("stage.end") < nomes.index("report.final")

    deltas = [json.loads(e[1]) for e in events if e[0] == "agent.delta"]
    assert deltas, "Nenhum agent.delta chegou ao cliente SSE"
    assert all(d["stage"] == "search" and d["agent"] == "historiador" for d in deltas)
    assert all(d["ponto_id"] == p_id for d in deltas)
    # Coalescido ou não, o texto concatenado tem de ser exatamente a soma dos deltas.
    assert "".join(d["text"] for d in deltas) == "".join(partes)
