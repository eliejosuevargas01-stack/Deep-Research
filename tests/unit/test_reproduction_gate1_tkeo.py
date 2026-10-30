# -*- coding: utf-8 -*-
"""Testes de reprodução e regressão para BUG-20261023-TKEO (DR-001).

Alvo: Segregar estritamente canais de content e reasoning_content.
Defeito demonstrado: Quando content é null/vazio e reasoning_content contém
texto diagnóstico de raciocínio, o sistema promove esse raciocínio interno a
análise final ou retorno do chat_completion.
"""
import pytest
import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.research_repository import ResearchRepository
from app.tools.llm_client import LLMClient
from app.core.searcher import Searcher
from app.tools.jina_client import JinaClient
from tests.mocks.http_mock import MockNetwork, create_mock_transport
from tests.unit.test_reproduction_gate1_helpers import make_llm_raw_response, make_serp_response


@pytest.mark.asyncio
async def test_searcher_content_null_reasoning_not_promoted_to_analise_final(
    db_session: AsyncSession,
) -> None:
    """[REPRODUÇÃO] Reasoning interno não pode ser promovido a análise_final quando content vier vazio.
    
    Cenário real DR-001 / Ensaio PHP: O modelo executa tool_call para jina_search
    (coletando evidências em raw_evidence_chunks) e na rodada final de resposta analítica
    emite content=None com reasoning_content preenchido com seu raciocínio operacional.
    O comportamento esperado é que reasoning_content NÃO seja promovido a analise_final.
    """
    mock_net = MockNetwork()
    DIAGNOSTIC_REASONING = "Analyzing Critical Vulnerabilities - internal thought"
    turn = 0

    def custom_llm_handler(request: httpx.Request) -> httpx.Response:
        nonlocal turn
        turn += 1
        if turn == 1:
            # Turno 1: persona aciona jina_search
            return make_llm_raw_response(
                tool_calls=[{
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "jina_search",
                        "arguments": '{"query": "falha php vulnerabilidade"}',
                    },
                }],
            )
        else:
            # Turno 2: modelo encerra com content=None e reasoning_content
            return make_llm_raw_response(
                content=None,
                reasoning=DIAGNOSTIC_REASONING,
                tool_calls=None,
            )

    mock_net.custom_handlers["chat/completions"] = custom_llm_handler
    transport = create_mock_transport(mock_net)

    repo = ResearchRepository(session=db_session)
    pesquisa = await repo.create_research(
        tema="Tema Teste Canais",
        pontos_textos=["Ponto 1 para teste de canais"],
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
    persona_res = resultado["resumo_coletas"][0]["personas"][0]

    # ASSERÇÃO DE CONTRATO (FALHA NO CÓDIGO ATUAL):
    # app/core/searcher.py:257 faz:
    # content = msg.get("content") or msg.get("reasoning_content") or ""
    # promovendo DIAGNOSTIC_REASONING a analise_final!
    assert persona_res["analise"] != DIAGNOSTIC_REASONING, (
        "DEFEITO CONFIRMADO (BUG-20261023-TKEO): O Searcher promoveu reasoning_content a analise_final "
        "quando content retornou nulo do modelo."
    )
    assert DIAGNOSTIC_REASONING not in persona_res["analise"]


@pytest.mark.asyncio
async def test_llm_client_chat_completion_does_not_return_reasoning_when_content_null() -> None:
    """[REPRODUÇÃO] LLMClient.chat_completion não pode retornar reasoning_content como content.
    
    Cenário: Rota /chat/completions retorna content=None e reasoning_content='Pensamento interno'.
    O método chat_completion deve retornar string vazia ou lançar erro, mas nunca
    entregar o pensamento interno como se fosse a resposta final do modelo.
    """
    mock_net = MockNetwork()
    INTERNAL_THOUGHT = "Pensamento interno e privado do modelo"

    def custom_llm_handler(request: httpx.Request) -> httpx.Response:
        return make_llm_raw_response(
            content=None,
            reasoning=INTERNAL_THOUGHT,
        )

    mock_net.custom_handlers["chat/completions"] = custom_llm_handler
    transport = create_mock_transport(mock_net)
    client = LLMClient(api_key="openai-key", transport=transport)

    content = await client.chat_completion(
        model="gpt-4o",
        messages=[{"role": "user", "content": "olá"}],
    )

    # ASSERÇÃO DE CONTRATO (FALHA NO CÓDIGO ATUAL):
    # app/tools/llm_client.py:266 faz: content = msg.get("content") or msg.get("reasoning_content")
    assert content != INTERNAL_THOUGHT, (
        "DEFEITO CONFIRMADO (BUG-20261023-TKEO): chat_completion devolveu reasoning_content "
        "ao invés de segregar o canal de resposta."
    )


@pytest.mark.asyncio
async def test_chat_completion_with_content_preserves_valid_content() -> None:
    """[PROTEÇÃO/REGRESSÃO] Resposta normal com content válido é preservada."""
    mock_net = MockNetwork()
    EXPECTED_CONTENT = "Resposta pública legítima da persona"
    THOUGHT = "Pensamento operacional"

    def custom_llm_handler(request: httpx.Request) -> httpx.Response:
        return make_llm_raw_response(
            content=EXPECTED_CONTENT,
            reasoning=THOUGHT,
        )

    mock_net.custom_handlers["chat/completions"] = custom_llm_handler
    transport = create_mock_transport(mock_net)
    client = LLMClient(api_key="openai-key", transport=transport)

    content = await client.chat_completion(
        model="gpt-4o",
        messages=[{"role": "user", "content": "olá"}],
    )
    assert content == EXPECTED_CONTENT
