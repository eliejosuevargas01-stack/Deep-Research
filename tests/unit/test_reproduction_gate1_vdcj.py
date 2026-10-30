# -*- coding: utf-8 -*-
"""Testes de reprodução e regressão para BUG-20261023-VDCJ (DR-004, DR-012).

Alvo: Estados verdadeiros para pontos e pesquisa (truthful state).
Defeito demonstrado:
1. Falha de 3 das 4 personas é mascarada: o ponto é marcado como 'coletado'
   integralmente caso uma única persona tenha lido alguma URL.
2. O status agregado 'status_pesquisa' retorna literalmente 'coletado'
   mesmo quando todos os pontos ou parte deles falharam.
"""
import json
import re
from typing import Any, Dict, List
import pytest
import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.research_repository import ResearchRepository
from app.tools.llm_client import LLMClient
from app.core.searcher import Searcher
from app.tools.jina_client import JinaClient
from tests.mocks.http_mock import MockNetwork, create_mock_transport
from tests.unit.test_reproduction_gate1_helpers import make_llm_json_response, make_llm_raw_response, make_serp_response


def _extract_chunk_id(msgs: List[Dict[str, Any]]) -> str:
    user_msgs = [m.get("content", "") for m in msgs if m.get("role") == "user"]
    last_user_msg = user_msgs[-1] if user_msgs else ""
    matches = re.findall(r"\[Trecho ID:\s*(chk_[a-zA-Z0-9_\-]+)\]", last_user_msg)
    if not matches:
        matches = [c for c in re.findall(r"chk_[a-zA-Z0-9_\-]+", last_user_msg) if c != "chk_id"]
    return matches[0] if matches else "chk_default"


@pytest.mark.asyncio
async def test_three_of_four_personas_failing_produces_partial_point_status(
    db_session: AsyncSession,
) -> None:
    """[REPRODUÇÃO] Três de quatro personas falhando deve produzir estado parcial, não 'coletado'.
    
    Cenário DR-004 / F-SEARCH-CONC-01:
    Em um ponto investigativo executado com as 4 personas (historiador, visionario, cetico, futurista),
    3 personas falham (sem resultados ou erro) e apenas 1 persona consegue ler fontes.
    O ponto não pode ser marcado como integralmente 'coletado': seu status deve ser 'parcial'
    ou 'coleta_parcial' para não mascarar a incompletude da investigação.
    """
    mock_net = MockNetwork()
    turn_by_persona = {}

    def custom_llm_handler(request: httpx.Request) -> httpx.Response:
        data = json.loads(request.content.decode("utf-8"))
        msgs = data.get("messages", [])
        content_req = str(msgs).lower()
        persona = "desconhecido"
        for p in ["historiador", "visionario", "cetico", "futurista"]:
            if p in content_req:
                persona = p
                break
        
        turn = turn_by_persona.get(persona, 0) + 1
        turn_by_persona[persona] = turn

        if persona == "historiador":
            if turn == 1:
                return make_llm_json_response({
                    "acao": "buscar",
                    "consulta": "historia",
                    "objetivo": "buscar documentos históricos",
                })
            else:
                chk_id = _extract_chunk_id(msgs)
                return make_llm_json_response({
                    "acao": "concluir",
                    "analise_final": "Síntese do Historiador com fontes e rigor metodológico.",
                    "conclusoes": [{
                        "claim_id": "c1",
                        "afirmacao": "Fato histórico confirmado.",
                        "tipo": "fato",
                        "evidencias": [chk_id],
                        "confianca": "alta",
                        "limitacoes": "",
                    }],
                    "lacunas": [],
                    "motivo_parada": "Concluído",
                })
        else:
            # As outras 3 personas encerram com parada insuficiente
            return make_llm_json_response({
                "acao": "parar_insuficiente",
                "motivo": "Sem fontes para esta perspectiva",
                "lacunas": ["Fontes ausentes"],
            })

    def custom_jina_handler(request: httpx.Request) -> httpx.Response:
        items = [
            {
                "title": "Fonte Historiador",
                "url": "https://historia.org/doc",
                "description": "Snippet histórico",
            }
        ]
        return make_serp_response(items)

    def custom_reader_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text="# Documento histórico real\nTexto completo da fonte com evidências documentadas.",
            headers={"Content-Type": "text/markdown"},
        )

    mock_net.custom_handlers["chat/completions"] = custom_llm_handler
    mock_net.custom_handlers["s.jina.ai"] = custom_jina_handler
    mock_net.custom_handlers["r.jina.ai"] = custom_reader_handler
    transport = create_mock_transport(mock_net)

    repo = ResearchRepository(session=db_session)
    pesquisa = await repo.create_research(
        tema="Tema Teste Estado Parcial",
        pontos_textos=["Ponto com 3 personas falhando"],
    )

    jina_client = JinaClient(api_key="jina-key", transport=transport)
    llm_client = LLMClient(api_key="openai-key", transport=transport)

    searcher = Searcher(
        research_repo=repo,
        jina_client=jina_client,
        llm_client=llm_client,
        personas=["historiador", "visionario", "cetico", "futurista"],
    )

    resultado = await searcher.execute_search(id_pesquisa=pesquisa.id_pesquisa)
    ponto_resumo = resultado["resumo_coletas"][0]

    assert ponto_resumo["status"] in ("parcial", "coleta_parcial"), (
        f"DEFEITO CONFIRMADO (BUG-20261023-VDCJ): Ponto com 3 de 4 personas falhando foi marcado "
        f"literalmente como '{ponto_resumo['status']}' em vez de 'parcial'/'coleta_parcial'."
    )


@pytest.mark.asyncio
async def test_all_points_failing_produces_falha_status_pesquisa(
    db_session: AsyncSession,
) -> None:
    """[REPRODUÇÃO] Quando todos os pontos falham, status_pesquisa não pode ser 'coletado'.
    
    Cenário DR-004 / F-SEARCH-CONC-02:
    Todos os pontos da pesquisa sofrem falha de coleta (zero URLs lidas).
    O resultado agregado do endpoint devolve status_pesquisa='coletado'.
    O comportamento esperado é status_pesquisa='falha' ou 'falha_coleta'.
    """
    mock_net = MockNetwork()

    # Toda chamada Jina falha com erro 402/500
    mock_net.custom_handlers["s.jina.ai"] = lambda r: httpx.Response(402, json={"code": 402, "message": "Sem saldo"})
    mock_net.custom_handlers["chat/completions"] = lambda r: make_llm_raw_response(content=None)
    transport = create_mock_transport(mock_net)

    repo = ResearchRepository(session=db_session)
    pesquisa = await repo.create_research(
        tema="Tema Teste Falha Total",
        pontos_textos=["Ponto Falho 1", "Ponto Falho 2"],
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

    assert resultado["status_pesquisa"] in ("falha", "falha_coleta"), (
        f"DEFEITO CONFIRMADO (BUG-20261023-VDCJ): Pesquisa com 100% de pontos falhados retornou "
        f"status_pesquisa='{resultado['status_pesquisa']}' em vez de 'falha'."
    )


@pytest.mark.asyncio
async def test_partial_points_failing_produces_parcial_status_pesquisa(
    db_session: AsyncSession,
) -> None:
    """[REPRODUÇÃO] Quando parte dos pontos falha, status_pesquisa deve ser 'parcial'."""
    mock_net = MockNetwork()
    turn_by_persona = {}

    def custom_llm_handler(request: httpx.Request) -> httpx.Response:
        data = json.loads(request.content.decode("utf-8"))
        msgs = data.get("messages", [])
        content_req = str(msgs).lower()
        if "ponto de sucesso" in content_req:
            persona = "desconhecido"
            for p in ["historiador", "visionario", "cetico", "futurista"]:
                if p in content_req:
                    persona = p
                    break
            t = turn_by_persona.get(persona, 0) + 1
            turn_by_persona[persona] = t
            if t == 1:
                return make_llm_json_response({
                    "acao": "buscar",
                    "consulta": f"busca {persona}",
                    "objetivo": "buscar evidências",
                })
            else:
                chk_id = _extract_chunk_id(msgs)
                return make_llm_json_response({
                    "acao": "concluir",
                    "analise_final": f"Síntese válida da persona {persona} com fontes e evidências comprovadas.",
                    "conclusoes": [{
                        "claim_id": "c1",
                        "afirmacao": "Fato comprovado.",
                        "tipo": "fato",
                        "evidencias": [chk_id],
                        "confianca": "alta",
                        "limitacoes": "",
                    }],
                    "lacunas": [],
                    "motivo_parada": "Concluído",
                })
        # Ponto de falha
        return make_llm_json_response({
            "acao": "parar_insuficiente",
            "motivo": "Sem fontes no ponto de falha",
            "lacunas": ["Fontes ausentes"],
        })

    def custom_jina_handler(request: httpx.Request) -> httpx.Response:
        return make_serp_response([{"title": "Doc", "url": "https://ok.com/doc", "description": "Snippet"}])

    def custom_reader_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="# Texto Real\nCorpo integral da página.", headers={"Content-Type": "text/markdown"})

    mock_net.custom_handlers["chat/completions"] = custom_llm_handler
    mock_net.custom_handlers["s.jina.ai"] = custom_jina_handler
    mock_net.custom_handlers["r.jina.ai"] = custom_reader_handler
    transport = create_mock_transport(mock_net)

    repo = ResearchRepository(session=db_session)
    pesquisa = await repo.create_research(
        tema="Tema Teste Parcial",
        pontos_textos=["Ponto de Sucesso", "Ponto de Falha"],
    )

    jina_client = JinaClient(api_key="jina-key", transport=transport)
    llm_client = LLMClient(api_key="openai-key", transport=transport)

    searcher = Searcher(
        research_repo=repo,
        jina_client=jina_client,
        llm_client=llm_client,
        personas=["historiador", "visionario", "cetico", "futurista"],
    )

    resultado = await searcher.execute_search(id_pesquisa=pesquisa.id_pesquisa)

    assert resultado["status_pesquisa"] == "parcial", (
        f"DEFEITO CONFIRMADO (BUG-20261023-VDCJ): Pesquisa com falha parcial retornou "
        f"status_pesquisa='{resultado['status_pesquisa']}' em vez de 'parcial'."
    )


@pytest.mark.asyncio
async def test_all_points_succeeding_produces_coletado(
    db_session: AsyncSession,
) -> None:
    """[PROTEÇÃO/REGRESSÃO] Quando todos os pontos têm sucesso pleno, status_pesquisa é 'coletado'."""
    mock_net = MockNetwork()
    turn_by_persona = {}

    def custom_llm_handler(request: httpx.Request) -> httpx.Response:
        data = json.loads(request.content.decode("utf-8"))
        msgs = data.get("messages", [])
        content_req = str(msgs).lower()
        persona = "desconhecido"
        for p in ["historiador", "visionario", "cetico", "futurista"]:
            if p in content_req:
                persona = p
                break
        t = turn_by_persona.get(persona, 0) + 1
        turn_by_persona[persona] = t

        if t % 2 == 1:
            return make_llm_json_response({
                "acao": "buscar",
                "consulta": f"busca {persona}",
                "objetivo": "buscar fontes",
            })
        else:
            chk_id = _extract_chunk_id(msgs)
            return make_llm_json_response({
                "acao": "concluir",
                "analise_final": f"Síntese com sucesso da persona {persona} com evidências sólidas.",
                "conclusoes": [{
                    "claim_id": "c1",
                    "afirmacao": "Fato comprovado.",
                    "tipo": "fato",
                    "evidencias": [chk_id],
                    "confianca": "alta",
                    "limitacoes": "",
                }],
                "lacunas": [],
                "motivo_parada": "Concluído",
            })

    def custom_jina_handler(request: httpx.Request) -> httpx.Response:
        return make_serp_response([{"title": "Doc", "url": "https://ok.com/doc", "description": "Snippet"}])

    def custom_reader_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="# Texto Real\nCorpo integral da fonte.", headers={"Content-Type": "text/markdown"})

    mock_net.custom_handlers["chat/completions"] = custom_llm_handler
    mock_net.custom_handlers["s.jina.ai"] = custom_jina_handler
    mock_net.custom_handlers["r.jina.ai"] = custom_reader_handler
    transport = create_mock_transport(mock_net)

    repo = ResearchRepository(session=db_session)
    pesquisa = await repo.create_research(
        tema="Tema Teste Pleno",
        pontos_textos=["Ponto 1", "Ponto 2"],
    )

    jina_client = JinaClient(api_key="jina-key", transport=transport)
    llm_client = LLMClient(api_key="openai-key", transport=transport)

    searcher = Searcher(
        research_repo=repo,
        jina_client=jina_client,
        llm_client=llm_client,
        personas=["historiador", "visionario", "cetico", "futurista"],
    )

    resultado = await searcher.execute_search(id_pesquisa=pesquisa.id_pesquisa)
    assert resultado["status_pesquisa"] == "coletado"
