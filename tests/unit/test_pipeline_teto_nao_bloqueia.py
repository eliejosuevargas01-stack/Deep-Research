"""Teto de auditoria consumido nunca bloqueia o relatório (PRD v3, RF-006-D)."""

import json

import pytest
import httpx
from sqlalchemy import update

from app.core.pipeline_runner import PipelineRunner
from app.db.models import ConteudoColetado, Ponto
from app.db.research_repository import ResearchRepository
from tests.mocks.http_mock import MockNetwork, create_mock_transport
from tests.unit.test_points_parallelism_acceptance import (
    CANONICAL_EIXO,
    CANONICAL_PLANO,
    _setup_search_mock,
)
from tests.unit.test_writer_acceptance import make_llm_json_response


@pytest.mark.asyncio
async def test_teto_de_auditoria_consumido_vai_para_redacao(async_engine, db_session) -> None:
    repo = ResearchRepository(session=db_session)
    eixos = [{**CANONICAL_EIXO, "ponto_n": 1}]
    pesq = await repo.create_research(
        tema="Segurança do PHP 2026",
        pontos_textos=["Ponto Alfa 1"],
        plano_estruturado=CANONICAL_PLANO,
        eixos_estruturados=eixos,
        metadados_planejamento={"preferencias": {"personas": ["historiador"]}},
    )
    id_pesquisa = pesq.id_pesquisa
    await db_session.execute(
        update(Ponto)
        .where(Ponto.id_pesquisa == id_pesquisa)
        .values(tentativas=4, tentativas_auditoria=3, status="coletado")
    )
    await db_session.commit()
    pontos = await repo.list_points(id_pesquisa)
    ponto_id = pontos[0].ponto_id
    db_session.add(ConteudoColetado(
        id="col-teto-1",
        id_pesquisa=id_pesquisa,
        ponto_id=ponto_id,
        rodada=1,
        tema=pesq.tema,
        ponto="Ponto Alfa 1",
        conteudo_coletado="Evidência coletada sobre segurança do PHP em 2026.",
        urls_lidas=json.dumps(["https://example.org/php-seguranca"]),
        urls_fonte=json.dumps(["https://example.org/php-seguranca"]),
        metadados_coleta=json.dumps({
            "versao": 3,
            "resultados_personas": {
                "historiador": {
                    "analise": "Resumo denso da coleta.",
                    "conclusoes": ["PHP mantém suporte ativo em 2026."],
                    "urls_fonte": ["https://example.org/php-seguranca"],
                    "urls_lidas": ["https://example.org/php-seguranca"],
                    "sucesso": True,
                }
            },
            "fontes": [{
                "url": "https://example.org/php-seguranca",
                "status": "read_ok",
                "uso": "utilizada",
                "titulo": "Segurança do PHP",
            }],
            "auditorias": [{
                "valido": True, "aplicado": True, "status": "reprovado",
                "pontuacao_percentual": 41.67, "criterios_aprovados": 5,
            }],
        }),
        criado_em="2026-11-02T16:00:00Z",
    ))
    await db_session.commit()

    mock_net = MockNetwork()
    _setup_search_mock(mock_net)
    estado = {"audit": 0, "writer": 0}

    async def llm_handler(request: httpx.Request) -> httpx.Response:
        data = json.loads(request.content.decode("utf-8"))
        msgs = data.get("messages", [])
        sys_msg = " ".join(m.get("content", "") for m in msgs if m.get("role") == "system").lower()
        if "redator" in sys_msg or "dossi" in sys_msg:
            estado["writer"] += 1
            return make_llm_json_response({"secoes": [], "sintese": "Dossiê com ressalvas"})
        if "auditor" in sys_msg:
            estado["audit"] += 1
            raise AssertionError("Auditoria não deveria ser chamada com teto consumido")
        return make_llm_json_response({"acao": "concluir", "analise_final": "ok", "urls_fonte": []})

    mock_net.custom_handlers["chat/completions"] = llm_handler
    runner = PipelineRunner(transport=create_mock_transport(mock_net))
    res = await runner.run(id_pesquisa=id_pesquisa)

    assert estado["audit"] == 0, "Auditoria deve ser ignorada quando o teto já foi consumido"
    assert estado["writer"] >= 1, "Writer deve ser chamado com ressalvas"
    assert res.get("status") in ("incompleto", "concluido")
