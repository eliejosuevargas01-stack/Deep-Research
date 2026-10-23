"""Testes unitários e de integração para validação de streaming universal e reasoning."""

import pytest
import pytest_asyncio
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Pesquisa, Ponto, ConteudoColetado
from app.db.research_repository import ResearchRepository
from app.tools.llm_client import LLMClient
from tests.mocks.http_mock import MockNetwork, create_mock_transport


@pytest.mark.asyncio
async def test_llm_client_returns_content_and_reasoning_in_tuple():
    """Valida se chat_completion_with_reasoning extrai content e reasoning_content."""
    mock_net = MockNetwork()
    transport = create_mock_transport(mock_net)
    client = LLMClient(
        api_key="sk-mock",
        transport=transport,
    )
    content, reasoning = await client.chat_completion_with_reasoning(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "teste reasoning"}],
    )
    assert content is not None
    assert len(content) > 0
    assert reasoning == "Raciocínio simulado para validação analítica."


@pytest.mark.asyncio
async def test_repository_persists_and_retrieves_reasoning(db_session: AsyncSession):
    """Valida a persistência das colunas de reasoning em pesquisa, pontos e conteudo_coletado."""
    repo = ResearchRepository(session=db_session)
    
    # 1. Cria pesquisa com reasoning de planejamento
    pesquisa = await repo.create_research(
        tema="Tema de Teste Reasoning",
        pontos_textos=["Ponto 1 para teste de reasoning"],
        reasoning_planejamento="Cadeia de raciocínio de planejamento",
    )
    assert pesquisa.id_pesquisa is not None
    pontos = await repo.list_points(pesquisa.id_pesquisa)
    assert len(pontos) == 1
    assert pontos[0].reasoning_planejamento == "Cadeia de raciocínio de planejamento"

    # 2. Atualiza ponto com reasoning de auditoria
    await repo.update_point_status(
        ponto_id=pontos[0].ponto_id,
        status="aprovado",
        reasoning_auditoria="Cadeia de raciocínio da auditoria detalhada",
    )
    ponto_atualizado = await repo.get_point(pontos[0].ponto_id)
    assert ponto_atualizado is not None
    assert ponto_atualizado.status == "aprovado"
    assert ponto_atualizado.reasoning_auditoria == "Cadeia de raciocínio da auditoria detalhada"

    # 3. Salva coleta com reasoning_coleta
    coleta = await repo.save_collected_content(
        id_pesquisa=pesquisa.id_pesquisa,
        ponto_id=pontos[0].ponto_id,
        tema=pesquisa.tema,
        ponto=pontos[0].ponto,
        conteudo_coletado="Evidência coletada",
        urls_lidas=["https://exemplo.com"],
        urls_fonte=["https://exemplo.com"],
        reasoning_coleta="Cadeia de raciocínio das 4 personas",
    )
    assert coleta.reasoning_coleta == "Cadeia de raciocínio das 4 personas"

    # 4. Atualiza dossiê com reasoning_dossier
    await repo.update_research_dossier(
        id_pesquisa=pesquisa.id_pesquisa,
        dossier_final="# Dossiê Final",
        reasoning_dossier="Cadeia de raciocínio profunda do redator final",
    )
    pesquisa_concluida = await repo.get_research(pesquisa.id_pesquisa)
    assert pesquisa_concluida is not None
    assert pesquisa_concluida.dossier_final == "# Dossiê Final"
    assert pesquisa_concluida.reasoning_dossier == "Cadeia de raciocínio profunda do redator final"
