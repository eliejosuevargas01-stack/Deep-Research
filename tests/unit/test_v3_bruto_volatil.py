"""PRD v3: bruto da Jina é volátil; só resumo e catálogo de URLs persistem.

Cobre (a) projeção persistida sem body/trechos/chunk_id, (b) acúmulo do resumo
quando a persona é reexecutada, (c) auditoria aprovando com evidência que só
existe no resumo da rodada 1 e (d) writer recebendo 3 rodadas sem corte.
"""

import json
from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auditor import Auditor
from app.core.searcher import _catalogo_de_urls, _fontes_da_persona, _recompor_personas
from app.core.writer import Writer
from app.db.research_repository import ResearchRepository
from app.tools.llm_client import LLMClient
from tests.mocks.http_mock import MockNetwork, create_mock_transport
from tests.unit.test_audit_acceptance import (
    create_research_fixture_with_plan,
    make_audit_12_vector,
)
from tests.unit.test_reproduction_gate1_helpers import make_llm_json_response

PERSONAS = ["historiador", "visionario", "cetico", "futurista"]


def _fonte(url: str, uso: str = "utilizada") -> dict:
    return {"url": url, "uso": uso, "titulo": f"Fonte {url}", "data_fonte": None, "status": "read_ok"}


def _meta_v3(urls_fonte: list[str], urls_lidas: list[str], analise: str = "Resumo denso.") -> dict:
    fontes = [_fonte(u) for u in dict.fromkeys(urls_fonte)]
    fontes += [_fonte(u, "lida_nao_utilizada") for u in urls_lidas if u not in urls_fonte]
    personas = {}
    for p in PERSONAS:
        personas[p] = {
            "analise": f"{analise} Persona {p}.",
            "sucesso": True,
            "lacunas": [],
            "urls_fonte": list(urls_fonte),
            "urls_lidas": list(dict.fromkeys(urls_lidas + urls_fonte)),
            "conclusoes": [],
        }
    return {
        "versao": 3,
        "fontes": fontes,
        "resultados_personas": personas,
        "diario_acoes": {p: [{"acao": "concluir"}] for p in PERSONAS},
        "recencia": {"data_mais_recente_fonte": None},
    }


def test_metadados_persistidos_nao_tem_body_trechos_chunk_id() -> None:
    """Catálogo projetado para persistência só carrega URL/uso/título/status."""
    url = "https://exemplo.org/pagina"
    ponto_sources = {
        url: {
            "url": url,
            "status": "read_ok",
            "titulo": "Página",
            "data_fonte": None,
            "body": "TEXTO BRUTO DA JINA QUE NÃO PODE SER PERSISTIDO",
        }
    }
    personas = [{"urls_fonte": [url], "urls_lidas": [url]}]
    catalogo = _catalogo_de_urls(ponto_sources, personas)
    fontes_persona = _fontes_da_persona([url], [url], catalogo)

    serializado = json.dumps({"fontes": catalogo, "personas": fontes_persona})
    for proibido in ("body", "trechos", "chunk_id", "body_hash", "start_offset"):
        assert proibido not in serializado
    assert catalogo[url]["uso"] == "utilizada"
    # O bruto continua apenas em RAM, no registro original.
    assert ponto_sources[url]["body"].startswith("TEXTO BRUTO")


def test_persona_reexecutada_acumula_resumo_da_rodada_1() -> None:
    meta_r1 = {
        "resultados_personas": {
            "historiador": {
                "analise": "Resumo da rodada 1.",
                "conclusoes": [{"claim_id": "c1", "afirmacao": "Fato 1", "evidencias": ["https://a.org/1"]}],
                "lacunas": ["lacuna 1"],
                "urls_lidas": ["https://a.org/1"],
                "urls_fonte": ["https://a.org/1"],
                "sucesso": True,
            }
        }
    }
    rodada2 = {
        "historiador": {
            "analise": "Resumo da rodada 2.",
            "conclusoes": [{"claim_id": "c2", "afirmacao": "Fato 2", "evidencias": ["https://b.org/2"]}],
            "lacunas": [],
            "urls_lidas": ["https://b.org/2"],
            "urls_fonte": ["https://b.org/2"],
            "sucesso": True,
        }
    }
    coleta_r1 = SimpleNamespace(id="col1", rodada=1, metadados_coleta=json.dumps(meta_r1))

    recomposed, _, _ = _recompor_personas(rodada2, [coleta_r1], PERSONAS, {}, {})

    hist = recomposed["historiador"]
    assert "Resumo da rodada 1." in hist["analise"]
    assert "Resumo da rodada 2." in hist["analise"]
    assert {c["claim_id"] for c in hist["conclusoes"]} == {"c1", "c2"}
    assert hist["urls_fonte"] == ["https://a.org/1", "https://b.org/2"]


@pytest.mark.asyncio
async def test_auditor_aprova_com_evidencia_so_no_resumo_da_rodada_1(
    db_session: AsyncSession,
) -> None:
    repo = ResearchRepository(session=db_session)
    pesq, pontos = await create_research_fixture_with_plan(repo)
    ponto = pontos[0]
    url_r1 = "https://a.org/rodada-1"
    url_r2 = "https://b.org/rodada-2"

    meta_r1 = _meta_v3([url_r1], [url_r1], "Resumo da rodada 1.")
    for p in PERSONAS:
        meta_r1["resultados_personas"][p]["conclusoes"] = [
            {"claim_id": f"c_{p}", "afirmacao": f"Fato da rodada 1 ({p})", "evidencias": [url_r1]}
        ]
    await repo.save_collected_content(
        id_pesquisa=pesq.id_pesquisa,
        ponto_id=ponto.ponto_id,
        tema=pesq.tema,
        ponto=ponto.ponto,
        conteudo_coletado="Síntese da rodada 1",
        urls_lidas=[url_r1],
        urls_fonte=[url_r1],
        metadados_coleta=meta_r1,
        rodada=1,
    )
    await repo.save_collected_content(
        id_pesquisa=pesq.id_pesquisa,
        ponto_id=ponto.ponto_id,
        tema=pesq.tema,
        ponto=ponto.ponto,
        conteudo_coletado="Síntese da rodada 2",
        urls_lidas=[url_r2],
        urls_fonte=[url_r2],
        metadados_coleta=_meta_v3([url_r2], [url_r2], "Resumo da rodada 2."),
        rodada=2,
    )

    mock_net = MockNetwork()
    mock_net.custom_handlers["chat/completions"] = lambda r: make_llm_json_response({
        "criterios": make_audit_12_vector(
            12,
            known_claim_ids=[f"c_{p}" for p in PERSONAS],
            known_source_ids=[url_r1, url_r2],
        ),
    })
    auditor = Auditor(
        research_repo=repo,
        llm_client=LLMClient(api_key="key", transport=create_mock_transport(mock_net)),
    )

    res = await auditor.execute_audit(id_pesquisa=pesq.id_pesquisa)
    item = res["auditorias"][0]
    assert item["status"] == "aprovado"
    payload = json.loads(mock_net.requests[0].content.decode("utf-8"))
    user_msgs = [m["content"] for m in payload.get("messages", []) if m.get("role") == "user"]
    texto = user_msgs[-1]
    assert "Resumo da rodada 1." in texto
    assert '"trechos"' not in texto and '"chunk_id"' not in texto


@pytest.mark.asyncio
async def test_writer_recebe_tres_rodadas_de_resumos_sem_corte(
    db_session: AsyncSession,
) -> None:
    repo = ResearchRepository(session=db_session)
    pesq, pontos = await create_research_fixture_with_plan(repo)
    ponto = pontos[0]

    analise_longa = "Resumo denso e completo da rodada. " * 2500
    for rodada in (1, 2, 3):
        url = f"https://exemplo.org/rodada-{rodada}"
        await repo.save_collected_content(
            id_pesquisa=pesq.id_pesquisa,
            ponto_id=ponto.ponto_id,
            tema=pesq.tema,
            ponto=ponto.ponto,
            conteudo_coletado=f"Síntese da rodada {rodada}",
            urls_lidas=[url],
            urls_fonte=[url],
            metadados_coleta=_meta_v3([url], [url], analise_longa),
            rodada=rodada,
        )

    coletas = await repo.get_collected_content_for_point(pesq.id_pesquisa, ponto.ponto_id)
    ultima = coletas[-1]
    setattr(ultima, "historico_coletas", coletas)

    writer = Writer(
        research_repo=repo,
        llm_client=LLMClient(api_key="key", transport=create_mock_transport(MockNetwork())),
    )
    contexto, *_ = writer._montar_contexto_estruturado(pesq, [ponto], [ultima], [{}])

    ponto_ctx = contexto["pontos"][0]
    assert len(ponto_ctx["rodadas"]) == 3
    assert [r["rodada"] for r in ponto_ctx["rodadas"]] == [1, 2, 3]
    assert ponto_ctx["rodadas"][0]["personas"]["historiador"]["analise"] == (
        f"{analise_longa} Persona historiador."
    )
    assert "trechos" not in json.dumps(ponto_ctx)
    assert len(ponto_ctx["urls_utilizadas"]) == 3
