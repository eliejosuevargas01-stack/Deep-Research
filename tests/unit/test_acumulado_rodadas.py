# -*- coding: utf-8 -*-
"""Acúmulo entre rodadas no modelo v3 (PRD v3, I-5).

Só resumo + catálogo de URLs atravessam rodadas: não há corpo, trecho ou chunk.
"""

import json
from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import writer as writer_module
from app.core.searcher import _recompor_personas
from app.core.writer import Writer, WriterContextOverflow
from app.db.research_repository import ResearchRepository
from app.tools.llm_client import LLMClient
from tests.mocks.http_mock import MockNetwork, create_mock_transport
from tests.unit.test_audit_acceptance import create_research_fixture_with_plan

PERSONAS = ["historiador", "visionario", "cetico", "futurista"]


def _coleta(meta: dict, rodada: int = 1) -> SimpleNamespace:
    return SimpleNamespace(metadados_coleta=json.dumps(meta), rodada=rodada, id=f"col_{rodada}")


def test_rodada_2_preserva_analise_e_claims_da_rodada_1() -> None:
    meta_rodada_1 = {
        "resultados_personas": {
            "historiador": {
                "analise": "Análise integral da rodada 1 sobre o tema.",
                "conclusoes": [
                    {"claim_id": "claim_r1", "afirmacao": "Fato da rodada 1.", "evidencias": ["https://a.org/1"]},
                ],
                "lacunas": ["lacuna da rodada 1"],
                "urls_lidas": ["https://a.org/1"],
                "urls_fonte": ["https://a.org/1"],
                "diario_acoes": [{"acao": "buscar", "query": "rodada 1"}],
                "sucesso": True,
            },
            "cetico": {
                "analise": "Análise do cético na rodada 1.",
                "conclusoes": [],
                "lacunas": [],
                "urls_lidas": ["https://a.org/1"],
                "urls_fonte": ["https://a.org/1"],
                "sucesso": True,
            },
        },
        "diario_acoes": {
            "historiador": [{"acao": "buscar", "query": "rodada 1"}],
            "cetico": [{"acao": "concluir"}],
        },
    }
    resultados_rodada_2 = {
        "historiador": {
            "analise": "Análise complementar produzida na rodada 2.",
            "conclusoes": [
                {"claim_id": "claim_r2", "afirmacao": "Fato novo da rodada 2.", "evidencias": ["https://b.org/2"]},
            ],
            "lacunas": ["lacuna da rodada 2"],
            "urls_lidas": ["https://b.org/2"],
            "urls_fonte": ["https://b.org/2"],
            "diario_acoes": [{"acao": "buscar", "query": "rodada 2"}],
            "sucesso": True,
        },
    }

    recomposed, diarios, _ledgers = _recompor_personas(
        resultados_rodada_2,
        [_coleta(meta_rodada_1)],
        PERSONAS,
        {"historiador": [{"acao": "buscar", "query": "rodada 2"}]},
        {},
    )

    hist = recomposed["historiador"]
    assert "Análise integral da rodada 1" in hist["analise"]
    assert "Análise complementar produzida na rodada 2" in hist["analise"]
    assert {c["claim_id"] for c in hist["conclusoes"]} == {"claim_r1", "claim_r2"}
    assert hist["urls_lidas"] == ["https://a.org/1", "https://b.org/2"]
    assert hist["urls_fonte"] == ["https://a.org/1", "https://b.org/2"]
    assert hist["lacunas"] == ["lacuna da rodada 1", "lacuna da rodada 2"]
    assert len(hist["diario_acoes"]) == 2
    assert [d["query"] for d in diarios["historiador"]] == ["rodada 1", "rodada 2"]

    # persona não reexecutada nesta rodada continua no acumulado
    assert recomposed["cetico"]["analise"] == "Análise do cético na rodada 1."


@pytest.mark.asyncio
async def test_writer_mantem_tres_rodadas_e_estoura_com_erro_explicito(
    db_session: AsyncSession,
) -> None:
    repo = ResearchRepository(session=db_session)
    pesq, pontos = await create_research_fixture_with_plan(repo)
    ponto = pontos[0]

    resumo = ("Resumo denso da rodada com dados, datas e fatos. " * 180)[:8000]
    for rodada in (1, 2, 3):
        url = f"https://example.org/rodada-{rodada}"
        await repo.save_collected_content(
            id_pesquisa=pesq.id_pesquisa,
            ponto_id=ponto.ponto_id,
            tema=pesq.tema,
            ponto=ponto.ponto,
            conteudo_coletado=f"Síntese da rodada {rodada}",
            urls_lidas=[url],
            urls_fonte=[url],
            metadados_coleta={
                "versao": 3,
                "fontes": [{"url": url, "uso": "utilizada", "titulo": f"Fonte {rodada}", "status": "read_ok"}],
                "resultados_personas": {
                    "historiador": {
                        "analise": resumo,
                        "sucesso": True,
                        "lacunas": [],
                        "urls_lidas": [url],
                        "urls_fonte": [url],
                        "conclusoes": [],
                    }
                },
                "diario_acoes": {"historiador": [{"acao": "concluir"}]},
            },
            rodada=rodada,
        )

    coletas = await repo.get_collected_content_for_point(pesq.id_pesquisa, ponto.ponto_id)
    assert [c.rodada for c in coletas] == [1, 2, 3]
    ultima = coletas[-1]
    setattr(ultima, "historico_coletas", coletas)

    writer = Writer(
        research_repo=repo,
        llm_client=LLMClient(api_key="key", transport=create_mock_transport(MockNetwork())),
    )
    contexto, *_ = writer._montar_contexto_estruturado(pesq, [ponto], [ultima], [{}])

    ponto_ctx = contexto["pontos"][0]
    assert [r["rodada"] for r in ponto_ctx["rodadas"]] == [1, 2, 3]
    assert all(r["personas"]["historiador"]["analise"] == resumo for r in ponto_ctx["rodadas"])
    assert "trechos" not in json.dumps(ponto_ctx)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(writer_module, "WRITER_MAX_CONTEXT_CHARS", 1000)
        with pytest.raises(WriterContextOverflow) as exc_info:
            writer._montar_contexto_estruturado(pesq, [ponto], [ultima], [{}])
    assert "WRITER_CONTEXT_OVERFLOW" in str(exc_info.value)
    assert "pontos=[1]" in str(exc_info.value)
