"""Contexto de streaming ao vivo do pipeline (SSE).

O `LLMClient` já recebe o raciocínio e o conteúdo em chunks do provedor
(`stream=True`). Este módulo propaga esses deltas para o `PipelineEventHub`
global sem acoplar o cliente LLM ao endpoint HTTP nem aos estágios.

Uso:

    with stream_scope(id_pesquisa, stage="search", agent="historiador", ponto_id=pid):
        ...  # chamadas ao LLMClient publicam `agent.delta` automaticamente

Fora de um `stream_scope` (chamadas HTTP avulsas de /plan, /search, /audit,
/writer, testes), `publish_delta` é no-op.
"""

import contextvars
from contextlib import contextmanager
from typing import Any, Dict, Iterator, Optional

_stream_scope: contextvars.ContextVar[Optional[Dict[str, Any]]] = contextvars.ContextVar(
    "pipeline_stream_scope", default=None
)


@contextmanager
def stream_scope(
    id_pesquisa: Optional[str],
    stage: str,
    agent: Optional[str] = None,
    ponto_id: Optional[str] = None,
) -> Iterator[None]:
    """Abre escopo de streaming para um estágio/agente do pipeline."""
    if not id_pesquisa:
        yield
        return

    token = _stream_scope.set(
        {
            "id_pesquisa": id_pesquisa,
            "stage": stage,
            "agent": agent,
            "ponto_id": ponto_id,
        }
    )
    try:
        yield
    finally:
        _stream_scope.reset(token)


def current_scope() -> Optional[Dict[str, Any]]:
    """Retorna o escopo de streaming ativo, se houver."""
    return _stream_scope.get()


def publish_delta(kind: str, text: str) -> None:
    """Publica um delta de raciocínio (`reasoning`) ou de resposta (`content`).

    Silencioso quando não há escopo ativo: chamadas diretas aos endpoints
    continuam funcionando sem hub nem assinantes.
    """
    scope = _stream_scope.get()
    if not scope or not text:
        return

    try:
        # Import tardio: evita ciclo (pipeline_runner -> searcher -> llm_client).
        from app.core.pipeline_runner import get_pipeline_event_hub

        get_pipeline_event_hub().publish(
            scope["id_pesquisa"],
            "agent.delta",
            {
                "id_pesquisa": scope["id_pesquisa"],
                "stage": scope["stage"],
                "agent": scope.get("agent"),
                "ponto_id": scope.get("ponto_id"),
                "kind": kind,
                "text": text,
            },
        )
    except Exception:
        # Streaming nunca pode derrubar a chamada ao LLM.
        return


def publish_stage_event(
    id_pesquisa: Optional[str],
    event: str,
    stage: str,
    agent: Optional[str] = None,
    ponto_id: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """Publica evento de ciclo de vida do estágio (`stage.start`/`stage.end`)."""
    if not id_pesquisa:
        return
    try:
        from app.core.pipeline_runner import get_pipeline_event_hub

        payload: Dict[str, Any] = {
            "id_pesquisa": id_pesquisa,
            "stage": stage,
            "agent": agent,
            "ponto_id": ponto_id,
        }
        if extra:
            payload.update(extra)
        get_pipeline_event_hub().publish(id_pesquisa, event, payload)
    except Exception:
        return
