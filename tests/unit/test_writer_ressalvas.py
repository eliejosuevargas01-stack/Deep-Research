"""Teto de tentativas não bloqueia o relatório final (PRD v3, RF-006-D)."""

import json

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.writer import Writer
from app.db.research_repository import ResearchRepository
from app.tools.llm_client import LLMClient
from tests.mocks.http_mock import MockNetwork, create_mock_transport
from tests.unit.test_writer_acceptance import (
    SAMPLE_VALID_ARTICLE,
    make_llm_json_response,
    make_llm_raw_response,
    make_writer_article_12_eval,
    setup_research_with_audit,
)


@pytest.mark.asyncio
async def test_ponto_reprovado_ainda_gera_dossie_com_ressalvas(db_session: AsyncSession) -> None:
    mock_net = MockNetwork()
    captured: list[str] = []

    def handler(req):
        body = json.loads(req.content.decode("utf-8"))
        msgs = body.get("messages", [])
        is_eval = any(
            m.get("role") == "system" and "auditor_redacao" in str(m.get("content", ""))
            for m in msgs
        ) or body.get("response_format", {}).get("type") == "json_object"
        if is_eval:
            return make_llm_json_response(make_writer_article_12_eval(aprovados_count=11))
        captured.extend(str(m.get("content", "")) for m in msgs)
        return make_llm_raw_response(content=SAMPLE_VALID_ARTICLE, finish_reason="stop")

    mock_net.custom_handlers["chat/completions"] = handler
    repo = ResearchRepository(session=db_session)
    id_pesquisa, ponto_id, _ = await setup_research_with_audit(repo=repo)

    await repo.update_point_status(
        ponto_id=ponto_id,
        status="reprovado",
        pontos_fracos="Reprovado no critério 2 (corroboração canônica).",
    )

    writer = Writer(research_repo=repo, llm_client=LLMClient(api_key="mock-key", transport=create_mock_transport(mock_net)))
    res = await writer.execute_writer(id_pesquisa=id_pesquisa, permitir_reprovados=True)

    pesquisa = await repo.get_research(id_pesquisa)
    assert pesquisa.dossier_final, "Dossiê deve ser publicado mesmo com ponto reprovado."
    assert res["status"] in ("concluido", "incompleto")
    prompt = " ".join(captured)
    assert "Ressalvas da auditoria" in prompt
    assert "SEM APROVAÇÃO NA AUDITORIA" in prompt


@pytest.mark.asyncio
async def test_ponto_reprovado_sem_flag_continua_bloqueado(db_session: AsyncSession) -> None:
    repo = ResearchRepository(session=db_session)
    id_pesquisa, ponto_id, _ = await setup_research_with_audit(repo=repo)
    await repo.update_point_status(ponto_id=ponto_id, status="reprovado", pontos_fracos="x")

    writer = Writer(research_repo=repo, llm_client=LLMClient(api_key="mock-key", transport=create_mock_transport(MockNetwork())))
    with pytest.raises(ValueError, match="UNAPPROVED_POINTS"):
        await writer.execute_writer(id_pesquisa=id_pesquisa)
    assert (await repo.get_research(id_pesquisa)).dossier_final is None
