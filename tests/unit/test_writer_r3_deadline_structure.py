# -*- coding: utf-8 -*-
"""Regressões causais r3 — contratos W07 (deadline TOTAL) e W04 (seções reais do Markdown).

Arquivo NOVO: não altera os 312 casos r1/r2. RED roda sobre o checkout congelado
da R2 (hashes conferidos 77/77 contra writer-unit-evidence-r2.json; snapshot
writer-r2-final-worker-source.tar.gz preserva a base).

- W07: orçamento total de execução (600s default, configurável) deve cobrir
  entrada→prontidão→reserva→loop geração/avaliação→atualização fresca→publicação
  →callback, não apenas o loop LLM. Orçamento integral >=1/2s nos testes
  (lease_seconds=int(timeout_seconds)); nunca aguardar 600s reais. TimeoutError
  TIPADO propaga para a rota (HTTP 504), sem retorno dict nominal 200.
- W04: seções obrigatórias como linhas de cabeçalho Markdown reais (lineno âncora,
  fora de cercas, não-inline/quote) e ao menos uma citação com URL do conjunto
  realmente lido; todas as citadas conhecidas. Sem parser externo/classificador.

Fixture: fase realmente atingida provada com Event + espera limitada; nenhum RED
fabricado por teste/fixture inválidos.
"""

import asyncio
import json
import time

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.writer import Writer, _validar_integridade_artigo
from app.db.models import Pesquisa
from app.db.research_repository import ResearchRepository
from app.services.webhook_client import WebhookClient
from app.tools.llm_client import LLMClient
from tests.mocks.http_mock import MockNetwork, create_mock_transport
from tests.unit.test_reproduction_gate1_helpers import (
    make_llm_json_response,
    make_llm_raw_response,
)
from tests.unit.test_writer_acceptance import (
    SAMPLE_VALID_ARTICLE,
    VALID_CANONICAL_URL,
    make_writer_article_12_eval,
    setup_research_with_audit,
)


ORCAMENTO_TOTAL = 2.0  # segundos, inteiro >=1/2 conforme direção (lease_seconds=int(timeout))
ATRASO_FASE = 3.0  # atraso da fase além do orçamento total


def _session_maker(async_engine: AsyncEngine) -> async_sessionmaker:
    return async_sessionmaker(
        bind=async_engine, class_=AsyncSession, expire_on_commit=False, autoflush=False, autocommit=False
    )


def _handler_artigo_eval(mock_net: MockNetwork) -> None:
    """LLM simulado: artigo válido + avaliação 12/12 (padrão dos testes Writer)."""

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


async def _pesquisa_fresca(async_engine: AsyncEngine, id_pesquisa: str):
    """Leitura em sessão FRESCA, distintos do ciclo do teste (nada de objetos giantes)."""
    maker = _session_maker(async_engine)
    async with maker() as s:
        pesq = (
            await s.execute(
                select(Pesquisa)
                .where(Pesquisa.id_pesquisa == id_pesquisa)
                .execution_options(populate_existing=True)
            )
        ).scalar_one()
        meta = {}
        if pesq.metadados_redacao:
            try:
                meta = json.loads(pesq.metadados_redacao)
            except Exception:
                meta = {}
        return pesq.status_pipeline, pesq.dossier_final, pesq.concluido_em, pesq.webhook_status, meta


async def _contar_ga(repo: ResearchRepository, id_pesquisa: str) -> int:
    return len(await repo.get_generation_attempts(id_pesquisa=id_pesquisa, etapa="write"))


# ==============================================================================
# W07(a): prontidão/pré-reserva além do orçamento TOTAL — sem publicação
# ==============================================================================

@pytest.mark.asyncio
async def test_r3_w07_readiness_delay_beyond_total_budget_blocks_publication(
    db_session: AsyncSession, async_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """W07: prontidão atrasada além do orçamento total deve abortar sem publicar (sem inferência)."""
    repo = ResearchRepository(session=db_session)
    id_pesquisa, _, _ = await setup_research_with_audit(repo=repo)
    pesq_antes = await repo.get_research(id_pesquisa)
    status_antes = pesq_antes.status_pipeline

    ev_fase = asyncio.Event()  # prova: fase de prontidão realmente atingida
    original = Writer._verificar_prontidao
    atraso_disponivel = {"aberto": True}  # UMA única pausa: apenas a 1ª prontidão (a de preparação);
    # _renovar_input_hash chama _verificar_prontidao internamente — atrasar também essa chamada
    # poluiria a janela de publicação e deslocaria a causa observada (lição de fixture da r2).

    async def prontidao_atrasada(self, id_pesquisa: str, pesquisa: Pesquisa):
        if atraso_disponivel["aberto"]:
            atraso_disponivel["aberto"] = False
            ev_fase.set()
            await asyncio.sleep(ATRASO_FASE)  # além do orçamento total (2s)
        return await original(self, id_pesquisa, pesquisa)

    monkeypatch.setattr(Writer, "_verificar_prontidao", prontidao_atrasada)

    mock_net = MockNetwork()
    _handler_artigo_eval(mock_net)
    llm_client = LLMClient(api_key="mock-key", transport=create_mock_transport(mock_net))
    writer = Writer(research_repo=repo, llm_client=llm_client, timeout_seconds=ORCAMENTO_TOTAL)

    inicio = time.monotonic()
    # W07/W12: TimeoutError TIPADO sobe para a rota (HTTP 504); nunca retorno nominal 200.
    with pytest.raises(TimeoutError):
        await writer.execute_writer(id_pesquisa=id_pesquisa)
    decorrido = time.monotonic() - inicio

    # Fase provada e execução limitada pelo deadline total (nunca ~600s).
    assert ev_fase.is_set(), "Fase de prontidão deve ter sido realmente atingida."
    assert decorrido < 10.0, f"Execução deve terminar pelo deadline total (decorrido={decorrido:.2f}s)."

    # Estado do banco não corrompido; nenhum documento publicado; 0 inference.
    status_now, dossier_now, concluido_now, _, _ = await _pesquisa_fresca(async_engine, id_pesquisa)
    assert status_now == status_antes, "Estado do estágio dono da fase não pode ser sobrescrito no timeout pré-reserva."
    assert dossier_now is None and concluido_now is None, "Nenhuma publicação pode ocorrer além do orçamento total."
    assert await _contar_ga(repo, id_pesquisa) == 0, "Nenhuma inferência pode ter ocorrido além do orçamento total."


@pytest.mark.asyncio
async def test_r3_w07_publication_window_delay_blocks_stale_doc_and_preserves_envelopes(
    db_session: AsyncSession, async_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """W07: atraso na atualização fresca/publicação após geração+avaliação não publica documento vencido; 2 envelopes preservados."""
    repo = ResearchRepository(session=db_session)
    id_pesquisa, _, _ = await setup_research_with_audit(repo=repo)

    ev_fase = asyncio.Event()  # prova: fase pós-loop (atualização fresca) realmente atingida
    original = Writer._renovar_input_hash

    async def renovar_atrasada(self, id_pesquisa: str):
        ev_fase.set()
        await asyncio.sleep(ATRASO_FASE)  # além do orçamento total restante
        return await original(self, id_pesquisa)

    monkeypatch.setattr(Writer, "_renovar_input_hash", renovar_atrasada)

    mock_net = MockNetwork()
    _handler_artigo_eval(mock_net)  # geração+avaliação rápidas; o atraso está na fase pós-loop
    llm_client = LLMClient(api_key="mock-key", transport=create_mock_transport(mock_net))
    writer = Writer(research_repo=repo, llm_client=llm_client, timeout_seconds=ORCAMENTO_TOTAL)

    inicio = time.monotonic()
    # W07/W12: TimeoutError TIPADO sobe para a rota (HTTP 504); posse própria liberada e
    # os 2 envelopes concluídos persistidos EXATAMENTE uma vez no caminho único de limpeza.
    with pytest.raises(TimeoutError):
        await writer.execute_writer(id_pesquisa=id_pesquisa)
    decorrido = time.monotonic() - inicio

    assert ev_fase.is_set(), "Fase de publicação/atualização fresca deve ter sido realmente atingida."
    assert decorrido < 10.0, f"Execução deve terminar pelo deadline total (decorrido={decorrido:.2f}s)."

    # Rascunho+avaliação concluídos preservados EXATAMENTE uma vez (2 envelopes), posse própria liberada.
    status_now, dossier_now, concluido_now, _, meta = await _pesquisa_fresca(async_engine, id_pesquisa)
    assert dossier_now is None and concluido_now is None, "Nenhuma publicação além do orçamento."
    assert status_now == "incompleto", "Estado deve refletir conclusão honesta de execução com timeout."
    assert meta.get("lease_token") in (None, []), "Posse própria deve ser liberada após timeout de publicação."
    assert len(meta.get("generation_attempt_ids") or []) == 2, (
        "Os dois envelopes concluídos (1 rascunho + 1 avaliação) devem estar vinculados nos metadados."
    )
    assert await _contar_ga(repo, id_pesquisa) == 2, (
        "Exatamente 2 envelopes (rascunho+avaliação) persistidos uma única vez."
    )


@pytest.mark.asyncio
async def test_r3_w07_callback_timeout_after_publication_preserves_article_and_cache(
    db_session: AsyncSession, async_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """W07: callback lento APÓS publicação confirmada não desfaz artigo válido nem duplica GAs; cache sem novas chamadas/envios e sem entrega inventada."""
    repo = ResearchRepository(session=db_session)
    id_pesquisa, _, _ = await setup_research_with_audit(repo=repo)

    ev_webhook = asyncio.Event()  # prova: callback realmente atingido após publicação
    contador_envios = {"qtd": 0}
    original_send = WebhookClient.send_webhook

    async def send_lento(self, url, payload, id_pesquisa, research_repo=None, **kwargs):
        contador_envios["qtd"] += 1
        ev_webhook.set()
        await asyncio.sleep(ATRASO_FASE)  # callback lento além do restante do orçamento
        return await original_send(self, url=url, payload=payload, id_pesquisa=id_pesquisa, research_repo=research_repo, **kwargs)

    monkeypatch.setattr(WebhookClient, "send_webhook", send_lento)

    mock_net = MockNetwork()
    _handler_artigo_eval(mock_net)
    transport = create_mock_transport(mock_net)
    llm_client = LLMClient(api_key="mock-key", transport=transport)
    webhook_client = WebhookClient(secret="test-sec", transport=transport)
    writer = Writer(
        research_repo=repo,
        llm_client=llm_client,
        webhook_client=webhook_client,
        callback_url="https://webhook.test/callback",
        timeout_seconds=ORCAMENTO_TOTAL,
    )
    inicio = time.monotonic()
    # W07/W12: TimeoutError TIPADO sobe para a rota (HTTP 504) — o artigo publicado NÃO é
    # desfeito e a entrega não observada fica registrada como desconhecida/NULL, nunca 200.
    with pytest.raises(TimeoutError):
        await writer.execute_writer(id_pesquisa=id_pesquisa)
    decorrido = time.monotonic() - inicio

    assert ev_webhook.is_set(), "Callback deve ter sido realmente atingido após a publicação."
    assert decorrido < 10.0, f"Execução deve terminar pelo deadline total (decorrido={decorrido:.2f}s)."

    # Banco: artigo/estado preservados; entrega real-or-desconhecida; GAs exatamente 1x.
    status_now, dossier_now, concluido_now, webhook_status_now, meta = await _pesquisa_fresca(async_engine, id_pesquisa)
    assert status_now == "concluido" and dossier_now == SAMPLE_VALID_ARTICLE and concluido_now is not None, (
        "Documento e estado publicados devem permanecer preservados."
    )
    assert webhook_status_now == "desconhecido", (
        "Entrega NÃO observada (callback cancelado pelo deadline) deve ficar registrada como desconhecida, "
        "nunca entregue (R2 excede o orçamento no callback e registra entregue)."
    )
    assert meta.get("artifact_hash"), "artifact_hash da publicação deve permanecer nos metadados."
    assert meta.get("tentativas_webhook") is None, "tentativas de entrega não observadas devem ficar NULL."
    assert len(meta.get("generation_attempt_ids") or []) == 2, "GAs da publicação permanecem vinculados."
    assert await _contar_ga(repo, id_pesquisa) == 2, "GAs não podem ser duplicados pelo timeout do callback."

    # Contagem real de chamadas LLM congelada após a 1ª execução (2 requisições: rascunho+avaliação)
    reqs_apos_primeira = len(mock_net.requests)
    assert reqs_apos_primeira == 2, "Primeira execução deve ter consumido exatamente 2 chamadas LLM."

    # Cache posterior: artigo válido, 0 inferências/0 reenvios, metadados reais ou desconhecidos.
    res2 = await writer.execute_writer(id_pesquisa=id_pesquisa)
    assert res2.get("status") == "concluido" and res2.get("dossier_final") == SAMPLE_VALID_ARTICLE, (
        "Cache deve retornar o artigo válido publicado."
    )
    entrega2 = res2.get("webhook_entrega") or {}
    assert entrega2.get("status") != "entregue", "Cache não pode inventar entrega."
    assert entrega2.get("tentativas") in (None, 0), "Cache não pode inventar contagem de tentativas."
    assert len(mock_net.requests) == reqs_apos_primeira, "Cache válido não pode gerar novas inferências."
    assert contador_envios["qtd"] == 1, "Cache não pode reenviar webhook."


@pytest.mark.asyncio
async def test_r3_w07_finalize_commit_window_timeout_persists_envelopes_once(
    db_session: AsyncSession, async_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """W07/C: deadline estourando DENTRO do finalize (antes do commit) não pode perder os 2 envelopes
    já observados nem publicar artigo — persistência decidida por estado REALMENTE observado (pós-commit),
    nunca por marcador de intenção; posse própria liberada com EXATAMENTE 2 GAs."""
    repo = ResearchRepository(session=db_session)
    id_pesquisa, _, _ = await setup_research_with_audit(repo=repo)

    ev_fase = asyncio.Event()  # prova: finalize realmente atingido após geração+avaliação
    original_finalize = ResearchRepository.finalize_writer_publication

    async def finalize_lento(self, **kwargs):
        ev_fase.set()
        await asyncio.sleep(ATRASO_FASE)  # deadline estoura ANTES do commit do finalize
        return await original_finalize(self, **kwargs)

    monkeypatch.setattr(ResearchRepository, "finalize_writer_publication", finalize_lento)

    mock_net = MockNetwork()
    _handler_artigo_eval(mock_net)
    llm_client = LLMClient(api_key="mock-key", transport=create_mock_transport(mock_net))
    writer = Writer(research_repo=repo, llm_client=llm_client, timeout_seconds=ORCAMENTO_TOTAL)

    inicio = time.monotonic()
    # TimeoutError TIPADO sobe para a rota (HTTP 504); nenhum artigo é publicado.
    with pytest.raises(TimeoutError):
        await writer.execute_writer(id_pesquisa=id_pesquisa)
    decorrido = time.monotonic() - inicio

    assert ev_fase.is_set(), "Finalize deve ter sido realmente atingido após geração+avaliação."
    assert decorrido < 10.0, f"Execução deve terminar pelo deadline total (decorrido={decorrido:.2f}s)."

    # Limpeza por posse: sem inferir persistência de intenção — os 2 envelopes observados
    # são persistidos EXATAMENTE uma vez na liberação; posse própria liberada sem artigo.
    status_now, dossier_now, concluido_now, _, meta = await _pesquisa_fresca(async_engine, id_pesquisa)
    assert dossier_now is None and concluido_now is None, "Nada pode ser publicado sem commit do finalize."
    assert status_now == "incompleto", "Estado deve refletir a conclusão honesta da limpeza por posse."
    assert meta.get("lease_token") in (None, []), "Posse própria deve ser liberada."
    assert len(meta.get("generation_attempt_ids") or []) == 2, "Os 2 envelopes observados devem constar na liberação."
    assert await _contar_ga(repo, id_pesquisa) == 2, "Persistência dos 2 envelopes EXATAMENTE uma vez (não 0, não 4)."


# ==============================================================================
# W04: seções reais do Markdown + citação conhecida (validação determinística)
# ==============================================================================

def test_r3_w04_rejects_article_flattened_without_real_section_lines() -> None:
    """W04: artigo válido com newlines convertidas em espaços (títulos inline) deve ser rejeitado."""
    achatado = " ".join(linha for linha in SAMPLE_VALID_ARTICLE.splitlines() if linha.strip())
    assert VALID_CANONICAL_URL in achatado, "Fixture da regressão mantém a URL conhecida."
    ok, motivo = _validar_integridade_artigo(
        achatado,
        finish_reason="stop",
        is_regular_finish=True,
        known_urls={VALID_CANONICAL_URL},
    )
    assert ok is False, (
        f"W04: quatro títulos em um parágrafo (sem linhas de cabeçalho Markdown reais) não podem valer "
        f"como seções; validação aceitou (motivo={motivo!r})."
    )


def test_r3_w04_rejects_article_without_known_citation() -> None:
    """W04: quatro seções reais/corpos efetivos sem NENHUMA URL do conjunto lido deve ser rejeitado."""
    sem_urls = SAMPLE_VALID_ARTICLE.replace(VALID_CANONICAL_URL, "")
    assert len(sem_urls.strip()) >= 100, "Fixture continua substantiva sem as URLs."
    ok, motivo = _validar_integridade_artigo(
        sem_urls,
        finish_reason="stop",
        is_regular_finish=True,
        known_urls={VALID_CANONICAL_URL},
    )
    assert ok is False, (
        f"W04: dossiê sem nenhuma citação/referência do conjunto realmente lido deve ser rejeitado; "
        f"validação aceitou (motivo={motivo!r})."
    )


def test_r3_w04_good_case_remains_valid() -> None:
    """W04 (guarda, válida na R2 e na r3): artigo canônico do projeto continua válido."""
    ok, motivo = _validar_integridade_artigo(
        SAMPLE_VALID_ARTICLE,
        finish_reason="stop",
        is_regular_finish=True,
        known_urls={VALID_CANONICAL_URL},
    )
    assert ok is True, f"Caso bom canônico não pode passar a falhar: {motivo!r}"
