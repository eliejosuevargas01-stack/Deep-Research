# -*- coding: utf-8 -*-
"""Deliberacao deterministica por evidencia web real (RF-07, RF-08).

Garante que ponto sem nenhuma URL lida nunca chega ao LLM de auditoria e que
a redacao so prossegue quando existe ao menos um ponto com fonte real.
"""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.research_repository import ResearchRepository
from tests.mocks.http_mock import MockNetwork, create_mock_transport

DIAGNOSTICO_402 = "JinaError 402 billing: saldo insuficiente"


@pytest.mark.asyncio
async def test_auditor_reprova_sem_chamar_llm_quando_nao_ha_evidencia(
    db_session: AsyncSession,
) -> None:
    """RF-07/CA-07.1: reprovacao deterministica com zero chamadas ao LLM."""
    from app.core.auditor import Auditor
    from app.tools.llm_client import LLMClient

    mock_net = MockNetwork()
    transport = create_mock_transport(mock_net)
    llm_client = LLMClient(api_key="openai-key", transport=transport)
    repo = ResearchRepository(session=db_session)

    pesquisa = await repo.create_research(tema="Tema Sem Fonte", pontos_textos=["Ponto Sem Fonte"])
    ponto = (await repo.list_points(pesquisa.id_pesquisa))[0]
    await repo.save_collected_content(
        id_pesquisa=pesquisa.id_pesquisa,
        ponto_id=ponto.ponto_id,
        tema=pesquisa.tema,
        ponto=ponto.ponto,
        conteudo_coletado="COLETA FALHOU",
        urls_lidas=[],
        urls_fonte=[],
        status_ponto="falha_coleta",
        diagnostico_falha=DIAGNOSTICO_402,
    )

    antes = len(mock_net.requests)
    auditor = Auditor(research_repo=repo, llm_client=llm_client, persona_prompt="Voce e o auditor")
    resultado = await auditor.execute_audit(id_pesquisa=pesquisa.id_pesquisa)
    depois = len(mock_net.requests)

    assert resultado["total_pontos"] == 1
    assert resultado["reprovados"] == 1
    assert resultado["aprovados"] == 0
    assert "402" in resultado["auditorias"][0]["pontos_fracos"]
    assert depois == antes  # nenhuma chamada LLM


@pytest.mark.asyncio
async def test_auditor_chama_llm_quando_existe_evidencia(db_session: AsyncSession) -> None:
    """Controle: com evidencia real a auditoria segue pelo LLM."""
    from app.core.auditor import Auditor
    from app.tools.llm_client import LLMClient

    mock_net = MockNetwork()
    transport = create_mock_transport(mock_net)
    llm_client = LLMClient(api_key="openai-key", transport=transport)
    repo = ResearchRepository(session=db_session)

    pesquisa = await repo.create_research(tema="Tema Com Fonte", pontos_textos=["Ponto Com Fonte"])
    ponto = (await repo.list_points(pesquisa.id_pesquisa))[0]
    await repo.save_collected_content(
        id_pesquisa=pesquisa.id_pesquisa,
        ponto_id=ponto.ponto_id,
        tema=pesquisa.tema,
        ponto=ponto.ponto,
        conteudo_coletado="### Perspectiva Historiador\n\nAnalise com fonte real.",
        urls_lidas=["https://unesco.org/estudo"],
        urls_fonte=["https://unesco.org/estudo"],
    )

    antes = len(mock_net.requests)
    auditor = Auditor(research_repo=repo, llm_client=llm_client, persona_prompt="Voce e o auditor")
    resultado = await auditor.execute_audit(id_pesquisa=pesquisa.id_pesquisa)
    depois = len(mock_net.requests)

    assert resultado["total_pontos"] == 1
    assert resultado["auditorias"][0]["status"] in ("aprovado", "reprovado")
    assert depois > antes  # houve deliberacao via LLM


@pytest.mark.asyncio
async def test_auditor_com_evidencia_mista_nao_gasta_llm_no_ponto_falho(
    db_session: AsyncSession,
) -> None:
    """CA-07.2: rodada valida delibera no LLM; rodada sem fonte e podada sem custo."""
    from app.core.auditor import Auditor
    from app.tools.llm_client import LLMClient

    mock_net = MockNetwork()
    transport = create_mock_transport(mock_net)
    llm_client = LLMClient(api_key="openai-key", transport=transport)
    repo = ResearchRepository(session=db_session)

    pesquisa = await repo.create_research(
        tema="Tema Misto", pontos_textos=["Ponto Com Fonte", "Ponto Sem Fonte"]
    )
    pontos = await repo.list_points(pesquisa.id_pesquisa)

    await repo.save_collected_content(
        id_pesquisa=pesquisa.id_pesquisa,
        ponto_id=pontos[0].ponto_id,
        tema=pesquisa.tema,
        ponto=pontos[0].ponto,
        conteudo_coletado="### Perspectiva Historiador\n\nAnalise com fonte real.",
        urls_lidas=["https://unesco.org/estudo"],
        urls_fonte=["https://unesco.org/estudo"],
    )
    await repo.save_collected_content(
        id_pesquisa=pesquisa.id_pesquisa,
        ponto_id=pontos[1].ponto_id,
        tema=pesquisa.tema,
        ponto=pontos[1].ponto,
        conteudo_coletado="COLETA FALHOU",
        urls_lidas=[],
        urls_fonte=[],
        status_ponto="falha_coleta",
        diagnostico_falha=DIAGNOSTICO_402,
    )

    auditor = Auditor(research_repo=repo, llm_client=llm_client, persona_prompt="Voce e o auditor")
    resultado = await auditor.execute_audit(id_pesquisa=pesquisa.id_pesquisa)

    por_ponto = {a["ponto_id"]: a for a in resultado["auditorias"]}
    assert por_ponto[pontos[0].ponto_id]["status"] in ("aprovado", "reprovado")
    assert por_ponto[pontos[1].ponto_id]["status"] == "reprovado"
    assert "402" in por_ponto[pontos[1].ponto_id]["pontos_fracos"]


@pytest.mark.asyncio
async def test_writer_bloqueia_quando_todos_pontos_sem_evidencia(
    db_session: AsyncSession,
) -> None:
    """RF-08/CA-08.1: NO_EVIDENCE_COLLECTED sem dossie inventado."""
    from app.core.writer import Writer
    from app.tools.llm_client import LLMClient

    mock_net = MockNetwork()
    transport = create_mock_transport(mock_net)
    llm_client = LLMClient(api_key="openai-key", transport=transport)
    repo = ResearchRepository(session=db_session)

    pesquisa = await repo.create_research(tema="Tema Sem Nada", pontos_textos=["Ponto Orfao"])
    ponto = (await repo.list_points(pesquisa.id_pesquisa))[0]
    await repo.save_collected_content(
        id_pesquisa=pesquisa.id_pesquisa,
        ponto_id=ponto.ponto_id,
        tema=pesquisa.tema,
        ponto=ponto.ponto,
        conteudo_coletado="COLETA FALHOU",
        urls_lidas=[],
        urls_fonte=[],
        status_ponto="falha_coleta",
        diagnostico_falha=DIAGNOSTICO_402,
    )
    await repo.update_point_status(
        ponto_id=ponto.ponto_id,
        status="reprovado",
        pontos_fracos=DIAGNOSTICO_402,
    )

    writer = Writer(
        research_repo=repo,
        llm_client=llm_client,
        personas=["redator final"],
    )
    with pytest.raises(ValueError, match="NO_EVIDENCE_COLLECTED"):
        await writer.execute_writer(id_pesquisa=pesquisa.id_pesquisa)

    assert (await repo.get_research(pesquisa.id_pesquisa)).dossier_final is None


@pytest.mark.asyncio
async def test_writer_prossegue_com_pelo_menos_um_ponto_valido(db_session: AsyncSession) -> None:
    """CA-08.2: falha parcial nao impede redacao dos pontos com evidencia."""
    from app.core.writer import Writer
    from app.tools.llm_client import LLMClient

    mock_net = MockNetwork()
    transport = create_mock_transport(mock_net)
    llm_client = LLMClient(api_key="openai-key", transport=transport)
    repo = ResearchRepository(session=db_session)

    pesquisa = await repo.create_research(
        tema="Tema Parcial", pontos_textos=["Ponto Com Fonte", "Ponto Sem Fonte"]
    )
    pontos = await repo.list_points(pesquisa.id_pesquisa)

    await repo.save_collected_content(
        id_pesquisa=pesquisa.id_pesquisa,
        ponto_id=pontos[0].ponto_id,
        tema=pesquisa.tema,
        ponto=pontos[0].ponto,
        conteudo_coletado="### Perspectiva Historiador\n\nAnalise com fonte real.",
        urls_lidas=["https://unesco.org/estudo"],
        urls_fonte=["https://unesco.org/estudo"],
    )
    await repo.save_collected_content(
        id_pesquisa=pesquisa.id_pesquisa,
        ponto_id=pontos[1].ponto_id,
        tema=pesquisa.tema,
        ponto=pontos[1].ponto,
        conteudo_coletado="COLETA FALHOU",
        urls_lidas=[],
        urls_fonte=[],
        status_ponto="falha_coleta",
        diagnostico_falha=DIAGNOSTICO_402,
    )
    await repo.update_point_status(ponto_id=pontos[0].ponto_id, status="aprovado")
    await repo.update_point_status(
        ponto_id=pontos[1].ponto_id, status="reprovado", pontos_fracos=DIAGNOSTICO_402
    )

    writer = Writer(
        research_repo=repo,
        llm_client=llm_client,
        personas=["redator final"],
    )
    resultado = await writer.execute_writer(id_pesquisa=pesquisa.id_pesquisa)
    assert resultado["status"] == "concluido"
    assert resultado["total_caracteres_dossier"] > 100
