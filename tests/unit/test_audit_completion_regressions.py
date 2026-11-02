# -*- coding: utf-8 -*-
"""Testes de regressão de conclusão de requisitos para Auditoria (Audit r5).

Cobre rigorosamente os requisitos v5 especificados para a etapa Audit r5:
1. Ramo sem coletas:
   - Persistência condicional de reprovação no Ponto, invalidação do dossiê, sincronização do status da pesquisa.
   - Preservação de posse ativa ('em_andamento' e 'auditando').
   - Corrida com nova coleta: A observa ausência, B comita nova coleta e status 'coletado', A não sobrescreve B.
   - Nenhuma coleta ou GenerationAttempt fictício gerado.
2. Encerramento consolidado de 3ª lease expirada:
   - Execução tanto via Auditor quanto via reserve_point_for_audit no repo.
   - Anexação de diagnóstico estruturado (valido=False, criterios=None, 0 notas, 0.0%) na coleta na mesma transação.
   - Deduplicação em repetições.
   - Persistência no Ponto apenas se sem coletas.
   - Não violação de lease ativa.
3. Leitura coerente em get_research com populate_existing após atualização concorrente.
4. Feedback usável pelo Search:
   - Projeção de afirmações reais de claims e URLs reais de fontes em tarefas e pontos_fracos.
   - Formatter compartilhado entre avaliação normal e recálculo em cache sem LLM.
   - Searcher recebe as afirmações e URLs reais na diretriz de re-pesquisa do system prompt.
5. Timeout real curto com AUDIT_POINT_TIMEOUT_SECONDS monkeypatchado e MockTransport suspenso por Event.
6. Preservação de envelopes observados:
   - Em falha de reparo de vetor (2ª chamada).
   - Em falha de reparo JSON interno em LLMClient.generate_json_envelope.
7. Ciclo de vida do llm_client no endpoint:
   - aclose() exatamente uma vez em sucesso, erro de geração e erro de configuração pós-construção.
   - Zero aclose() se a construção falhou previamente.
8. Invalidação real de cache por alteração de model_strong e persona_prompt.
9. Descarte de engine global extra no teardown de fixture para prevenir warnings aiosqlite.
"""

import asyncio
from datetime import datetime, timedelta, timezone
import json
from typing import Any, Dict, List, Optional
import httpx
from httpx import ASGITransport, AsyncClient
import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.v1.endpoints.audit import router as audit_router
from app.core.auditor import AUDIT_POINT_LEASE_SECONDS, Auditor
from app.core.searcher import Searcher
from app.db.init_db import init_db
from app.db.models import ConteudoColetado, GenerationAttempt, Pesquisa, Ponto
from app.db.research_repository import ResearchRepository
from app.db.session import create_engine_with_pragmas, get_engine, reset_engine
from app.main import app
from app.tools.jina_client import JinaClient
from app.tools.llm_client import LLMClient
from tests.mocks.http_mock import MockNetwork, create_mock_transport
from tests.unit.test_audit_acceptance import (
    create_research_fixture_with_plan,
    make_audit_12_vector,
    make_standard_coleta_metadata,
)
from tests.unit.test_reproduction_gate1_helpers import make_llm_json_response

DEFAULT_AUDITOR_PERSONAS = [
    "planejador",
    "historiador",
    "visionario",
    "cetico",
    "futurista",
    "auditor",
    "redator final",
]


# ==============================================================================
# 1. DIAGNÓSTICOS SEM DADOS E CAS DE COLETAS
# ==============================================================================

@pytest.mark.asyncio
async def test_r5_no_collection_persists_reproved_and_invalidates_dossier(
    test_env,
    tmp_path,
) -> None:
    """Ramo sem coletas deve persistir Ponto como reprovado, invalidar dossiê e sincronizar pesquisa em sessão fresca."""
    db_file = tmp_path / "r5_no_coleta_persist.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"
    engine = create_engine_with_pragmas(db_url)
    await init_db(engine)

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with session_maker() as s_init:
        r_init = ResearchRepository(session=s_init)
        pesq, pontos = await create_research_fixture_with_plan(r_init)
        ponto = pontos[0]

        # Estado prévio: pesquisa tinha dossiê final registrado
        pesq.dossier_final = "Dossiê final prévio que deve ser invalidado"
        pesq.concluido_em = datetime.now(timezone.utc).isoformat()
        await s_init.commit()
        id_pesq = pesq.id_pesquisa
        id_ponto = ponto.ponto_id

    async with session_maker() as s_exec:
        r_exec = ResearchRepository(session=s_exec)
        llm = LLMClient(api_key="mock-key", transport=create_mock_transport(MockNetwork()))
        auditor = Auditor(
            research_repo=r_exec,
            llm_client=llm,
            personas=DEFAULT_AUDITOR_PERSONAS,
        )
        resultado = await auditor.execute_audit(
            id_pesquisa=id_pesq,
            ponto_id=id_ponto,
            criterios_minimos=11,
        )

        assert resultado["total_pontos"] == 1
        assert resultado["reprovados"] == 1
        assert resultado["aprovados"] == 0
        assert resultado["pronto_para_writer"] is False
        assert resultado["status_geral"] == "reprovado"

        item = resultado["auditorias"][0]
        assert item["status"] == "reprovado"
        assert item["valido"] is False
        assert item["criterios"] is None
        assert item["criterios_aprovados"] == 0
        assert item["pontuacao_percentual"] == 0.0
        assert "Nenhum conteúdo coletado" in (item["pontos_fracos"] or "")
        assert item["diagnostico"] == "Sem coletas"

    # Confere persistência no banco em sessão realmente nova
    async with session_maker() as s_fresh:
        r_fresh = ResearchRepository(session=s_fresh)
        ponto_db = await r_fresh.get_point(id_ponto)
        assert ponto_db is not None
        assert ponto_db.status == "reprovado", "Ponto sem coletas deve ter status persistido como 'reprovado'"
        assert "Nenhum conteúdo coletado" in (ponto_db.pontos_fracos or "")

        pesq_db = await r_fresh.get_research(id_pesq)
        assert pesq_db is not None
        assert pesq_db.dossier_final is None, "Dossiê deve ser invalidado ao reprovar ponto sem coletas"
        assert pesq_db.concluido_em is None
        assert pesq_db.status_pipeline == "reprovado"

        # Nenhuma coleta ou GenerationAttempt deve ser fabricada
        coletas = await r_fresh.get_collected_content_for_point(id_pesq, id_ponto)
        assert len(coletas) == 0, "Nenhuma coleta deve ser fabricada no banco de dados"

        gas = (
            await s_fresh.execute(
                select(GenerationAttempt).where(GenerationAttempt.ponto_id == id_ponto)
            )
        ).scalars().all()
        assert len(gas) == 0, "Nenhum GenerationAttempt deve ser gerado sem chamada LLM"

    await engine.dispose()


@pytest.mark.asyncio
async def test_r5_no_collection_active_possession_preserved(
    db_session: AsyncSession,
) -> None:
    """Ponto sem coletas em posse ativa ('em_andamento' ou 'auditando') não pode ser alterado para 'reprovado'."""
    repo = ResearchRepository(session=db_session)
    pesq, pontos = await create_research_fixture_with_plan(repo)
    ponto = pontos[0]

    ponto.status = "em_andamento"
    pesq.dossier_final = "Dossiê preservado"
    await db_session.commit()

    llm = LLMClient(api_key="mock-key", transport=create_mock_transport(MockNetwork()))
    auditor = Auditor(research_repo=repo, llm_client=llm, personas=DEFAULT_AUDITOR_PERSONAS)

    await auditor.execute_audit(id_pesquisa=pesq.id_pesquisa, ponto_id=ponto.ponto_id)

    ponto_check = await repo.get_point(ponto.ponto_id)
    pesq_check = await repo.get_research(pesq.id_pesquisa)
    assert ponto_check.status == "em_andamento", "Não pode sobrescrever ponto em busca ativa"
    assert pesq_check.dossier_final == "Dossiê preservado", "Não pode invalidar dossiê em posse ativa"


@pytest.mark.asyncio
async def test_r5_no_collection_cas_race_with_concurrent_new_coleta(
    test_env,
    tmp_path,
) -> None:
    """Corrida real: A observa ausência de coletas; B comita nova coleta e move para 'coletado'; A não sobrescreve B."""
    db_file = tmp_path / "r5_no_coleta_race.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"
    engine = create_engine_with_pragmas(db_url)
    await init_db(engine)

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with session_maker() as s_init:
        r_init = ResearchRepository(session=s_init)
        pesq, pontos = await create_research_fixture_with_plan(r_init)
        ponto = pontos[0]
        id_pesq = pesq.id_pesquisa
        id_ponto = ponto.ponto_id

    a_saw_empty = asyncio.Event()
    b_saved_coleta = asyncio.Event()

    async def worker_a():
        async with session_maker() as s_a:
            r_a = ResearchRepository(session=s_a)
            original_get_coletas = r_a.get_collected_content_for_point

            async def hooked_get_coletas(id_p, p_id):
                res = await original_get_coletas(id_p, p_id)
                a_saw_empty.set()
                # Aguarda B concluir a inserção da nova coleta com timeout finito
                await asyncio.wait_for(b_saved_coleta.wait(), timeout=5.0)
                return res

            r_a.get_collected_content_for_point = hooked_get_coletas
            llm_a = LLMClient(api_key="mock-key", transport=create_mock_transport(MockNetwork()))
            auditor_a = Auditor(research_repo=r_a, llm_client=llm_a, personas=DEFAULT_AUDITOR_PERSONAS)
            return await auditor_a.execute_audit(id_pesquisa=id_pesq, ponto_id=id_ponto)

    async def worker_b():
        # Aguarda A observar ausência de coletas
        await asyncio.wait_for(a_saw_empty.wait(), timeout=5.0)
        async with session_maker() as s_b:
            r_b = ResearchRepository(session=s_b)
            meta_b = make_standard_coleta_metadata()
            await r_b.save_collected_content(
                id_pesquisa=id_pesq,
                ponto_id=id_ponto,
                tema="Tema",
                ponto="Ponto",
                conteudo_coletado="Conteúdo B legítimo",
                urls_lidas=["https://php.net/security-2026"],
                urls_fonte=["https://php.net/security-2026"],
                metadados_coleta=meta_b,
            )
            # Atualiza ponto para 'coletado' e grava dossiê marcador da revisão B
            await s_b.execute(
                update(Ponto)
                .where(Ponto.ponto_id == id_ponto)
                .values(status="coletado", atualizado_em=datetime.now(timezone.utc).isoformat())
            )
            await s_b.execute(
                update(Pesquisa)
                .where(Pesquisa.id_pesquisa == id_pesq)
                .values(dossier_final="Dossiê marcador da coleta B")
            )
            await s_b.commit()
            b_saved_coleta.set()

    task_a = asyncio.create_task(worker_a())
    task_b = asyncio.create_task(worker_b())

    try:
        res_a, _ = await asyncio.gather(task_a, task_b)
    finally:
        a_saw_empty.set()
        b_saved_coleta.set()

    # Confere que o ponto permaneceu 'coletado' e o dossiê da revisão B foi preservado
    async with session_maker() as s_check:
        r_check = ResearchRepository(session=s_check)
        ponto_check = await r_check.get_point(id_ponto)
        pesq_check = await r_check.get_research(id_pesq)
        assert ponto_check.status == "coletado", "Coleta B nova não pode ser sobrescrita por decisão sem coletas de A"
        assert pesq_check.dossier_final == "Dossiê marcador da coleta B", "Dossiê marcador da revisão B deve permanecer intacto"

    await engine.dispose()


# ==============================================================================
# 2. ENCERRAMENTO CONSOLIDADO DE 3ª LEASE EXPIRADA COM DIAGNÓSTICO ESTRUTURADO
# ==============================================================================

@pytest.mark.asyncio
@pytest.mark.parametrize("criterios_minimos", [10, 11, 12])
async def test_r5_expired_third_lease_consolidated_termination_with_structured_diagnostic(
    db_session: AsyncSession,
    criterios_minimos: int,
) -> None:
    """Encerramento de 3ª lease expirada via Auditor e reserve_point_for_audit anexa diagnóstico estruturado na coleta."""
    repo = ResearchRepository(session=db_session)
    pesq, pontos = await create_research_fixture_with_plan(repo)
    ponto = pontos[0]

    meta = make_standard_coleta_metadata()
    coleta = await repo.save_collected_content(
        id_pesquisa=pesq.id_pesquisa,
        ponto_id=ponto.ponto_id,
        tema=pesq.tema,
        ponto=ponto.ponto,
        conteudo_coletado="Conteúdo existente",
        urls_lidas=["https://php.net/security-2026"],
        urls_fonte=["https://php.net/security-2026"],
        metadados_coleta=meta,
    )

    # Configura 3ª tentativa com lease expirada (usa o lease real do auditor).
    from app.core.auditor import AUDIT_POINT_LEASE_SECONDS as _LEASE

    passado_iso = (datetime.now(timezone.utc) - timedelta(seconds=_LEASE + 150)).isoformat()
    ponto.status = "auditando"
    ponto.tentativas_auditoria = 3
    ponto.atualizado_em = passado_iso
    pesq.dossier_final = "Dossiê final"
    await db_session.commit()

    llm = LLMClient(api_key="mock-key", transport=create_mock_transport(MockNetwork()))
    auditor = Auditor(research_repo=repo, llm_client=llm, personas=DEFAULT_AUDITOR_PERSONAS)

    res = await auditor.execute_audit(
        id_pesquisa=pesq.id_pesquisa,
        ponto_id=ponto.ponto_id,
        criterios_minimos=criterios_minimos,
    )

    item = res["auditorias"][0]
    assert item["status"] == "reprovado"
    assert item["valido"] is False
    assert item["criterios"] is None
    assert item["criterios_aprovados"] == 0
    assert item["pontuacao_percentual"] == 0.0
    assert "lease expirada" in (item["diagnostico"] or "").lower()

    # Confere persistência no banco
    ponto_db = await repo.get_point(ponto.ponto_id)
    assert ponto_db.status == "reprovado"
    assert ponto_db.tentativas_auditoria == 3, "Contador de tentativas de auditoria não deve ser incrementado para 4"
    assert "lease expirada" in (ponto_db.pontos_fracos or "").lower()

    pesq_db = await repo.get_research(pesq.id_pesquisa)
    assert pesq_db.dossier_final is None

    # Confere histórico estruturado anexado à coleta existente
    stmt_meta = select(ConteudoColetado.metadados_coleta).where(ConteudoColetado.id == coleta.id)
    meta_db_raw = (await db_session.execute(stmt_meta)).scalar_one()
    meta_db = json.loads(meta_db_raw)
    assert "auditorias" in meta_db
    assert len(meta_db["auditorias"]) == 1

    entry = meta_db["auditorias"][0]
    assert entry["status"] == "reprovado"
    assert entry["valido"] is False
    assert entry["criterios"] is None
    assert entry["criterios_aprovados"] == 0
    assert entry["pontuacao_percentual"] == 0.0
    assert "lease expirada" in entry["diagnostico"].lower()

    # Confere corte na API e no histórico em sessão fresh contra o corte solicitado
    session_maker = async_sessionmaker(bind=db_session.bind, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as s_fresh:
        raw_fresh = (await s_fresh.execute(stmt_meta)).scalar_one()
        meta_fresh = json.loads(raw_fresh)
        entry_fresh = meta_fresh["auditorias"][0]
        assert item["criterios_minimos"] == entry_fresh["criterios_minimos"] == criterios_minimos

    # Execução pelo caminho reserve_point_for_audit não deve duplicar o diagnóstico no histórico
    with pytest.raises(ValueError) as exc_info:
        await repo.reserve_point_for_audit(ponto.ponto_id, lease_seconds=AUDIT_POINT_LEASE_SECONDS)
    assert "MAX_ATTEMPTS_EXCEEDED" in str(exc_info.value)

    meta_db_raw2 = (await db_session.execute(stmt_meta)).scalar_one()
    meta_db2 = json.loads(meta_db_raw2)
    assert len(meta_db2["auditorias"]) == 1, "Diagnóstico estruturado não deve ser duplicado em repetição"


@pytest.mark.asyncio
async def test_r5_expired_third_lease_without_collection_persists_only_on_point(
    db_session: AsyncSession,
) -> None:
    """3ª lease expirada em ponto sem nenhuma coleta persiste diagnóstico apenas no Ponto sem fabricar coleta."""
    repo = ResearchRepository(session=db_session)
    pesq, pontos = await create_research_fixture_with_plan(repo)
    ponto = pontos[0]

    from app.core.auditor import AUDIT_POINT_LEASE_SECONDS as _LEASE

    passado_iso = (datetime.now(timezone.utc) - timedelta(seconds=_LEASE + 150)).isoformat()
    ponto.status = "auditando"
    ponto.tentativas_auditoria = 3
    ponto.atualizado_em = passado_iso
    await db_session.commit()

    with pytest.raises(ValueError) as exc_info:
        await repo.reserve_point_for_audit(ponto.ponto_id, lease_seconds=AUDIT_POINT_LEASE_SECONDS)
    assert "MAX_ATTEMPTS_EXCEEDED" in str(exc_info.value)

    ponto_db = await repo.get_point(ponto.ponto_id)
    assert ponto_db.status == "reprovado"
    assert "lease expirada" in (ponto_db.pontos_fracos or "").lower()

    coletas = await repo.get_collected_content_for_point(pesq.id_pesquisa, ponto.ponto_id)
    assert len(coletas) == 0, "Nenhuma coleta deve ser fabricada quando o ponto não possui coletas prévias"


# ==============================================================================
# 3. LEITURA COERENTE EM GET_RESEARCH (POPULATE_EXISTING)
# ==============================================================================

@pytest.mark.asyncio
async def test_r5_get_research_populate_existing_reflects_updated_pipeline_status(
    test_env,
    tmp_path,
) -> None:
    """get_research deve atualizar a instância mesmo quando ela já está no IdentityMap da sessão."""
    db_file = tmp_path / "r5_get_research_fresh.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"
    engine = create_engine_with_pragmas(db_url)
    await init_db(engine)

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with session_maker() as s_init:
        r_init = ResearchRepository(session=s_init)
        pesq, _ = await create_research_fixture_with_plan(r_init)
        id_pesq = pesq.id_pesquisa

    async with session_maker() as s_reader, session_maker() as s_writer:
        r_reader = ResearchRepository(session=s_reader)
        r_writer = ResearchRepository(session=s_writer)

        # 1. Sessão leitora carrega Pesquisa no seu IdentityMap
        pesq_loaded = await r_reader.get_research(id_pesq)
        assert pesq_loaded is not None
        assert pesq_loaded.status_pipeline == "planejado"

        # 2. Sessão escritora atualiza diretamente no banco para 'auditado' e comita
        await s_writer.execute(
            update(Pesquisa)
            .where(Pesquisa.id_pesquisa == id_pesq)
            .values(status_pipeline="auditado")
        )
        await s_writer.commit()

        # 3. Sessão leitora chama get_research novamente
        pesq_refreshed = await r_reader.get_research(id_pesq)
        assert pesq_refreshed is not None
        assert pesq_refreshed.status_pipeline == "auditado", (
            "get_research deve usar populate_existing=True para refletir atualizações concorrentes do banco"
        )

    await engine.dispose()


# ==============================================================================
# 4. FEEDBACK COM AFIRMAÇÕES REAIS E URLS DE FONTES (NORMAL E CACHE)
# ==============================================================================

@pytest.mark.asyncio
async def test_r5_audit_feedback_projects_real_claims_and_urls_in_normal_and_cache(
    db_session: AsyncSession,
) -> None:
    """Feedback projetado deve conter o texto das afirmações e as URLs das fontes, não apenas IDs."""
    repo = ResearchRepository(session=db_session)
    pesq, pontos = await create_research_fixture_with_plan(repo)
    ponto = pontos[0]

    # Prepara coleta com afirmação e fonte canônicas reais
    meta = make_standard_coleta_metadata(
        source_url="https://php.net/security-2026-cve",
    )
    meta["resultados_personas"]["historiador"]["conclusoes"][0]["afirmacao"] = (
        "PHP 8.3.13 mitigou vulnerabilidade de leitura arbitrária de memória sem impacto de RCE."
    )
    await repo.save_collected_content(
        id_pesquisa=pesq.id_pesquisa,
        ponto_id=ponto.ponto_id,
        tema=pesq.tema,
        ponto=ponto.ponto,
        conteudo_coletado="Conteúdo de teste",
        urls_lidas=["https://php.net/security-2026-cve"],
        urls_fonte=["https://php.net/security-2026-cve"],
        metadados_coleta=meta,
    )

    # Mock: LLM aprova 10 critérios e reprova 11 e 12 apontando claim_1 e src_1 exclusivamente para cetico
    vector_10 = make_audit_12_vector(
        10,
        known_claim_ids=["claim_1", "claim_2", "claim_3", "claim_4"],
        known_source_ids=["https://php.net/security-2026-cve"],
    )
    vector_10[10]["lacuna"] = "Falta confirmação do impacto em versões legadas"
    vector_10[10]["correcao"] = "Consultar advisories complementares do PHP 8.1 e 8.2"
    vector_10[10]["personas_pertinentes"] = ["cetico"]

    vector_10[11]["lacuna"] = "Dedução sobre versões anteriores não comprovada"
    vector_10[11]["correcao"] = "Obter changelog das branches legadas"
    vector_10[11]["personas_pertinentes"] = ["cetico"]

    mock_net = MockNetwork()
    mock_net.custom_handlers["chat/completions"] = lambda r: make_llm_json_response({
        "criterios": vector_10,
        "resumo_auditoria": "Parecer com 10/12 aprovados.",
    })
    llm = LLMClient(api_key="mock-key", transport=create_mock_transport(mock_net))
    auditor = Auditor(research_repo=repo, llm_client=llm, personas=DEFAULT_AUDITOR_PERSONAS)

    # 1. Avaliação normal reprovada com limiar 11 (10/12)
    res_normal = await auditor.execute_audit(
        id_pesquisa=pesq.id_pesquisa,
        ponto_id=ponto.ponto_id,
        criterios_minimos=11,
    )
    item_normal = res_normal["auditorias"][0]
    assert item_normal["status"] == "reprovado"

    pf_normal = item_normal["pontos_fracos"] or ""
    assert "PHP 8.3.13 mitigou vulnerabilidade" in pf_normal, "pontos_fracos deve conter a afirmação real do claim"
    assert "https://php.net/security-2026-cve" in pf_normal, "pontos_fracos deve conter a URL real da fonte"
    assert "claim_1" in pf_normal, "pontos_fracos deve manter o ID para rastreabilidade"
    assert "cetico" in pf_normal, "pontos_fracos deve conter a persona pertinente"
    assert "visionario" not in pf_normal, "pontos_fracos não deve incluir personas não listadas para a falha"

    tarefas_normal = item_normal["tarefas"]
    assert tarefas_normal is not None and len(tarefas_normal) == 2
    t11 = next(t for t in tarefas_normal if t["criterio_id"] == 11)
    assert "afirmacoes" in t11 and any("PHP 8.3.13 mitigou vulnerabilidade" in str(x) for x in t11["afirmacoes"])
    assert "urls_fontes" in t11 and "https://php.net/security-2026-cve" in t11["urls_fontes"]

    # 2. Avaliação aprovada com limiar 10
    res_aprovado = await auditor.execute_audit(
        id_pesquisa=pesq.id_pesquisa,
        ponto_id=ponto.ponto_id,
        criterios_minimos=10,
    )
    assert res_aprovado["auditorias"][0]["status"] == "aprovado"
    assert res_aprovado["auditorias"][0]["pontos_fracos"] is None

    # 3. Recálculo em cache sem LLM para limiar 11 -> reprovado
    mock_net.custom_handlers.clear()

    res_cache = await auditor.execute_audit(
        id_pesquisa=pesq.id_pesquisa,
        ponto_id=ponto.ponto_id,
        criterios_minimos=11,
    )
    item_cache = res_cache["auditorias"][0]
    assert item_cache["status"] == "reprovado"
    pf_cache = item_cache["pontos_fracos"] or ""

    assert "PHP 8.3.13 mitigou vulnerabilidade" in pf_cache, "pontos_fracos em cache deve conter a afirmação real"
    assert "https://php.net/security-2026-cve" in pf_cache, "pontos_fracos em cache deve conter a URL real"


@pytest.mark.asyncio
async def test_r5_searcher_receives_projected_audit_feedback_in_system_prompt(
    db_session: AsyncSession,
) -> None:
    """Searcher da rodada seguinte deve receber o feedback textual gerado pelo Auditor no system prompt."""
    repo = ResearchRepository(session=db_session)
    pesq, pontos = await create_research_fixture_with_plan(repo)
    ponto = pontos[0]

    # Prepara coleta e executa Auditor para produzir o feedback real
    meta = make_standard_coleta_metadata(source_url="https://php.net/security-2026-cve")
    meta["resultados_personas"]["historiador"]["conclusoes"][0]["afirmacao"] = (
        "PHP 8.3.13 mitigou vulnerabilidade de leitura arbitrária de memória sem impacto de RCE."
    )
    await repo.save_collected_content(
        id_pesquisa=pesq.id_pesquisa,
        ponto_id=ponto.ponto_id,
        tema=pesq.tema,
        ponto=ponto.ponto,
        conteudo_coletado="Conteúdo de teste",
        urls_lidas=["https://php.net/security-2026-cve"],
        urls_fonte=["https://php.net/security-2026-cve"],
        metadados_coleta=meta,
    )

    vector_10 = make_audit_12_vector(
        10,
        known_claim_ids=["claim_1", "claim_2", "claim_3", "claim_4"],
        known_source_ids=["https://php.net/security-2026-cve"],
    )
    vector_10[10]["lacuna"] = "Falta confirmação do impacto em versões legadas"
    vector_10[10]["correcao"] = "Consultar advisories complementares do PHP 8.1 e 8.2"
    vector_10[10]["personas_pertinentes"] = ["cetico"]
    vector_10[11]["personas_pertinentes"] = ["cetico"]

    mock_net_aud = MockNetwork()
    mock_net_aud.custom_handlers["chat/completions"] = lambda r: make_llm_json_response({
        "criterios": vector_10,
        "resumo_auditoria": "Reprovado 10/12.",
    })
    llm_aud = LLMClient(api_key="mock-key", transport=create_mock_transport(mock_net_aud))
    auditor = Auditor(research_repo=repo, llm_client=llm_aud, personas=DEFAULT_AUDITOR_PERSONAS)

    await auditor.execute_audit(id_pesquisa=pesq.id_pesquisa, ponto_id=ponto.ponto_id, criterios_minimos=11)

    # Agora aciona o Searcher na rodada seguinte com o ponto já reprovado pelo Auditor
    captured_requests: List[httpx.Request] = []
    mock_net_search = MockNetwork()

    def capture_search(req: httpx.Request) -> httpx.Response:
        captured_requests.append(req)
        return make_llm_json_response({
            "acao": "concluir",
            "analise_final": "Análise conclusiva pós-auditoria.",
            "conclusoes": [{
                "claim_id": "c_novo",
                "afirmacao": "Validação concluída.",
                "tipo": "fato",
                "evidencias": ["chk_1"],
                "confianca": "alta",
                "limitacoes": "",
            }],
            "lacunas": [],
            "motivo_parada": "Concluído",
        })

    mock_net_search.custom_handlers["chat/completions"] = capture_search
    transport_search = create_mock_transport(mock_net_search)

    jina_client = JinaClient(api_key="mock-jina", transport=transport_search)
    llm_search = LLMClient(api_key="mock-key", transport=transport_search)

    searcher = Searcher(
        research_repo=repo,
        jina_client=jina_client,
        llm_client=llm_search,
        personas=["cetico"],
    )

    await searcher.execute_search(id_pesquisa=pesq.id_pesquisa, ponto_id=ponto.ponto_id, personas=["cetico"])

    assert len(captured_requests) > 0, "Searcher deve ter acionado o LLM"
    req_body = json.loads(captured_requests[0].content.decode("utf-8"))
    all_msgs = [m["content"] for m in req_body.get("messages", [])]
    all_text = " ".join(all_msgs)

    assert "DIRETRIZ DE RE-PESQUISA" in all_text
    assert "PHP 8.3.13 mitigou vulnerabilidade" in all_text, "Contexto do Searcher deve receber a afirmação do claim reprovado"
    assert "https://php.net/security-2026-cve" in all_text, "Contexto do Searcher deve receber a URL reprovada"


# ==============================================================================
# 5. TIMEOUT REAL CURTO
# ==============================================================================

@pytest.mark.asyncio
async def test_r5_audit_short_timeout_releases_possession_and_persists_diagnostic(
    test_env,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Timeout real curto deve suspender no handler, liberar posse em sessão fresca e registrar diagnóstico honesto."""
    import app.core.auditor as auditor_module
    monkeypatch.setattr(auditor_module, "AUDIT_POINT_TIMEOUT_SECONDS", 0.2)

    db_file = tmp_path / "r5_timeout_fresh.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"
    engine = create_engine_with_pragmas(db_url)
    await init_db(engine)

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with session_maker() as s_init:
        r_init = ResearchRepository(session=s_init)
        pesq, pontos = await create_research_fixture_with_plan(r_init)
        ponto = pontos[0]
        meta = make_standard_coleta_metadata()
        await r_init.save_collected_content(
            id_pesquisa=pesq.id_pesquisa,
            ponto_id=ponto.ponto_id,
            tema=pesq.tema,
            ponto=ponto.ponto,
            conteudo_coletado="Conteúdo",
            urls_lidas=["https://php.net/security-2026"],
            urls_fonte=["https://php.net/security-2026"],
            metadados_coleta=meta,
        )
        await s_init.commit()
        id_pesq = pesq.id_pesquisa
        id_ponto = ponto.ponto_id

    handler_reached = asyncio.Event()
    release_hang_event = asyncio.Event()

    async def hanging_handler(request: httpx.Request) -> httpx.Response:
        handler_reached.set()
        try:
            await asyncio.wait_for(release_hang_event.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            pass
        return make_llm_json_response({"criterios": []})

    mock_transport = httpx.MockTransport(hanging_handler)
    llm = LLMClient(api_key="mock-key", transport=mock_transport)

    try:
        async with session_maker() as s_exec:
            r_exec = ResearchRepository(session=s_exec)
            auditor = Auditor(research_repo=r_exec, llm_client=llm, personas=DEFAULT_AUDITOR_PERSONAS)
            with pytest.raises(asyncio.TimeoutError):
                await auditor.execute_audit(id_pesquisa=id_pesq, ponto_id=id_ponto)
    finally:
        release_hang_event.set()
        await llm.aclose()

    assert handler_reached.is_set(), "O transporte HTTP mockado deve ter sido efetivamente alcançado antes do timeout"

    # Confere liberação da reserva do ponto e diagnóstico persistido em sessão fresca
    async with session_maker() as s_fresh:
        r_fresh = ResearchRepository(session=s_fresh)
        ponto_db = await r_fresh.get_point(id_ponto)
        assert ponto_db.status == "coletado", "Ponto deve ter reserva liberada para 'coletado' após timeout"
        assert ponto_db.pontos_fracos is not None and len(ponto_db.pontos_fracos.strip()) > 0, (
            "Diagnóstico de timeout não pode ser string vazia"
        )
        assert "timeout" in ponto_db.pontos_fracos.lower()

        # Zero GenerationAttempts fictícios gerados
        gas = (
            await s_fresh.execute(
                select(GenerationAttempt).where(GenerationAttempt.ponto_id == id_ponto)
            )
        ).scalars().all()
        assert len(gas) == 0, "Nenhum GenerationAttempt com métricas fictícias deve ser persistido em timeout"

    await engine.dispose()


# ==============================================================================
# 6. PRESERVAÇÃO DE ENVELOPES EM REPARO E VÍNCULO DE GAIDS
# ==============================================================================

@pytest.mark.asyncio
async def test_r5_audit_repair_vector_preserves_observed_envelopes_and_links_gaids(
    db_session: AsyncSession,
) -> None:
    """Reparo de vetor: envelopes concluídos da 1ª chamada sobrevivem se o reparo seguinte falhar com 500."""
    repo = ResearchRepository(session=db_session)
    pesq, pontos = await create_research_fixture_with_plan(repo)
    ponto = pontos[0]

    meta = make_standard_coleta_metadata()
    coleta = await repo.save_collected_content(
        id_pesquisa=pesq.id_pesquisa,
        ponto_id=ponto.ponto_id,
        tema=pesq.tema,
        ponto=ponto.ponto,
        conteudo_coletado="Conteúdo",
        urls_lidas=["https://php.net/security-2026"],
        urls_fonte=["https://php.net/security-2026"],
        metadados_coleta=meta,
    )

    call_count = 0

    def fail_on_vector_repair(req: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return make_llm_json_response({
                "criterios": [{"id": 1, "aprovado": True, "justificativa": "ok", "claim_ids": [], "source_ids": []}],
                "resumo_auditoria": "Incompleto proposital",
            })
        return httpx.Response(500, json={"error": "LLM Provider Unavailable"})

    mock_net = MockNetwork()
    mock_net.custom_handlers["chat/completions"] = fail_on_vector_repair
    llm = LLMClient(api_key="mock-key", transport=create_mock_transport(mock_net))
    auditor = Auditor(research_repo=repo, llm_client=llm, personas=DEFAULT_AUDITOR_PERSONAS)

    from app.tools.errors import LLMCallError
    with pytest.raises(LLMCallError):
        await auditor.execute_audit(id_pesquisa=pesq.id_pesquisa, ponto_id=ponto.ponto_id)

    assert call_count >= 2, "Devem ocorrer pelo menos 2 chamadas: 1ª original e reparo dirigido de vetor"

    gas = (
        await db_session.execute(
            select(GenerationAttempt).where(GenerationAttempt.ponto_id == ponto.ponto_id)
        )
    ).scalars().all()
    assert len(gas) >= 1, "O envelope da 1ª chamada observada deve ser persistido em GenerationAttempt"

    stmt_meta = select(ConteudoColetado.metadados_coleta).where(ConteudoColetado.id == coleta.id)
    meta_db = json.loads((await db_session.execute(stmt_meta)).scalar_one())
    assert "auditorias" in meta_db and len(meta_db["auditorias"]) > 0
    last_aud = meta_db["auditorias"][-1]
    assert "generation_attempt_ids" in last_aud
    assert len(last_aud["generation_attempt_ids"]) >= 1


@pytest.mark.asyncio
async def test_r5_audit_repair_json_internal_preserves_observed_envelopes(
    db_session: AsyncSession,
) -> None:
    """Reparo JSON interno em LLMClient: envelope da 1ª chamada com JSON truncado sobrevive se a 2ª chamada falhar."""
    from app.tools.errors import LLMCallError

    call_count = 0

    def fail_on_second_json_call(req: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # Retorna resposta HTTP 200 com JSON válido na camada de transporte, mas content truncado no assistente
            return httpx.Response(
                200,
                json={
                    "choices": [{
                        "message": {
                            "role": "assistant",
                            "content": '{"criterios": [',
                        },
                        "finish_reason": "stop",
                    }],
                    "usage": {"total_tokens": 12},
                },
            )
        # 2ª tentativa (reparo JSON interno) falha com 500
        return httpx.Response(500, json={"error": "JSON repair server down"})

    mock_net = MockNetwork()
    mock_net.custom_handlers["chat/completions"] = fail_on_second_json_call
    llm = LLMClient(api_key="mock-key", transport=create_mock_transport(mock_net))

    try:
        with pytest.raises(Exception) as exc_info:
            await llm.generate_json_envelope(
                model_type="strong",
                messages=[{"role": "user", "content": "teste json"}],
            )

        err = exc_info.value
        # O erro propagado DEVE carregar o envelope da 1ª tentativa observada (first_envelope)
        priors = getattr(err.envelope, "prior_envelopes", None) if hasattr(err, "envelope") and err.envelope else []
        all_err_envs = list(priors or [])
        if hasattr(err, "envelopes") and err.envelopes:
            all_err_envs.extend(err.envelopes)
        assert any(e.content_final and '{"criterios": [' in str(e.content_final) for e in all_err_envs), (
            "Envelope da 1ª chamada observada com JSON truncado deve sobreviver nos envelopes da exceção do reparo"
        )
    finally:
        await llm.aclose()


# ==============================================================================
# 7. CICLO DE VIDA DO LLM_CLIENT NO ENDPOINT (ACLOSE NO FINALLY)
# ==============================================================================

@pytest.mark.asyncio
async def test_r5_endpoint_aclose_lifecycle_on_success_and_errors(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verifica que llm_client.aclose() é invocado exatamente 1 vez em sucesso, erro de geração e erro de configuração."""
    repo = ResearchRepository(session=db_session)
    pesq, pontos = await create_research_fixture_with_plan(repo)
    ponto = pontos[0]

    meta = make_standard_coleta_metadata()
    await repo.save_collected_content(
        id_pesquisa=pesq.id_pesquisa,
        ponto_id=ponto.ponto_id,
        tema=pesq.tema,
        ponto=ponto.ponto,
        conteudo_coletado="Conteúdo",
        urls_lidas=["https://php.net/security-2026"],
        urls_fonte=["https://php.net/security-2026"],
        metadados_coleta=meta,
    )

    aclose_calls = []
    original_aclose = LLMClient.aclose

    async def spy_aclose(self_client):
        aclose_calls.append(self_client)
        await original_aclose(self_client)

    monkeypatch.setattr(LLMClient, "aclose", spy_aclose)

    # 1. Caso Sucesso (HTTP 200)
    mock_net_200 = MockNetwork()
    mock_net_200.custom_handlers["chat/completions"] = lambda r: make_llm_json_response({
        "criterios": make_audit_12_vector(12, known_claim_ids=["claim_1", "claim_2", "claim_3", "claim_4"]),
        "resumo_auditoria": "Aprovado via HTTP.",
    })
    monkeypatch.setattr("app.api.v1.endpoints.audit._get_transport", lambda: create_mock_transport(mock_net_200))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/audit", json={"id_pesquisa": pesq.id_pesquisa})
        assert resp.status_code == 200
        assert len(aclose_calls) == 1, "aclose deve ser chamado exatamente 1 vez em sucesso"

    # 2. Caso Erro de Geração em pesquisa nova (sem colisão com cache anterior)
    aclose_calls.clear()
    pesq2, pontos2 = await create_research_fixture_with_plan(repo)
    ponto2 = pontos2[0]
    meta2 = make_standard_coleta_metadata()
    await repo.save_collected_content(
        id_pesquisa=pesq2.id_pesquisa,
        ponto_id=ponto2.ponto_id,
        tema=pesq2.tema,
        ponto=ponto2.ponto,
        conteudo_coletado="Conteúdo 2",
        urls_lidas=["https://php.net/security-2026"],
        urls_fonte=["https://php.net/security-2026"],
        metadados_coleta=meta2,
    )

    err_handler_calls = 0
    def fail_llm(req: httpx.Request) -> httpx.Response:
        nonlocal err_handler_calls
        err_handler_calls += 1
        return httpx.Response(500, json={"error": "LLM Provider Unavailable"})

    mock_net_err = MockNetwork()
    mock_net_err.custom_handlers["chat/completions"] = fail_llm
    monkeypatch.setattr("app.api.v1.endpoints.audit._get_transport", lambda: create_mock_transport(mock_net_err))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/audit", json={"id_pesquisa": pesq2.id_pesquisa})
        assert err_handler_calls > 0, "O handler de erro deve ter sido acionado"
        assert resp.status_code in (400, 500, 502)
        assert len(aclose_calls) == 1, "aclose deve ser chamado exatamente 1 vez em erro de geração"

    # 3. Caso Erro de Configuração pós-construção do cliente
    aclose_calls.clear()
    def mock_auditor_init_fail(*args, **kwargs):
        raise ValueError("Configuração inválida: persona 'auditor' ausente")

    monkeypatch.setattr("app.api.v1.endpoints.audit.Auditor.__init__", mock_auditor_init_fail)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/audit", json={"id_pesquisa": pesq.id_pesquisa})
        assert resp.status_code == 400
        assert len(aclose_calls) == 1, "aclose deve ser chamado exatamente 1 vez em erro de configuração pós-construção"

    # 4. Caso Falha antes da construção do cliente (ex: resolve_key falha)
    aclose_calls.clear()
    async def mock_resolve_key_fail(*args, **kwargs):
        raise RuntimeError("Falha de conexão com KMS")

    monkeypatch.setattr("app.api.v1.endpoints.audit.resolve_key", mock_resolve_key_fail)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/audit", json={"id_pesquisa": pesq.id_pesquisa})
        assert resp.status_code == 500
        assert len(aclose_calls) == 0, "aclose NÃO deve ser chamado se o cliente não chegou a ser construído"


# ==============================================================================
# 8. INVALIDAÇÃO DE CACHE POR MODELO E INSTRUÇÃO
# ==============================================================================

@pytest.mark.asyncio
async def test_r5_cache_invalidation_on_model_strong_and_persona_prompt_change(
    db_session: AsyncSession,
) -> None:
    """Alteração real de model_strong ou de persona_prompt deve invalidar cache e disparar nova chamada."""
    repo = ResearchRepository(session=db_session)
    pesq, pontos = await create_research_fixture_with_plan(repo)
    ponto = pontos[0]

    meta = make_standard_coleta_metadata()
    coleta = await repo.save_collected_content(
        id_pesquisa=pesq.id_pesquisa,
        ponto_id=ponto.ponto_id,
        tema=pesq.tema,
        ponto=ponto.ponto,
        conteudo_coletado="Conteúdo",
        urls_lidas=["https://php.net/security-2026"],
        urls_fonte=["https://php.net/security-2026"],
        metadados_coleta=meta,
    )

    llm_call_count = 0
    def count_llm_handler(req: httpx.Request) -> httpx.Response:
        nonlocal llm_call_count
        llm_call_count += 1
        return make_llm_json_response({
            "criterios": make_audit_12_vector(12, known_claim_ids=["claim_1", "claim_2", "claim_3", "claim_4"]),
            "resumo_auditoria": f"Aprovado chamada {llm_call_count}",
        })

    mock_net = MockNetwork()
    mock_net.custom_handlers["chat/completions"] = count_llm_handler
    transport = create_mock_transport(mock_net)

    # 1. Primeira avaliação com modelo "gpt-4o"
    llm_1 = LLMClient(api_key="mock-key", model_strong="gpt-4o", transport=transport)
    auditor_1 = Auditor(
        research_repo=repo,
        llm_client=llm_1,
        persona_prompt="Prompt auditor v1.",
    )
    res_1 = await auditor_1.execute_audit(id_pesquisa=pesq.id_pesquisa, ponto_id=ponto.ponto_id)
    assert res_1["auditorias"][0]["valido"] is True
    assert llm_call_count == 1

    # 2. Reutilização idêntica: zero chamadas LLM (cache hit)
    res_2 = await auditor_1.execute_audit(id_pesquisa=pesq.id_pesquisa, ponto_id=ponto.ponto_id)
    assert res_2["auditorias"][0]["valido"] is True
    assert llm_call_count == 1, "Reutilização idêntica não deve disparar nova chamada LLM"

    # 3. Alteração do model_strong ("gpt-4o-2024-11-20") com mesma entrada e persona_prompt
    llm_2 = LLMClient(api_key="mock-key", model_strong="gpt-4o-2024-11-20", transport=transport)
    auditor_2 = Auditor(
        research_repo=repo,
        llm_client=llm_2,
        persona_prompt="Prompt auditor v1.",
    )
    res_3 = await auditor_2.execute_audit(id_pesquisa=pesq.id_pesquisa, ponto_id=ponto.ponto_id)
    assert res_3["auditorias"][0]["valido"] is True
    assert llm_call_count == 2, "Alteração de model_strong deve invalidar cache e disparar nova chamada"

    # 4. Alteração de persona_prompt com mesmo modelo
    auditor_3 = Auditor(
        research_repo=repo,
        llm_client=llm_2,
        persona_prompt="Prompt auditor v2 com novas regras.",
    )
    res_4 = await auditor_3.execute_audit(id_pesquisa=pesq.id_pesquisa, ponto_id=ponto.ponto_id)
    assert res_4["auditorias"][0]["valido"] is True
    assert llm_call_count == 3, "Alteração de persona_prompt deve invalidar cache e disparar nova chamada"

    # Confere que o histórico da coleta contém exatamente 3 auditorias com hashes distintos
    stmt_meta = select(ConteudoColetado.metadados_coleta).where(ConteudoColetado.id == coleta.id)
    meta_db = json.loads((await db_session.execute(stmt_meta)).scalar_one())
    assert len(meta_db["auditorias"]) == 3
    hashes = {a.get("input_hash") for a in meta_db["auditorias"]}
    assert len(hashes) == 3, "Cada auditoria deve registrar seu próprio input_hash real gerado pelo código"


# ==============================================================================
# 9. TEARDOWN E LIMPEZA DE ENGINE GLOBAL
# ==============================================================================

@pytest.mark.asyncio
async def test_r5_async_engine_teardown_disposes_global_engine(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O teardown da fixture async_engine em conftest deve invocar dispose() no engine global extra."""
    from app.db import session as db_session_module
    import tests.conftest as conftest_module

    # Força a criação do engine global via get_engine()
    db_file = tmp_path / "global_engine_probe.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_file}")
    global_engine = get_engine()
    assert db_session_module._engine is not None

    from sqlalchemy.ext.asyncio import AsyncEngine
    dispose_called = False
    original_dispose = AsyncEngine.dispose

    async def spy_dispose(self_engine):
        nonlocal dispose_called
        if self_engine is global_engine:
            dispose_called = True
        await original_dispose(self_engine)

    monkeypatch.setattr(AsyncEngine, "dispose", spy_dispose)

    # Executa o gerador de fixture async_engine como gerador assíncrono real para exercitar seu teardown
    fixture_gen = conftest_module.async_engine.__wrapped__(str(db_file), None)
    try:
        engine_yielded = await anext(fixture_gen)
    except Exception:
        pass
    else:
        try:
            await anext(fixture_gen)
        except StopAsyncIteration:
            pass

    assert dispose_called, "O teardown da fixture async_engine deve invocar dispose() no engine global extra"
    assert db_session_module._engine is None, "O engine global deve ser resetado após o teardown"


# ==============================================================================
# 10. PRESERVAÇÃO DE ENVELOPE CONCLUÍDO EM CANCELAMENTO DE REPARO JSON INTERNO (r6)
# ==============================================================================

@pytest.mark.asyncio
async def test_r6_audit_internal_json_repair_cancellation_preserves_first_envelope_and_gas(
    tmp_path,
) -> None:
    """Exercita Auditor.execute_audit real sobre SQLite descartável e transporte MockTransport.

    1ª resposta: HTTP JSON 200, finish_reason='stop', usage conhecido, mas content com JSON inválido.
    2ª resposta: reparo interno (stream=False) fica suspenso em voo aguardando Event.
    Cancela a task enquanto a chamada 2 está em voo.
    Afirma propagação estrita de CancelledError.
    Em sessão fresca, valida:
    - call_count == 2 (fronteira real de reparo JSON interno alcançada)
    - exatamente 1 GenerationAttempt preservado no banco (da 1ª chamada concluída)
    - atributos reais de content, finish_reason='stop', usage no GenerationAttempt
    - vínculo id_auditoria -> generation_attempt_ids na coleta
    - reserva do ponto liberada para 'coletado' (não 'auditando'), com diagnóstico honesto
    - sem vetor válido, sem 4ª avaliação fictícia
    - nenhum GA fictício gerado para a 2ª chamada interrompida em voo.
    """
    db_file = tmp_path / "r6_cancel_internal_json_repair.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"
    engine = create_engine_with_pragmas(db_url)
    await init_db(engine)

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with session_maker() as s_init:
        r_init = ResearchRepository(session=s_init)
        pesq, pontos = await create_research_fixture_with_plan(r_init)
        ponto = pontos[0]
        meta = make_standard_coleta_metadata(source_url="https://exemplo.org/artigo-seguranca")
        coleta = await r_init.save_collected_content(
            id_pesquisa=pesq.id_pesquisa,
            ponto_id=ponto.ponto_id,
            tema=pesq.tema,
            ponto=ponto.ponto,
            conteudo_coletado="Conteúdo de validação para auditoria e teste de cancelamento r6",
            urls_lidas=["https://exemplo.org/artigo-seguranca"],
            urls_fonte=["https://exemplo.org/artigo-seguranca"],
            metadados_coleta=meta,
        )
        await s_init.commit()
        id_pesq = pesq.id_pesquisa
        id_ponto = ponto.ponto_id
        id_coleta = coleta.id

    call_count = 0
    second_call_in_flight = asyncio.Event()
    release_second_call = asyncio.Event()

    async def async_handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # 1ª chamada: HTTP regular 200, finish_reason='stop', usage conhecido, mas content com JSON inválido
            return httpx.Response(
                200,
                json={
                    "id": "chatcmpl-mock-r6-invalid-json",
                    "object": "chat.completion",
                    "created": 1729720000,
                    "model": "gpt-4o",
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": '{"criterios": [corrompido',
                            },
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 120,
                        "completion_tokens": 15,
                        "total_tokens": 135,
                    },
                },
            )
        elif call_count == 2:
            # 2ª chamada: reparo JSON interno em voo
            second_call_in_flight.set()
            await release_second_call.wait()
            return httpx.Response(
                200,
                json={
                    "id": "chatcmpl-mock-r6-second-call",
                    "object": "chat.completion",
                    "created": 1729720001,
                    "model": "gpt-4o",
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": '{"criterios": []}',
                            },
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 999,
                        "completion_tokens": 999,
                        "total_tokens": 1998,
                    },
                },
            )
        return httpx.Response(500, json={"error": "chamada inesperada"})

    transport = httpx.MockTransport(async_handler)
    llm = LLMClient(api_key="mock-key-r6", transport=transport)

    async with session_maker() as s_exec:
        r_exec = ResearchRepository(session=s_exec)
        auditor = Auditor(research_repo=r_exec, llm_client=llm, personas=DEFAULT_AUDITOR_PERSONAS)

        audit_task = asyncio.create_task(
            auditor.execute_audit(id_pesquisa=id_pesq, ponto_id=id_ponto)
        )

        try:
            async with asyncio.timeout(3.0):
                await second_call_in_flight.wait()

            assert call_count == 2, "A segunda chamada (reparo JSON interno) deve estar confirmada em voo"
            assert not audit_task.done(), "A tarefa de auditoria deve estar suspensa na 2ª chamada"

            # Cancela a tarefa enquanto a 2ª chamada está suspensa em voo
            audit_task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await audit_task
        finally:
            release_second_call.set()
            if not audit_task.done():
                audit_task.cancel()
                try:
                    await audit_task
                except (asyncio.CancelledError, Exception):
                    pass
            await llm.aclose()

    # Verificações estritas em sessão NOVA
    async with session_maker() as s_fresh:
        r_fresh = ResearchRepository(session=s_fresh)

        # 1. call_count == 2
        assert call_count == 2, "Devem ter ocorrido exatamente 2 chamadas no transporte"

        # 2. Somente GenerationAttempt da primeira chamada concluída é preservado
        gas = (
            await s_fresh.execute(
                select(GenerationAttempt).where(GenerationAttempt.ponto_id == id_ponto)
            )
        ).scalars().all()
        assert len(gas) == 1, (
            f"Deveria haver exatamente 1 GenerationAttempt preservado (da 1ª chamada concluída), "
            f"mas foram encontrados {len(gas)}. Se 0, first_envelope foi perdido no cancelamento!"
        )
        ga = gas[0]
        assert ga.finish_reason == "stop"
        assert ga.is_regular_finish is True
        ga_usage = json.loads(ga.usage_json) if ga.usage_json else {}
        assert ga_usage.get("total_tokens") == 135
        assert ga_usage.get("prompt_tokens") == 120
        assert ga_usage.get("completion_tokens") == 15
        assert ga.content_final == '{"criterios": [corrompido'
        assert ga.messages_json is not None and len(ga.messages_json) > 0
        assert ga.etapa == "audit"
        assert ga.persona == "auditor"

        # 3. Nenhum GA ou métrica fictícia da segunda chamada (em voo)
        assert ga_usage.get("total_tokens") != 1998
        assert ga_usage.get("prompt_tokens") != 999

        # 4. Histórico da coleta e vínculo de IDs
        stmt_meta = select(ConteudoColetado.metadados_coleta).where(ConteudoColetado.id == id_coleta)
        raw_meta = (await s_fresh.execute(stmt_meta)).scalar_one()
        meta_db = json.loads(raw_meta)
        assert "auditorias" in meta_db and len(meta_db["auditorias"]) > 0
        last_aud = meta_db["auditorias"][-1]
        assert last_aud["valido"] is False
        assert last_aud["status"] == "reprovado"
        assert last_aud["criterios"] is None
        assert last_aud["criterios_aprovados"] == 0
        assert last_aud["pontuacao_percentual"] == 0.0
        assert "generation_attempt_ids" in last_aud
        assert len(last_aud["generation_attempt_ids"]) == 1
        assert last_aud["generation_attempt_ids"][0] == ga.id

        # 5. Reserva do ponto liberada e status honesto (não auditando, sem 4ª avaliação)
        ponto_db = await r_fresh.get_point(id_ponto)
        assert ponto_db is not None
        assert ponto_db.status == "coletado", f"Status do ponto deveria ser 'coletado', mas é '{ponto_db.status}'"
        assert ponto_db.status != "auditando"
        assert ponto_db.pontos_fracos is not None and len(ponto_db.pontos_fracos.strip()) > 0
        assert ponto_db.tentativas_auditoria <= 3

    await engine.dispose()



# ==============================================================================
# Regressão: TimeoutError sem mensagem virava "AUDIT_PROCESSING_ERROR: " (vazio)
# ==============================================================================

@pytest.mark.asyncio
async def test_audit_timeout_maps_to_504_with_explicit_code(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Timeout do ponto deve sair como HTTP 504 AUDIT_TIMEOUT, nunca 500 com detalhe vazio."""
    from fastapi import HTTPException

    from app.api.v1.endpoints import audit as audit_endpoint
    from app.schemas.audit import AuditRequest

    async def execute_audit_estourado(self, **kwargs):  # noqa: ANN001, ARG001
        raise TimeoutError()

    monkeypatch.setattr(audit_endpoint.Auditor, "execute_audit", execute_audit_estourado)

    payload = AuditRequest(id_pesquisa="00000000-0000-0000-0000-000000000000")

    with pytest.raises(HTTPException) as exc:
        await audit_endpoint.audit_research(payload=payload, db=db_session)

    assert exc.value.status_code == 504
    assert "AUDIT_TIMEOUT" in str(exc.value.detail)
    assert "tempo limite" in str(exc.value.detail)
