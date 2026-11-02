# -*- coding: utf-8 -*-
"""Regressões causais r4 — simplicidade do Writer, telemetria de webhook com dono/arte-fato,
nenhuma transação SQL aberta sobre I/O externo e fechamento do cliente de webhook na rota.

Arquivo NOVO (r4): não altera os casos r1/r2/r3. RED roda sobre a base congelada da R3
(78/78 hashes conferidos contra writer-unit-evidence-r3.json; snapshot
writer-r3-final-worker-source.tar.gz preserva a base).

- B (W10/W11, adendo v6 "Separar validade do artigo e resultado de entrega, preservando o
  retorno real e impedindo gravações tardias sobre nova pesquisa"): o WebhookClient não pode
  gravar webhook_status/webhook_resposta INCONDICIONALMENTE no caminho do Writer. O único
  persistidor do Writer é update_webhook_delivery condicional por artifact_hash. Se outra
  etapa invalidar o artigo durante o HTTP do callback (nova coleta → status 'buscando',
  metadados_redacao/dossier/concluido_em/webhook_* limpos), a resposta 2xx do callback A
  não pode registrar 'entregue' no estado novo sem artefato.
- C (W08, adendo v6 "Não manter transação aberta durante LLM ou webhook"): nenhuma transação
  SQLAlchemy pode permanecer aberta nas fronteiras de I/O externo (chamadas LLM e callback
  webhook), provado com session.in_transaction() nos handlers MockTransport reais.
- D (W12): a rota POST /api/v1/writer deve fechar TAMBÉM o WebhookClient que criou, em
  finally, inclusive no caminho de erro, sem impedir o fechamento do LLMClient.
- A (guardas de simplicidade/canon: sem RED de comportamento inventado): UMA única fronteira
  asyncio.timeout no core do Writer e mensagens definidas UMA única vez pelos builders
  (textos/hash/fingerprint preservados).
"""

import asyncio  # noqa: F401  (contrato assíncrono do Writer; mantém paridade com r3)
import inspect
import json
import re
from typing import Any, Dict, List, Optional
import uuid

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

import app.api.v1.endpoints.writer as writer_endpoint_module
from app.core import writer as writer_core
from app.core.writer import Writer
from app.db.models import Pesquisa
from app.db.research_repository import ResearchRepository
from app.main import app
from app.services.webhook_client import WebhookClient
from app.tools.llm_client import LLMClient
from tests.unit.test_reproduction_gate1_helpers import (
    make_llm_json_response,
    make_llm_raw_response,
)
from tests.unit.test_writer_acceptance import (
    SAMPLE_VALID_ARTICLE,
    make_writer_article_12_eval,
    setup_research_with_audit,
)


URL_CALLBACK = "https://webhook.test/callback"


def _session_maker(async_engine: AsyncEngine) -> async_sessionmaker:
    return async_sessionmaker(
        bind=async_engine, class_=AsyncSession, expire_on_commit=False, autoflush=False, autocommit=False
    )


def _transport_artigo_eval(
    repo: ResearchRepository,
    tx_flags: Optional[List[bool]] = None,
    mensagens_capturadas: Optional[List[Dict[str, Any]]] = None,
) -> httpx.MockTransport:
    """LLM simulado: rascunho válido + avaliação 12/12 (padrão dos testes Writer).

    Quando tx_flags é fornecido, registra session.in_transaction() na fronteira de rede real
    (MockTransport) de CADA chamada — prova causal do estado da sessão durante o I/O.
    """

    def handler(req: httpx.Request) -> httpx.Response:
        if tx_flags is not None:
            tx_flags.append(repo.session.in_transaction())
        body = json.loads(req.content.decode("utf-8"))
        msgs = body.get("messages", [])
        if mensagens_capturadas is not None:
            mensagens_capturadas.append({"messages": msgs, "response_format": body.get("response_format")})
        is_eval = any(
            m.get("role") == "system" and "auditor_redacao" in str(m.get("content", ""))
            for m in msgs
        ) or body.get("response_format", {}).get("type") == "json_object"
        if is_eval:
            return make_llm_json_response(make_writer_article_12_eval(12))
        return make_llm_raw_response(content=SAMPLE_VALID_ARTICLE, finish_reason="stop")

    return httpx.MockTransport(handler)


# ==============================================================================
# B: telemetria de webhook condicionada a dono/arte-fato (nunca incondicional)
# ==============================================================================

@pytest.mark.asyncio
async def test_r4_webhook_telemetry_owned_by_artifact_under_concurrent_invalidation(
    db_session: AsyncSession, async_engine: AsyncEngine
) -> None:
    """B: callback A respondido 2xx após invalidação B (nova coleta) não pode gravar
    'entregue' no estado novo sem artefato; único persistidor é o update condicional."""
    repo = ResearchRepository(session=db_session)
    id_pesquisa, _, _ = await setup_research_with_audit(repo=repo)

    invalidacoes_b = {"qtd": 0}

    async def handler_webhook(req: httpx.Request) -> httpx.Response:
        # Sessão B REAL (SQL própria) invalida o artigo como nova coleta DURANTE o HTTP do callback:
        # status buscando; metadados_redacao/dossier/concluido_em/webhook_status/webhook_resposta limpos.
        maker = _session_maker(async_engine)
        async with maker() as session_b:
            stmt = (
                update(Pesquisa)
                .where(Pesquisa.id_pesquisa == id_pesquisa)
                .values(
                    status_pipeline="buscando",
                    metadados_redacao=None,
                    dossier_final=None,
                    concluido_em=None,
                    webhook_status=None,
                    webhook_resposta=None,
                )
            )
            await session_b.execute(stmt)
            await session_b.commit()
        invalidacoes_b["qtd"] += 1
        return httpx.Response(200, json={"status": "recebido", "evento": "research.completed"})

    webhook_client = WebhookClient(secret="test-sec", transport=httpx.MockTransport(handler_webhook))
    llm_client = LLMClient(api_key="mock-key", transport=_transport_artigo_eval(repo))
    writer = Writer(
        research_repo=repo,
        llm_client=llm_client,
        webhook_client=webhook_client,
        callback_url=URL_CALLBACK,
    )
    try:
        res = await writer.execute_writer(id_pesquisa=id_pesquisa)
    finally:
        await llm_client.aclose()
        await webhook_client.aclose()

    # Sanidade da fixture: execução regular com publicação e callback real (2xx) controlado.
    assert res.get("status") == "concluido", "Artigo deve ter sido publicado regularmente antes do callback."
    assert invalidacoes_b["qtd"] == 1, "Callback A deve ter sido realmente atendido após a invalidação B."

    # Leitura FRESCA (sessão C independente): estado/telemetria da invalidação B permanecem intactos.
    maker = _session_maker(async_engine)
    async with maker() as session_c:
        pesq = (
            await session_c.execute(select(Pesquisa).where(Pesquisa.id_pesquisa == id_pesquisa))
        ).scalar_one()
        assert pesq.status_pipeline == "buscando", "Nova coleta (sessão B) não pode ser sobrescrita pelo Writer."
        assert pesq.dossier_final is None and pesq.concluido_em is None, (
            "Artigo invalidado pela nova coleta não pode ser restaurado pela entrega do callback."
        )
        assert pesq.metadados_redacao is None, "Metadados da nova coleta permanecem limpos (sem artefato)."
        assert pesq.webhook_status is None, (
            "Entrega 2xx do callback A NÃO pode registrar 'entregue' no estado novo sem artefato: "
            f"webhook_status={pesq.webhook_status!r} foi gravado incondicionalmente pelo WebhookClient."
        )
        assert pesq.webhook_resposta is None, "Resposta de entrega não pode ser gravada no estado novo sem artefato."

    async with maker() as session_ga:
        repo_ga = ResearchRepository(session=session_ga)
        gas = await repo_ga.get_generation_attempts(id_pesquisa=id_pesquisa, etapa="write")
        assert len(gas) == 2, f"Exatamente 2 envelopes reais (rascunho+avaliação) persistidos; obtido {len(gas)}."


# ==============================================================================
# C: nenhuma transação SQL aberta durante I/O externo (LLM e webhook)
# ==============================================================================

@pytest.mark.asyncio
async def test_r4_no_open_sql_transaction_during_llm_and_webhook_io(
    db_session: AsyncSession, async_engine: AsyncEngine
) -> None:
    """C: estado REAL da sessão na fronteira de rede — in_transaction() False nas 2 chamadas
    LLM e no callback webhook (reserva sem reabertura de leitura; leitura pós-publicação
    encerrada antes do despacho)."""
    repo = ResearchRepository(session=db_session)
    id_pesquisa, _, _ = await setup_research_with_audit(repo=repo)

    llm_tx: List[bool] = []
    webhook_tx: List[bool] = []

    async def handler_webhook(req: httpx.Request) -> httpx.Response:
        webhook_tx.append(repo.session.in_transaction())
        return httpx.Response(200, json={"status": "recebido", "evento": "research.completed"})

    webhook_client = WebhookClient(secret="test-sec", transport=httpx.MockTransport(handler_webhook))
    llm_client = LLMClient(api_key="mock-key", transport=_transport_artigo_eval(repo, tx_flags=llm_tx))
    writer = Writer(
        research_repo=repo,
        llm_client=llm_client,
        webhook_client=webhook_client,
        callback_url=URL_CALLBACK,
    )
    try:
        res = await writer.execute_writer(id_pesquisa=id_pesquisa)
    finally:
        await llm_client.aclose()
        await webhook_client.aclose()

    # Sanidade da fixture: caminho feliz regular (rascunho + avaliação aprovada + callback).
    assert res.get("status") == "concluido", "Execução regular deve publicar artigo aprovado (12/12)."
    flags_io = {"llm": llm_tx, "webhook": webhook_tx}
    assert len(llm_tx) == 2 and len(webhook_tx) == 1, (
        f"Fronteiras de I/O não atingidas como esperado (2 chamadas LLM + 1 webhook): {flags_io}."
    )
    assert all(flag is False for flag in llm_tx) and webhook_tx[0] is False, (
        f"Transação SQLAlchemy ABERTA durante I/O externo — LLM: {llm_tx}, webhook: {webhook_tx} — "
        "a reserva não pode reabrir leitura após o commit e a leitura da publicação deve ser "
        "encerrada antes do despacho."
    )


# ==============================================================================
# D: rota fecha TAMBÉM o WebhookClient criado (finally, inclusive caminho de erro)
# ==============================================================================

@pytest.mark.asyncio
async def test_r4_route_closes_webhook_client_on_error_path(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D: em erro controlado, a rota preserva 502 e fecha AMBOS os clientes criados
    (LLMClient e WebhookClient) em finally, sem impedir o fechamento do outro."""
    criados: List[Any] = []
    fechados: List[Any] = []
    orig_webhook_aclose = WebhookClient.aclose

    class SpyWebhookClient(WebhookClient):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            criados.append(self)

        async def aclose(self) -> None:
            fechados.append(self)
            return await orig_webhook_aclose(self)

    monkeypatch.setattr(writer_endpoint_module, "WebhookClient", SpyWebhookClient)

    llm_aclose_qtd = {"qtd": 0}
    orig_llm_aclose = LLMClient.aclose

    async def spy_llm_aclose(self: Any) -> None:
        llm_aclose_qtd["qtd"] += 1
        return await orig_llm_aclose(self)

    monkeypatch.setattr(LLMClient, "aclose", spy_llm_aclose)

    async def execute_erro_controlado(self: Any, id_pesquisa: str) -> Dict[str, Any]:
        raise httpx.ConnectError("erro controlado de provedor para caminho de falha da rota")

    monkeypatch.setattr("app.core.writer.Writer.execute_writer", execute_erro_controlado)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/v1/writer", json={"id_pesquisa": str(uuid.uuid4())})

    assert r.status_code == 502, f"Erro controlado deve mapear 502 (mapeamentos preservados); obtido {r.status_code}."
    assert len(criados) == 1, f"A rota deve criar exatamente 1 WebhookClient por requisição; obtido {len(criados)}."
    assert llm_aclose_qtd["qtd"] == 1, "Fechamento do LLMClient deve ser preservado em finally."
    assert len(fechados) >= 1 and fechados[0] is criados[0], (
        f"Rota deve fechar TAMBÉM o WebhookClient criado, inclusive no caminho de erro "
        f"(acloses do webhook observados: {len(fechados)})."
    )


# ==============================================================================
# A (guardas): UMA fronteira de deadline + builders canônicos únicos (hash/fingerprint)
# ==============================================================================

def test_r4_single_timeout_boundary_in_writer_core() -> None:
    """A: UMA única fronteira asyncio.timeout no core do Writer (sem janelas internas redundantes)."""
    fonte = inspect.getsource(writer_core)
    n_fronteiras = len(re.findall(r"async with asyncio\.timeout\(", fonte))
    assert n_fronteiras == 1, (
        f"O core do Writer deve ter EXATAMENTE 1 fronteira asyncio.timeout (entrada); "
        f"encontradas {n_fronteiras} (janelas internas redundantes)."
    )


@pytest.mark.asyncio
async def test_r4_prompts_single_canonical_definition_and_stable_input_hash(
    db_session: AsyncSession, async_engine: AsyncEngine
) -> None:
    """A: mensagens efetivas ao LLM são EXATAMENTE as dos builders (sem literais duplicados
    que sobrescrevem/replugam) e o input_hash da publicação é estável na recomputação fresca."""
    repo = ResearchRepository(session=db_session)
    id_pesquisa, _, _ = await setup_research_with_audit(repo=repo)

    capturas: List[Dict[str, Any]] = []
    llm_client = LLMClient(
        api_key="mock-key", transport=_transport_artigo_eval(repo, mensagens_capturadas=capturas)
    )
    writer = Writer(research_repo=repo, llm_client=llm_client)
    try:
        res = await writer.execute_writer(id_pesquisa=id_pesquisa)
    finally:
        await llm_client.aclose()

    assert res.get("status") == "concluido", "Execução regular para sanidade da fixture (12/12)."
    assert len(capturas) == 2, f"2 chamadas LLM capturadas (rascunho+avaliação); obtido {len(capturas)}."

    # Reconstrução a partir dos builders (definição canônica única) sobre a base persistida
    pesquisa = await repo.get_research(id_pesquisa)
    assert pesquisa is not None
    pontos, coletas, auditorias, _ignorados = await writer._verificar_prontidao(id_pesquisa, pesquisa)
    contexto_dict, *_ = writer._montar_contexto_estruturado(pesquisa, pontos, coletas, auditorias)
    plano_obj = contexto_dict.get("plano", {})
    publico = plano_obj.get("publico") or "Especialistas e tomadores de decisão"
    formato = plano_obj.get("formato_entrega") or "Dossiê analítico com citações canônicas"

    msgs_rascunho = capturas[0]["messages"]
    assert msgs_rascunho[0]["content"] == writer._construir_system_prompt(publico, formato), (
        "System prompt do rascunho deve vir do builder canônico (público/formato preservados)."
    )
    assert msgs_rascunho[1]["content"] == writer._construir_user_prompt(pesquisa, contexto_dict), (
        "User prompt do rascunho deve vir do builder canônico (texto/hash/fingerprint preservados)."
    )
    msgs_eval = capturas[1]["messages"]
    assert msgs_eval[0]["content"] == writer._construir_prompt_avaliacao(), (
        "System prompt da avaliação deve vir do builder canônico (12 critérios, sem literal duplicado)."
    )

    # input_hash persistido na publicação é estável na recomputação fresca (fingerprint único)
    meta = {}
    if pesquisa.metadados_redacao:
        meta = json.loads(pesquisa.metadados_redacao) if isinstance(pesquisa.metadados_redacao, str) else pesquisa.metadados_redacao
    hash_persistido = meta.get("input_hash")
    assert hash_persistido, "Publicação deve registrar input_hash nos metadados."
    hash_fresco = await writer._renovar_input_hash(id_pesquisa)
    assert hash_fresco == hash_persistido, (
        "Recomputação fresca (builders canônicos) deve reproduzir exatamente o input_hash da publicação."
    )
