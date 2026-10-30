# -*- coding: utf-8 -*-
"""Testes determinísticos para ReadingCoordinator: regressões de identidade de task e drenagem em cancelamento."""

import asyncio
import pytest
from app.core.reading_coordinator import ReadingCoordinator


@pytest.mark.asyncio
async def test_reading_coordinator_finally_does_not_remove_replacement_task() -> None:
    """Verifica que o finally de uma tarefa anterior encerrada não remove a tarefa substituta."""
    coord = ReadingCoordinator()
    url = "https://example.org/race"

    t1_done = asyncio.Event()
    c1_proceed_finally = asyncio.Event()

    # Intercepta fetch_url para pausar consumer 1 antes do bloco finally
    orig_shield = asyncio.shield

    call_count = 0

    async def fetch_1():
        nonlocal call_count
        call_count += 1
        return {"url": url, "body": "doc 1", "status": "read_failed"}

    async def fetch_2():
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.1)
        return {"url": url, "body": "doc 2", "status": "read_ok"}

    # Mock de shield para forçar context switch antes do finally de consumer 1
    async def hooked_shield(arg):
        res = await orig_shield(arg)
        if call_count == 1:
            t1_done.set()
            await c1_proceed_finally.wait()
        return res

    # Dispara consumer 1
    async def consumer_1():
        # Vamos rodar fetch_url com monkeypatch de shield dentro da corotina
        return await coord.fetch_url(url, fetch_1)

    import unittest.mock as mock
    with mock.patch("asyncio.shield", side_effect=hooked_shield):
        c1_task = asyncio.create_task(consumer_1())
        await t1_done.wait()

        # Neste ponto, task 1 concluiu, mas consumer 1 ainda NÃO executou o finally.
        # Agora consumer 2 solicita a mesma URL e deve criar task 2:
        c2_task = asyncio.create_task(coord.fetch_url(url, fetch_2))
        await asyncio.sleep(0.01)

        # Task 2 deve estar in-flight
        t2 = coord.in_flight.get(url)
        assert t2 is not None

        # Libera consumer 1 para executar o seu finally:
        c1_proceed_finally.set()
        await c1_task

        # FALHA NO CÓDIGO ANTERIOR: o finally de consumer 1 faz in_flight.pop(url) incondicionalmente,
        # removendo t2!
        assert coord.in_flight.get(url) is t2, "Finally de task anterior removeu task 2 substituta!"

        # Limpeza
        c2_task.cancel()
        await asyncio.gather(c2_task, return_exceptions=True)
        await coord.close()


@pytest.mark.asyncio
async def test_reading_coordinator_cancelled_consumer_does_not_cancel_replacement_task() -> None:
    """Verifica que o cancelamento de um consumidor não cancela uma nova tarefa substituta por race na URL."""
    coord = ReadingCoordinator()
    url = "https://example.org/cancel-race"

    t1_done = asyncio.Event()
    c1_hold = asyncio.Event()

    orig_shield = asyncio.shield

    call_count = 0

    async def fetch_1():
        nonlocal call_count
        call_count += 1
        return {"url": url, "body": "doc 1", "status": "read_failed"}

    async def fetch_2():
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.05)
        return {"url": url, "body": "doc 2", "status": "read_ok"}

    async def hooked_shield(arg):
        res = await orig_shield(arg)
        if call_count == 1:
            t1_done.set()
            await c1_hold.wait()
        return res

    import unittest.mock as mock
    with mock.patch("asyncio.shield", side_effect=hooked_shield):
        c1_task = asyncio.create_task(coord.fetch_url(url, fetch_1))
        await t1_done.wait()

        # Task 1 concluiu mas consumer 1 está retido dentro de fetch_url
        # Consumer 2 inicia e cria task 2 substituta para a mesma URL
        c2_task = asyncio.create_task(coord.fetch_url(url, fetch_2))
        await asyncio.sleep(0.01)

        # Agora cancela consumer 1
        c1_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await c1_task

        # Consumer 2 NÃO pode ter sido cancelado pelo cancel de consumer 1!
        res2 = await c2_task
        assert res2 is not None
        assert res2["body"] == "doc 2"
        await coord.close()


@pytest.mark.asyncio
async def test_reading_coordinator_last_reference_cancel_drains_task_and_close_waits() -> None:
    """Verifica que a última referência cancelada aguarda finalização da tarefa e close() não retorna antes do cleanup."""
    coord = ReadingCoordinator()
    url = "https://example.org/cleanup"

    started = asyncio.Event()
    cleaned_up = asyncio.Event()

    async def fetch_with_cleanup():
        started.set()
        try:
            await asyncio.sleep(10.0)
        finally:
            # Simula limpeza assíncrona (fechar socket, liberar buffers)
            await asyncio.sleep(0.05)
            cleaned_up.set()

    c1 = asyncio.create_task(coord.fetch_url(url, fetch_with_cleanup))
    await started.wait()

    # Cancela o único consumidor (última referência)
    c1.cancel()

    # Aguarda o cancelamento de c1
    with pytest.raises(asyncio.CancelledError):
        await c1

    # Quando c1 retorna CancelledError, a task subjacente DEVE já ter completado o cleanup!
    assert cleaned_up.is_set(), "Consumidor retornou do cancelamento antes do cleanup da tarefa subjacente!"

    # E se close() for chamado, ele também deve garantir que nenhuma task esteja pendente
    await coord.close()


@pytest.mark.asyncio
async def test_reading_coordinator_close_waits_for_draining_tasks_when_called_concurrently() -> None:
    """Verifica que coord.close() drena tarefas mesmo se a última referência acabou de cancelar."""
    coord = ReadingCoordinator()
    url = "https://example.org/close-drain"

    started = asyncio.Event()
    cleanup_started = asyncio.Event()
    cleaned_up = asyncio.Event()

    async def fetch_with_slow_cleanup():
        started.set()
        try:
            await asyncio.sleep(10.0)
        finally:
            cleanup_started.set()
            await asyncio.sleep(0.08)
            cleaned_up.set()

    c1 = asyncio.create_task(coord.fetch_url(url, fetch_with_slow_cleanup))
    await started.wait()

    # Cancela c1 e imediatamente chama close()
    c1.cancel()
    # Chama close() concorrentemente
    close_task = asyncio.create_task(coord.close())

    await close_task
    assert cleaned_up.is_set(), "close() retornou antes do cleanup da task ter terminado!"
    with pytest.raises(asyncio.CancelledError):
        await c1


@pytest.mark.asyncio
async def test_reading_coordinator_repeated_cancellation_during_drain() -> None:
    """Verifica que cancelamentos repetidos no consumidor não impedem o cleanup e a drenagem da task."""
    coord = ReadingCoordinator()
    url = "https://example.org/repeated-cancel"

    started = asyncio.Event()
    cleaned_up = asyncio.Event()

    async def fetch_coro():
        started.set()
        try:
            await asyncio.sleep(10.0)
        finally:
            await asyncio.sleep(0.05)
            cleaned_up.set()

    c1 = asyncio.create_task(coord.fetch_url(url, fetch_coro))
    await started.wait()

    # Cancela repetidamente
    c1.cancel()
    await asyncio.sleep(0.01)
    c1.cancel()  # Segundo cancel durante o drain
    c1.cancel()  # Terceiro cancel

    with pytest.raises(asyncio.CancelledError):
        await c1

    assert cleaned_up.is_set(), "Task subjacente não foi finalizada sob cancelamento repetido!"
    await coord.close()


@pytest.mark.asyncio
async def test_reading_coordinator_does_not_serialize_different_urls() -> None:
    """Verifica que a busca de URLs distintas ocorre em paralelo real e não é serializada."""
    coord = ReadingCoordinator()
    url_a = "https://example.org/a"
    url_b = "https://example.org/b"

    started_a = asyncio.Event()
    started_b = asyncio.Event()
    hang_a = asyncio.Event()

    async def fetch_a():
        started_a.set()
        await hang_a.wait()
        return {"url": url_a, "body": "a", "status": "read_ok"}

    async def fetch_b():
        started_b.set()
        return {"url": url_b, "body": "b", "status": "read_ok"}

    t_a = asyncio.create_task(coord.fetch_url(url_a, fetch_a))
    await started_a.wait()

    # Enquanto url_a está aguardando (bloqueada no hang_a), url_b DEVE executar e retornar imediatamente
    t_b = asyncio.create_task(coord.fetch_url(url_b, fetch_b))
    res_b = await asyncio.wait_for(t_b, timeout=0.5)
    assert res_b["status"] == "read_ok"

    hang_a.set()
    res_a = await t_a
    assert res_a["status"] == "read_ok"
    await coord.close()


@pytest.mark.asyncio
async def test_reading_coordinator_fetch_url_rejected_after_close() -> None:
    """fetch_url() após close() DEVE ser rejeitado com RuntimeError e não executar a corotina."""
    coord = ReadingCoordinator()
    await coord.close()

    called = False

    async def fetch_fn():
        nonlocal called
        called = True
        return {"url": "https://example.org/closed", "body": "test", "status": "read_ok"}

    with pytest.raises(RuntimeError, match="ReadingCoordinator.*fechado|ReadingCoordinator is closed"):
        await coord.fetch_url("https://example.org/closed", fetch_fn)

    assert not called, "Corotina de busca foi executada mesmo com coordenador fechado!"


@pytest.mark.asyncio
async def test_reading_coordinator_fetch_url_rejected_during_close_drain() -> None:
    """fetch_url() invocado enquanto close() ainda drena tarefas em andamento DEVE ser rejeitado."""
    coord = ReadingCoordinator()
    url = "https://example.org/drain-block"

    started = asyncio.Event()
    release_cleanup = asyncio.Event()

    async def slow_fetch():
        started.set()
        try:
            await asyncio.sleep(10.0)
        finally:
            await release_cleanup.wait()

    # Inicia fetch lento
    t1 = asyncio.create_task(coord.fetch_url(url, slow_fetch))
    await started.wait()

    # Dispara close() em background (vai ficar bloqueado no drain de slow_fetch)
    close_task = asyncio.create_task(coord.close())
    await asyncio.sleep(0.01)

    # Tenta novo fetch_url durante o drain
    new_called = False

    async def new_fetch():
        nonlocal new_called
        new_called = True
        return {"url": "https://example.org/new", "body": "new", "status": "read_ok"}

    with pytest.raises(RuntimeError, match="ReadingCoordinator.*fechado|ReadingCoordinator is closed"):
        await coord.fetch_url("https://example.org/new", new_fetch)

    assert not new_called, "Nova tarefa foi admitida enquanto close() drenava tarefas pendentes!"

    # Libera cleanup e finaliza
    release_cleanup.set()
    await close_task
    with pytest.raises(asyncio.CancelledError):
        await t1


@pytest.mark.asyncio
async def test_reading_coordinator_close_is_idempotent() -> None:
    """close() invocado múltiplas vezes não gera erro e mantém estado fechado."""
    coord = ReadingCoordinator()
    await coord.close()
    await coord.close()
    await coord.close()

    async def fetch_dummy():
        return None

    with pytest.raises(RuntimeError):
        await coord.fetch_url("https://example.org/idempotent", fetch_dummy)


@pytest.mark.asyncio
async def test_reading_coordinator_close_shielded_against_cancellation() -> None:
    """Se a task que chama close() for cancelada, o cancel e drenagem das tarefas em andamento continua blindado."""
    coord = ReadingCoordinator()
    url = "https://example.org/close-cancel"

    started = asyncio.Event()
    cleanup_done = asyncio.Event()

    async def slow_fetch():
        started.set()
        try:
            await asyncio.sleep(10.0)
        finally:
            await asyncio.sleep(0.05)
            cleanup_done.set()

    t_fetch = asyncio.create_task(coord.fetch_url(url, slow_fetch))
    await started.wait()

    # Dispara close() e cancela a task de close imediatamente
    close_task = asyncio.create_task(coord.close())
    await asyncio.sleep(0.01)
    close_task.cancel()

    # Mesmo com cancel no chamador de close, a drenagem deve ser garantida
    with pytest.raises(asyncio.CancelledError):
        await close_task

    # Aguarda um instante para conferir que a task interna não ficou órfã
    assert cleanup_done.is_set(), "Drenagem da task não foi concluída após cancelamento de close()!"
    with pytest.raises(asyncio.CancelledError):
        await t_fetch


@pytest.mark.asyncio
async def test_reading_coordinator_multiple_consumers_coexistence_and_close() -> None:
    """Múltiplos consumidores na mesma URL coexistem: cancelamento de um não afeta outros; close() encerra todos."""
    coord = ReadingCoordinator()
    url = "https://example.org/multi-consumer"

    started = asyncio.Event()

    async def shared_fetch():
        started.set()
        await asyncio.sleep(10.0)
        return {"url": url, "body": "ok", "status": "read_ok"}

    c1 = asyncio.create_task(coord.fetch_url(url, shared_fetch))
    await started.wait()
    c2 = asyncio.create_task(coord.fetch_url(url, shared_fetch))
    c3 = asyncio.create_task(coord.fetch_url(url, shared_fetch))

    # Cancela apenas c1
    c1.cancel()
    with pytest.raises(asyncio.CancelledError):
        await c1

    # c2 e c3 continuam vivos e não foram cancelados
    assert not c2.done()
    assert not c3.done()

    # Agora fecha o coordenador
    await coord.close()

    # c2 e c3 devem ter recebido o encerramento da task
    with pytest.raises(asyncio.CancelledError):
        await c2
    with pytest.raises(asyncio.CancelledError):
        await c3

