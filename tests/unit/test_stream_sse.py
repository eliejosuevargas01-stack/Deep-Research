# -*- coding: utf-8 -*-
"""Testes do encanamento SSE em tempo real (deltas do LLM -> hub -> frontend).

Cobre:
1. `stream_scope` + `publish_delta` publicam `agent.delta` no hub com a
   atribuição correta (estágio/agente/ponto).
2. Fora de escopo, `publish_delta` é no-op (endpoints HTTP avulsos e testes).
3. O endpoint SSE coalesce deltas consecutivos do mesmo agente num único frame,
   sem perder eventos de outro tipo que estejam na fila.
"""

import asyncio
import json
from typing import Any, Dict

from app.api.v1.endpoints.pipeline import _drain_deltas, _format_sse
from app.core.pipeline_runner import get_pipeline_event_hub
from app.core.stream_context import publish_delta, publish_stage_event, stream_scope

ID = "pesq-stream-teste"


def test_publish_delta_without_scope_is_noop() -> None:
    """Sem escopo ativo nada é publicado (chamadas diretas aos endpoints)."""
    hub = get_pipeline_event_hub()
    queue = hub.subscribe(ID)
    try:
        publish_delta("reasoning", "texto que não deve vazar")
        assert queue.empty()
    finally:
        hub.unsubscribe(ID, queue)


def test_stream_scope_publishes_agent_delta_with_attribution() -> None:
    hub = get_pipeline_event_hub()
    queue = hub.subscribe(ID)
    try:
        with stream_scope(ID, "search", agent="historiador", ponto_id="ponto-1"):
            publish_delta("reasoning", "pensando")
            publish_delta("content", '{"acao"')

        event_type, payload = queue.get_nowait()
        assert event_type == "agent.delta"
        assert payload == {
            "id_pesquisa": ID,
            "stage": "search",
            "agent": "historiador",
            "ponto_id": "ponto-1",
            "kind": "reasoning",
            "text": "pensando",
        }

        event_type2, payload2 = queue.get_nowait()
        assert event_type2 == "agent.delta"
        assert payload2["kind"] == "content"
        assert payload2["text"] == '{"acao"'
    finally:
        hub.unsubscribe(ID, queue)


def test_stream_scope_resets_after_exit() -> None:
    """Depois do bloco, deltas voltam a ser descartados (sem vazamento entre pontos)."""
    hub = get_pipeline_event_hub()
    queue = hub.subscribe(ID)
    try:
        with stream_scope(ID, "audit", agent="auditor", ponto_id="ponto-1"):
            publish_delta("reasoning", "dentro")
        publish_delta("reasoning", "fora")

        assert not queue.empty()
        queue.get_nowait()
        assert queue.empty()
    finally:
        hub.unsubscribe(ID, queue)


def test_publish_stage_event_reaches_hub() -> None:
    hub = get_pipeline_event_hub()
    queue = hub.subscribe(ID)
    try:
        publish_stage_event(ID, "stage.start", "writer", agent="redator final")
        event_type, payload = queue.get_nowait()
        assert event_type == "stage.start"
        assert payload["stage"] == "writer"
        assert payload["agent"] == "redator final"
    finally:
        hub.unsubscribe(ID, queue)


def test_drain_deltas_merges_same_agent_and_preserves_foreign_event() -> None:
    """Deltas do mesmo agente viram um frame; evento de outro tipo não é perdido."""
    queue: asyncio.Queue = asyncio.Queue()
    queue.put_nowait(("agent.delta", {
        "id_pesquisa": ID, "stage": "search", "agent": "cetico",
        "ponto_id": "p1", "kind": "reasoning", "text": "B",
    }))
    queue.put_nowait(("agent.delta", {
        "id_pesquisa": ID, "stage": "search", "agent": "futurista",
        "ponto_id": "p1", "kind": "reasoning", "text": "C",
    }))

    first: Dict[str, Any] = {
        "id_pesquisa": ID, "stage": "search", "agent": "cetico",
        "ponto_id": "p1", "kind": "reasoning", "text": "A",
    }
    merged, pending = _drain_deltas(first, queue)

    assert merged["text"] == "AB"
    assert pending is not None, "Evento de outro agente deve ser devolvido, não descartado"
    assert pending[1]["agent"] == "futurista"
    assert queue.empty()


def test_format_sse_is_w3c_compatible() -> None:
    frame = _format_sse("agent.delta", {"text": "olá\nmundo"})
    assert frame.startswith("event: agent.delta\ndata: ")
    assert frame.endswith("\n\n")
    payload = json.loads(frame.split("data: ", 1)[1].strip())
    assert payload["text"] == "olá\nmundo"
