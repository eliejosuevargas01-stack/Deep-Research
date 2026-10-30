# -*- coding: utf-8 -*-
"""Regressão do bug "0 URLs lidas" (investigação b2c898ff, tema "maria corina machado").

Causas raiz cobertas aqui:

1. O Reader ignorava o proxy configurado: `JinaClient(base_url=<worker>)` continuava
   lendo em `r.jina.ai`, enviando a credencial do proxy para a Jina real → 401 em
   toda leitura, logo `urls_lidas=[]` e auditoria reprovando.
2. O limite por leitura era um `wait_for(..., timeout=10.0)` fixo, menor que o
   timeout do cliente (20s) e que o deadline do proxy (18s) → toda página real
   estourava em 10s.
3. A falha de leitura era engolida (`except Exception: return None`), deixando o
   diário de ações sem qualquer diagnóstico do motivo.
"""

import asyncio
import json
from typing import Any, Dict

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.searcher import Searcher
from app.db.research_repository import ResearchRepository
from app.tools.jina_client import JinaClient
from app.tools.llm_client import LLMClient
from tests.mocks.http_mock import MockNetwork, create_mock_transport
from tests.unit.test_audit_acceptance import create_research_fixture_with_plan
from tests.unit.test_reproduction_gate1_helpers import (
    make_llm_json_response,
    make_serp_response,
)


def test_reader_uses_proxy_base_when_search_base_is_a_proxy() -> None:
    """Credencial de proxy não pode vazar para r.jina.ai: Reader segue o proxy."""
    client = JinaClient(api_key="proxy-client-key", base_url="https://worker.exemplo.workers.dev")
    assert client.search_base_url == "https://worker.exemplo.workers.dev"
    assert client.reader_base_url == "https://worker.exemplo.workers.dev"


def test_reader_keeps_canonical_host_for_direct_jina() -> None:
    """Sem proxy, o Reader continua em r.jina.ai (contrato original preservado)."""
    client = JinaClient(api_key="jina-key", base_url="https://s.jina.ai")
    assert client.reader_base_url == "https://r.jina.ai"


def test_client_timeout_default_covers_proxy_deadline() -> None:
    """O timeout do cliente precisa cobrir o deadline do proxy (era 20s fixos)."""
    client = JinaClient(api_key="jina-key")
    assert client.timeout >= 40.0


@pytest.mark.asyncio
async def test_searcher_default_reader_timeout_is_45s(db_session: AsyncSession) -> None:
    repo = ResearchRepository(session=db_session)
    searcher = Searcher(
        research_repo=repo,
        jina_client=JinaClient(api_key="jina-key", transport=create_mock_transport(MockNetwork())),
        llm_client=LLMClient(api_key="llm-key", transport=create_mock_transport(MockNetwork())),
        personas=["historiador"],
    )
    assert searcher.reader_timeout_seconds == 45.0


@pytest.mark.asyncio
async def test_reader_failure_is_recorded_in_diario_com_motivo(db_session: AsyncSession) -> None:
    """Leitura que estoura registra `erros_reader` com o motivo, em vez de sumir."""
    repo = ResearchRepository(session=db_session)
    pesq, pontos = await create_research_fixture_with_plan(repo, n_pontos=1)

    mock_net = MockNetwork()
    turnos: Dict[str, int] = {}

    def llm_handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8"))
        sys_msg = payload["messages"][0]["content"]
        persona = "historiador"
        turnos[persona] = turnos.get(persona, 0) + 1
        if turnos[persona] == 1:
            return make_llm_json_response({
                "acao": "buscar",
                "consulta": "maria corina machado nobel 2025",
                "objetivo": "Obter fonte primária do Nobel",
            })
        return make_llm_json_response({
            "acao": "concluir",
            "analise_final": "Sem evidência web suficiente para concluir com segurança.",
            "conclusoes": [],
            "lacunas": ["fonte primária"],
            "motivo_parada": "Leituras falharam.",
        })

    def serp_handler(request: httpx.Request) -> httpx.Response:
        return make_serp_response([{
            "url": "https://www.nobelprize.org/prizes/peace/2025/machado/facts/",
            "title": "The Nobel Peace Prize 2025",
            "description": "Maria Corina Machado awarded the 2025 Nobel Peace Prize.",
        }])

    async def reader_lento(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(2.0)
        return httpx.Response(200, text="corpo", headers={"Content-Type": "text/markdown"})

    mock_net.custom_handlers["chat/completions"] = llm_handler
    mock_net.custom_handlers["s.jina.ai"] = serp_handler
    mock_net.custom_handlers["r.jina.ai"] = reader_lento
    transport = create_mock_transport(mock_net)

    searcher = Searcher(
        research_repo=repo,
        jina_client=JinaClient(api_key="jina-key", transport=transport),
        llm_client=LLMClient(api_key="llm-key", transport=transport),
        personas=["historiador"],
        point_timeout_seconds=30.0,
        # piso de 1.0s no __init__: timeout efetivo de 1s < 2s de latência do mock
        reader_timeout_seconds=0.5,
    )

    resumo = await searcher.execute_search(id_pesquisa=pesq.id_pesquisa)
    assert resumo["total_pontos_processados"] == 1

    coletas = await repo.get_collected_content_for_point(pesq.id_pesquisa, pontos[0].ponto_id)
    assert coletas, "Coleta deve ter sido persistida"
    metadados: Dict[str, Any] = json.loads(coletas[-1].metadados_coleta)
    acoes = metadados["diario_acoes"]["historiador"]
    busca = next(a for a in acoes if a["acao"] == "buscar")

    assert busca["urls_lidas"] == []
    assert busca["erros_reader"], "Falha de leitura deve ser diagnosticada, não silenciada"
    assert "timeout" in busca["erros_reader"][0]["erro"].lower()
    assert busca["erros_reader"][0]["url"].startswith("https://www.nobelprize.org/")
