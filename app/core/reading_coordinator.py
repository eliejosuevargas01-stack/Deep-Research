# -*- coding: utf-8 -*-
"""Coordenação de leituras compartilhadas com desduplicação in-flight e isolamento de cancelamento."""

import asyncio
from typing import Any, Callable, Coroutine, Dict, Optional, Set


class ReadingCoordinator:
    """Coordena leituras web compartilhadas entre múltiplos pontos e personas.

    Garante:
    1. Desduplicação de requisições: apenas 1 tarefa in-flight por URL.
    2. Cache compartilhado em memória de leituras bem-sucedidas imune a envenenamento.
    3. Contagem de referência de consumidores associada à tarefa específica: o cancelamento de
       um consumidor não cancela a leitura enquanto outros consumidores daquela tarefa aguardarem.
    4. Remoção estrita por identidade da tarefa: finally/except nunca removem nem cancelam tarefas
       substitutas de uma URL.
    5. Fechamento e drenagem ordenados: última referência cancelada aguarda o término da tarefa
       mesmo sob cancelamentos repetidos; close() cancela e aguarda todas as tarefas pendentes
       (incluindo órfãs em drenagem), sem serializar URLs distintas.
    """

    def __init__(self) -> None:
        self.shared_cache: Dict[str, Dict[str, Any]] = {}
        self.in_flight: Dict[str, asyncio.Task] = {}
        self._task_consumers: Dict[asyncio.Task, int] = {}
        self._all_tasks: Set[asyncio.Task] = set()
        self._lock = asyncio.Lock()
        self._closed: bool = False

    async def fetch_url(
        self,
        url: str,
        fetch_coro_fn: Callable[[], Coroutine[Any, Any, Optional[Dict[str, Any]]]],
    ) -> Optional[Dict[str, Any]]:
        """Busca URL com cache compartilhado, dedup in-flight e refcount seguro de cancelamento."""
        if self._closed:
            raise RuntimeError("ReadingCoordinator fechado")

        if not url or not url.strip():
            return None

        # 1. Verifica cache de leituras já bem-sucedidas
        if url in self.shared_cache:
            return self.shared_cache[url]

        async with self._lock:
            if self._closed:
                raise RuntimeError("ReadingCoordinator fechado")
            if url in self.shared_cache:
                return self.shared_cache[url]
            task = self.in_flight.get(url)
            if task is None or task.done():
                task = asyncio.create_task(fetch_coro_fn())
                self.in_flight[url] = task
                self._task_consumers[task] = 0
                self._all_tasks.add(task)
                task.add_done_callback(self._all_tasks.discard)
            self._task_consumers[task] += 1

        consumer_active = True
        try:
            record = await asyncio.shield(task)
            if record and isinstance(record, dict) and record.get("status") == "read_ok":
                self.shared_cache[url] = record
            return record
        except asyncio.CancelledError:
            orphan_task: Optional[asyncio.Task] = None
            async with self._lock:
                if consumer_active and task in self._task_consumers:
                    self._task_consumers[task] -= 1
                    consumer_active = False
                    if self._task_consumers[task] <= 0:
                        self._task_consumers.pop(task, None)
                        if self.in_flight.get(url) is task:
                            self.in_flight.pop(url, None)
                        if not task.done():
                            task.cancel()
                            orphan_task = task
            # Aguarda a drenagem da tarefa órfã fora do lock para não serializar outras URLs,
            # blindado contra cancelamentos repetidos
            if orphan_task is not None:
                while not orphan_task.done():
                    try:
                        await asyncio.shield(orphan_task)
                    except asyncio.CancelledError:
                        pass
                    except Exception:
                        break
            raise
        finally:
            async with self._lock:
                if consumer_active and task in self._task_consumers:
                    self._task_consumers[task] -= 1
                    if self._task_consumers[task] <= 0:
                        self._task_consumers.pop(task, None)
                if self.in_flight.get(url) is task and task.done():
                    self.in_flight.pop(url, None)

    async def close(self) -> None:
        """Cancela e aguarda todas as tarefas pendentes e em drenagem, prevenindo órfãos."""
        async with self._lock:
            self._closed = True
            pending = [t for t in self._all_tasks if not t.done()]
            for t in pending:
                t.cancel()

        if pending:
            was_cancelled = False

            async def _drain_pending() -> None:
                await asyncio.gather(*pending, return_exceptions=True)

            gather_task = asyncio.create_task(_drain_pending())
            while not gather_task.done():
                try:
                    await asyncio.shield(gather_task)
                except asyncio.CancelledError:
                    was_cancelled = True
                except Exception:
                    break
            if was_cancelled:
                raise asyncio.CancelledError()
