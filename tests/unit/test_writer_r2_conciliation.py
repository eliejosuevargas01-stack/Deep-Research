# -*- coding: utf-8 -*-
"""Regressões causais r2 da conciliação Writer (F01/F02/F03 — H01/H02/H03).

Arquivo NOVO: não altera os 309 casos r1. Provas RED rodam sobre o checkout
inalterado da r1 (hashes de app/ conferidos 76/76 contra writer-unit-evidence-r1.json
e writer-r2-fixture-gate-capture.json). A execução inicial deste arquivo travou por
defeitos de FIXTURE (diagnóstico preservado em writer-r2-fixture-gate-capture.json):
vela de instrumentação corrigidas aqui — a pausa do H01 atinge apenas o primeiro
UPDATE da reserva A (cleanups subsequentes fluem normais), a assinatura do wrapper
do H02 aceita id_pesquisa, e a asserção adulta do H03 prova ausência de ORDEM
INCONDICIONAL (a política condicional pode mencionar criança sem forçá-la).

- F01/H01 (W08): cleanup de posse que infere dono por horário não pode liberar
  a posse legítima de B; liberar exclusivamente o tokenA local com CAS.
- F02/H02 (W10/W12): Runner não pode regravar status do Writer sobre um novo
  ciclo Search/Audit na janela pós-Writer/pre-condicional.
- F03/H03 (W03): ordem de exposição do público derivada do pedido/plano em
  linguagem natural (entrada REAL 'Criança de 5 anos...'), com política
  condicional; adulto não é forçado a registro infantil.
"""

import asyncio
import json

import httpx
import pytest
from sqlalchemy import Update, select
from sqlalchemy import update as sql_update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.pipeline_runner import PipelineRunner
from app.core.writer import Writer
from app.db.models import Pesquisa
from app.db.research_repository import ResearchRepository
from app.tools.llm_client import LLMClient
from tests.mocks.http_mock import MockNetwork, create_mock_transport
from tests.unit.test_reproduction_gate1_helpers import (
    make_llm_json_response,
    make_llm_raw_response,
)
from tests.unit.test_writer_acceptance import (
    CANONICAL_PLANO,
    SAMPLE_VALID_ARTICLE,
    make_writer_article_12_eval,
    setup_research_with_audit,
)


@pytest.mark.asyncio
async def test_r2_cancelled_reserve_never_releases_other_owner_lease(
    db_session: AsyncSession, async_engine: AsyncEngine
) -> None:
    """F01/H01: cancelamento da reserva A pausada ANTES do UPDATE não pode liberar a posse legítima de B."""
    repo = ResearchRepository(session=db_session)
    id_pesquisa, _, _ = await setup_research_with_audit(repo=repo)

    maker = async_sessionmaker(
        bind=async_engine, class_=AsyncSession, expire_on_commit=False, autoflush=False, autocommit=False
    )
    s_a = maker()
    s_b = maker()
    repo_a = ResearchRepository(session=s_a)
    repo_b = ResearchRepository(session=s_b)

    ev_a_pause = asyncio.Event()  # sinaliza: A passou pelo precheck e pausou antes do UPDATE

    orig_exec_a = s_a.execute
    pausa_disponivel = {"aberta": True}  # UMA única pausa: apenas o PRIMEIRO UPDATE (o da reserva A)

    async def pausa_antes_do_update(stmt, *a, **kw):
        # Pausa a sessão A SOMENTE no primeiro UPDATE (reserva A); updates posteriores de
        # cleanup/liberação executam normalmente, revelando o comportamento real do código.
        if pausa_disponivel["aberta"] and isinstance(stmt, Update):
            pausa_disponivel["aberta"] = False
            ev_a_pause.set()
            # A fica suspensa indefinidamente aqui; o teste a cancela nesse ponto.
            await asyncio.Event().wait()
        return await orig_exec_a(stmt, *a, **kw)

    s_a.execute = pausa_antes_do_update

    task_a = asyncio.create_task(
        repo_a.reserve_research_for_writer(id_pesquisa=id_pesquisa, lease_seconds=600)
    )
    await asyncio.wait_for(ev_a_pause.wait(), timeout=10.0)

    # B adquire a posse legitimamente enquanto A está suspensa antes de gravar qualquer coisa.
    token_b, _ = await repo_b.reserve_research_for_writer(id_pesquisa=id_pesquisa, lease_seconds=600)

    # A é cancelada no próprio ponto de pausa (não gravou e não concluiu a aquisição);
    # espera limitada: fixture travada aparece como TimeoutError, nunca como hang silencioso.
    cancel_ok = {"cancelled": False}
    task_a.cancel()
    try:
        await asyncio.wait_for(asyncio.shield(task_a), timeout=10.0)
    except asyncio.CancelledError:
        cancel_ok["cancelled"] = True
    except asyncio.TimeoutError:
        pytest.fail("Fixture travada: task_a não concluiu em 10s após cancel() (timeout de fixture, não RED).")
    assert cancel_ok["cancelled"], "Reserva A deveria propagar CancelledError."

    s_check = maker()
    try:
        pesq = (
            await s_check.execute(
                select(Pesquisa)
                .where(Pesquisa.id_pesquisa == id_pesquisa)
                .execution_options(populate_existing=True)
            )
        ).scalar_one()
        meta = json.loads(pesq.metadados_redacao or "{}")
        assert meta.get("lease_token") == token_b, (
            f"Lease de B foi clobberada pelo cleanup de A (lease_token={meta.get('lease_token')!r} "
            f"em vez de {token_b!r}) — inferência de dono por horário liberou posse alheia (F01/H01)."
        )
        assert meta.get("status") == "redigindo", "Estado de redação de B deve permanecer intacto."
    finally:
        await s_check.close()
        await s_a.close()
        await s_b.close()


@pytest.mark.asyncio
async def test_r2_runner_keeps_new_stage_status_after_writer_window(
    db_session: AsyncSession, async_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """F02/H02: Runner não pode regravar o status do Writer sobre um novo ciclo Search/Audit."""
    repo = ResearchRepository(session=db_session)
    id_pesquisa, _, _ = await setup_research_with_audit(repo=repo)

    mock_net = MockNetwork()

    def handler(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content.decode("utf-8"))
        msgs = body.get("messages", [])
        is_eval = any(
            m.get("role") == "system" and "auditor_redacao" in str(m.get("content", ""))
            for m in msgs
        ) or body.get("response_format", {}).get("type") == "json_object"
        if is_eval:
            return make_llm_json_response(make_writer_article_12_eval(12))
        return make_llm_raw_response(content=SAMPLE_VALID_ARTICLE, finish_reason="stop")

    mock_net.custom_handlers["chat/completions"] = handler

    # Isola Search/Audit: todos os pontos já aprovados; auditoria declara pronto na 1ª rodada.
    async def spy_search(self, id_pesquisa, ponto_id, personas=None):
        return {"status": "coletado"}

    async def spy_audit(self, id_pesquisa):
        return {"pronto_para_writer": True, "auditorias": []}

    monkeypatch.setattr("app.core.searcher.Searcher.execute_search", spy_search)
    monkeypatch.setattr("app.core.auditor.Auditor.execute_audit", spy_audit)

    # Writer REAL executa e publica; na JANELA pós-Writer/pre-Runner, um novo ciclo
    # (Search/Audit) reserva/escreve estado NOVO: apaga metadados, dossier final,
    # concluido_em do Writer e muda o status_pipeline para o estágio dele ("buscando").
    real_writer = Writer.execute_writer
    janela = {"executada": False}

    async def writer_com_janela(self2, id_pesquisa: str, **kwargs):  # assinatura compatível com o Runner
        res = await real_writer(self2, id_pesquisa=id_pesquisa)
        assert res.get("status") == "concluido", "Writer real deve publicar antes da janela."
        s_new = async_sessionmaker(
            bind=async_engine, class_=AsyncSession, expire_on_commit=False, autoflush=False, autocommit=False
        )()
        try:
            await s_new.execute(
                sql_update(Pesquisa)
                .where(Pesquisa.id_pesquisa == id_pesquisa)
                .values(
                    metadados_redacao=None,
                    dossier_final=None,
                    concluido_em=None,
                    status_pipeline="buscando",
                )
            )
            await s_new.commit()
        finally:
            await s_new.close()
        janela["executada"] = True
        return res

    monkeypatch.setattr(Writer, "execute_writer", writer_com_janela)

    runner = PipelineRunner(transport=create_mock_transport(mock_net))
    res = await runner.run(id_pesquisa=id_pesquisa)

    assert janela["executada"] is True, "Janela pós-Writer deve ter sido executada."
    # Retorno honesto do Writer (nunca fallback concluido no retorno).
    assert res.get("status") == "concluido"

    s_check = async_sessionmaker(
        bind=async_engine, class_=AsyncSession, expire_on_commit=False, autoflush=False, autocommit=False
    )()
    try:
        pesq = (
            await s_check.execute(
                select(Pesquisa)
                .where(Pesquisa.id_pesquisa == id_pesquisa)
                .execution_options(populate_existing=True)
            )
        ).scalar_one()
    finally:
        await s_check.close()

    assert pesq.status_pipeline == "buscando", (
        f"Runner regravou status do Writer ('concluido') sobre o estado novo do estágio "
        f"concorrente: status_pipeline={pesq.status_pipeline!r} (F02/H02)."
    )
    assert pesq.dossier_final is None, "Documento apagado pelo novo ciclo deve permanecer apagado."
    assert pesq.metadados_redacao is None, "Metadados apagados pelo novo ciclo devem permanecer apagados."


@pytest.mark.asyncio
async def test_r2_child_order_from_real_plan_and_adult_not_forced(
    db_session: AsyncSession,
) -> None:
    """F03/H03: ordem de exposição derivada do pedido/plano REAL; adulto não recebe ordem INCONDICIONAL infantil."""
    PUBLICO_REAL = "Criança de 5 anos (linguagem lúdica, analógica e sem jargões técnicos para a explicação final)"
    formato_real = "Explicação simples com analogias e apêndice técnico"

    # ---- Caso REAL (e2e): plano com o público real do pedido, sem a palavra 'infantil' ----
    mock_net = MockNetwork()
    generation_messages: list = []

    def handler(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content.decode("utf-8"))
        msgs = body.get("messages", [])
        is_eval = any(
            m.get("role") == "system" and "auditor_redacao" in str(m.get("content", ""))
            for m in msgs
        ) or body.get("response_format", {}).get("type") == "json_object"
        if is_eval:
            return make_llm_json_response(make_writer_article_12_eval(12))
        generation_messages.extend(msgs)
        return make_llm_raw_response(content=SAMPLE_VALID_ARTICLE, finish_reason="stop")

    mock_net.custom_handlers["chat/completions"] = handler
    transport = create_mock_transport(mock_net)
    llm_client = LLMClient(api_key="mock-key", transport=transport)
    repo = ResearchRepository(session=db_session)

    plano_real = dict(CANONICAL_PLANO)
    plano_real["publico"] = PUBLICO_REAL
    plano_real["formato_entrega"] = formato_real

    id_pesquisa, _, _ = await setup_research_with_audit(repo=repo, plano_override=plano_real)

    writer = Writer(research_repo=repo, llm_client=llm_client)
    await writer.execute_writer(id_pesquisa=id_pesquisa)

    gen_prompt = " ".join(m.get("content", "") for m in generation_messages).lower()
    assert PUBLICO_REAL.lower() in gen_prompt, "Declaração REAL do público do pedido deve chegar verbatim ao redator."
    assert (
        "a explicação vem primeiro" in gen_prompt or "a explicação vem em primeiro" in gen_prompt
    ), "Ordem de exposição à criança (derivada do pedido/plano real, sem depender da palavra 'infantil') deve constar no prompt (F03/H03)."

    # ---- Controle adulto (builder direto): política condicional; SEM ordem incondicional de infantil ----
    class _SemEstado:  # _construir_system_prompt não usa self
        pass

    sys_adulto = Writer._construir_system_prompt(
        _SemEstado(), "Especialistas e tomadores de decisão", "Dossiê analítico com citações canônicas"
    )
    adulto_lower = sys_adulto.lower()
    # Política condicional pode mencionar criança SEM forçar: prova de ausência de ordem INCONDICIONAL.
    assert "explicação em primeiro plano" not in adulto_lower, (
        "Público adulto não pode receber ordem INCONDICIONAL de exposição infantil (o condicional do pedido é quem decide)."
    )
    assert "abra sempre com explicação infantil" not in adulto_lower, (
        "Público adulto não pode receber mandato incondicional de registro infantil."
    )
    assert "Sumário Executivo" in sys_adulto, "Estrutura formal padrão permanece para o caso adulto."
