# -*- coding: utf-8 -*-
"""Acúmulo integral do histórico entre rodadas (PRD v2, I-5; RF-004-C; RF-005-A; RF-006-A).

Cobre os três pontos de perda de histórico em retry:
(a) searcher: persona reexecutada soma a rodada nova à análise/claims/URLs anteriores;
(b) auditor: claim da rodada 1 continua válido depois do retry da rodada 2;
(c) writer: todas as rodadas entram integrais e o estouro do limite vira erro explícito.
"""

import json
from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import writer as writer_module
from app.core.auditor import Auditor, _agregar_metadados_coletas
from app.core.searcher import _recompor_personas
from app.core.writer import Writer, WriterContextOverflow
from app.db.research_repository import ResearchRepository
from app.tools.llm_client import LLMClient
from tests.mocks.http_mock import MockNetwork, create_mock_transport
from tests.unit.test_audit_acceptance import (
    create_research_fixture_with_plan,
    make_audit_12_vector,
    make_chunk_data,
    make_persona_result,
    make_source_data,
    make_standard_coleta_metadata,
)
from tests.unit.test_reproduction_gate1_helpers import make_llm_json_response

PERSONAS = ["historiador", "visionario", "cetico", "futurista"]


def _coleta(meta: dict, rodada: int = 1) -> SimpleNamespace:
    return SimpleNamespace(metadados_coleta=json.dumps(meta), rodada=rodada, id=f"col_{rodada}")


# ==============================================================================
# (a) Searcher: rodada 2 preserva a análise da rodada 1 na persona reexecutada
# ==============================================================================

def test_rodada_2_preserva_analise_e_claims_da_rodada_1() -> None:
    meta_rodada_1 = {
        "resultados_personas": {
            "historiador": {
                "analise": "Análise integral da rodada 1 sobre o tema.",
                "conclusoes": [
                    {"claim_id": "claim_r1", "afirmacao": "Fato da rodada 1.", "evidencias": ["chk_1"]},
                ],
                "lacunas": ["lacuna da rodada 1"],
                "urls_lidas": ["https://a.org/1"],
                "urls_fonte": ["https://a.org/1"],
                "diario_acoes": [{"acao": "buscar", "query": "rodada 1"}],
                "sucesso": True,
            },
            "cetico": {
                "analise": "Análise do cético na rodada 1.",
                "conclusoes": [{"claim_id": "claim_cetico", "afirmacao": "Ressalva.", "evidencias": ["chk_1"]}],
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
        "selecao_contexto": {"cetico": {"selected_chunk_ids": ["chk_1"]}},
    }
    resultados_rodada_2 = {
        "historiador": {
            "analise": "Análise complementar produzida na rodada 2.",
            "conclusoes": [
                {"claim_id": "claim_r2", "afirmacao": "Fato novo da rodada 2.", "evidencias": ["chk_2"]},
            ],
            "lacunas": ["lacuna da rodada 2"],
            "urls_lidas": ["https://b.org/2"],
            "urls_fonte": ["https://b.org/2"],
            "diario_acoes": [{"acao": "buscar", "query": "rodada 2"}],
            "sucesso": True,
        },
    }

    recomposed, diarios, ledgers = _recompor_personas(
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

    # persona não reexecutada nesta rodada continua no acumulado, com diário/ledger
    assert recomposed["cetico"]["analise"] == "Análise do cético na rodada 1."
    assert diarios["cetico"] == [{"acao": "concluir"}]
    assert ledgers["cetico"] == {"selected_chunk_ids": ["chk_1"]}


# ==============================================================================
# (b) Auditor: claim que cita chunk da rodada 1 é aceito após retry
# ==============================================================================

def _meta_rodada_2(url: str) -> dict:
    body = (
        "Relatório complementar da segunda rodada com dados adicionais verificados "
        "sobre o mesmo objeto investigado e sem contradizer a evidência anterior."
    )
    src = make_source_data("src_1", url, body)  # mesmo source_id da rodada 1, conteúdo distinto
    chk = make_chunk_data(1, "src_1", url, body, start_offset=0, length=80)
    personas = {}
    for idx, _p in enumerate(PERSONAS, 1):
        personas[_p] = {
            "analise": f"Acúmulo da persona {_p} com a rodada 1 preservada.",
            "conclusoes": [
                # claim da rodada 1 preservado no snapshot (cita chunk que só existe na rodada 1)
                {
                    "claim_id": f"claim_{idx}",
                    "afirmacao": f"Afirmação factual verificada {idx} da persona {_p}.",
                    "tipo": "fato",
                    "evidencias": ["chk_r1"],
                    "confianca": "alta",
                    "limitacoes": "",
                },
                {
                    "claim_id": f"claim_{idx}_r2",
                    "afirmacao": f"Afirmação nova da rodada 2 para {_p}.",
                    "tipo": "fato",
                    "evidencias": ["chk_1"],
                    "confianca": "alta",
                    "limitacoes": "",
                },
            ],
            "lacunas": [],
            "sucesso": True,
        }
    return {
        "versao": 1,
        # trechos/fontes apenas da rodada 2: o corpus antigo não veio no snapshot novo
        "fontes": {"src_1": src},
        "trechos": {"chk_1": chk},
        "resultados_personas": personas,
        "diario_acoes": {p: [{"acao": "concluir"}] for p in PERSONAS},
        "selecao_contexto": {p: {"selected_chunk_ids": ["chk_1"]} for p in PERSONAS},
    }


def _meta_rodada_1() -> dict:
    meta = make_standard_coleta_metadata()
    meta["trechos"] = {"chk_r1": meta["trechos"]["chk_1"]}
    meta["trechos"]["chk_r1"]["chunk_id"] = "chk_r1"
    meta["selecao_contexto"] = {p: {"selected_chunk_ids": ["chk_r1"]} for p in PERSONAS}
    for p_data in meta["resultados_personas"].values():
        for claim in p_data["conclusoes"]:
            claim["evidencias"] = ["chk_r1"]
    return meta


@pytest.mark.asyncio
async def test_auditor_aceita_claim_de_chunk_da_rodada_1_apos_retry(db_session: AsyncSession) -> None:
    repo = ResearchRepository(session=db_session)
    pesq, pontos = await create_research_fixture_with_plan(repo)
    ponto = pontos[0]

    url_r1 = "https://php.net/security-2026"
    url_r2 = "https://example.org/rodada-2"
    for rodada, (url, meta) in enumerate([(url_r1, _meta_rodada_1()), (url_r2, _meta_rodada_2(url_r2))], 1):
        await repo.save_collected_content(
            id_pesquisa=pesq.id_pesquisa,
            ponto_id=ponto.ponto_id,
            tema=pesq.tema,
            ponto=ponto.ponto,
            conteudo_coletado=f"Conteúdo consolidado da rodada {rodada}",
            urls_lidas=[url],
            urls_fonte=[url],
            metadados_coleta=meta,
            rodada=rodada,
        )

    coletas = await repo.get_collected_content_for_point(pesq.id_pesquisa, ponto.ponto_id)
    assert [c.rodada for c in coletas] == [1, 2]

    agregado = _agregar_metadados_coletas(coletas)
    # corpus da rodada 1 preservado e colisão de source_id da rodada 2 remapeada
    assert "chk_r1" in agregado["trechos"]
    assert "src_1" in agregado["fontes"]
    assert "src_1__r2" in agregado["fontes"]
    assert agregado["trechos"]["chk_1"]["source_id"] == "src_1__r2"
    assert agregado["fontes"]["src_1__r2"]["source_id"] == "src_1__r2"

    mock_net = MockNetwork()
    mock_net.custom_handlers["chat/completions"] = lambda r: make_llm_json_response({
        "criterios": make_audit_12_vector(
            12,
            known_claim_ids=["claim_1", "claim_2", "claim_3", "claim_4", "claim_1_r2"],
            known_source_ids=["src_1", "src_1__r2"],
        ),
    })
    llm = LLMClient(api_key="key", transport=create_mock_transport(mock_net))
    auditor = Auditor(research_repo=repo, llm_client=llm)

    resultado = await auditor.execute_audit(id_pesquisa=pesq.id_pesquisa)
    item = resultado["auditorias"][0]

    assert len(mock_net.requests) > 0, "auditoria deveria ter chegado ao LLM"
    assert item["status"] == "aprovado"
    assert item["valido"] is True
    # o prompt entregue ao auditor contém o trecho da rodada 1
    prompts = [json.loads(r.content.decode("utf-8")) for r in mock_net.requests]
    assert any("chk_r1" in json.dumps(p, ensure_ascii=False) for p in prompts)


# ==============================================================================
# (c) Writer: 3 rodadas integrais, sem corte; estouro vira erro explícito
# ==============================================================================

@pytest.mark.asyncio
async def test_writer_mantem_tres_rodadas_e_estoura_com_erro_explicito(db_session: AsyncSession) -> None:
    repo = ResearchRepository(session=db_session)
    pesq, pontos = await create_research_fixture_with_plan(repo)
    ponto = pontos[0]

    texto_longo = ("Evidência íntegra da rodada com mais de quatro mil caracteres. " * 100)[:6000]
    for rodada in (1, 2, 3):
        url = f"https://example.org/rodada-{rodada}"
        src = make_source_data(f"src_{rodada}", url, texto_longo)
        chk = make_chunk_data(rodada, f"src_{rodada}", url, texto_longo, start_offset=0, length=6000)
        await repo.save_collected_content(
            id_pesquisa=pesq.id_pesquisa,
            ponto_id=ponto.ponto_id,
            tema=pesq.tema,
            ponto=ponto.ponto,
            conteudo_coletado=f"### Perspectiva Historiador\n\nSíntese da rodada {rodada}",
            urls_lidas=[url],
            urls_fonte=[url],
            metadados_coleta={
                "versao": 1,
                "fontes": {f"src_{rodada}": src},
                "trechos": {f"chk_{rodada}": chk},
                "resultados_personas": {
                    "historiador": make_persona_result(
                        persona="historiador",
                        analise=f"Análise da rodada {rodada}.",
                        claims=[],
                    )
                },
                "diario_acoes": {"historiador": [{"acao": "concluir"}]},
                "selecao_contexto": {"historiador": {"selected_chunk_ids": [f"chk_{rodada}"]}},
            },
            rodada=rodada,
        )

    coletas = await repo.get_collected_content_for_point(pesq.id_pesquisa, ponto.ponto_id)
    assert [c.rodada for c in coletas] == [1, 2, 3]
    ultima = coletas[-1]
    setattr(ultima, "historico_coletas", coletas)

    writer = Writer(research_repo=repo, llm_client=LLMClient(api_key="key", transport=create_mock_transport(MockNetwork())))
    contexto, *_ = writer._montar_contexto_estruturado(pesq, [ponto], [ultima], [{}])

    ponto_ctx = contexto["pontos"][0]
    assert len(ponto_ctx["rodadas"]) == 3
    assert [r["rodada"] for r in ponto_ctx["rodadas"]] == [1, 2, 3]
    # nenhum texto cortado em 4000 chars
    assert ponto_ctx["trechos"][0]["text"] == texto_longo
    assert all(len(r["trechos"][0]["text"]) == 6000 for r in ponto_ctx["rodadas"])

    # limite estourado: insuficiência explícita, nunca corte silencioso
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(writer_module, "WRITER_MAX_CONTEXT_CHARS", 1000)
        with pytest.raises(WriterContextOverflow) as exc_info:
            writer._montar_contexto_estruturado(pesq, [ponto], [ultima], [{}])
    mensagem = str(exc_info.value)
    assert "WRITER_CONTEXT_OVERFLOW" in mensagem
    assert "pontos=[1]" in mensagem
