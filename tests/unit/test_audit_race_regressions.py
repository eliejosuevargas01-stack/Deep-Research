# -*- coding: utf-8 -*-
"""Testes de regressão de concorrência para Auditoria (Audit r4).

Cobre estritamente as três corridas identificadas no parecer audit-review-r3-conciliation.md
e no adendo vigente addendum-confiabilidade-20261024-v5-audit.md:
- C01: Recálculo antigo por cache após nova coleta (CAS do recálculo não pode sobrepor estado de nova coleta).
- C02: Diagnóstico de evidência antiga em _handle_precondition_failure não altera revisão nova aprovada nem apaga dossiê.
- C03: Histórico na mesma coleta após perda de posse por expiração de lease preserva ambas as auditorias (B aplicado e A obsoleto).

Todas as corridas utilizam SQLite em arquivo com WAL, sessões assíncronas independentes,
eventos e barreiras com timeouts finitos (sem sleeps) e mocks HTTP assíncronos.
"""
import asyncio
from datetime import datetime, timedelta, timezone
import json
from typing import Any, Dict, List, Optional
import httpx
import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.auditor import AUDIT_POINT_LEASE_SECONDS, Auditor
from app.db.init_db import init_db
from app.db.models import ConteudoColetado, GenerationAttempt, Pesquisa, Ponto
from app.db.research_repository import ResearchRepository
from app.db.session import create_engine_with_pragmas
from app.tools.llm_client import LLMClient
from tests.mocks.http_mock import create_mock_transport
from tests.unit.test_audit_acceptance import (
    create_research_fixture_with_plan,
    make_audit_12_vector,
    make_standard_coleta_metadata,
)
from tests.unit.test_reproduction_gate1_helpers import make_llm_json_response

DEFAULT_AUDITOR_PERSONAS = ["planejador", "historiador", "visionario", "cetico", "futurista", "auditor", "redator final"]


# ==============================================================================
# C01 — RECÁLCULO ANTIGO APÓS NOVA COLETA
# ==============================================================================

@pytest.mark.asyncio
async def test_c01_recalculate_audit_threshold_race_with_new_coleta(test_env, tmp_path) -> None:
    """C01: Recálculo antigo de limiar não pode aplicar status nem sobrescrever nova coleta B."""
    db_file = tmp_path / "c01_recalc_race.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"
    engine = create_engine_with_pragmas(db_url)
    await init_db(engine)

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    # 1. Configuração inicial com coleta A legítima
    async with session_maker() as s_init:
        r_init = ResearchRepository(session=s_init)
        pesq, pontos = await create_research_fixture_with_plan(r_init)
        ponto = pontos[0]
        meta_a = make_standard_coleta_metadata(source_url="https://php.net/security-coleta-a")
        coleta_a = await r_init.save_collected_content(
            id_pesquisa=pesq.id_pesquisa,
            ponto_id=ponto.ponto_id,
            tema=pesq.tema,
            ponto=ponto.ponto,
            conteudo_coletado="Conteudo da Coleta A",
            urls_lidas=["https://php.net/security-coleta-a"],
            urls_fonte=["https://php.net/security-coleta-a"],
            metadados_coleta=meta_a,
            rodada=1,
        )

    # 2. Primeira avaliação legítima da coleta A: corte 12 com vetor de 11 critérios aprovados -> reprovado
    llm_calls = 0

    async def llm_handler(req: httpx.Request) -> httpx.Response:
        nonlocal llm_calls
        llm_calls += 1
        return make_llm_json_response({"criterios": make_audit_12_vector(11)})

    async with session_maker() as s_eval1:
        r_eval1 = ResearchRepository(session=s_eval1)
        llm1 = LLMClient(api_key="mock", transport=httpx.MockTransport(llm_handler))
        auditor1 = Auditor(research_repo=r_eval1, llm_client=llm1, personas=DEFAULT_AUDITOR_PERSONAS)
        try:
            res1 = await auditor1.execute_audit(id_pesquisa=pesq.id_pesquisa, criterios_minimos=12)
            assert res1["auditorias"][0]["status"] == "reprovado"
            assert res1["auditorias"][0]["criterios_aprovados"] == 11
            assert res1["auditorias"][0]["valido"] is True
            assert llm_calls == 1
        finally:
            await llm1.aclose()

    # 3. Extrai input_hash real gerado pela primeira avaliação
    async with session_maker() as s_chk:
        coleta_db = await s_chk.get(ConteudoColetado, coleta_a.id)
        meta_db = json.loads(coleta_db.metadados_coleta or "{}")
        aud_entry = meta_db["auditorias"][-1]
        real_input_hash = aud_entry["input_hash"]
        assert real_input_hash is not None and len(real_input_hash) > 10

    # 4. Prepara eventos para a barreira em recalculate_audit_threshold
    in_recalc_scope = [False]
    event_a_read_coleta = asyncio.Event()
    event_b_done = asyncio.Event()
    barrier_fired = [False]

    async def run_auditor_a():
        async with session_maker() as session_a:
            repo_a = ResearchRepository(session=session_a)

            orig_recalc = repo_a.recalculate_audit_threshold

            async def scoped_recalculate(*args, **kwargs):
                in_recalc_scope[0] = True
                try:
                    return await orig_recalc(*args, **kwargs)
                finally:
                    in_recalc_scope[0] = False

            repo_a.recalculate_audit_threshold = scoped_recalculate

            orig_execute = session_a.execute

            async def hooked_execute(statement, *args, **kwargs):
                res = await orig_execute(statement, *args, **kwargs)
                if in_recalc_scope[0] and not barrier_fired[0]:
                    stmt_str = str(statement).upper().replace("\n", " ").strip()
                    if stmt_str.startswith("SELECT") and "CONTEUDO_COLETADO.ID" in stmt_str and "ORDER BY" in stmt_str and "LIMIT" in stmt_str:
                        barrier_fired[0] = True
                        event_a_read_coleta.set()
                        await asyncio.wait_for(event_b_done.wait(), timeout=5.0)
                return res

            session_a.execute = hooked_execute

            # LLM não deve ser invocado no recálculo puro por corte
            llm_a = LLMClient(api_key="mock", transport=httpx.MockTransport(llm_handler))
            auditor_a = Auditor(research_repo=repo_a, llm_client=llm_a, personas=DEFAULT_AUDITOR_PERSONAS)
            try:
                return await auditor_a.execute_audit(id_pesquisa=pesq.id_pesquisa, criterios_minimos=11)
            finally:
                await llm_a.aclose()

    task_a = asyncio.create_task(run_auditor_a())

    try:
        # Aguarda A ler a coleta atual especificamente dentro de recalculate_audit_threshold
        await asyncio.wait_for(event_a_read_coleta.wait(), timeout=5.0)

        # 5. Enquanto A está suspenso, Sessão B executa Search real: reserva e salva coleta B
        async with session_maker() as session_b:
            repo_b = ResearchRepository(session=session_b)
            ponto_reservado = await repo_b.reserve_point(ponto.ponto_id)
            meta_b = make_standard_coleta_metadata(source_url="https://php.net/security-coleta-b")
            coleta_b = await repo_b.save_collected_content(
                id_pesquisa=pesq.id_pesquisa,
                ponto_id=ponto.ponto_id,
                tema=pesq.tema,
                ponto=ponto.ponto,
                conteudo_coletado="Conteudo legitimo da nova Coleta B",
                urls_lidas=["https://php.net/security-coleta-b"],
                urls_fonte=["https://php.net/security-coleta-b"],
                metadados_coleta=meta_b,
                rodada=2,
                expected_tentativa=ponto_reservado.tentativas,
                expected_token=ponto_reservado.lease_token,
                status_ponto="coletado",
            )
            assert coleta_b.id != coleta_a.id
            event_b_done.set()

        # 6. Aguarda término de A
        res_a = await asyncio.wait_for(task_a, timeout=5.0)

        # 7. Asserções rigorosas em nova Sessão C independente
        async with session_maker() as session_c:
            repo_c = ResearchRepository(session=session_c)
            p_c = await repo_c.get_point(ponto.ponto_id)
            # O recálculo da coleta A antiga NÃO pode sobrescrever o ponto da coleta B para 'aprovado'
            assert p_c.status == "coletado", (
                f"FALHA C01: Recálculo obsoleto sobrescreveu ponto para '{p_c.status}', esperado 'coletado' da nova coleta B!"
            )
            # Coleta B é a mais recente
            coletas_c = await repo_c.get_collected_content_for_point(pesq.id_pesquisa, ponto.ponto_id)
            assert len(coletas_c) == 2
            assert coletas_c[-1].id == coleta_b.id

            # O histórico da coleta A não pode ter se aplicado como decisão ativa da nova coleta
            coleta_a_db = await session_c.get(ConteudoColetado, coleta_a.id)
            meta_a_db = json.loads(coleta_a_db.metadados_coleta or "{}")
            auds_a = meta_a_db.get("auditorias", [])
            assert len(auds_a) >= 1
            # Se houve tentativa de recálculo, não pode constar como aplicado com sucesso alterando o ponto atual
            for aud in auds_a:
                if aud.get("recalculo") is True:
                    assert aud.get("aplicado") is False, "Recálculo concorrente desatualizado não pode ter aplicado=True!"

            # Nenhuma chamada LLM adicional
            assert llm_calls == 1
    finally:
        if not task_a.done():
            event_b_done.set()
            try:
                await asyncio.wait_for(task_a, timeout=2.0)
            except Exception:
                pass

    await engine.dispose()


# ==============================================================================
# C02 — DIAGNÓSTICO DE EVIDÊNCIA ANTIGA NÃO ALTERA REVISÃO NOVA
# ==============================================================================

@pytest.mark.asyncio
async def test_c02_precondition_failure_race_does_not_override_new_review(test_env, tmp_path) -> None:
    """C02: Falha de precondição em coleta A antiga não pode reprovar nem apagar dossiê de revisão B aprovada."""
    db_file = tmp_path / "c02_precond_race.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"
    engine = create_engine_with_pragmas(db_url)
    await init_db(engine)

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    # 1. Configuração inicial com coleta A que falha na precondição (sem URLs lidas)
    async with session_maker() as s_init:
        r_init = ResearchRepository(session=s_init)
        pesq, pontos = await create_research_fixture_with_plan(r_init)
        ponto = pontos[0]
        coleta_a = await r_init.save_collected_content(
            id_pesquisa=pesq.id_pesquisa,
            ponto_id=ponto.ponto_id,
            tema=pesq.tema,
            ponto=ponto.ponto,
            conteudo_coletado="Conteudo A falho sem URLs",
            urls_lidas=[],
            urls_fonte=[],
            metadados_coleta={},
            rodada=1,
        )

    # 2. Configura Auditor A com barreira em _handle_precondition_failure
    event_a_precondition = asyncio.Event()
    event_b_done = asyncio.Event()

    async def run_auditor_a():
        async with session_maker() as session_a:
            repo_a = ResearchRepository(session=session_a)
            llm_a = LLMClient(api_key="mock_a", transport=create_mock_transport())
            auditor_a = Auditor(research_repo=repo_a, llm_client=llm_a, personas=DEFAULT_AUDITOR_PERSONAS)

            orig_handle = auditor_a._handle_precondition_failure

            async def hooked_handle(id_pesquisa, ponto, ultima_coleta, threshold, pontos_fracos, diagnostico):
                event_a_precondition.set()
                await asyncio.wait_for(event_b_done.wait(), timeout=5.0)
                return await orig_handle(
                    id_pesquisa=id_pesquisa,
                    ponto=ponto,
                    ultima_coleta=ultima_coleta,
                    threshold=threshold,
                    pontos_fracos=pontos_fracos,
                    diagnostico=diagnostico,
                )

            auditor_a._handle_precondition_failure = hooked_handle
            try:
                return await auditor_a.execute_audit(id_pesquisa=pesq.id_pesquisa)
            finally:
                await llm_a.aclose()

    task_a = asyncio.create_task(run_auditor_a())

    try:
        # Aguarda A chegar em _handle_precondition_failure
        await asyncio.wait_for(event_a_precondition.wait(), timeout=5.0)

        # 3. Enquanto A está suspenso, Sessão B executa coleta B válida, aprova via auditoria e grava dossiê marcador
        llm_b_calls = 0

        async def llm_b_handler(req: httpx.Request) -> httpx.Response:
            nonlocal llm_b_calls
            llm_b_calls += 1
            return make_llm_json_response({"criterios": make_audit_12_vector(12)})

        async with session_maker() as session_b:
            repo_b = ResearchRepository(session=session_b)
            meta_b = make_standard_coleta_metadata(source_url="https://php.net/security-coleta-b-valid")
            coleta_b = await repo_b.save_collected_content(
                id_pesquisa=pesq.id_pesquisa,
                ponto_id=ponto.ponto_id,
                tema=pesq.tema,
                ponto=ponto.ponto,
                conteudo_coletado="Conteudo valido da sessao B com fontes canônicas",
                urls_lidas=["https://php.net/security-coleta-b-valid"],
                urls_fonte=["https://php.net/security-coleta-b-valid"],
                metadados_coleta=meta_b,
                rodada=2,
            )

            llm_b = LLMClient(api_key="mock_b", transport=httpx.MockTransport(llm_b_handler))
            auditor_b = Auditor(research_repo=repo_b, llm_client=llm_b, personas=DEFAULT_AUDITOR_PERSONAS)
            try:
                res_b = await auditor_b.execute_audit(id_pesquisa=pesq.id_pesquisa, criterios_minimos=11)
                assert res_b["auditorias"][0]["status"] == "aprovado"
                assert res_b["pronto_para_writer"] is True
                assert llm_b_calls == 1
            finally:
                await llm_b.aclose()

            # Sessão B grava dossiê marcador da revisão B
            await repo_b.update_research_dossier(pesq.id_pesquisa, dossier_final="DOSSIER_MARCADOR_B_REV2")
            await session_b.commit()
            event_b_done.set()

        # 4. Aguarda liberação e conclusão de A
        res_a = await asyncio.wait_for(task_a, timeout=5.0)

        # 5. Asserções rigorosas em nova Sessão C
        async with session_maker() as session_c:
            repo_c = ResearchRepository(session=session_c)
            p_c = await repo_c.get_point(ponto.ponto_id)
            pesq_c = await repo_c.get_research(pesq.id_pesquisa)

            # O ponto DEVE permanecer 'aprovado' da sessão B
            assert p_c.status == "aprovado", (
                f"FALHA C02: Diagnóstico obsoleto da coleta A alterou o ponto aprovado para '{p_c.status}'!"
            )
            # O dossiê marcador da sessão B DEVE permanecer intacto
            assert pesq_c.dossier_final == "DOSSIER_MARCADOR_B_REV2", (
                f"FALHA C02: Dossiê marcador da pesquisa foi apagado pelo diagnóstico obsoleto de A!"
            )

            # Histórico da coleta A: diagnóstico deve constar como não aplicado
            coleta_a_db = await session_c.get(ConteudoColetado, coleta_a.id)
            meta_a_db = json.loads(coleta_a_db.metadados_coleta or "{}")
            auds_a = meta_a_db.get("auditorias", [])
            assert len(auds_a) >= 1
            assert auds_a[-1]["aplicado"] is False, "Diagnóstico obsoleto da coleta A não pode ter aplicado=True!"

            # Apenas 1 chamada LLM ocorreu (a legítima da sessão B)
            assert llm_b_calls == 1
    finally:
        if not task_a.done():
            event_b_done.set()
            try:
                await asyncio.wait_for(task_a, timeout=2.0)
            except Exception:
                pass

    await engine.dispose()


# ==============================================================================
# C03 — HISTÓRICO NA MESMA COLETA APÓS PERDA DE POSSE
# ==============================================================================

@pytest.mark.asyncio
async def test_c03_same_coleta_lost_lease_preserves_both_audit_histories(test_env, tmp_path) -> None:
    """C03: Auditor com lease expirada que perde posse na MESMA coleta preserva ambas as auditorias no histórico."""
    db_file = tmp_path / "c03_lost_lease_history.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"
    engine = create_engine_with_pragmas(db_url)
    await init_db(engine)

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    # 1. Configuração inicial com coleta única legítima
    async with session_maker() as s_init:
        r_init = ResearchRepository(session=s_init)
        pesq, pontos = await create_research_fixture_with_plan(r_init)
        ponto = pontos[0]
        meta_init = make_standard_coleta_metadata(source_url="https://php.net/security-c03")
        coleta = await r_init.save_collected_content(
            id_pesquisa=pesq.id_pesquisa,
            ponto_id=ponto.ponto_id,
            tema=pesq.tema,
            ponto=ponto.ponto,
            conteudo_coletado="Conteudo unico para teste C03",
            urls_lidas=["https://php.net/security-c03"],
            urls_fonte=["https://php.net/security-c03"],
            metadados_coleta=meta_init,
            rodada=1,
        )
        coleta_id = coleta.id

    # 2. Configura Auditor A com suspensão no LLM
    event_a_in_llm = asyncio.Event()
    event_b_done = asyncio.Event()

    async def llm_a_handler(req: httpx.Request) -> httpx.Response:
        event_a_in_llm.set()
        await asyncio.wait_for(event_b_done.wait(), timeout=5.0)
        return make_llm_json_response({"criterios": make_audit_12_vector(11)})

    async def run_auditor_a():
        async with session_maker() as session_a:
            repo_a = ResearchRepository(session=session_a)
            llm_a = LLMClient(api_key="mock_a", transport=httpx.MockTransport(llm_a_handler))
            auditor_a = Auditor(research_repo=repo_a, llm_client=llm_a, personas=DEFAULT_AUDITOR_PERSONAS)
            try:
                return await auditor_a.execute_audit(id_pesquisa=pesq.id_pesquisa, criterios_minimos=12)
            finally:
                await llm_a.aclose()

    task_a = asyncio.create_task(run_auditor_a())

    try:
        # Aguarda A reservar o ponto e entrar no LLM
        await asyncio.wait_for(event_a_in_llm.wait(), timeout=5.0)

        # 3. Enquanto A está suspenso, Sessão B envelhece timestamp de lease de A (simulando abandono)
        # e assume posse via reserva real para auditar a MESMA coleta
        async with session_maker() as session_b:
            old_lease_time = (
                datetime.now(timezone.utc) - timedelta(seconds=AUDIT_POINT_LEASE_SECONDS + 60)
            ).isoformat()
            await session_b.execute(
                update(Ponto)
                .where(Ponto.ponto_id == ponto.ponto_id)
                .values(atualizado_em=old_lease_time)
            )
            await session_b.commit()

            repo_b = ResearchRepository(session=session_b)

            async def llm_b_handler(req: httpx.Request) -> httpx.Response:
                return make_llm_json_response({"criterios": make_audit_12_vector(12)})

            llm_b = LLMClient(api_key="mock_b", transport=httpx.MockTransport(llm_b_handler))
            auditor_b = Auditor(research_repo=repo_b, llm_client=llm_b, personas=DEFAULT_AUDITOR_PERSONAS)
            try:
                res_b = await auditor_b.execute_audit(id_pesquisa=pesq.id_pesquisa, criterios_minimos=11)
                assert res_b["auditorias"][0]["status"] == "aprovado"
            finally:
                await llm_b.aclose()

            # Sessão B grava dossiê marcador da revisão B
            await repo_b.update_research_dossier(pesq.id_pesquisa, dossier_final="DOSSIER_B_MARCADOR_C03")
            await session_b.commit()
            event_b_done.set()

        # 4. Aguarda A acordar e finalizar
        res_a = await asyncio.wait_for(task_a, timeout=5.0)

        # 5. Asserções rigorosas em nova Sessão C independente
        async with session_maker() as session_c:
            repo_c = ResearchRepository(session=session_c)
            p_c = await repo_c.get_point(ponto.ponto_id)
            pesq_c = await repo_c.get_research(pesq.id_pesquisa)

            # Ponto e dossiê de B preservados
            assert p_c.status == "aprovado"
            assert pesq_c.dossier_final == "DOSSIER_B_MARCADOR_C03"
            assert p_c.tentativas_auditoria == 2

            # Histórico da MESMA coleta DEVE conter AMBAS as auditorias (B aplicado e A não aplicado)
            coleta_c = await session_c.get(ConteudoColetado, coleta_id)
            meta_c = json.loads(coleta_c.metadados_coleta or "{}")
            auditorias = meta_c.get("auditorias", [])

            assert len(auditorias) == 2, (
                f"FALHA C03: Histórico de auditorias perdeu registros! Esperado 2, obteve {len(auditorias)}: {auditorias}"
            )

            b_entries = [a for a in auditorias if a.get("aplicado") is True]
            a_entries = [a for a in auditorias if a.get("aplicado") is False]

            assert len(b_entries) == 1, (
                f"FALHA C03: Auditoria aplicada de B foi apagada pelo commit da sessão A! Auditorias: {auditorias}"
            )
            assert len(a_entries) == 1, (
                f"FALHA C03: Auditoria não aplicada de A não foi registrada! Auditorias: {auditorias}"
            )
            assert b_entries[0]["id_auditoria"] != a_entries[0]["id_auditoria"]

            # Verifica vínculo de GenerationAttempts
            stmt_ga = select(GenerationAttempt).where(
                GenerationAttempt.id_pesquisa == pesq.id_pesquisa,
                GenerationAttempt.ponto_id == ponto.ponto_id,
                GenerationAttempt.etapa == "audit",
            )
            gas = (await session_c.execute(stmt_ga)).scalars().all()
            assert len(gas) >= 2, f"Esperado ao menos 2 GenerationAttempts persistidos, obteve {len(gas)}"
    finally:
        if not task_a.done():
            event_b_done.set()
            try:
                await asyncio.wait_for(task_a, timeout=2.0)
            except Exception:
                pass

    await engine.dispose()
