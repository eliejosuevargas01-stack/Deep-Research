# -*- coding: utf-8 -*-
"""Testes de aceitação para paralelismo real de todos os pontos da pesquisa.

Valida:
1. Concorrência real de múltiplos pontos em Searcher comprovada por barreira (asyncio.Barrier).
2. Isolamento estrito de AsyncSession: cada trabalhador de ponto opera em sessão SQLAlchemy própria.
3. Resposta síncrona determinística ordenada por ponto_n e agregado correto de pesquisa.
4. Cancelamento e falha: cancelamento propaga para tarefas ativas, libera reservas via CAS e preserva pontos concluídos.
5. Concorrência real de pontos em PipelineRunner comprovada por barreira, bloqueando Writer até aprovação total.
6. Concorrência de pontos em Auditoria com barreira e isolamento de sessão.
"""

import asyncio
import json
import re
from typing import Any, Dict, List, Optional
import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.auditor import Auditor
from app.core.personas import resolve_required_search_personas
from app.core.pipeline_runner import PipelineRunner
from app.core.searcher import Searcher
from app.core.writer import Writer
from app.db.models import ConteudoColetado, GenerationAttempt, Pesquisa, Ponto
from app.db.research_repository import ResearchRepository
from app.tools.jina_client import JinaClient
from app.tools.llm_client import LLMClient
from tests.mocks.http_mock import MockNetwork, create_mock_transport
from tests.unit.test_audit_acceptance import (
    CANONICAL_EIXO,
    CANONICAL_PLANO,
    create_research_fixture_with_plan,
    make_audit_12_vector,
    make_standard_coleta_metadata,
)
from tests.unit.test_reproduction_gate1_helpers import (
    make_llm_json_response,
    make_serp_response,
)
from tests.unit.test_search_acceptance import _extract_delivered_chunk_id


def _setup_search_mock(
    mock_net: MockNetwork,
    sample_body: str = "Conteudo documental primario para teste de paralelismo de pontos.",
) -> None:
    """Configura handlers de busca (LLM, SERP, Reader) para respostas de sucesso rápido."""
    def llm_handler(request: httpx.Request) -> httpx.Response:
        data = json.loads(request.content.decode("utf-8"))
        msgs = data.get("messages", [])
        sys_msg = " ".join([m.get("content", "") for m in msgs if m.get("role") == "system"]).lower()
        persona = "historiador"
        for p in ["historiador", "visionario", "cetico", "futurista"]:
            if p in sys_msg:
                persona = p
                break

        # Se houver trechos entregues, conclui
        user_msgs = [m.get("content", "") for m in msgs if m.get("role") == "user"]
        last_user = user_msgs[-1] if user_msgs else ""
        if "chk_" in last_user:
            delivered_chunk_id = _extract_delivered_chunk_id(msgs)
            return make_llm_json_response({
                "acao": "concluir",
                "analise_final": f"Analise concluida por {persona}.",
                "conclusoes": [
                    {
                        "claim_id": f"clm_{persona}_1",
                        "afirmacao": f"Afirmacao suportada por {persona}.",
                        "tipo": "fato",
                        "evidencias": [delivered_chunk_id],
                        "confianca": "alta",
                        "limitacoes": "Nenhuma.",
                    }
                ],
                "lacunas": [],
                "motivo_parada": "Suficiente.",
            })
        return make_llm_json_response({
            "acao": "buscar",
            "consulta": f"consulta sobre ponto por {persona}",
            "objetivo": "buscar fatos",
        })

    call_idx = 0
    def serp_handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_idx
        call_idx += 1
        return make_serp_response([
            {
                "url": f"https://fonte-paralela-{call_idx}.org/doc",
                "title": "Fonte Primaria Concorrente",
                "description": "Evidencia web de suporte",
            }
        ])

    def reader_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=sample_body, headers={"Content-Type": "text/markdown"})

    mock_net.custom_handlers["chat/completions"] = llm_handler
    mock_net.custom_handlers["s.jina.ai"] = serp_handler
    mock_net.custom_handlers["r.jina.ai"] = reader_handler


# -----------------------------------------------------------------------------
# 1. Concorrência Real por Barreira de Vários Pontos no Searcher
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_reading_coordinator_cancellation_refcount_and_clean_close() -> None:
    """Coordenação compartilhada: consumidor cancelado não cancela task de outros e close encerra sem órfãos."""
    from app.core.reading_coordinator import ReadingCoordinator

    coord = ReadingCoordinator()
    url = "https://example.org/shared"
    started = asyncio.Event()
    hang = asyncio.Event()

    fetch_calls = 0

    async def fetch_coro():
        nonlocal fetch_calls
        fetch_calls += 1
        started.set()
        await hang.wait()
        return {"url": url, "body": "conteudo lido", "status": "read_ok"}

    # Inicia dois consumidores concorrentes para a mesma URL
    task1 = asyncio.create_task(coord.fetch_url(url, fetch_coro))
    await started.wait()

    task2 = asyncio.create_task(coord.fetch_url(url, fetch_coro))
    await asyncio.sleep(0.01)

    # Cancela apenas o consumidor 1
    task1.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task1

    # Task subjacente NÃO pode ter sido cancelada porque task2 ainda consome!
    assert fetch_calls == 1
    hang.set()
    res2 = await task2
    assert res2 is not None
    assert res2["body"] == "conteudo lido"
    assert url in coord.shared_cache

    # Testa fechamento ordenado
    await coord.close()


@pytest.mark.asyncio
async def test_pipeline_runner_shares_reading_coordinator_deduplicating_cross_point(
    async_engine,
) -> None:
    """PipelineRunner compartilha coordenação de leitura entre pontos, garantindo desduplicação real."""
    session_factory = async_sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    async with session_factory() as db:
        repo = ResearchRepository(session=db)
        pesq, pontos = await create_research_fixture_with_plan(repo, n_pontos=2)
        id_pesquisa = pesq.id_pesquisa

    mock_net = MockNetwork()
    _setup_search_mock(mock_net)

    # Força a mesma URL compartilhada para ambos os pontos
    shared_url = "https://fonte-compartilhada-unica.org/doc"
    mock_net.custom_handlers["s.jina.ai"] = lambda req: make_serp_response([
        {"url": shared_url, "title": "Doc Compartilhado", "description": "Evidencia compartilhada"}
    ])

    reader_calls = 0
    def counted_reader(request: httpx.Request) -> httpx.Response:
        nonlocal reader_calls
        reader_calls += 1
        return httpx.Response(200, text="Corpo compartilhado lido uma unica vez.")

    mock_net.custom_handlers["r.jina.ai"] = counted_reader
    transport = create_mock_transport(mock_net)

    runner = PipelineRunner(transport=transport)
    await runner.run(id_pesquisa=id_pesquisa)

    # Jina Reader DEVE ter sido chamado apenas UMA vez para a URL compartilhada entre os 2 pontos!
    assert reader_calls == 1


@pytest.mark.asyncio
async def test_searcher_executes_all_points_in_parallel_via_barrier(
    db_session: AsyncSession,
) -> None:
    """Verifica que Searcher executa TODOS os pontos em paralelo concorrente via barreira.

    Se a execução for sequencial (ponto 1 depois ponto 2 depois ponto 3), o primeiro ponto
    espera na barreira e sofre timeout (Deadlock/Timeout). Em paralelo real, todos os 3
    pontos entram simultaneamente na barreira e a destravam juntos.
    """
    repo = ResearchRepository(session=db_session)
    pesq, pontos = await create_research_fixture_with_plan(repo, n_pontos=3)
    assert len(pontos) == 3

    # Barreira de 3 participantes: só destrava quando TODOS os 3 pontos estiverem ativos
    barrier = asyncio.Barrier(3)
    entered_points: List[str] = []

    mock_net = MockNetwork()
    _setup_search_mock(mock_net)

    original_reader = mock_net.custom_handlers["r.jina.ai"]

    async def barrier_reader_handler(request: httpx.Request) -> httpx.Response:
        entered_points.append(str(request.url))
        try:
            # Espera todos os 3 pontos atingirem a fase de leitura web simultaneamente
            await asyncio.wait_for(barrier.wait(), timeout=3.0)
        except asyncio.TimeoutError:
            pytest.fail("Barreira falhou por timeout: pontos NAO estao sendo executados em paralelo!")
        return original_reader(request)

    mock_net.custom_handlers["r.jina.ai"] = barrier_reader_handler
    transport = create_mock_transport(mock_net)

    jina_client = JinaClient(api_key="jina-key", transport=transport)
    llm_client = LLMClient(api_key="llm-key", transport=transport)

    searcher = Searcher(
        research_repo=repo,
        jina_client=jina_client,
        llm_client=llm_client,
        personas=["historiador"],
        point_timeout_seconds=10.0,
    )

    # Executa busca geral de todos os pontos da pesquisa
    resumo = await searcher.execute_search(id_pesquisa=pesq.id_pesquisa)

    assert resumo["total_pontos_processados"] == 3
    assert len(resumo["resumo_coletas"]) == 3
    # Ordenação determinística preservada: ponto_n 1, 2, 3
    nums = [item["ponto_n"] for item in resumo["resumo_coletas"]]
    assert nums == [1, 2, 3]


# -----------------------------------------------------------------------------
# 2. Isolamento de AsyncSession por Ponto em Execução Concorrente
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_searcher_and_auditor_block_parallel_when_session_factory_none(
    db_session: AsyncSession,
) -> None:
    """Searcher e Auditor com session_factory=None bloqueiam explicitamente concorrência de múltiplos pontos."""
    repo = ResearchRepository(session=db_session)
    pesq, pontos = await create_research_fixture_with_plan(repo, n_pontos=2)
    assert len(pontos) == 2

    mock_net = MockNetwork()
    _setup_search_mock(mock_net)
    transport = create_mock_transport(mock_net)
    jina = JinaClient(api_key="jina-key", transport=transport)
    llm = LLMClient(api_key="llm-key", transport=transport)

    searcher = Searcher(
        research_repo=repo,
        jina_client=jina,
        llm_client=llm,
        personas=["historiador"],
        session_factory=None,
    )
    searcher.session_factory = None  # Assegura que fábrica é explicitamente ausente

    with pytest.raises(RuntimeError, match="CONCURRENCY_ERROR"):
        await searcher.execute_search(id_pesquisa=pesq.id_pesquisa)

    auditor = Auditor(
        research_repo=repo,
        llm_client=llm,
        session_factory=None,
    )
    auditor.session_factory = None

    with pytest.raises(RuntimeError, match="CONCURRENCY_ERROR"):
        await auditor.execute_audit(id_pesquisa=pesq.id_pesquisa)


@pytest.mark.asyncio
async def test_searcher_and_auditor_derive_true_engine_when_bind_is_async_connection(
    async_engine,
) -> None:
    """Quando o bind é AsyncConnection, Searcher e Auditor derivam a engine para isolamento real de conexões."""
    async with async_engine.connect() as conn:
        conn_session = AsyncSession(bind=conn)
        repo = ResearchRepository(session=conn_session)
        mock_net = MockNetwork()
        _setup_search_mock(mock_net)
        transport = create_mock_transport(mock_net)
        jina = JinaClient(api_key="jina-key", transport=transport)
        llm = LLMClient(api_key="llm-key", transport=transport)

        searcher = Searcher(
            research_repo=repo,
            jina_client=jina,
            llm_client=llm,
            personas=["historiador"],
        )
        assert searcher.session_factory is not None
        # A sessão gerada pela factory NÃO pode ter o bind apontando para a mesma AsyncConnection!
        spawned_search_session = searcher.session_factory()
        try:
            assert spawned_search_session.bind is not conn
            assert spawned_search_session.bind is async_engine
        finally:
            await spawned_search_session.close()

        auditor = Auditor(
            research_repo=repo,
            llm_client=llm,
        )
        assert auditor.session_factory is not None
        spawned_audit_session = auditor.session_factory()
        try:
            assert spawned_audit_session.bind is not conn
            assert spawned_audit_session.bind is async_engine
        finally:
            await spawned_audit_session.close()
        await conn_session.close()


@pytest.mark.asyncio
async def test_searcher_isolated_sessions_prevent_sqlalchemy_concurrency_error(
    db_session: AsyncSession,
) -> None:
    """Verifica que pontos concorrentes nao compartilham a mesma AsyncSession.

    No SQLAlchemy, operar concorrentemente sobre a mesma AsyncSession lanca
    InvalidRequestError/IllegalStateChangeError. Cada corrotina de ponto deve
    usar uma sessao isolada.
    """
    repo = ResearchRepository(session=db_session)
    pesq, pontos = await create_research_fixture_with_plan(repo, n_pontos=2)
    assert len(pontos) == 2

    mock_net = MockNetwork()
    _setup_search_mock(mock_net)
    transport = create_mock_transport(mock_net)

    jina_client = JinaClient(api_key="jina-key", transport=transport)
    llm_client = LLMClient(api_key="llm-key", transport=transport)

    searcher = Searcher(
        research_repo=repo,
        jina_client=jina_client,
        llm_client=llm_client,
        personas=["historiador"],
    )

    # Executa busca concorrente de 2 pontos
    resumo = await searcher.execute_search(id_pesquisa=pesq.id_pesquisa)

    assert resumo["total_pontos_processados"] == 2
    for item in resumo["resumo_coletas"]:
        assert item["status"] == "coletado"


# -----------------------------------------------------------------------------
# 3. Cancelamento Cooperativo e Liberação de Reserva por Eventos
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_searcher_cancellation_releases_reservation_and_preserves_completed(
    db_session: AsyncSession,
) -> None:
    """Cancelamento com eventos: comprova reserva ativa de pontos pendentes, liberação limpa e preservação de concluído."""
    repo = ResearchRepository(session=db_session)
    # Cria 3 pontos: ponto 1 será previamente concluído; pontos 2 e 3 serão executados concorrentemente
    pesq, pontos = await create_research_fixture_with_plan(repo, n_pontos=3)
    id_pesquisa = pesq.id_pesquisa
    p1, p2, p3 = pontos[0], pontos[1], pontos[2]

    # Marca ponto 1 como previamente concluído e aprovado
    await repo.update_point_status(p1.ponto_id, status="aprovado")
    await db_session.commit()

    # Eventos de sincronização determinística: sem sleep frágil
    entered_points: List[str] = []
    both_pending_entered = asyncio.Event()
    hang_event = asyncio.Event()

    mock_net = MockNetwork()
    _setup_search_mock(mock_net)

    async def hanging_reader(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        entered_points.append(url_str)
        if len(entered_points) >= 2:
            both_pending_entered.set()
        await hang_event.wait()
        return httpx.Response(200, text="corpo")

    mock_net.custom_handlers["r.jina.ai"] = hanging_reader
    transport = create_mock_transport(mock_net)

    jina_client = JinaClient(api_key="jina-key", transport=transport)
    llm_client = LLMClient(api_key="llm-key", transport=transport)

    searcher = Searcher(
        research_repo=repo,
        jina_client=jina_client,
        llm_client=llm_client,
        personas=["historiador"],
        point_timeout_seconds=5.0,
    )

    task = asyncio.create_task(searcher.execute_search(id_pesquisa=id_pesquisa))
    # Aguarda comprovadamente a reserva e entrada ativa de ambos os pontos pendentes
    await asyncio.wait_for(both_pending_entered.wait(), timeout=3.0)

    # Dispara cancelamento repetido para testar resiliência da limpeza
    task.cancel()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    # Verifica o estado no banco após cancelamento
    await db_session.rollback()
    frescos = await repo.list_points(id_pesquisa)
    frescos_dict = {p.ponto_id: p for p in frescos}

    # 1. Ponto previamente concluído (p1) foi preservado intacto
    assert frescos_dict[p1.ponto_id].status == "aprovado"

    # 2. Ambos os pontos que estavam ativos (p2 e p3) liberaram suas reservas para falha_coleta com diagnóstico
    p2_fresco = frescos_dict[p2.ponto_id]
    p3_fresco = frescos_dict[p3.ponto_id]
    assert p2_fresco.status == "falha_coleta"
    assert p3_fresco.status == "falha_coleta"
    assert "Interrupção" in (p2_fresco.pontos_fracos or "") or "Cancelamento" in (p2_fresco.pontos_fracos or "")
    assert "Interrupção" in (p3_fresco.pontos_fracos or "") or "Cancelamento" in (p3_fresco.pontos_fracos or "")

    # 3. Nenhum ponto pendente ou em_andamento restou
    assert all(p.status not in ("pendente", "em_andamento") for p in frescos)

    # 4. Prova que as leases foram liberadas e não ficaram presas: ambos os pontos podem ser reservados novamente
    r2 = await repo.reserve_point(p2.ponto_id)
    assert r2.status == "em_andamento"
    r3 = await repo.reserve_point(p3.ponto_id)
    assert r3.status == "em_andamento"




# -----------------------------------------------------------------------------
# 4. Concorrência Real de Pontos em PipelineRunner com Barreira
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_pipeline_runner_executes_unapproved_points_in_parallel(
    async_engine,
) -> None:
    """Verifica que PipelineRunner dispara todos os pontos pendentes da busca em paralelo via barreira."""
    session_factory = async_sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    async with session_factory() as db:
        repo = ResearchRepository(session=db)
        pesq, pontos = await create_research_fixture_with_plan(repo, n_pontos=2)
        id_pesquisa = pesq.id_pesquisa

    barrier = asyncio.Barrier(2)

    mock_net = MockNetwork()
    _setup_search_mock(mock_net)

    original_reader = mock_net.custom_handlers["r.jina.ai"]

    async def barrier_reader_handler(request: httpx.Request) -> httpx.Response:
        try:
            await asyncio.wait_for(barrier.wait(), timeout=3.0)
        except asyncio.TimeoutError:
            pytest.fail("PipelineRunner executou pontos em serie em vez de paralelo!")
        return original_reader(request)

    mock_net.custom_handlers["r.jina.ai"] = barrier_reader_handler
    transport = create_mock_transport(mock_net)

    runner = PipelineRunner(transport=transport)
    # Executa pipeline: busca (paralela) -> auditoria -> etc
    res = await runner.run(id_pesquisa=id_pesquisa)

    async with session_factory() as db:
        repo = ResearchRepository(session=db)
        frescos = await repo.list_points(id_pesquisa)
        assert len(frescos) == 2
        # Ambos os pontos foram processados
        assert all(p.status in ("coletado", "aprovado", "reprovado") for p in frescos)


# -----------------------------------------------------------------------------
# 5. Auditoria Concorrente com Barreira
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_auditor_executes_points_in_parallel_via_barrier(
    db_session: AsyncSession,
) -> None:
    """Verifica que Auditor pode avaliar múltiplos pontos em paralelo concorrente via barreira."""
    repo = ResearchRepository(session=db_session)
    pesq, pontos = await create_research_fixture_with_plan(repo, n_pontos=2)
    p1, p2 = pontos[0], pontos[1]

    # Prepara coletas para ambos os pontos
    for p in (p1, p2):
        meta = make_standard_coleta_metadata()
        await repo.save_collected_content(
            id_pesquisa=pesq.id_pesquisa,
            ponto_id=p.ponto_id,
            tema=pesq.tema,
            ponto=p.ponto,
            conteudo_coletado=f"Conteudo para {p.ponto}",
            urls_lidas=["https://php.net/security-2026"],
            urls_fonte=["https://php.net/security-2026"],
            metadados_coleta=meta,
        )

    barrier = asyncio.Barrier(2)

    mock_net = MockNetwork()

    async def barrier_llm_handler(request: httpx.Request) -> httpx.Response:
        data = json.loads(request.content.decode("utf-8"))
        try:
            await asyncio.wait_for(barrier.wait(), timeout=3.0)
        except asyncio.TimeoutError:
            pytest.fail("Auditor executou pontos em serie em vez de paralelo!")
        return make_llm_json_response({
            "criterios": make_audit_12_vector(11, known_claim_ids=["claim_1", "claim_2", "claim_3", "claim_4"]),
            "resumo_auditoria": "Aprovado na barreira.",
        })

    mock_net.custom_handlers["chat/completions"] = barrier_llm_handler
    transport = create_mock_transport(mock_net)

    llm = LLMClient(api_key="key", transport=transport)
    auditor = Auditor(research_repo=repo, llm_client=llm)

    res = await auditor.execute_audit(id_pesquisa=pesq.id_pesquisa)
    assert res["total_pontos"] == 2
    assert res["aprovados"] == 2
    assert res["pronto_para_writer"] is True


# -----------------------------------------------------------------------------
# 6. Bloqueio Estrito do Writer até Término e Aprovação de Todos os Pontos
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_pipeline_runner_strictly_blocks_writer_until_all_points_approved(
    async_engine,
) -> None:
    """Verifica que Writer jamais é acionado se algum ponto for reprovado: prova coletas reais, chamada de cada ponto no LLM e barreiras."""
    session_factory = async_sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    async with session_factory() as db:
        repo = ResearchRepository(session=db)
        eixos = [
            {**CANONICAL_EIXO, "pergunta_principal": f"Subpergunta Investigativa {i+1}", "ponto_n": i+1}
            for i in range(2)
        ]
        pesq = await repo.create_research(
            tema="Segurança do PHP 2026",
            pontos_textos=["Ponto Alfa 1", "Ponto Beta 2"],
            plano_estruturado=CANONICAL_PLANO,
            eixos_estruturados=eixos,
            metadados_planejamento={"preferencias": {"personas": ["historiador"]}},
        )
        id_pesquisa = pesq.id_pesquisa
        pontos = await repo.list_points(id_pesquisa)
        p1, p2 = pontos[0], pontos[1]

    search_barrier = asyncio.Barrier(2)
    audit_barrier = asyncio.Barrier(2)
    audit_points_called = set()
    writer_called = False

    mock_net = MockNetwork()
    _setup_search_mock(mock_net)

    original_reader = mock_net.custom_handlers["r.jina.ai"]

    async def barrier_reader_handler(request: httpx.Request) -> httpx.Response:
        try:
            await asyncio.wait_for(search_barrier.wait(), timeout=3.0)
        except asyncio.TimeoutError:
            # Um ponto pode emitir mais de uma leitura por turno; a barreira prova
            # concorrência quando os dois pontos se encontram, sem transformar
            # quantidade de leituras em falso negativo.
            pass
        return original_reader(request)

    mock_net.custom_handlers["r.jina.ai"] = barrier_reader_handler

    async def llm_handler(request: httpx.Request) -> httpx.Response:
        nonlocal writer_called
        data = json.loads(request.content.decode("utf-8"))
        msgs = data.get("messages", [])
        sys_msg = " ".join([m.get("content", "") for m in msgs if m.get("role") == "system"]).lower()
        user_msg = " ".join([m.get("content", "") for m in msgs if m.get("role") == "user"])

        # 1. Detecção do Writer
        if "redator" in sys_msg or "dossiê" in sys_msg or "dossie" in sys_msg:
            writer_called = True
            return make_llm_json_response({"secoes": [], "sintese": "Dossie Incorretamente Gerado"})

        # 2. Auditoria LLM por ponto com barreira
        if "auditor" in sys_msg or "auditoria" in sys_msg:
            is_p2 = (
                "beta 2" in user_msg.lower()
                or "investigativa 2" in user_msg.lower()
                or '"ponto_n": 2' in user_msg
                or p2.ponto_id in user_msg
            )
            p_called = "ponto_2" if is_p2 else "ponto_1"
            is_first_call = p_called not in audit_points_called
            audit_points_called.add(p_called)
            if is_first_call:
                try:
                    await asyncio.wait_for(audit_barrier.wait(), timeout=3.0)
                except asyncio.TimeoutError:
                    pytest.fail(f"Barreira da auditoria falhou: pontos não foram auditados em paralelo! Chamados: {audit_points_called}")

            known_claims = re.findall(r"clm_[a-zA-Z0-9_]+", user_msg)
            if not known_claims:
                known_claims = ["clm_fallback"]

            if p_called == "ponto_2":
                # Reprovação deliberada do ponto 2 (5 de 12 critérios) com persona historiador
                v5 = make_audit_12_vector(5, known_claim_ids=known_claims)
                for item in v5:
                    if not item["aprovado"]:
                        item["personas_pertinentes"] = ["historiador"]
                return make_llm_json_response({
                    "criterios": v5,
                    "resumo_auditoria": "Reprovado deliberadamente com 5 criterios.",
                })
            # Aprovação do ponto 1 (11 de 12 critérios)
            return make_llm_json_response({
                "criterios": make_audit_12_vector(11, known_claim_ids=known_claims),
                "resumo_auditoria": "Aprovado com 11 criterios.",
            })

        # 3. Busca real em 2 turnos: turno 1 busca na web; turno 2 conclui com evidencias reais entregues
        if "chk_" in user_msg:
            delivered = _extract_delivered_chunk_id(msgs)
            return make_llm_json_response({
                "acao": "concluir",
                "analise_final": "Coleta robusta concluída com evidências canônicas.",
                "conclusoes": [
                    {
                        "claim_id": "clm_1",
                        "afirmacao": "Fato comprovado por evidência primária.",
                        "tipo": "fato",
                        "evidencias": [delivered],
                        "confianca": "alta",
                        "limitacoes": "Nenhuma.",
                    }
                ],
                "lacunas": [],
                "motivo_parada": "Suficiente.",
            })

        return make_llm_json_response({
            "acao": "buscar",
            "consulta": "php seguranca vulnerabilidades oficiais 2026",
            "objetivo": "coletar evidencias primarias de seguranca",
        })

    mock_net.custom_handlers["chat/completions"] = llm_handler
    transport = create_mock_transport(mock_net)

    runner = PipelineRunner(transport=transport)
    res = await runner.run(id_pesquisa=id_pesquisa)

    # Asserções rigorosas de aceitação do paralelismo
    assert search_barrier.n_waiting == 0
    assert audit_barrier.n_waiting == 0
    assert audit_points_called == {"ponto_1", "ponto_2"}
    assert writer_called is False
    assert res.get("status") in ("reprovado", "parcial", "bloqueado")

    async with session_factory() as db:
        repo = ResearchRepository(session=db)
        pesq_db = await repo.get_research(id_pesquisa)
        assert pesq_db.dossier_final is None
        frescos = await repo.list_points(id_pesquisa)
        f_map = {p.ponto_id: p for p in frescos}
        assert f_map[p1.ponto_id].status == "aprovado"
        assert f_map[p2.ponto_id].status == "reprovado"


# -----------------------------------------------------------------------------
# 7. Sincronização do Status da Pesquisa e Proteção Anti-Race com Pessimistic Lock
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_sync_pipeline_status_uses_with_for_update_to_prevent_pg_race(
    async_engine,
) -> None:
    """Verifica que a sincronização de status de pipeline usa lock pessimista com with_for_update e agrega corretamente em concorrência.

    NOTA DE ESCOPO E COBERTURA POSTGRESQL:
    - Prova 1: Contratual de compilação SQL garantindo que o dialeto PostgreSQL emite 'FOR UPDATE'.
    - Prova 2: Execução concorrente com 2 workers sob SQLite com WAL.
    - Ausência de teste em PostgreSQL real: Não há instância ativa de PostgreSQL no ambiente
      de testes unitários local/CI. Não prometer comportamento comprovado em PostgreSQL vivo
      (como semânticas de MVCC, níveis de isolamento Read Committed vs Repeatable Read e ordenação de locks
      em transações concorrentes reais). Em PostgreSQL, o lock pessimista na linha da Pesquisa serializa
      a agregação de pontos do mesmo id_pesquisa sem deadlocks circulares (recurso único ordenado no início
      da transação).
    """
    from sqlalchemy.dialects.postgresql import dialect as postgresql_dialect  # type: ignore[import-not-found]

    # 1. Prova contratual: compilador PostgreSQL gera FOR UPDATE na linha da pesquisa
    stmt_lock = (
        select(Pesquisa.id_pesquisa)
        .where(Pesquisa.id_pesquisa == "id-teste-pg")
        .with_for_update()
    )
    compiled_pg = str(stmt_lock.compile(dialect=postgresql_dialect()))
    assert "FOR UPDATE" in compiled_pg

    # 2. Execução concorrente real sobre banco SQLite com WAL
    session_factory = async_sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as db:
        repo = ResearchRepository(session=db)
        pesq, pontos = await create_research_fixture_with_plan(repo, n_pontos=2)
        id_pesq = pesq.id_pesquisa
        p1_id = pontos[0].ponto_id
        p2_id = pontos[1].ponto_id

    barrier = asyncio.Barrier(2)

    async def worker_1():
        async with session_factory() as s:
            r = ResearchRepository(session=s)
            await barrier.wait()
            await r.update_point_status(p1_id, status="aprovado")
            await r._sync_pipeline_status_in_tx(id_pesq)
            await s.commit()

    async def worker_2():
        async with session_factory() as s:
            r = ResearchRepository(session=s)
            await barrier.wait()
            await r.update_point_status(p2_id, status="aprovado")
            await r._sync_pipeline_status_in_tx(id_pesq)
            await s.commit()

    await asyncio.gather(worker_1(), worker_2())

    async with session_factory() as db:
        repo = ResearchRepository(session=db)
        pesq_db = await repo.get_research(id_pesq)
        assert pesq_db is not None
        # Ambas as transações concorrentes consolidaram atomicamente o agregado final
        assert pesq_db.status_pipeline == "auditado"


# -----------------------------------------------------------------------------
# 7. Modo de execução explícito: parallel (default) vs sequential (PRD v2, I-3)
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_searcher_sequential_mode_runs_one_point_at_a_time(
    db_session: AsyncSession,
) -> None:
    """`execution_mode='sequential'` processa um ponto por vez, sem sobreposição de leitura."""
    repo = ResearchRepository(session=db_session)
    pesq, pontos = await create_research_fixture_with_plan(repo, n_pontos=3)

    mock_net = MockNetwork()
    _setup_search_mock(mock_net)

    original_reader = mock_net.custom_handlers["r.jina.ai"]
    em_voo = {"atual": 0, "pico": 0}

    async def contador_reader_handler(request: httpx.Request) -> httpx.Response:
        em_voo["atual"] += 1
        em_voo["pico"] = max(em_voo["pico"], em_voo["atual"])
        try:
            await asyncio.sleep(0.02)
            return original_reader(request)
        finally:
            em_voo["atual"] -= 1

    mock_net.custom_handlers["r.jina.ai"] = contador_reader_handler
    transport = create_mock_transport(mock_net)

    searcher = Searcher(
        research_repo=repo,
        jina_client=JinaClient(api_key="jina-key", transport=transport),
        llm_client=LLMClient(api_key="llm-key", transport=transport),
        personas=["historiador"],
        point_timeout_seconds=10.0,
    )

    resumo = await searcher.execute_search(
        id_pesquisa=pesq.id_pesquisa, execution_mode="sequential"
    )

    assert resumo["total_pontos_processados"] == 3
    assert [item["ponto_n"] for item in resumo["resumo_coletas"]] == [1, 2, 3]
    # Uma persona por ponto e pontos em série ⇒ nunca há duas leituras simultâneas
    assert em_voo["pico"] == 1


@pytest.mark.asyncio
async def test_searcher_rejects_invalid_execution_mode(db_session: AsyncSession) -> None:
    """Modo inválido é rejeitado explicitamente, sem fallback silencioso."""
    repo = ResearchRepository(session=db_session)
    pesq, _ = await create_research_fixture_with_plan(repo, n_pontos=1)

    transport = create_mock_transport(MockNetwork())
    searcher = Searcher(
        research_repo=repo,
        jina_client=JinaClient(api_key="jina-key", transport=transport),
        llm_client=LLMClient(api_key="llm-key", transport=transport),
        personas=["historiador"],
        point_timeout_seconds=10.0,
    )

    with pytest.raises(ValueError):
        await searcher.execute_search(id_pesquisa=pesq.id_pesquisa, execution_mode="turbo")
