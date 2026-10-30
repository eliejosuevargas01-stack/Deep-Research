# -*- coding: utf-8 -*-
"""Testes determinísticos de cancelamento e proteção de reservas para Searcher e Auditor.

Cobre:
1. Interrupção pré-try / logo após reserva em Auditor (linhas 1122-1144) e liberação atômica via CAS.
2. Cancelamento repetido em Auditor durante cleanup / release sem perder liberação.
3. Interrupção pré-try / logo após reserva em Searcher (linhas 1315-1321) e cleanup via CAS.
4. Single-session fallback com transação abortada prévia: rollback antes do cleanup para não perder diagnóstico.
"""

import asyncio
from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional
import httpx
import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.auditor import AUDIT_POINT_LEASE_SECONDS, Auditor
from app.core.searcher import SEARCH_POINT_LEASE_SECONDS, Searcher
from app.db.init_db import init_db
from app.db.models import ConteudoColetado, GenerationAttempt, Pesquisa, Ponto
from app.db.research_repository import ResearchRepository
from app.db.session import create_engine_with_pragmas
from app.tools.jina_client import JinaClient
from app.tools.llm_client import LLMClient
from tests.unit.test_audit_acceptance import (
    create_research_fixture_with_plan,
    make_standard_coleta_metadata,
)
from tests.unit.test_reproduction_gate1_helpers import make_llm_json_response

DEFAULT_AUDITOR_PERSONAS = ["planejador", "historiador", "visionario", "cetico", "futurista", "auditor", "redator final"]


@pytest.mark.asyncio
async def test_auditor_cancellation_immediately_after_reserve_releases_via_cas(test_env, tmp_path) -> None:
    """Auditor cancelado logo após reserva (linhas 1122-1144 pré-try) DEVE liberar a reserva via CAS."""
    db_file = tmp_path / "audit_cancel_pre_try.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"
    engine = create_engine_with_pragmas(db_url)
    await init_db(engine)

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with session_maker() as s_init:
        r_init = ResearchRepository(session=s_init)
        pesq, pontos = await create_research_fixture_with_plan(r_init, n_pontos=1)
        ponto = pontos[0]
        meta = make_standard_coleta_metadata(source_url="https://php.net/sec")
        await r_init.save_collected_content(
            id_pesquisa=pesq.id_pesquisa,
            ponto_id=ponto.ponto_id,
            tema=pesq.tema,
            ponto=ponto.ponto,
            conteudo_coletado="Conteudo inicial",
            urls_lidas=["https://php.net/sec"],
            urls_fonte=["https://php.net/sec"],
            metadados_coleta=meta,
            rodada=1,
        )

    # Hook em get_point dentro do auditor para cancelar a task logo após a reserva
    task_ref = [None]
    reserve_done = asyncio.Event()

    async with session_maker() as s_run:
        repo = ResearchRepository(session=s_run)
        orig_get_point = repo.get_point

        async def hooked_get_point(ponto_id: str):
            # Chamado na linha 1125, logo após reserve_point_for_audit
            reserve_done.set()
            # Força o cancelamento da task corrente exatamente no intervalo pré-try
            if task_ref[0] is not None:
                task_ref[0].cancel()
            await asyncio.sleep(0)  # Cede controle para propagar CancelledError
            return await orig_get_point(ponto_id)

        repo.get_point = hooked_get_point

        llm = LLMClient(api_key="mock", transport=httpx.MockTransport(lambda r: make_llm_json_response({})))
        auditor = Auditor(
            research_repo=repo,
            llm_client=llm,
            personas=DEFAULT_AUDITOR_PERSONAS,
            session_factory=session_maker,
        )

        task = asyncio.create_task(auditor.execute_audit(id_pesquisa=pesq.id_pesquisa, criterios_minimos=11))
        task_ref[0] = task

        with pytest.raises(asyncio.CancelledError):
            await task
        await llm.aclose()

    # Verifica o estado no banco de dados: o ponto NÃO pode ficar preso em 'auditando'!
    async with session_maker() as s_check:
        r_check = ResearchRepository(session=s_check)
        ponto_db = await r_check.get_point(ponto.ponto_id)
        assert ponto_db is not None
        assert ponto_db.status != "auditando", f"Ponto ficou travado em 'auditando' após cancelamento pré-try: {ponto_db.status}"


@pytest.mark.asyncio
async def test_auditor_repeated_cancellation_during_release_does_not_abort_cleanup(test_env, tmp_path) -> None:
    """Cancelamento repetido no Auditor durante release_point_audit_reservation não aborta a blindagem."""
    db_file = tmp_path / "audit_repeated_cancel.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"
    engine = create_engine_with_pragmas(db_url)
    await init_db(engine)

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with session_maker() as s_init:
        r_init = ResearchRepository(session=s_init)
        pesq, pontos = await create_research_fixture_with_plan(r_init, n_pontos=1)
        ponto = pontos[0]
        meta = make_standard_coleta_metadata(source_url="https://php.net/sec")
        await r_init.save_collected_content(
            id_pesquisa=pesq.id_pesquisa,
            ponto_id=ponto.ponto_id,
            tema=pesq.tema,
            ponto=ponto.ponto,
            conteudo_coletado="Conteudo inicial",
            urls_lidas=["https://php.net/sec"],
            urls_fonte=["https://php.net/sec"],
            metadados_coleta=meta,
            rodada=1,
        )

    llm_started = asyncio.Event()

    async def slow_llm_handler(req: httpx.Request) -> httpx.Response:
        llm_started.set()
        await asyncio.sleep(10.0)
        return make_llm_json_response({})

    task_ref = [None]

    async with session_maker() as s_run:
        repo = ResearchRepository(session=s_run)
        orig_release = repo.release_point_audit_reservation

        async def hooked_release(*args, **kwargs):
            # Dispara cancelamento repetido enquanto o release está executando
            if task_ref[0] is not None:
                task_ref[0].cancel()
                task_ref[0].cancel()
            await asyncio.sleep(0.05)
            return await orig_release(*args, **kwargs)

        repo.release_point_audit_reservation = hooked_release

        llm = LLMClient(api_key="mock", transport=httpx.MockTransport(slow_llm_handler))
        auditor = Auditor(
            research_repo=repo,
            llm_client=llm,
            personas=DEFAULT_AUDITOR_PERSONAS,
            session_factory=session_maker,
        )

        task = asyncio.create_task(auditor.execute_audit(id_pesquisa=pesq.id_pesquisa, criterios_minimos=11))
        task_ref[0] = task

        await llm_started.wait()
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task
        await llm.aclose()

    # O ponto deve ter sido liberado com sucesso apesar do cancelamento repetido no handler
    async with session_maker() as s_check:
        r_check = ResearchRepository(session=s_check)
        ponto_db = await r_check.get_point(ponto.ponto_id)
        assert ponto_db is not None
        assert ponto_db.status != "auditando", f"Ponto ficou travado em 'auditando': {ponto_db.status}"


@pytest.mark.asyncio
async def test_searcher_cancellation_during_or_immediately_after_reserve_releases_via_cas(test_env, tmp_path) -> None:
    """Searcher cancelado durante o commit da reserva ou logo no retorno (antes de entrar no try antigo) DEVE liberar a reserva via CAS."""
    db_file = tmp_path / "search_cancel_at_reserve.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"
    engine = create_engine_with_pragmas(db_url)
    await init_db(engine)

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with session_maker() as s_init:
        r_init = ResearchRepository(session=s_init)
        pesq, pontos = await create_research_fixture_with_plan(r_init, n_pontos=1)
        ponto = pontos[0]
        p_id = str(ponto.ponto_id)

    task_ref = [None]

    async with session_maker() as s_run:
        repo = ResearchRepository(session=s_run)
        orig_reserve = repo.reserve_point

        async def hooked_reserve(*args, **kwargs):
            # Executa a reserva no banco (efetiva o UPDATE e commit)
            res = await orig_reserve(*args, **kwargs)
            # Cancela a tarefa no retorno exato da reserva (antes de qualquer bloco try subsequente no caller)
            if task_ref[0] is not None:
                task_ref[0].cancel()
            await asyncio.sleep(0)  # Cede controle para propagar CancelledError imediatamente
            return res

        repo.reserve_point = hooked_reserve

        llm = LLMClient(api_key="mock", transport=httpx.MockTransport(lambda r: make_llm_json_response({})))
        jina = JinaClient(api_key="mock", transport=httpx.MockTransport(lambda r: httpx.Response(200, json={})))
        searcher = Searcher(
            research_repo=repo,
            jina_client=jina,
            llm_client=llm,
            personas=["historiador"],
            session_factory=session_maker,
        )

        task = asyncio.create_task(searcher.execute_search(id_pesquisa=pesq.id_pesquisa, ponto_id=p_id))
        task_ref[0] = task

        with pytest.raises(asyncio.CancelledError):
            await task
        await llm.aclose()
        await jina.aclose()

    # O ponto NÃO pode ficar em 'em_andamento'
    async with session_maker() as s_check:
        r_check = ResearchRepository(session=s_check)
        ponto_db = await r_check.get_point(p_id)
        assert ponto_db is not None
        assert ponto_db.status != "em_andamento", f"Ponto ficou travado em 'em_andamento' após cancelamento na reserva: {ponto_db.status}"


@pytest.mark.asyncio
async def test_single_session_fallback_aborted_tx_rolls_back_before_cleanup(test_env, tmp_path) -> None:
    """Em single-session fallback (session_factory=None), transação abortada sofre rollback prévio para salvar diagnóstico e liberar."""
    db_file = tmp_path / "single_session_abort.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"
    engine = create_engine_with_pragmas(db_url)
    await init_db(engine)

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with session_maker() as s_single:
        repo = ResearchRepository(session=s_single)
        pesq, pontos = await create_research_fixture_with_plan(repo, n_pontos=1)
        ponto = pontos[0]
        p_id = str(ponto.ponto_id)

        async def failing_llm_handler(req: httpx.Request) -> httpx.Response:
            # Provoca erro que coloca s_single em estado de rollback pendente (PendingRollbackError)
            bad_p = Pesquisa(id_pesquisa="conflict_id", tema="t1")
            s_single.add(bad_p)
            try:
                await s_single.flush()
            except Exception:
                pass
            raise RuntimeError("Falha de rede LLM fatal após flush corrompido")

        llm = LLMClient(api_key="mock", transport=httpx.MockTransport(failing_llm_handler))
        jina = JinaClient(api_key="mock", transport=httpx.MockTransport(lambda r: httpx.Response(200, json={})))
        searcher = Searcher(
            research_repo=repo,
            jina_client=jina,
            llm_client=llm,
            personas=["historiador"],
            session_factory=None,
        )
        searcher.session_factory = None

        with pytest.raises(Exception):
            await searcher.execute_search(id_pesquisa=pesq.id_pesquisa, ponto_id=p_id)
        await llm.aclose()
        await jina.aclose()

    # Verifica se o diagnóstico e liberação foram executados sem estourar PendingRollbackError
    async with session_maker() as s_check:
        r_check = ResearchRepository(session=s_check)
        ponto_db = await r_check.get_point(p_id)
        assert ponto_db is not None
        assert ponto_db.status in ("falha_coleta", "falha"), f"Status inesperado: {ponto_db.status}"
        assert ponto_db.pontos_fracos is not None, "Diagnóstico não foi salvo devido a falha no cleanup!"
        assert "Falha de rede LLM fatal" in ponto_db.pontos_fracos or "Interrupção na busca" in ponto_db.pontos_fracos


@pytest.mark.asyncio
async def test_auditor_single_session_fallback_aborted_tx_rolls_back_before_cleanup(test_env, tmp_path) -> None:
    """Em Auditor single-session fallback (session_factory=None), transação abortada sofre rollback prévio para liberar via CAS."""
    db_file = tmp_path / "audit_single_abort.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"
    engine = create_engine_with_pragmas(db_url)
    await init_db(engine)

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with session_maker() as s_single:
        repo = ResearchRepository(session=s_single)
        pesq, pontos = await create_research_fixture_with_plan(repo, n_pontos=1)
        ponto = pontos[0]
        p_id = str(ponto.ponto_id)
        meta = make_standard_coleta_metadata(source_url="https://php.net/sec")
        await repo.save_collected_content(
            id_pesquisa=pesq.id_pesquisa,
            ponto_id=p_id,
            tema=pesq.tema,
            ponto=ponto.ponto,
            conteudo_coletado="Conteudo inicial",
            urls_lidas=["https://php.net/sec"],
            urls_fonte=["https://php.net/sec"],
            metadados_coleta=meta,
            rodada=1,
        )

        async def failing_llm_handler(req: httpx.Request) -> httpx.Response:
            # Corrompe a transação atual para gerar PendingRollbackError
            bad_p = Pesquisa(id_pesquisa="conflict_audit", tema="t1")
            s_single.add(bad_p)
            try:
                await s_single.flush()
            except Exception:
                pass
            raise RuntimeError("Falha de rede LLM com transação pendente de rollback")

        llm = LLMClient(api_key="mock", transport=httpx.MockTransport(failing_llm_handler))
        auditor = Auditor(
            research_repo=repo,
            llm_client=llm,
            personas=DEFAULT_AUDITOR_PERSONAS,
            session_factory=None,
        )
        auditor.session_factory = None

        with pytest.raises(Exception):
            await auditor.execute_audit(id_pesquisa=pesq.id_pesquisa, criterios_minimos=11)
        await llm.aclose()

    async with session_maker() as s_check:
        r_check = ResearchRepository(session=s_check)
        ponto_db = await r_check.get_point(p_id)
        assert ponto_db is not None
        assert ponto_db.status != "auditando", f"Ponto permaneceu em 'auditando': {ponto_db.status}"
        assert ponto_db.status == "coletado"


@pytest.mark.asyncio
async def test_searcher_rejected_concurrent_worker_with_identical_timestamp_never_releases_owner(test_env, tmp_path) -> None:
    """Worker rejeitado por concorrência em Searcher NUNCA pode liberar a reserva do worker dono, mesmo se timestamp colidir."""
    from unittest.mock import patch

    db_file = tmp_path / "searcher_collision.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"
    engine = create_engine_with_pragmas(db_url)
    await init_db(engine)

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    fixed_time = datetime.now(timezone.utc)
    fixed_iso = fixed_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    class MockDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed_time

    with patch("app.core.searcher.datetime", MockDatetime), patch("app.db.research_repository.datetime", MockDatetime):
        async with session_maker() as s_init:
            r_init = ResearchRepository(session=s_init)
            pesq, pontos = await create_research_fixture_with_plan(r_init, n_pontos=1)
            p_id = str(pontos[0].ponto_id)

        # Worker 2 faz snapshot inicial de list_points antes da reserva de Worker 1
        async with session_maker() as s_w2:
            repo_w2 = ResearchRepository(session=s_w2)
            pts_w2 = await repo_w2.list_points(pesq.id_pesquisa)

            # Worker 1 adquire legitimamente a reserva do ponto no instante fixo
            async with session_maker() as s_w1:
                r_w1 = ResearchRepository(session=s_w1)
                await r_w1.reserve_point(p_id, lease_seconds=600, lease_token=fixed_iso)

            # Confere que Worker 1 é dono ativo da reserva
            async with session_maker() as s_verify:
                r_verify = ResearchRepository(session=s_verify)
                p_owner = await r_verify.get_point(p_id)
                assert p_owner is not None
                assert p_owner.status == "em_andamento"
                assert p_owner.atualizado_em == fixed_iso

            # Worker 2 é disparado no mesmo instante fixo com o snapshot concorrente
            repo_w2.list_points = lambda id_pesquisa: asyncio.sleep(0, result=pts_w2)

            llm_w2 = LLMClient(api_key="mock", transport=httpx.MockTransport(lambda r: make_llm_json_response({})))
            jina_w2 = JinaClient(api_key="mock", transport=httpx.MockTransport(lambda r: httpx.Response(200, json={})))
            searcher_w2 = Searcher(
                research_repo=repo_w2,
                jina_client=jina_w2,
                llm_client=llm_w2,
                personas=["historiador"],
                session_factory=session_maker,
            )

            with pytest.raises(Exception) as exc_info:
                await searcher_w2.execute_search(id_pesquisa=pesq.id_pesquisa, ponto_id=p_id)

            assert "CONCURRENT_EXECUTION" in str(exc_info.value) or "já está em andamento" in str(exc_info.value)

            await llm_w2.aclose()
            await jina_w2.aclose()

        # VULNERABILIDADE RED: No código vulnerável, Worker 2 cai no except e libera a reserva de Worker 1 via candidate!
        # O Ponto deve permanecer ESTRITAMENTE em 'em_andamento' sob a posse de Worker 1!
        async with session_maker() as s_final:
            r_final = ResearchRepository(session=s_final)
            p_final = await r_final.get_point(p_id)
            assert p_final is not None
            assert p_final.status == "em_andamento", (
                f"VULNERABILIDADE DETECTADA: Worker 2 rejeitado liberou a reserva do Worker 1! "
                f"Status atual: '{p_final.status}' (esperado 'em_andamento'), pontos_fracos: '{p_final.pontos_fracos}'"
            )

    await engine.dispose()


@pytest.mark.asyncio
async def test_auditor_rejected_concurrent_worker_with_identical_timestamp_never_releases_owner(test_env, tmp_path) -> None:
    """Worker rejeitado por concorrência em Auditor NUNCA pode liberar a reserva de auditoria do dono, mesmo sob colisão de timestamp."""
    from unittest.mock import patch

    db_file = tmp_path / "auditor_collision.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"
    engine = create_engine_with_pragmas(db_url)
    await init_db(engine)

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    fixed_time = datetime.now(timezone.utc)
    fixed_iso = fixed_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    class MockDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed_time

    with patch("app.core.auditor.datetime", MockDatetime), patch("app.db.research_repository.datetime", MockDatetime):
        async with session_maker() as s_init:
            r_init = ResearchRepository(session=s_init)
            pesq, pontos = await create_research_fixture_with_plan(r_init, n_pontos=1)
            p_id = str(pontos[0].ponto_id)

            meta = make_standard_coleta_metadata(source_url="https://php.net/sec")
            await r_init.save_collected_content(
                id_pesquisa=pesq.id_pesquisa,
                ponto_id=p_id,
                tema=pesq.tema,
                ponto=pontos[0].ponto,
                conteudo_coletado="Conteudo inicial",
                urls_lidas=["https://php.net/sec"],
                urls_fonte=["https://php.net/sec"],
                metadados_coleta=meta,
                rodada=1,
            )

        # Worker 2 faz snapshot inicial de list_points antes da reserva de Worker 1
        async with session_maker() as s_w2:
            repo_w2 = ResearchRepository(session=s_w2)
            pts_w2 = await repo_w2.list_points(pesq.id_pesquisa)

            # Worker 1 adquire legitimamente a reserva de auditoria no instante fixo
            async with session_maker() as s_w1:
                r_w1 = ResearchRepository(session=s_w1)
                await r_w1.reserve_point_for_audit(p_id, lease_seconds=600, lease_token=fixed_iso)

            # Confere que Worker 1 é dono ativo da auditoria
            async with session_maker() as s_verify:
                r_verify = ResearchRepository(session=s_verify)
                p_owner = await r_verify.get_point(p_id)
                assert p_owner is not None
                assert p_owner.status == "auditando"
                assert p_owner.atualizado_em == fixed_iso

            repo_w2.list_points = lambda id_pesquisa: asyncio.sleep(0, result=pts_w2)

            llm_w2 = LLMClient(api_key="mock", transport=httpx.MockTransport(lambda r: make_llm_json_response({})))
            auditor_w2 = Auditor(
                research_repo=repo_w2,
                llm_client=llm_w2,
                personas=DEFAULT_AUDITOR_PERSONAS,
                session_factory=session_maker,
            )

            with pytest.raises(Exception) as exc_info:
                await auditor_w2.execute_audit(id_pesquisa=pesq.id_pesquisa, criterios_minimos=11)

            assert "CONCURRENT_EXECUTION" in str(exc_info.value) or "já está em andamento" in str(exc_info.value)

            await llm_w2.aclose()

        # VULNERABILIDADE RED: Worker 2 rejeitado nunca deve liberar Worker 1!
        async with session_maker() as s_final:
            r_final = ResearchRepository(session=s_final)
            p_final = await r_final.get_point(p_id)
            assert p_final is not None
            assert p_final.status == "auditando", (
                f"VULNERABILIDADE DETECTADA: Worker 2 rejeitado liberou a auditoria de Worker 1! "
                f"Status atual: '{p_final.status}' (esperado 'auditando'), pontos_fracos: '{p_final.pontos_fracos}'"
            )

    await engine.dispose()


@pytest.mark.asyncio
async def test_storage_varchar_30_limits_and_iso_format_compliance(test_env, tmp_path) -> None:
    """Verifica cumprimento estrito do limite VARCHAR(30) para datas e compilação do schema no dialeto PostgreSQL."""
    from sqlalchemy.dialects.postgresql import dialect as postgresql_dialect
    from sqlalchemy.schema import CreateTable

    # 1. Prova contratual: compilador PostgreSQL gera VARCHAR(30) para atualizado_em e VARCHAR(64) para lease_token
    pg_table_ddl = str(CreateTable(Ponto.__table__).compile(dialect=postgresql_dialect()))
    assert "VARCHAR(30)" in pg_table_ddl
    assert "VARCHAR(64)" in pg_table_ddl

    # 2. Execução real no SQLite com WAL e verificação dos tamanhos de strings de data
    db_file = tmp_path / "storage_limits.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"
    engine = create_engine_with_pragmas(db_url)
    await init_db(engine)

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with session_maker() as s:
        repo = ResearchRepository(session=s)
        pesq, pontos = await create_research_fixture_with_plan(repo, n_pontos=1)
        p_id = str(pontos[0].ponto_id)

        # Reserva de busca gera atualizado_em <= 30 chars e lease_token de 32 chars hex
        p_res = await repo.reserve_point(p_id)
        assert len(p_res.atualizado_em) <= 30
        assert len(p_res.atualizado_em) == 27  # Formato estrito YYYY-MM-DDTHH:MM:SS.ffffffZ
        assert p_res.atualizado_em.endswith("Z")
        assert p_res.lease_token is not None
        assert len(p_res.lease_token) == 32

        # Salvamento de conteúdo preserva limites
        meta = make_standard_coleta_metadata(source_url="https://php.net/sec")
        await repo.save_collected_content(
            id_pesquisa=pesq.id_pesquisa,
            ponto_id=p_id,
            tema=pesq.tema,
            ponto=pontos[0].ponto,
            conteudo_coletado="Conteudo teste",
            urls_lidas=["https://php.net/sec"],
            urls_fonte=["https://php.net/sec"],
            metadados_coleta=meta,
            expected_tentativa=1,
            expected_token=p_res.lease_token,
        )
        p_coletado = await repo.get_point(p_id)
        assert p_coletado is not None
        assert len(p_coletado.atualizado_em) <= 30
        assert p_coletado.lease_token is None

        # Reserva de auditoria gera lease_token forte e data <= 30 chars
        tok_audit = await repo.reserve_point_for_audit(p_id)
        p_audit = await repo.get_point(p_id)
        assert p_audit is not None
        assert len(p_audit.atualizado_em) <= 30
        assert len(tok_audit) == 32
        assert p_audit.lease_token == tok_audit

        # Liberação de auditoria
        await repo.release_point_audit_reservation(p_id, expected_token=tok_audit, expected_tentativa=1)
        p_rel = await repo.get_point(p_id)
        assert p_rel is not None
        assert len(p_rel.atualizado_em) <= 30
        assert p_rel.lease_token is None

    await engine.dispose()


@pytest.mark.asyncio
async def test_searcher_cancellation_during_commit_or_refresh_barrier_releases_via_candidate_cas(test_env, tmp_path) -> None:
    """Barrier real durante commit/refresh da reserva em Searcher: se cancelado durante commit sobrevivente,
    cleanup com token candidato UUID CAS NÃO é pulado e libera posse órfã em sessão independente."""
    db_file = tmp_path / "search_barrier_cancel.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"
    engine = create_engine_with_pragmas(db_url)
    await init_db(engine)

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with session_maker() as s_init:
        r_init = ResearchRepository(session=s_init)
        pesq, pontos = await create_research_fixture_with_plan(r_init, n_pontos=1)
        p_id = str(pontos[0].ponto_id)

    barrier = asyncio.Barrier(2)
    task_ref: List[Optional[asyncio.Task]] = [None]
    worker_task: List[Optional[asyncio.Task]] = [None]

    async with session_maker() as s_worker:
        repo = ResearchRepository(session=s_worker)
        orig_reserve = repo.reserve_point
        orig_commit = s_worker.commit
        in_reserve = [True]

        async def hooked_reserve(*args, **kwargs):
            worker_task[0] = asyncio.current_task()
            return await orig_reserve(*args, **kwargs)

        async def hooked_commit(*args, **kwargs):
            if in_reserve[0]:
                in_reserve[0] = False
                await barrier.wait()
            return await orig_commit(*args, **kwargs)

        repo.reserve_point = hooked_reserve
        s_worker.commit = hooked_commit

        llm = LLMClient(api_key="mock", transport=httpx.MockTransport(lambda r: make_llm_json_response({})))
        jina = JinaClient(api_key="mock", transport=httpx.MockTransport(lambda r: httpx.Response(200, json={})))
        searcher = Searcher(
            research_repo=repo,
            jina_client=jina,
            llm_client=llm,
            personas=["historiador"],
            session_factory=session_maker,
        )

        task = asyncio.create_task(searcher.execute_search(id_pesquisa=pesq.id_pesquisa, ponto_id=p_id))
        task_ref[0] = task

        # Aguarda o commit da reserva ser efetivado no banco
        await barrier.wait()
        # Cancela a tarefa do worker que executa a reserva durante o commit/refresh
        if worker_task[0] is not None:
            worker_task[0].cancel()
            worker_task[0].cancel()
        task.cancel()
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task
        assert task.done()
        await llm.aclose()
        await jina.aclose()

    # Sessão independente verifica ausência de posse órfã
    async with session_maker() as s_check:
        r_check = ResearchRepository(session=s_check)
        ponto_db = await r_check.get_point(p_id)
        assert ponto_db is not None
        assert ponto_db.status != "em_andamento", (
            f"FALHA: Ponto ficou órfão em 'em_andamento' porque reserved_token era None no cancelamento! "
            f"lease_token={ponto_db.lease_token}"
        )
        assert ponto_db.lease_token is None, f"Posse órfã: lease_token não foi liberado via CAS: {ponto_db.lease_token}"

    await engine.dispose()


@pytest.mark.asyncio
async def test_auditor_cancellation_during_commit_or_refresh_barrier_releases_via_candidate_cas(test_env, tmp_path) -> None:
    """Barrier real durante commit/refresh da reserva em Auditor: se cancelado durante commit sobrevivente,
    cleanup com token candidato UUID CAS NÃO é pulado e libera posse órfã em sessão independente."""
    db_file = tmp_path / "audit_barrier_cancel.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"
    engine = create_engine_with_pragmas(db_url)
    await init_db(engine)

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with session_maker() as s_init:
        r_init = ResearchRepository(session=s_init)
        pesq, pontos = await create_research_fixture_with_plan(r_init, n_pontos=1)
        p_id = str(pontos[0].ponto_id)
        meta = make_standard_coleta_metadata(source_url="https://php.net/sec")
        await r_init.save_collected_content(
            id_pesquisa=pesq.id_pesquisa,
            ponto_id=p_id,
            tema=pesq.tema,
            ponto=pontos[0].ponto,
            conteudo_coletado="Conteudo inicial",
            urls_lidas=["https://php.net/sec"],
            urls_fonte=["https://php.net/sec"],
            metadados_coleta=meta,
            rodada=1,
        )

    barrier = asyncio.Barrier(2)
    task_ref: List[Optional[asyncio.Task]] = [None]

    async with session_maker() as s_worker:
        repo = ResearchRepository(session=s_worker)
        orig_commit = s_worker.commit
        in_reserve = [True]

        async def hooked_commit():
            if in_reserve[0]:
                in_reserve[0] = False
                await barrier.wait()
            return await orig_commit()

        s_worker.commit = hooked_commit

        llm = LLMClient(api_key="mock", transport=httpx.MockTransport(lambda r: make_llm_json_response({})))
        auditor = Auditor(
            research_repo=repo,
            llm_client=llm,
            personas=DEFAULT_AUDITOR_PERSONAS,
            session_factory=session_maker,
        )

        task = asyncio.create_task(auditor.execute_audit(id_pesquisa=pesq.id_pesquisa, criterios_minimos=11))
        task_ref[0] = task

        # Aguarda o commit da reserva de auditoria no banco
        await barrier.wait()
        # Dispara cancelamento único/repetido no worker
        task.cancel()
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task
        assert task.done()
        await llm.aclose()

    # Sessão independente verifica ausência de posse órfã
    async with session_maker() as s_check:
        r_check = ResearchRepository(session=s_check)
        ponto_db = await r_check.get_point(p_id)
        assert ponto_db is not None
        assert ponto_db.status != "auditando", (
            f"FALHA: Ponto ficou órfão em 'auditando' porque token_audit era None no cancelamento! "
            f"lease_token={ponto_db.lease_token}"
        )
        assert ponto_db.lease_token is None, f"Posse órfã: lease_token não foi liberado via CAS: {ponto_db.lease_token}"

    await engine.dispose()


@pytest.mark.asyncio
async def test_save_collected_content_requires_cas_token_and_rejects_stolen_or_wrong_lease_on_same_tentativa(test_env, tmp_path) -> None:
    """Demonstra caso real de mesma tentativa/posse: save_collected_content DEVE exigir CAS por token.
    Impede que worker com token expirado/antigo ou chamada sem token finalize e roube reserva ativa de outro worker."""
    db_file = tmp_path / "save_cas_token.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"
    engine = create_engine_with_pragmas(db_url)
    await init_db(engine)

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with session_maker() as s_init:
        r_init = ResearchRepository(session=s_init)
        pesq, pontos = await create_research_fixture_with_plan(r_init, n_pontos=1)
        p_id = str(pontos[0].ponto_id)

    # 1. Worker 1 adquire reserva legítima com token_1 na tentativa 1
    token_1 = "tok_worker_1_" + "a" * 20
    async with session_maker() as s1:
        r1 = ResearchRepository(session=s1)
        p_res1 = await r1.reserve_point(p_id, lease_seconds=600, lease_token=token_1)
        assert p_res1.tentativas == 1
        assert p_res1.lease_token == token_1

    # 2. Simula reassociação/posse concorrente na mesma tentativa 1 por Worker 2 com token_2
    token_2 = "tok_worker_2_" + "b" * 20
    async with session_maker() as s_admin:
        p_obj = (await s_admin.execute(select(Ponto).where(Ponto.ponto_id == p_id))).scalar_one()
        p_obj.lease_token = token_2
        p_obj.status = "em_andamento"
        p_obj.tentativas = 1
        await s_admin.commit()

    # 3. Worker 1 atrasado tenta salvar com seu token antigo token_1 (mesma tentativa 1) -> DEVE FALHAR via CAS
    async with session_maker() as s1_late:
        r1_late = ResearchRepository(session=s1_late)
        with pytest.raises(RuntimeError, match=r"(?i)(POSSESSION_LOST|posse|token)"):
            await r1_late.save_collected_content(
                id_pesquisa=pesq.id_pesquisa,
                ponto_id=p_id,
                tema=pesq.tema,
                ponto=pontos[0].ponto,
                conteudo_coletado="Conteudo atrasado do Worker 1",
                urls_lidas=[],
                urls_fonte=[],
                expected_tentativa=1,
                expected_token=token_1,  # Token 1 não confere com token 2 ativo no banco!
            )

    # 4. Chamador não autenticado (expected_token=None) tenta salvar na mesma tentativa 1 sem token -> DEVE FALHAR (não pode roubar lease ativa)
    async with session_maker() as s_rogue:
        r_rogue = ResearchRepository(session=s_rogue)
        with pytest.raises(RuntimeError, match=r"(?i)(POSSESSION_LOST|posse|token)"):
            await r_rogue.save_collected_content(
                id_pesquisa=pesq.id_pesquisa,
                ponto_id=p_id,
                tema=pesq.tema,
                ponto=pontos[0].ponto,
                conteudo_coletado="Conteudo sem token tentando roubar",
                urls_lidas=[],
                urls_fonte=[],
                expected_tentativa=1,
                expected_token=None,  # Sem token não pode sobrescrever lease ativa!
            )

    # 5. Worker 2 dono legítimo salva com expected_token=token_2 -> DEVE PASSAR com sucesso
    async with session_maker() as s2:
        r2 = ResearchRepository(session=s2)
        coleta_ok = await r2.save_collected_content(
            id_pesquisa=pesq.id_pesquisa,
            ponto_id=p_id,
            tema=pesq.tema,
            ponto=pontos[0].ponto,
            conteudo_coletado="Conteudo legítimo do Worker 2",
            urls_lidas=["https://exemplo.com/ok"],
            urls_fonte=["https://exemplo.com/ok"],
            expected_tentativa=1,
            expected_token=token_2,
        )
        assert coleta_ok is not None

        # Ponto agora foi finalizado como 'coletado' e lease_token foi limpo
        p_final = await r2.get_point(p_id)
        assert p_final is not None
        assert p_final.status == "coletado"
        assert p_final.lease_token is None

    # 6. Fallback legado: registro sem lease ativa (lease_token IS NULL) aceita expected_tentativa sem quebrar
    async with session_maker() as s_legado:
        # Coloca ponto em em_andamento com lease_token=None (modelo legado)
        p_obj = (await s_legado.execute(select(Ponto).where(Ponto.ponto_id == p_id))).scalar_one()
        p_obj.status = "em_andamento"
        p_obj.lease_token = None
        p_obj.tentativas = 2
        await s_legado.commit()

    await engine.dispose()


@pytest.mark.asyncio
async def test_timestamp_harmonization_across_all_paths_and_legacy_timezone_migration(test_env, tmp_path) -> None:
    """Verifica que todos os paths do banco geram estritamente timestamps UTC de 27 chars (VARCHAR(30)),
    e que a migração aditiva normaliza legados com offsets de fuso e fronteiras preservando a comparação de lease."""
    from app.db.credentials_repository import CredentialsRepository
    from app.services.crypto_service import CryptoService

    db_file = tmp_path / "timestamp_harmonization.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"
    engine = create_engine_with_pragmas(db_url)
    await init_db(engine)

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    # 1. Criação de pesquisa: criado_em e pontos atualizado_em/criado_em DEVEM ter 27 chars e terminar com 'Z'
    async with session_maker() as s1:
        r1 = ResearchRepository(session=s1)
        pesq = await r1.create_research(
            tema="Pesquisa Timestamps",
            pontos_textos=["Ponto 1", "Ponto 2"],
        )
        pontos = await r1.list_points(pesq.id_pesquisa)
        assert len(pesq.criado_em) == 27, f"pesquisa.criado_em tem tamanho {len(pesq.criado_em)}: '{pesq.criado_em}'"
        assert pesq.criado_em.endswith("Z")

        p0 = pontos[0]
        assert len(p0.criado_em) == 27, f"ponto.criado_em tem tamanho {len(p0.criado_em)}: '{p0.criado_em}'"
        assert len(p0.atualizado_em) == 27, f"ponto.atualizado_em tem tamanho {len(p0.atualizado_em)}: '{p0.atualizado_em}'"
        assert p0.criado_em.endswith("Z")
        assert p0.atualizado_em.endswith("Z")

        # 2. update_point_status DEVE gerar atualizado_em com 27 chars e terminar com 'Z'
        p_upd = await r1.update_point_status(p0.ponto_id, status="em_andamento")
        assert len(p_upd.atualizado_em) == 27, f"update_point_status atualizado_em tem {len(p_upd.atualizado_em)}: '{p_upd.atualizado_em}'"
        assert p_upd.atualizado_em.endswith("Z")

        # 3. update_research_dossier DEVE gerar concluido_em com 27 chars e terminar com 'Z'
        p_comp = await r1.update_research_dossier(pesq.id_pesquisa, dossier_final="# Dossiê")
        assert p_comp is not None
        assert p_comp.concluido_em is not None
        assert len(p_comp.concluido_em) == 27, f"concluido_em tem tamanho {len(p_comp.concluido_em)}: '{p_comp.concluido_em}'"
        assert p_comp.concluido_em.endswith("Z")

        # 4. Credencial atualizado_em DEVE ter 27 chars e terminar com 'Z'
        crypto = CryptoService()
        c_repo = CredentialsRepository(session=s1, crypto_service=crypto)
        cred = await c_repo.save_credential("CHAVE_TESTE", "valor123", tipo="parametro")
        assert len(cred.atualizado_em) == 27, f"credencial.atualizado_em tem {len(cred.atualizado_em)}: '{cred.atualizado_em}'"
        assert cred.atualizado_em.endswith("Z")

    # 5. Inserção direta de dados legados no SQLite simulando bancos antigos com diferentes formatos e fusos
    async with engine.begin() as conn:
        # Ponto com ISO 32 chars (+00:00)
        await conn.execute(text(
            "INSERT INTO pontos (ponto_id, id_pesquisa, tema, ponto_n, ponto, status, tentativas, tentativas_auditoria, criado_em, atualizado_em) "
            "VALUES ('legacy_iso32', :pid, 't', 3, 'P3', 'pendente', 0, 0, '2026-10-27T10:00:00.123456+00:00', '2026-10-27T10:00:00.123456+00:00')"
        ), {"pid": pesq.id_pesquisa})

        # Ponto com timezone offset -03:00 (10:00:00 UTC)
        await conn.execute(text(
            "INSERT INTO pontos (ponto_id, id_pesquisa, tema, ponto_n, ponto, status, tentativas, tentativas_auditoria, criado_em, atualizado_em) "
            "VALUES ('legacy_tz_sp', :pid, 't', 4, 'P4', 'em_andamento', 0, 0, '2026-10-27T07:00:00.123456-03:00', '2026-10-27T07:00:00.123456-03:00')"
        ), {"pid": pesq.id_pesquisa})

        # Ponto na fronteira de virada de dia com offset -03:00 (23:30:00-03:00 -> 02:30:00 do dia seguinte UTC)
        await conn.execute(text(
            "INSERT INTO pontos (ponto_id, id_pesquisa, tema, ponto_n, ponto, status, tentativas, tentativas_auditoria, criado_em, atualizado_em) "
            "VALUES ('legacy_frontier', :pid, 't', 5, 'P5', 'em_andamento', 0, 0, '2026-10-27T23:30:00.000000-03:00', '2026-10-27T23:30:00.000000-03:00')"
        ), {"pid": pesq.id_pesquisa})

        # Ponto legado com 19 caracteres (YYYY-MM-DD HH:MM:SS)
        await conn.execute(text(
            "INSERT INTO pontos (ponto_id, id_pesquisa, tema, ponto_n, ponto, status, tentativas, tentativas_auditoria, criado_em, atualizado_em) "
            "VALUES ('legacy_space', :pid, 't', 6, 'P6', 'pendente', 0, 0, '2026-10-27 10:00:00', '2026-10-27 10:00:00')"
        ), {"pid": pesq.id_pesquisa})

        # Aplica a migração aditiva sobre o banco com dados legados
        from app.db.init_db import _run_additive_migrations
        await _run_additive_migrations(conn)

    # 6. Verifica que todos os registros legados foram normalizados rigorosamente para 27 chars em UTC
    async with session_maker() as s_check:
        r_check = ResearchRepository(session=s_check)

        p_iso32 = await r_check.get_point("legacy_iso32")
        assert p_iso32 is not None
        assert p_iso32.atualizado_em == "2026-10-27T10:00:00.123456Z"
        assert len(p_iso32.atualizado_em) == 27

        p_tz_sp = await r_check.get_point("legacy_tz_sp")
        assert p_tz_sp is not None
        assert p_tz_sp.atualizado_em == "2026-10-27T10:00:00.123456Z"
        assert len(p_tz_sp.atualizado_em) == 27

        p_front = await r_check.get_point("legacy_frontier")
        assert p_front is not None
        assert p_front.atualizado_em == "2026-10-28T02:30:00.000000Z"
        assert len(p_front.atualizado_em) == 27

        p_space = await r_check.get_point("legacy_space")
        assert p_space is not None
        assert p_space.atualizado_em == "2026-10-27T10:00:00.000000Z"
        assert len(p_space.atualizado_em) == 27

        # 7. Teste de comparação de vencimento de lease em SQL (< lease_cutoff)
        # Cutoff de 10:05:00 UTC deve considerar que 10:00:00 está expirado, mas 02:30:00 do dia 28 NÃO está expirado
        lease_cutoff = "2026-10-27T10:05:00.000000Z"
        res_expirados = (await s_check.execute(
            select(Ponto.ponto_id).where(Ponto.atualizado_em < lease_cutoff).order_by(Ponto.ponto_id)
        )).scalars().all()
        assert "legacy_iso32" in res_expirados
        assert "legacy_tz_sp" in res_expirados
        assert "legacy_space" in res_expirados
        assert "legacy_frontier" not in res_expirados, "Data do dia 28 não pode ser menor que cutoff do dia 27!"

    await engine.dispose()




