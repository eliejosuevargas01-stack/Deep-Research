"""Contrato do adaptador Hermes: os 4 payloads HTTP derivados de arquivos do workspace."""

import json

import pytest

from app.core import hermes_adapter
from app.schemas.audit import AuditResponse
from app.schemas.plan import PlanPontoItem, PlanPreferencias, PlanResponse
from app.schemas.search import SearchResponse
from app.schemas.writer import WriterResponse

PLANO = {
    "pedido_original": "Computação quântica no Brasil",
    "pedido_normalizado": "Mapear o estado da arte da computação quântica no Brasil e os riscos de adoção até 2030.",
    "publico": "decisor",
    "formato_entrega": "relatório",
    "recorte_temporal": "2015-2026",
    "data_referencia": "2026-11-02",
    "politica_recencia": "auto",
    "pressupostos": ["Não há hardware quântico comercial brasileiro em 2026."],
    "ambiguidades": [],
    "pergunta_de_esclarecimento": None,
    "eixos": [
        {
            "pergunta_principal": "Quem financia pesquisa quântica no Brasil?",
            "subperguntas": ["Quais editais federais existem?", "Quanto foi desembolsado por ano?"],
            "hipoteses": ["O financiamento é majoritariamente público."],
            "consultas_iniciais": ["financiamento pesquisa quântica brasil"],
            "fontes_primarias_desejadas": ["MCTI", "FINEP"],
            "riscos_de_vies": ["Somar editais anunciados como se fossem desembolsados."],
            "evidencias_que_refutariam": ["Contrato privado de P&D acima de R$ 100 mi."],
            "criterio_de_conclusao": "Série de desembolsos anuais com fonte orçamentária.",
            "investigabilidade": "Portais de transparência e relatórios anuais do MCTI.",
            "eixo_essencial": True,
        },
        {
            "pergunta_principal": "Qual o gargalo de talentos?",
            "subperguntas": ["Quantos doutores atuam na área?", "Há programas de formação?"],
            "hipoteses": ["A formação é concentrada em poucos grupos."],
            "consultas_iniciais": ["doutores computação quântica brasil"],
            "fontes_primarias_desejadas": ["CAPES", "CNPq"],
            "riscos_de_vies": ["Confundir egressos de cursos genéricos com especialistas."],
            "evidencias_que_refutariam": ["Programa de formação com mais de 100 alunos/ano."],
            "criterio_de_conclusao": "Contagem de grupos e egressos por instituição.",
            "investigabilidade": "Plataforma Sucupira e diretórios de grupos de pesquisa.",
            "eixo_essencial": True,
        },
    ],
    "personas": {
        "historiador": "origem e trajetória",
        "visionario": "cenários futuros",
        "cetico": "limites e riscos",
        "futurista": "sinais fracos",
    },
}


def _busca(persona, urls, tentativas=1, paginas=1):
    """Artefato `<PERSONA>_SEARCH.json` com N tentativas."""
    return {
        "persona": persona,
        "tentativas": [
            {
                "rodada": n,
                "consultas": [f'consulta {n}: "{u}"' for u in urls],
                "analise": "\n".join(f"- achado {u}" for u in urls),
                "lacunas": [],
                "urls_lidas": list(urls),
                "urls_fonte": list(urls),
                "paginas_lidas": paginas,
            }
            for n in range(1, tentativas + 1)
        ],
    }


CRITERIOS = [
    {"id": i, "nome": f"criterio_{i}", "aprovado": i != 2, "justificativa": "ok" if i != 2 else "faltou fonte primária"}
    for i in range(1, 13)
]

DOSSIE = {"dossier_final": "# Dossiê\n\nTexto final com fontes.\n"}


@pytest.fixture
def workspace(tmp_path):
    ws = tmp_path / "computacao-quantica-abcd1234"
    ws.mkdir()
    (ws / "PLAN.json").write_text(json.dumps(PLANO, ensure_ascii=False), encoding="utf-8")
    (ws / "HISTORIADOR_SEARCH.json").write_text(
        json.dumps(_busca("historiador", ["https://a.example/1", "https://a.example/2"], tentativas=2, paginas=2)),
        encoding="utf-8",
    )
    (ws / "VISIONARIO_SEARCH.json").write_text(
        json.dumps(_busca("visionario", ["https://b.example/1"])), encoding="utf-8"
    )
    (ws / "CETICO_SEARCH.json").write_text(
        json.dumps(_busca("cetico", ["https://c.example/1"])), encoding="utf-8"
    )
    (ws / "FUTURISTA_SEARCH.json").write_text(
        json.dumps(_busca("futurista", ["https://d.example/1"])), encoding="utf-8"
    )
    (ws / "AUDITORIA.json").write_text(
        json.dumps({
            "rodadas": [
                {"rodada": 1, "veredito": "REPROVADO", "nota": 11, "criterios": CRITERIOS[:12], "lacunas": "faltou corroboração"},
                {"rodada": 2, "veredito": "APROVADO", "nota": 11, "criterios": CRITERIOS[:12], "lacunas": "sem documento primário do PPA."},
            ]
        }, ensure_ascii=False),
        encoding="utf-8",
    )
    (ws / "DOSSIE.json").write_text(json.dumps(DOSSIE, ensure_ascii=False), encoding="utf-8")
    return ws


def test_plan_payload_le_plan_json(workspace):
    """PLAN.json é o próprio objeto JSON — sem cercas, sem markdown."""
    (workspace / "PLAN.json").write_text("# comentário\n" + json.dumps(PLANO, ensure_ascii=False), encoding="utf-8")
    resultado = hermes_adapter.plan_payload(workspace)
    assert resultado["valido"] is False  # texto fora do JSON é erro, não é ignorado

    (workspace / "PLAN.json").write_text(json.dumps(PLANO, ensure_ascii=False), encoding="utf-8")
    assert hermes_adapter.plan_payload(workspace)["valido"] is True


def test_plan_payload_valida_bloco_json(workspace):
    resultado = hermes_adapter.plan_payload(workspace)

    assert resultado["valido"] is True
    assert resultado["erro"] is None
    assert resultado["plano"]["pedido_original"] == PLANO["pedido_original"]
    assert set(resultado["plano"]) >= set(hermes_adapter.CHAVES_PLANO)

    pontos = hermes_adapter.pontos_do_plano(resultado["plano"])
    assert pontos == [e["pergunta_principal"] for e in PLANO["eixos"]]
    resposta = PlanResponse(
        id_pesquisa="abcd1234-0000-0000-0000-000000000000",
        tema=resultado["plano"]["pedido_original"],
        n_pontos=len(pontos),
        criado_em="2026-11-02T10:00:00+00:00",
        pontos=[
            PlanPontoItem(
                ponto_id=f"p{i}",
                ponto_n=i,
                ponto=texto,
                eixo_estruturado=eixo,
            )
            for i, (texto, eixo) in enumerate(zip(pontos, PLANO["eixos"]), start=1)
        ],
        plano_estruturado=resultado["plano"],
        preferencias=PlanPreferencias(
            n_pontos=len(pontos), personas=sorted(resultado["plano"]["personas"])
        ),
    )
    assert resposta.n_pontos == 2
    eixo = resposta.pontos[0].eixo_estruturado
    assert eixo is not None
    assert eixo.hipoteses == PLANO["eixos"][0]["hipoteses"]
    plano_resp = resposta.plano_estruturado
    assert plano_resp is not None
    assert plano_resp.eixos[0].pergunta_principal == pontos[0]


def test_plan_payload_rejeita_bloco_incompleto(workspace):
    (workspace / "PLAN.json").write_text(json.dumps({"pedido_original": "só isso"}), encoding="utf-8")

    resultado = hermes_adapter.plan_payload(workspace)

    assert resultado["valido"] is False
    assert "fora do contrato" in resultado["erro"]


def test_search_payload_deriva_dos_quatro_arquivos(workspace):
    payload = hermes_adapter.search_payload("abcd1234", workspace)
    resposta = SearchResponse(**payload)

    resumo = resposta.resumo_coletas[0]
    assert {p.persona for p in resumo.personas} == set(hermes_adapter.PERSONA_ARQUIVOS)
    assert resumo.total_urls_fonte == 5
    assert resumo.total_urls_lidas == 7  # 2+2 do historiador (2 tentativas) + 1+1+1
    assert resumo.tentativas == 2
    assert all(p.falha_coleta is False for p in resumo.personas)


def test_audit_payload_usa_ultima_rodada(workspace):
    payload = hermes_adapter.audit_payload("abcd1234", workspace, criterios_minimos=11)
    resposta = AuditResponse(**payload)

    assert resposta.pronto_para_writer is True
    assert resposta.aprovados == 1
    assert resposta.auditorias[0].criterios_aprovados == 11
    assert resposta.auditorias[0].pontuacao_percentual == pytest.approx(91.67)

    # Motivo da reprovação precisa chegar à tela: critério a critério + lacunas.
    criterios = payload["auditorias"][0]["criterios"]
    assert [c["id"] for c in criterios] == list(range(1, 13))
    assert [c["id"] for c in criterios if not c["aprovado"]] == [2]
    assert "fonte primária" in criterios[1]["justificativa"]
    assert payload["auditorias"][0]["pontos_fracos"] == "sem documento primário do PPA."


def test_writer_payload_entrega_dossie(workspace):
    payload = hermes_adapter.writer_payload("abcd1234", "Computação quântica", workspace)
    resposta = WriterResponse(**payload)

    assert resposta.status == "concluido"
    assert resposta.dossier_final is not None
    assert resposta.dossier_final.startswith("# Dossiê")
    assert resposta.total_caracteres_dossier == len(resposta.dossier_final)


@pytest.mark.asyncio
async def test_endpoints_hermes_devolvem_os_schemas_atuais(db_session, workspace):
    """Os 3 endpoints de leitura derivam de arquivos e validam os schemas existentes."""
    from unittest.mock import AsyncMock, patch

    from app.api.v1.endpoints import audit as audit_mod
    from app.api.v1.endpoints import search as search_mod
    from app.api.v1.endpoints import writer as writer_mod
    from app.db.research_repository import ResearchRepository
    from app.schemas.audit import AuditRequest
    from app.schemas.search import SearchRequest
    from app.schemas.writer import WriterRequest

    repo = ResearchRepository(session=db_session)
    pesquisa = await repo.create_research(
        tema="Computação quântica no Brasil",
        pontos_textos=["Quem financia?"],
        id_pesquisa="abcd1234-0000-0000-0000-000000000000",
    )

    with (
        patch.object(hermes_adapter, "garantir_pesquisa", AsyncMock(return_value=workspace)),
        patch.object(hermes_adapter, "aguardar_coletas", AsyncMock(return_value=None)),
        patch.object(hermes_adapter, "aguardar_arquivo", AsyncMock(return_value=workspace)),
    ):
        busca = await search_mod.search_points(
            SearchRequest(id_pesquisa=pesquisa.id_pesquisa), db_session
        )
        auditoria = await audit_mod.audit_research(
            AuditRequest(id_pesquisa=pesquisa.id_pesquisa), db_session
        )
        dossie = await writer_mod.write_dossier(
            WriterRequest(id_pesquisa=pesquisa.id_pesquisa), db_session
        )

    assert isinstance(busca, SearchResponse)
    assert isinstance(auditoria, AuditResponse)
    assert isinstance(dossie, WriterResponse)
    assert dossie.dossier_final == json.loads((workspace / "DOSSIE.json").read_text(encoding="utf-8"))["dossier_final"]
