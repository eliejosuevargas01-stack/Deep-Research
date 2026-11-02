"""Barramento de eventos do pipeline de pesquisa (SSE) e utilitários de tempo.

O ciclo de pesquisa em si roda no processo Hermes (app/core/hermes_planner.py);
este módulo mantém apenas o hub em memória consumido por /pipeline e /plan.
"""

import asyncio
from collections import OrderedDict
from datetime import datetime, timezone
import logging
import threading
from typing import Any, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger(__name__)


def _format_iso_utc() -> str:
    """Retorna timestamp corrente formatado em ISO 8601 UTC."""
    return datetime.now(timezone.utc).isoformat()


class EventPayload(dict):
    """Payload de evento de pipeline com id/seq_id transparentes que preservam igualdade exata."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.id: Optional[int] = None
        self.seq_id: Optional[int] = None

    def __getitem__(self, key: Any) -> Any:
        if key in ("id", "seq_id") and not super().__contains__(key) and getattr(self, key, None) is not None:
            return getattr(self, key)
        return super().__getitem__(key)

    def __contains__(self, key: Any) -> bool:
        if key in ("id", "seq_id") and getattr(self, key, None) is not None:
            return True
        return super().__contains__(key)

    def get(self, key: Any, default: Any = None) -> Any:
        if key in ("id", "seq_id") and not super().__contains__(key) and getattr(self, key, None) is not None:
            return getattr(self, key)
        return super().get(key, default)


class PipelineEventHub:
    """Hub thread-safe e assíncrono para publicação e assinatura de eventos do pipeline em tempo real."""

    def __init__(self, max_history_per_research: int = 100, max_researches: int = 50) -> None:
        self._subscribers: Dict[str, Set[asyncio.Queue]] = {}
        self._history: OrderedDict[str, List[Tuple[str, Dict[str, Any]]]] = OrderedDict()
        self._seq_counters: Dict[str, int] = {}
        self._lock = threading.Lock()
        self._max_history = max_history_per_research
        self._max_researches = max_researches

    def subscribe(self, id_pesquisa: str) -> asyncio.Queue:
        """Registra um assinante e retorna uma fila assíncrona isolada para a pesquisa."""
        q, _ = self.subscribe_with_history(id_pesquisa, last_event_id=None)
        return q

    def subscribe_with_history(
        self,
        id_pesquisa: str,
        last_event_id: Optional[Union[int, str]] = None,
    ) -> Tuple[asyncio.Queue, List[Tuple[str, Dict[str, Any]]]]:
        """Registra assinante e retorna eventos históricos atomicamente sob lock."""
        q: asyncio.Queue = asyncio.Queue()
        with self._lock:
            if id_pesquisa not in self._subscribers:
                self._subscribers[id_pesquisa] = set()
            self._subscribers[id_pesquisa].add(q)

            raw_history = list(self._history.get(id_pesquisa, []))
            if id_pesquisa in self._history:
                self._history.move_to_end(id_pesquisa)

            if last_event_id is not None:
                try:
                    last_id = int(last_event_id)
                    filtered_history = [
                        (evt, d) for evt, d in raw_history
                        if isinstance(d, dict) and (d.get("id", 0) or 0) > last_id
                    ]
                except (ValueError, TypeError):
                    filtered_history = raw_history
            else:
                filtered_history = raw_history

        return q, filtered_history

    def unsubscribe(self, id_pesquisa: str, queue: asyncio.Queue) -> None:
        """Remove o assinante da pesquisa de forma segura."""
        with self._lock:
            if id_pesquisa in self._subscribers:
                self._subscribers[id_pesquisa].discard(queue)
                if not self._subscribers[id_pesquisa]:
                    self._subscribers.pop(id_pesquisa, None)

    def publish(self, id_pesquisa: str, event: str, data: Dict[str, Any]) -> None:
        """Publica um evento para todos os assinantes ativos e armazena no buffer recente."""
        with self._lock:
            if id_pesquisa not in self._history:
                while len(self._history) >= self._max_researches:
                    evicted_id, _ = self._history.popitem(last=False)
                    self._subscribers.pop(evicted_id, None)
                    self._seq_counters.pop(evicted_id, None)
                self._history[id_pesquisa] = []
            else:
                self._history.move_to_end(id_pesquisa)

            seq_id = self._seq_counters.get(id_pesquisa, 0) + 1
            self._seq_counters[id_pesquisa] = seq_id

            if isinstance(data, dict):
                wrapped = EventPayload(data)
                wrapped.id = seq_id
                wrapped.seq_id = seq_id
                event_data = wrapped
            else:
                event_data = data

            hist = self._history[id_pesquisa]
            hist.append((event, event_data))
            if len(hist) > self._max_history:
                hist.pop(0)
            subscribers = list(self._subscribers.get(id_pesquisa, set()))

        for q in subscribers:
            try:
                q.put_nowait((event, event_data))
            except Exception:
                try:
                    loop = getattr(q, "_loop", None)
                    if loop and loop.is_running():
                        loop.call_soon_threadsafe(q.put_nowait, (event, event_data))
                except Exception as exc_put:
                    logger.warning(
                        f"[PipelineEventHub] Falha ao despachar evento '{event}' para {id_pesquisa}: {exc_put}"
                    )

    def get_history(self, id_pesquisa: str) -> List[Tuple[str, Dict[str, Any]]]:
        """Retorna snapshot imutável do histórico de eventos recentes para a pesquisa."""
        with self._lock:
            if id_pesquisa in self._history:
                self._history.move_to_end(id_pesquisa)
                return list(self._history[id_pesquisa])
            return []

    def clear(self, id_pesquisa: Optional[str] = None) -> None:
        """Limpa filas e histórico da pesquisa ou globalmente."""
        with self._lock:
            if id_pesquisa:
                self._subscribers.pop(id_pesquisa, None)
                self._history.pop(id_pesquisa, None)
                self._seq_counters.pop(id_pesquisa, None)
            else:
                self._subscribers.clear()
                self._history.clear()
                self._seq_counters.clear()


_global_pipeline_event_hub = PipelineEventHub()


def get_pipeline_event_hub() -> PipelineEventHub:
    """Retorna a instância canônica compartilhada do barramento de eventos."""
    return _global_pipeline_event_hub
