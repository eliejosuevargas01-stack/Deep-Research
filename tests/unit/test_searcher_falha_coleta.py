# -*- coding: utf-8 -*-
"""Regressao: falha de coleta nao pode gerar dossie sem evidencia web.

Cobre o incidente real em que saldo insuficiente da Jina (HTTP 402) era
convertido em lista vazia, o loop ReAct seguia para a sintese final e o ponto
era marcado "coletado" com uma analise longa, convincente e sem nenhuma fonte.

Atende RF-03, RF-04, RF-05 e RF-06 da feature 004.
"""
import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.research_repository import ResearchRepository
from tests.mocks.http_mock import MockNetwork, create_mock_transport


def _mock_sem_jina() -> MockNetwork:
    """Rede simulada onde toda busca SERP falha com 402 (saldo insuficiente)."""
    mock_net = MockNetwork()

    async def jina_402(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            402,
            json={
                "code": 402,
                "message": (
                    "Account balance not enough to run this query, "
                    "please recharge."
                ),
            },
        )

    mock_net.custom_handlers["s.jina.ai"] = jina_402
    return mock_net


@pytest.mark.asyncio
async def test_falha_402_marca_ponto_como_falha_coleta(db_session: AsyncSession) -> None:
    """RF-03/CA-03.1 e RF-06/CA-06.1: zero URLs lidas => falha_coleta, nao 'coletado'."""
    from app.core.searcher import Searcher
    from app.tools.jina_client import JinaClient
    from app.tools.llm_client import LLMClient

    mock_net = _mock_sem_jina()
    transport = create_mock_transport(mock_net)

    repo = ResearchRepository(session=db_session)
    pesquisa = await repo.create_research(
        tema="Tema com Provedor Sem Saldo",
        pontos_textos=["Ponto sem evidencia possivel"],
    )
    pontos = await repo.list_points(pesquisa.id_pesquisa)

    jina_client = JinaClient(api_key="jina-key", transport=transport, min_backoff=0.0)
    llm_client = LLMClient(api_key="openai-key", transport=transport)

    searcher = Searcher(
        research_repo=repo,
        jina_client=jina_client,
        llm_client=llm_client,
        personas=["historiador"],
    )
    resultado = await searcher.execute_search(id_pesquisa=pesquisa.id_pesquisa)

    # CA-03.1 + CA-04.4
    assert resultado["total_falhas_coleta"] == 1
    resumo = resultado["resumo_coletas"][0]
    assert resumo["status"] == "falha_coleta"
    assert resumo["falha_coleta"] is True
    assert resumo["total_urls_lidas"] == 0

    # CA-04.1 + CA-04.2: diagnostico com categoria e acao corretiva
    assert "402" in resumo["diagnostico"]
    assert "saldo" in resumo["diagnostico"].lower()

    # CA-06.1 + CA-06.2: status e justificativa persistidos no ponto
    ponto_db = await repo.get_point(pontos[0].ponto_id)
    assert ponto_db is not None
    assert ponto_db.status == "falha_coleta"
    assert "402" in (ponto_db.pontos_fracos or "")


@pytest.mark.asyncio
async def test_nenhuma_sintese_e_chamada_ao_llm_quando_nao_ha_evidencia(
    db_session: AsyncSession,
) -> None:
    """RF-05/CA-05.1 e CA-05.3: sem evidencia, o LLM de sintese nao e chamado."""
    from app.core.searcher import Searcher
    from app.tools.jina_client import JinaClient
    from app.tools.llm_client import LLMClient

    mock_net = _mock_sem_jina()
    transport = create_mock_transport(mock_net)

    repo = ResearchRepository(session=db_session)
    pesquisa = await repo.create_research(
        tema="Tema Sem Evidencia",
        pontos_textos=["Ponto Unico"],
    )
    pontos = await repo.list_points(pesquisa.id_pesquisa)

    # LLM devolve 500: qualquer chamada de sintese falharia alto.
    mock_net.set_llm_status_sequence([500])

    jina_client = JinaClient(api_key="jina-key", transport=transport, min_backoff=0.0)
    llm_client = LLMClient(api_key="openai-key", transport=transport)

    searcher = Searcher(
        research_repo=repo,
        jina_client=jina_client,
        llm_client=llm_client,
        personas=["historiador"],
    )
    resultado = await searcher.execute_search(id_pesquisa=pesquisa.id_pesquisa)

    resumo = resultado["resumo_coletas"][0]
    persona = resumo["personas"][0]

    # CA-05.1: a analise nao passou pelo LLM de sintese
    assert "COLETA FALHOU" in persona["analise"]
    assert persona["falha_coleta"] is True
    assert persona["urls_fonte"] == []
    assert "402" in (persona["diagnostico"] or "")

    # CA-05.3: nenhuma URL lida persistida
    todas = await repo.get_collected_content_for_point(
        pesquisa.id_pesquisa, pontos[0].ponto_id
    )
    assert len(todas) == 1
    assert todas[0].urls_lidas == "[]"


@pytest.mark.asyncio
async def test_falha_de_coleta_nao_apaga_coleta_anterior_com_evidencia(
    db_session: AsyncSession,
) -> None:
    """RF-06/CA-06.3: a rodada falha nao destrui a coleta anterior valida do ponto."""
    from app.core.searcher import Searcher
    from app.tools.jina_client import JinaClient
    from app.tools.llm_client import LLMClient

    mock_net = _mock_sem_jina()
    transport = create_mock_transport(mock_net)

    repo = ResearchRepository(session=db_session)
    pesquisa = await repo.create_research(
        tema="Tema Rodadas",
        pontos_textos=["Ponto com Historico"],
    )
    pontos = await repo.list_points(pesquisa.id_pesquisa)

    # Rodada 1 com evidencia real
    await repo.save_collected_content(
        id_pesquisa=pesquisa.id_pesquisa,
        ponto_id=pontos[0].ponto_id,
        tema=pesquisa.tema,
        ponto=pontos[0].ponto,
        conteudo_coletado="### Perspectiva Historiador\n\nAnalise com fonte real.",
        urls_lidas=["https://unesco.org/estudo"],
        urls_fonte=["https://unesco.org/estudo"],
    )

    jina_client = JinaClient(api_key="jina-key", transport=transport, min_backoff=0.0)
    llm_client = LLMClient(api_key="openai-key", transport=transport)

    searcher = Searcher(
        research_repo=repo,
        jina_client=jina_client,
        llm_client=llm_client,
        personas=["historiador"],
    )
    resultado = await searcher.execute_search(id_pesquisa=pesquisa.id_pesquisa)

    resumo = resultado["resumo_coletas"][0]
    assert resumo["status"] == "falha_coleta"

    historico = await repo.get_collected_content_for_point(
        pesquisa.id_pesquisa, pontos[0].ponto_id
    )
    # CA-06.3: a coleta valida anterior continua la
    assert len(historico) == 2
    assert historico[0].urls_lidas == '["https://unesco.org/estudo"]'


@pytest.mark.asyncio
async def test_texto_extenso_do_llm_nao_mascara_ausencia_de_fonte(
    db_session: AsyncSession,
) -> None:
    """RF-03/CA-03.2: analise longa nao caracteriza coleta; so URL efetiva caracteriza."""
    from app.core.searcher import Searcher
    from app.tools.jina_client import JinaClient
    from app.tools.llm_client import LLMClient

    mock_net = _mock_sem_jina()
    transport = create_mock_transport(mock_net)

    repo = ResearchRepository(session=db_session)
    pesquisa = await repo.create_research(
        tema="Tema Analise Longa Sem Fonte",
        pontos_textos=["Ponto Com Resposta Elegante"],
    )

    jina_client = JinaClient(api_key="jina-key", transport=transport, min_backoff=0.0)
    llm_client = LLMClient(api_key="openai-key", transport=transport)

    searcher = Searcher(
        research_repo=repo,
        jina_client=jina_client,
        llm_client=llm_client,
        personas=["historiador"],
    )
    resultado = await searcher.execute_search(id_pesquisa=pesquisa.id_pesquisa)

    resumo = resultado["resumo_coletas"][0]
    # Conteudo analitico existe (o texto de falha), mas nao ha evidencia
    assert resumo["tamanho_conteudo_caracteres"] > 0
    assert resumo["total_urls_lidas"] == 0
    assert resumo["falha_coleta"] is True
    assert resumo["status"] == "falha_coleta"
