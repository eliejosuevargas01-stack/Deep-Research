# -*- coding: utf-8 -*-
"""Testes de reprodução e regressão para BUG-20261023-XAXC (DR-008).

Alvo: Diferenciar reader_full, snippet_only, cache e URL não lida.
Defeito demonstrado: A descrição da SERP (description) é contabilizada
como página integralmente lida (urls_lidas / total_urls_lidas), mesmo quando
o conteúdo completo (content) não foi obtido do leitor.
"""
import pytest
import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.research_repository import ResearchRepository
from app.tools.llm_client import LLMClient
from app.core.searcher import Searcher
from app.tools.jina_client import JinaClient
from tests.mocks.http_mock import MockNetwork, create_mock_transport
from tests.unit.test_reproduction_gate1_helpers import make_llm_json_response, make_serp_response


@pytest.mark.asyncio
async def test_serp_description_only_does_not_count_as_full_page_read(
    db_session: AsyncSession,
) -> None:
    """[REPRODUÇÃO] Item retornado apenas com snippet/description não pode incrementar total_urls_lidas.
    
    Cenário DR-008 / F-SEARCH-SPEC-01:
    A SERP retorna 3 resultados, mas nenhum possui 'content' integral (apenas 'description').
    O Searcher não pode marcar essas URLs como lidas integralmente (total_urls_lidas deve ser 0).
    A descrição é apenas uma pista preliminar (snippet_only) e não prova de leitura completa.
    """
    mock_net = MockNetwork()
    turn = 0

    def custom_llm_handler(request: httpx.Request) -> httpx.Response:
        nonlocal turn
        turn += 1
        if turn == 1:
            return make_llm_json_response({
                "acao": "buscar",
                "consulta": "pesquisa fontes",
                "objetivo": "buscar fontes preliminares",
            })
        else:
            return make_llm_json_response({
                "acao": "parar_insuficiente",
                "motivo": "Apenas snippets disponíveis, sem leitura integral",
                "lacunas": ["Fontes sem corpo"],
            })

    def custom_jina_handler(request: httpx.Request) -> httpx.Response:
        items = [
            {
                "title": "Documento A",
                "url": "https://fontes.org/doc-a",
                "description": "Snippet descritivo curto do resultado da SERP A",
            },
            {
                "title": "Documento B",
                "url": "https://fontes.org/doc-b",
                "description": "Snippet descritivo curto do resultado da SERP B",
            },
        ]
        return make_serp_response(items)

    def custom_reader_handler(request: httpx.Request) -> httpx.Response:
        # Reader não encontra corpo (retorna vazio)
        return httpx.Response(200, text="", headers={"Content-Type": "text/markdown"})

    mock_net.custom_handlers["chat/completions"] = custom_llm_handler
    mock_net.custom_handlers["s.jina.ai"] = custom_jina_handler
    mock_net.custom_handlers["r.jina.ai"] = custom_reader_handler
    transport = create_mock_transport(mock_net)

    repo = ResearchRepository(session=db_session)
    pesquisa = await repo.create_research(
        tema="Tema Teste Proveniência Snippet",
        pontos_textos=["Ponto 1 para teste de snippet"],
    )

    jina_client = JinaClient(api_key="jina-key", transport=transport)
    llm_client = LLMClient(api_key="openai-key", transport=transport)

    searcher = Searcher(
        research_repo=repo,
        jina_client=jina_client,
        llm_client=llm_client,
        personas=["historiador"],
    )

    resultado = await searcher.execute_search(id_pesquisa=pesquisa.id_pesquisa)
    resumo_ponto = resultado["resumo_coletas"][0]

    assert resumo_ponto["total_urls_lidas"] == 0, (
        f"DEFEITO CONFIRMADO (BUG-20261023-XAXC): {resumo_ponto['total_urls_lidas']} URLs foram "
        "contabilizadas como lidas integralmente, mas todas eram apenas snippets/description."
    )


@pytest.mark.asyncio
async def test_reader_full_content_counts_as_full_read(
    db_session: AsyncSession,
) -> None:
    """[PROTEÇÃO/REGRESSÃO] Item com content integral real é contabilizado em total_urls_lidas."""
    mock_net = MockNetwork()
    turn = 0

    def custom_llm_handler(request: httpx.Request) -> httpx.Response:
        nonlocal turn
        turn += 1
        if turn == 1:
            return make_llm_json_response({
                "acao": "buscar",
                "consulta": "pesquisa fontes",
                "objetivo": "buscar fontes reais",
            })
        else:
            return make_llm_json_response({
                "acao": "concluir",
                "analise_final": "Síntese com base no corpo integral",
                "conclusoes": [],
                "lacunas": [],
                "motivo_parada": "Concluído",
            })

    def custom_jina_handler(request: httpx.Request) -> httpx.Response:
        items = [
            {
                "title": "Documento Real",
                "url": "https://fontes.org/doc-real",
                "description": "Snippet preliminar",
            },
        ]
        return make_serp_response(items)

    def custom_reader_handler(request: httpx.Request) -> httpx.Response:
        # Reader entrega corpo integral
        return httpx.Response(
            200,
            text="# Relatório Oficial Completo\n\nTexto integral da fonte com 500 palavras de dados empíricos...",
            headers={"Content-Type": "text/markdown"},
        )

    mock_net.custom_handlers["chat/completions"] = custom_llm_handler
    mock_net.custom_handlers["s.jina.ai"] = custom_jina_handler
    mock_net.custom_handlers["r.jina.ai"] = custom_reader_handler
    transport = create_mock_transport(mock_net)

    repo = ResearchRepository(session=db_session)
    pesquisa = await repo.create_research(
        tema="Tema Teste Leitura Real",
        pontos_textos=["Ponto com leitura real"],
    )

    jina_client = JinaClient(api_key="jina-key", transport=transport)
    llm_client = LLMClient(api_key="openai-key", transport=transport)

    searcher = Searcher(
        research_repo=repo,
        jina_client=jina_client,
        llm_client=llm_client,
        personas=["historiador"],
    )

    resultado = await searcher.execute_search(id_pesquisa=pesquisa.id_pesquisa)
    resumo_ponto = resultado["resumo_coletas"][0]
    assert resumo_ponto["total_urls_lidas"] == 1
