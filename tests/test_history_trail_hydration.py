"""Trilha das personas reidratada do banco (F5 e clique no histórico)."""

from __future__ import annotations

import json
from types import SimpleNamespace

from app.api.v1.endpoints.research import _busca_persistida, _personas_do_conteudo

CONTEUDO = (
    "## historiador\n\nAchados históricos com fontes.\n\n"
    "## visionario\n\nCenários de 2030 com dois caminhos.\n"
)


def test_personas_do_conteudo_recorta_cada_secao():
    personas = _personas_do_conteudo(CONTEUDO)
    assert [p["persona"] for p in personas] == ["historiador", "visionario"]
    assert personas[0]["analise"].startswith("Achados históricos")
    assert personas[1]["analise"].startswith("Cenários de 2030")


def test_busca_persistida_reconstroi_resumo_coletas():
    coleta = SimpleNamespace(
        ponto_id="p1",
        conteudo_coletado=CONTEUDO,
        urls_lidas=json.dumps(["https://epe.gov.br/a", "https://epe.gov.br/b"]),
        urls_fonte=json.dumps(["https://epe.gov.br/a"]),
        rodada=1,
    )
    ponto = SimpleNamespace(ponto_id="p1", ponto_n=1, status="aprovado")

    busca = _busca_persistida("plan-1-a9f4c21b", [coleta], [ponto])

    assert busca is not None
    resumo = busca["resumo_coletas"][0]
    assert resumo["ponto_n"] == 1
    assert resumo["status"] == "aprovado"
    assert resumo["total_urls_lidas"] == 2
    assert [p["persona"] for p in resumo["personas"]] == ["historiador", "visionario"]


def test_sem_coletas_nao_inventa_busca():
    assert _busca_persistida("plan-1-a9f4c21b", [], []) is None
