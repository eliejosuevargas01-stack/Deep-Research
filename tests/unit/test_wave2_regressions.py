"""Testes de regressão da Onda 2: B-11 (SSE atômico com seq_id monotônico e last_event_id).

Cobre:
1. PipelineEventHub numera eventos publicados com seq_id monotônico isolado por pesquisa.
2. PipelineEventHub.subscribe_with_history retorna tupla atômica (queue, history) sob lock.
3. Filtro de histórico com last_event_id retorna somente eventos com seq_id > int(last_event_id).
4. _format_sse emite id: <seq_id> na formatação SSE canônica.
5. Endpoint /api/v1/pipeline/{id}/stream extrai Last-Event-ID do header e entrega eventos perdidos.
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
import pytest
import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.pipeline import _format_sse, stream_pipeline_progress
from app.core.pipeline_runner import PipelineEventHub, get_pipeline_event_hub
from app.db.research_repository import ResearchRepository
from app.main import app


def test_b11_event_hub_monotonic_seq_id_per_research() -> None:
    """Valida que cada pesquisa possui contador monotônico independente de seq_id."""
    hub = PipelineEventHub()
    id_a = "pesquisa-alpha"
    id_b = "pesquisa-beta"

    hub.publish(id_a, "stage.start", {"stage": "search"})
    hub.publish(id_a, "search.progress", {"queries": 1})
    hub.publish(id_b, "stage.start", {"stage": "plan"})

    hist_a = hub.get_history(id_a)
    hist_b = hub.get_history(id_b)

    assert len(hist_a) == 2
    assert hist_a[0][1].get("id") == 1
    assert hist_a[1][1].get("id") == 2
    assert hist_a[0][1].get("seq_id") == 1
    assert hist_a[1][1].get("seq_id") == 2

    assert len(hist_b) == 1
    assert hist_b[0][1].get("id") == 1
    assert hist_b[0][1].get("seq_id") == 1


def test_b11_event_hub_subscribe_with_history_all() -> None:
    """subscribe_with_history sem last_event_id retorna fila vazia e todo o histórico existente."""
    hub = PipelineEventHub()
    p_id = "pesquisa-hist-all"

    hub.publish(p_id, "pipeline.status", {"status": "iniciado"})
    hub.publish(p_id, "point.status", {"ponto_n": 1})

    queue, history = hub.subscribe_with_history(p_id, last_event_id=None)

    assert len(history) == 2
    assert history[0][0] == "pipeline.status"
    assert history[1][0] == "point.status"
    assert queue.empty()

    # Próximo publish vai para a fila
    hub.publish(p_id, "search.progress", {"urls": 3})
    assert not queue.empty()
    evt, data = queue.get_nowait()
    assert evt == "search.progress"
    assert data.get("id") == 3


def test_b11_event_hub_subscribe_with_history_filtered_by_last_event_id() -> None:
    """subscribe_with_history filtra histórico retornando somente eventos com seq_id > last_event_id."""
    hub = PipelineEventHub()
    p_id = "pesquisa-hist-filter"

    for i in range(1, 6):
        hub.publish(p_id, "test.event", {"indice": i})

    # Solicita a partir do evento 3 (deve retornar seq_ids 4 e 5)
    queue, history = hub.subscribe_with_history(p_id, last_event_id="3")

    assert len(history) == 2
    assert [h[1].get("id") for h in history] == [4, 5]
    assert [h[1]["indice"] for h in history] == [4, 5]

    # Solicita com last_event_id igual ao último emitido
    _, history_empty = hub.subscribe_with_history(p_id, last_event_id=5)
    assert len(history_empty) == 0

    # Solicita com last_event_id inválido (fallback para histórico completo)
    _, history_invalid = hub.subscribe_with_history(p_id, last_event_id="invalido")
    assert len(history_invalid) == 5


def test_b11_format_sse_includes_id() -> None:
    """_format_sse deve serializar 'id: <seq_id>' antes de 'event:' e 'data:'."""
    # Sem id
    frame_no_id = _format_sse("point.status", {"ponto_id": "p1"})
    assert "id:" not in frame_no_id
    assert frame_no_id.startswith("event: point.status\ndata: ")

    # Com id no dicionário (via EventPayload ou chave direta)
    frame_with_dict_id = _format_sse("point.status", {"ponto_id": "p1", "id": 42})
    assert frame_with_dict_id.startswith("id: 42\nevent: point.status\ndata: ")
    assert frame_with_dict_id.endswith("\n\n")

    # Com id explícito via parâmetro
    frame_explicit_id = _format_sse("agent.delta", {"text": "chunk"}, event_id=7)
    assert frame_explicit_id.startswith("id: 7\nevent: agent.delta\ndata: ")


@pytest.mark.asyncio
async def test_b11_stream_endpoint_replays_history_from_last_event_id_header(db_session: AsyncSession) -> None:
    """stream_pipeline_progress extrai Last-Event-ID do header e entrega eventos perdidos do histórico."""
    repo = ResearchRepository(session=db_session)
    pesquisa = await repo.create_research(
        tema="Reconexão SSE com Last-Event-ID",
        pontos_textos=["Ponto 1 para reconexão"],
    )
    await db_session.commit()

    hub = get_pipeline_event_hub()
    hub.clear(pesquisa.id_pesquisa)

    # Publica 4 eventos no hub
    hub.publish(pesquisa.id_pesquisa, "pipeline.status", {"status_pipeline": "buscando"})
    hub.publish(pesquisa.id_pesquisa, "search.progress", {"step": 1})
    hub.publish(pesquisa.id_pesquisa, "search.progress", {"step": 2})
    hub.publish(pesquisa.id_pesquisa, "report.final", {
        "status": "concluido",
        "dossier_final": "Dossiê reconectado",
    })

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        # Reconecta simulando que o cliente já tinha recebido até o evento id=2
        resp = await client.get(
            f"/api/v1/pipeline/{pesquisa.id_pesquisa}/stream",
            headers={"Last-Event-ID": "2"},
        )
        assert resp.status_code == 200

    raw_text = resp.text
    # Deve conter id: 3 e id: 4, mas não id: 1 nem id: 2
    assert "id: 3" in raw_text
    assert "id: 4" in raw_text
    assert "id: 1" not in raw_text
    assert "id: 2" not in raw_text
    assert "Dossiê reconectado" in raw_text
