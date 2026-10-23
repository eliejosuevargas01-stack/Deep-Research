# -*- coding: utf-8 -*-
"""Testes de diagnóstico e isolamento da ferramenta Jina e respostas enviadas ao modelo.

Valida:
1. Normalização de base_url com ou sem schema (s.jina.ai -> https://s.jina.ai).
2. Resolução de base_url a partir do campo base_url da credencial JINA_API_KEY.
3. Envio correto da resposta de tool para o LLM quando a busca retorna vazia (sem mentir que URLs já foram lidas).
4. Envio de mensagem de erro explícita no role: "tool" quando a tool Jina falha.
5. Inclusão da diretriz de tratamento de falha no prompt da persona.
"""

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.searcher import Searcher, TOOLS_DEFINITIONS
from app.db.credentials_repository import CredentialsRepository
from app.db.research_repository import ResearchRepository
from app.services.credential_resolver import resolve_jina_base_url
from app.tools.errors import JinaError
from app.tools.jina_client import JinaClient, _normalize_base_url
from app.tools.llm_client import LLMClient
from tests.mocks.http_mock import MockNetwork, create_mock_transport


def test_normalize_base_url() -> None:
    """Verifica normalização automática de URLs com e sem schema."""
    assert _normalize_base_url("s.jina.ai", "https://s.jina.ai") == "https://s.jina.ai"
    assert _normalize_base_url("https://custom.jina.ai/", "https://s.jina.ai") == "https://custom.jina.ai"
    assert _normalize_base_url("http://localhost:8000/", "https://s.jina.ai") == "http://localhost:8000"
    assert _normalize_base_url(None, "https://s.jina.ai") == "https://s.jina.ai"
    assert _normalize_base_url("", "https://s.jina.ai") == "https://s.jina.ai"


@pytest.mark.asyncio
async def test_resolve_jina_base_url_from_credential_record(db_session: AsyncSession) -> None:
    """Verifica que resolve_jina_base_url extrai o campo base_url do registro JINA_API_KEY quando não há chave isolada."""
    repo = CredentialsRepository(session=db_session)
    await repo.save_credential(
        chave="JINA_API_KEY",
        valor="test-key-12345",
        tipo="jina",
        base_url="https://proxy.jina.local",
    )

    resolved = await resolve_jina_base_url(db=db_session)
    assert resolved == "https://proxy.jina.local"


@pytest.mark.asyncio
async def test_searcher_prompt_contains_explicit_failure_instruction(
    db_session: AsyncSession,
) -> None:
    """Verifica que o prompt agêntico possui diretriz explícita para falhas de ferramenta."""
    repo = ResearchRepository(session=db_session)
    pesquisa = await repo.create_research(
        tema="Tema Teste Prompt",
        pontos_textos=["Ponto Teste"],
    )
    pontos = await repo.list_points(pesquisa.id_pesquisa)

    mock_net = MockNetwork()
    transport = create_mock_transport(mock_net)
    jina_client = JinaClient(api_key="jina-test", transport=transport)
    llm_client = LLMClient(api_key="openai-test", transport=transport)

    searcher = Searcher(
        research_repo=repo,
        jina_client=jina_client,
        llm_client=llm_client,
        personas=["historiador"],
    )

    # Executa a busca
    await searcher.execute_search(pesquisa.id_pesquisa)

    # Obtém as mensagens geradas para a persona na memória
    memoria_persona = searcher.memoria[f"{pesquisa.id_pesquisa}:{pontos[0].ponto_id}"]["historiador"]
    system_msg = memoria_persona["messages"][0]["content"]

    assert "RESPOSTA EXPLÍCITA EM CASO DE FALHA OU AUSÊNCIA DE CONTEÚDO" in system_msg
    assert "É ESTRITAMENTE PROIBIDO inventar fatos" in system_msg


@pytest.mark.asyncio
async def test_searcher_tool_response_on_empty_results(db_session: AsyncSession) -> None:
    """Verifica que busca vazia (0 resultados) não mente que URLs foram lidas anteriormente."""
    repo = ResearchRepository(session=db_session)
    pesquisa = await repo.create_research(
        tema="Tema Busca Vazia",
        pontos_textos=["Ponto Vazio"],
    )
    pontos = await repo.list_points(pesquisa.id_pesquisa)

    mock_net = MockNetwork()
    # Simula Jina retornando lista vazia
    async def jina_empty(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"code": 200, "data": []})

    mock_net.custom_handlers["s.jina.ai"] = jina_empty
    transport = create_mock_transport(mock_net)

    jina_client = JinaClient(api_key="jina-test", transport=transport)
    llm_client = LLMClient(api_key="openai-test", transport=transport)

    searcher = Searcher(
        research_repo=repo,
        jina_client=jina_client,
        llm_client=llm_client,
        personas=["historiador"],
    )

    await searcher.execute_search(pesquisa.id_pesquisa)

    memoria_persona = searcher.memoria[f"{pesquisa.id_pesquisa}:{pontos[0].ponto_id}"]["historiador"]
    msgs = memoria_persona["messages"]

    # Localiza mensagem do tipo tool
    tool_msgs = [m for m in msgs if m.get("role") == "tool"]
    assert len(tool_msgs) > 0
    # Mensagem deve informar que não retornou nenhuma URL, e NÃO dizer que já foram lidas
    assert "não retornou nenhuma URL ou resultado" in tool_msgs[0]["content"]
    assert "já foram lidas anteriormente" not in tool_msgs[0]["content"]


@pytest.mark.asyncio
async def test_searcher_tool_response_on_tool_failure(db_session: AsyncSession) -> None:
    """Verifica que quando a tool Jina falha (ex: 402), a mensagem com erro explícito é enviada como role: tool."""
    repo = ResearchRepository(session=db_session)
    pesquisa = await repo.create_research(
        tema="Tema Erro Tool",
        pontos_textos=["Ponto Falha"],
    )
    pontos = await repo.list_points(pesquisa.id_pesquisa)

    mock_net = MockNetwork()
    async def jina_402(request: httpx.Request) -> httpx.Response:
        return httpx.Response(402, json={"code": 402, "message": "Account balance not enough, please recharge."})

    mock_net.custom_handlers["s.jina.ai"] = jina_402
    transport = create_mock_transport(mock_net)

    jina_client = JinaClient(api_key="jina-test", transport=transport, min_backoff=0.0)
    llm_client = LLMClient(api_key="openai-test", transport=transport)

    searcher = Searcher(
        research_repo=repo,
        jina_client=jina_client,
        llm_client=llm_client,
        personas=["historiador"],
    )

    res = await searcher.execute_search(pesquisa.id_pesquisa)
    assert res["resumo_coletas"][0]["falha_coleta"] is True

    memoria_persona = searcher.memoria[f"{pesquisa.id_pesquisa}:{pontos[0].ponto_id}"]["historiador"]
    msgs = memoria_persona["messages"]

    # Mensagem de tool presente com erro explícito
    tool_msgs = [m for m in msgs if m.get("role") == "tool"]
    assert len(tool_msgs) == 1
    assert "ERRO NA FERRAMENTA jina_search" in tool_msgs[0]["content"]
    assert "402" in tool_msgs[0]["content"] or "saldo" in tool_msgs[0]["content"].lower()
