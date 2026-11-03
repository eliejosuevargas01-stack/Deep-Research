"""Contrato do adaptador Hermes: os 4 payloads HTTP derivados de arquivos do workspace."""

import json

import pytest

from app.core import hermes_adapter
from app.schemas.audit import AuditResponse
from app.schemas.plan import PlanPontoItem, PlanPreferencias, PlanResponse
from app.schemas.search import SearchResponse
from app.schemas.writer import WriterResponse

PLANO = {
    "versao": "v10",
    "tema": "Computação quântica no Brasil",
    "objetivo": "Mapear o estado da arte e os riscos de adoção até 2030.",
    "escopo": "Iniciativas públicas e privadas brasileiras.",
    "perguntas": ["Quem financia pesquisa quântica no Brasil?", "Qual o gargalo de talentos?"],
    "personas": {
        "historiador": "origem e trajetória",
        "visionario": "cenários futuros",
        "cetico": "limites e riscos",
        "futurista": "sinais fracos",
    },
    "criterios_evidencia": ["fonte primária", "data explícita"],
    "criterios_aprovacao": {"minimo": 11, "total": 12},
}


def _search_md(urls, tentativas=1, total=1):
    partes = []
    for n in range(1, tentativas + 1):
        partes.append(f"tentativa {n}\n")
        partes.extend(f"- consulta {n}: {u}\n" for u in urls)
        partes.append(f"TOTAL: {total} páginas\n")
    return "\n".join(partes)


@pytest.fixture
def workspace(tmp_path):
    ws = tmp_path / "computacao-quantica-abcd1234"
    ws.mkdir()
    (ws / "PLAN.md").write_text(
        "# Plano\n\n```json\n" + json.dumps(PLANO, ensure_ascii=False) + "\n```\n",
        encoding="utf-8",
    )
    (ws / "HISTORIADOR_SEARCH.md").write_text(
        _search_md(["https://a.example/1", "https://a.example/2"], tentativas=2, total=2),
        encoding="utf-8",
    )
    (ws / "VISIONARIO_SEARCH.md").write_text(
        _search_md(["https://b.example/1"]), encoding="utf-8"
    )
    (ws / "CETICO_SEARCH.md").write_text(
        _search_md(["https://c.example/1"]), encoding="utf-8"
    )
    (ws / "FUTURISTA_SEARCH.md").write_text(
        _search_md(["https://d.example/1"]), encoding="utf-8"
    )
    (ws / "AUDITORIA.md").write_text(
        "## Rodada 1 — REPROVADO — nota 9/12\nfaltou corroboração\n\n"
        "## Rodada 2 — APROVADO — nota 11/12\nok\n",
        encoding="utf-8",
    )
    (ws / "DOSSIE.md").write_text("# Dossiê\n\nTexto final com fontes.\n", encoding="utf-8")
    return ws


def test_plan_payload_aceita_json_sem_cerca(workspace):
    """O planner as vezes escreve o objeto solto, sem ```json."""
    import json as _json

    from app.core.hermes_adapter import CHAVES_PLANO

    solto = {k: ("x" if k != "personas" else {p: "x" for p in hermes_adapter.PERSONA_ARQUIVOS}) for k in CHAVES_PLANO}
    (workspace / "PLAN.md").write_text("# Plano\n\n" + _json.dumps(solto), encoding="utf-8")
    resultado = hermes_adapter.plan_payload(workspace)
    assert resultado["valido"] is True


def test_plan_payload_valida_bloco_json(workspace):
    resultado = hermes_adapter.plan_payload(workspace)

    assert resultado["valido"] is True
    assert resultado["erro"] is None
    assert resultado["plano"]["tema"] == PLANO["tema"]
    assert set(resultado["plano"]) >= set(hermes_adapter.CHAVES_PLANO)

    pontos = hermes_adapter.pontos_do_plano(resultado["plano"])
    assert pontos == [PLANO["tema"]]  # perfil Hermes = um ponto (tema inteiro)
    resposta = PlanResponse(
        id_pesquisa="abcd1234-0000-0000-0000-000000000000",
        tema=resultado["plano"]["tema"],
        n_pontos=len(pontos),
        criado_em="2026-11-02T10:00:00+00:00",
        pontos=[
            PlanPontoItem(ponto_id=f"p{i}", ponto_n=i, ponto=texto)
            for i, texto in enumerate(pontos, start=1)
        ],
        preferencias=PlanPreferencias(
            n_pontos=len(pontos), personas=sorted(resultado["plano"]["personas"])
        ),
    )
    assert resposta.n_pontos == 1


def test_plan_payload_rejeita_bloco_incompleto(workspace):
    (workspace / "PLAN.md").write_text(
        "```json\n" + json.dumps({"versao": "v10"}) + "\n```\n", encoding="utf-8"
    )

    resultado = hermes_adapter.plan_payload(workspace)

    assert resultado["valido"] is False
    assert "chaves ausentes" in resultado["erro"]


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
    assert dossie.dossier_final == (workspace / "DOSSIE.md").read_text(encoding="utf-8")
