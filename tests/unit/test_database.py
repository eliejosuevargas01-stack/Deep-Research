"""Testes unitários para o banco de dados e repositórios relacionais.

Cobre esquema DDL, verificação de pragmas WAL, integridade referencial com
deleção em cascata, restrições de unicidade e operações do ResearchRepository.
Atende a DT-02, RF-02, RF-04, RF-05 e RNF-08.
"""

import uuid
import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from app.db.init_db import init_db
from app.db.models import ConteudoColetado, Pesquisa, Ponto
from app.db.research_repository import ResearchRepository


@pytest.mark.asyncio
async def test_sqlite_pragmas_and_init_db(async_engine: AsyncEngine) -> None:
    """Verifica ativação mandatória de WAL, foreign_keys, synchronous e busy_timeout."""
    info = await init_db(async_engine)

    assert info["journal_mode"] == "wal"
    assert info["foreign_keys"] == 1
    assert info["busy_timeout"] == 30000
    assert info["synchronous"] == 1  # 1 = NORMAL no SQLite

    # Confere que as 4 tabelas fundamentais foram criadas
    async with async_engine.connect() as conn:
        result = await conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        )
        tabelas = {row[0] for row in result.fetchall()}

    assert {"pesquisa", "pontos", "conteudo_coletado", "credenciais"}.issubset(tabelas)


@pytest.mark.asyncio
async def test_cascade_deletion_research_to_points_and_content(
    db_session: AsyncSession,
) -> None:
    """Verifica que a exclusão da Pesquisa remove em cascata pontos e conteúdos vinculados."""
    repo = ResearchRepository(session=db_session)
    pesquisa = await repo.create_research(
        tema="Tema Teste Cascata",
        pontos_textos=["Ponto 1", "Ponto 2"],
    )
    id_pesquisa = pesquisa.id_pesquisa

    pontos = await repo.list_points(id_pesquisa)
    assert len(pontos) == 2

    # Insere conteúdo coletado para o ponto 1
    await repo.save_collected_content(
        id_pesquisa=id_pesquisa,
        ponto_id=pontos[0].ponto_id,
        tema=pesquisa.tema,
        ponto=pontos[0].ponto,
        conteudo_coletado="Texto do conteúdo",
        urls_lidas=["https://exemplo.com/doc1"],
        urls_fonte=["https://exemplo.com/doc1"],
    )

    # Deleta a pesquisa raiz
    await db_session.delete(pesquisa)
    await db_session.commit()

    # Verifica que pontos foram removidos via CASCADE
    stmt_pontos = select(Ponto).where(Ponto.id_pesquisa == id_pesquisa)
    pontos_restantes = (await db_session.execute(stmt_pontos)).scalars().all()
    assert len(pontos_restantes) == 0

    # Verifica que conteúdos foram removidos via CASCADE
    stmt_conteudo = select(ConteudoColetado).where(ConteudoColetado.id_pesquisa == id_pesquisa)
    conteudos_restantes = (await db_session.execute(stmt_conteudo)).scalars().all()
    assert len(conteudos_restantes) == 0


@pytest.mark.asyncio
async def test_unique_constraint_pesquisa_ponto_n(db_session: AsyncSession) -> None:
    """Verifica que a restrição uq_pesquisa_ponto_n impede ordinais duplicados."""
    id_pesquisa = str(uuid.uuid4())
    pesquisa = Pesquisa(
        id_pesquisa=id_pesquisa,
        tema="Tema Unicidade",
        criado_em="2026-10-21T18:30:00Z",
    )
    db_session.add(pesquisa)

    ponto_1 = Ponto(
        ponto_id=str(uuid.uuid4()),
        id_pesquisa=id_pesquisa,
        tema=pesquisa.tema,
        ponto_n=1,
        ponto="Primeiro Ponto",
        status="pendente",
        criado_em="2026-10-21T18:30:00Z",
        atualizado_em="2026-10-21T18:30:00Z",
    )
    ponto_duplicado = Ponto(
        ponto_id=str(uuid.uuid4()),
        id_pesquisa=id_pesquisa,
        tema=pesquisa.tema,
        ponto_n=1,  # Mesmo número ordinal para a mesma pesquisa
        ponto="Ponto com mesmo número",
        status="pendente",
        criado_em="2026-10-21T18:30:00Z",
        atualizado_em="2026-10-21T18:30:00Z",
    )
    db_session.add(ponto_1)
    db_session.add(ponto_duplicado)

    with pytest.raises(IntegrityError):
        await db_session.commit()

    await db_session.rollback()


@pytest.mark.asyncio
async def test_unique_constraint_conteudo_ponto(db_session: AsyncSession) -> None:
    """Verifica que a restrição uq_conteudo_ponto impede duplicidade de coleta por ponto."""
    repo = ResearchRepository(session=db_session)
    pesquisa = await repo.create_research(
        tema="Tema Unicidade Conteúdo",
        pontos_textos=["Ponto Único"],
    )
    ponto = (await repo.list_points(pesquisa.id_pesquisa))[0]

    conteudo_1 = ConteudoColetado(
        id=str(uuid.uuid4()),
        id_pesquisa=pesquisa.id_pesquisa,
        ponto_id=ponto.ponto_id,
        tema=pesquisa.tema,
        ponto=ponto.ponto,
        conteudo_coletado="Texto 1",
        urls_lidas="[]",
        urls_fonte="[]",
        criado_em="2026-10-21T18:30:00Z",
    )
    conteudo_duplicado = ConteudoColetado(
        id=str(uuid.uuid4()),
        id_pesquisa=pesquisa.id_pesquisa,
        ponto_id=ponto.ponto_id,  # Mesmo ponto_id
        tema=pesquisa.tema,
        ponto=ponto.ponto,
        conteudo_coletado="Texto 2",
        urls_lidas="[]",
        urls_fonte="[]",
        criado_em="2026-10-21T18:30:00Z",
    )
    db_session.add(conteudo_1)
    db_session.add(conteudo_duplicado)

    with pytest.raises(IntegrityError):
        await db_session.commit()

    await db_session.rollback()


@pytest.mark.asyncio
async def test_research_repository_create_and_get(db_session: AsyncSession) -> None:
    """Verifica criação de pesquisa com N pontos e posterior leitura."""
    repo = ResearchRepository(session=db_session)
    tema = "Impacto da IA na Medicina"
    pontos_textos = [f"Eixo investigativo {i}" for i in range(1, 6)]

    pesquisa = await repo.create_research(tema=tema, pontos_textos=pontos_textos)
    assert pesquisa.tema == tema
    assert pesquisa.id_pesquisa is not None

    pontos = await repo.list_points(pesquisa.id_pesquisa)
    assert len(pontos) == 5
    for i, p in enumerate(pontos, start=1):
        assert p.ponto_n == i
        assert p.status == "pendente"
        assert p.ponto == f"Eixo investigativo {i}"

    recuperada = await repo.get_research(pesquisa.id_pesquisa)
    assert recuperada is not None
    assert recuperada.tema == tema


@pytest.mark.asyncio
async def test_research_repository_url_deduplication(db_session: AsyncSession) -> None:
    """Verifica agregação e deduplicação de URLs consultadas por id_pesquisa (RN-04)."""
    repo = ResearchRepository(session=db_session)
    pesquisa = await repo.create_research(
        tema="Tema Deduplicação URLs",
        pontos_textos=["Ponto A", "Ponto B"],
    )
    pontos = await repo.list_points(pesquisa.id_pesquisa)

    # Coleta 1
    await repo.save_collected_content(
        id_pesquisa=pesquisa.id_pesquisa,
        ponto_id=pontos[0].ponto_id,
        tema=pesquisa.tema,
        ponto=pontos[0].ponto,
        conteudo_coletado="Texto 1",
        urls_lidas=["https://exemplo.com/doc1", "https://exemplo.com/doc2"],
        urls_fonte=["https://exemplo.com/doc1"],
    )

    # Coleta 2 com URL repetida (doc2) e URL nova (doc3)
    await repo.save_collected_content(
        id_pesquisa=pesquisa.id_pesquisa,
        ponto_id=pontos[1].ponto_id,
        tema=pesquisa.tema,
        ponto=pontos[1].ponto,
        conteudo_coletado="Texto 2",
        urls_lidas=["https://exemplo.com/doc2", "https://exemplo.com/doc3"],
        urls_fonte=["https://exemplo.com/doc3"],
    )

    urls_deduplicadas = await repo.get_read_urls(pesquisa.id_pesquisa)
    assert urls_deduplicadas == {
        "https://exemplo.com/doc1",
        "https://exemplo.com/doc2",
        "https://exemplo.com/doc3",
    }


@pytest.mark.asyncio
async def test_save_collected_content_registra_falha_coleta_sem_apagar_historico(
    db_session: AsyncSession,
) -> None:
    """RF-06/CA-06.1 e CA-06.3: falha persistida preserva coletas anteriores."""
    repo = ResearchRepository(session=db_session)
    pesquisa = await repo.create_research(
        tema="Tema Rodadas com Falha",
        pontos_textos=["Ponto com Histórico"],
    )
    ponto = (await repo.list_points(pesquisa.id_pesquisa))[0]

    # Rodada 1: coleta válida
    await repo.save_collected_content(
        id_pesquisa=pesquisa.id_pesquisa,
        ponto_id=ponto.ponto_id,
        tema=pesquisa.tema,
        ponto=ponto.ponto,
        conteudo_coletado="Análise com fonte real.",
        urls_lidas=["https://exemplo.com/doc1"],
        urls_fonte=["https://exemplo.com/doc1"],
    )
    assert (await repo.get_point(ponto.ponto_id)).status == "coletado"  # type: ignore[union-attr]

    # Rodada 2: falha de coleta registrada com diagnóstico
    await repo.save_collected_content(
        id_pesquisa=pesquisa.id_pesquisa,
        ponto_id=ponto.ponto_id,
        tema=pesquisa.tema,
        ponto=ponto.ponto,
        conteudo_coletado="COLETA FALHOU",
        urls_lidas=[],
        urls_fonte=[],
        status_ponto="falha_coleta",
        diagnostico_falha="JinaError 402 billing: saldo insuficiente",
    )
    ponto_falho = await repo.get_point(ponto.ponto_id)
    assert ponto_falho is not None
    assert ponto_falho.status == "falha_coleta"
    assert "402" in (ponto_falho.pontos_fracos or "")

    # CA-06.3: rodada anterior intacta
    rodadas = await repo.get_collected_content_for_point(pesquisa.id_pesquisa, ponto.ponto_id)
    assert len(rodadas) == 2
    assert rodadas[0].urls_lidas == '["https://exemplo.com/doc1"]'

    # RF-07/CA-07.1: evidência real ainda disponível apesar da rodada falha
    evidencia = await repo.get_last_coleta_evidence(pesquisa.id_pesquisa, ponto.ponto_id)
    assert evidencia is not None
    assert evidencia.urls_lidas == '["https://exemplo.com/doc1"]'


@pytest.mark.asyncio
async def test_get_last_coleta_evidence_none_quando_todas_rodadas_falharam(
    db_session: AsyncSession,
) -> None:
    """RF-07: sem nenhuma URL lida, não existe evidência para a auditoria deliberar."""
    repo = ResearchRepository(session=db_session)
    pesquisa = await repo.create_research(
        tema="Tema Sem Evidência",
        pontos_textos=["Ponto Sem Fonte"],
    )
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
        diagnostico_falha="JinaError 402 billing: saldo insuficiente",
    )
    evidencia = await repo.get_last_coleta_evidence(pesquisa.id_pesquisa, ponto.ponto_id)
    assert evidencia is None


@pytest.mark.asyncio
async def test_research_repository_update_point_status_and_dossier(
    db_session: AsyncSession,
) -> None:
    """Verifica atualização de parecer do ponto e registro do dossiê final com status de webhook."""
    repo = ResearchRepository(session=db_session)
    pesquisa = await repo.create_research(
        tema="Tema Atualização Parecer",
        pontos_textos=["Ponto para reprovação"],
    )
    ponto = (await repo.list_points(pesquisa.id_pesquisa))[0]

    # Atualiza ponto com reprovação e pontos_fracos
    atualizado = await repo.update_point_status(
        ponto_id=ponto.ponto_id,
        status="reprovado",
        pontos_fracos="Fontes fracas e desatualizadas",
    )
    assert atualizado is not None
    assert atualizado.status == "reprovado"
    assert atualizado.pontos_fracos == "Fontes fracas e desatualizadas"

    # Atualiza dossiê final e webhook
    pesquisa_concluida = await repo.update_research_dossier(
        id_pesquisa=pesquisa.id_pesquisa,
        dossier_final="# Dossiê Final Completo",
        webhook_status="entregue",
        webhook_resposta="200 OK",
    )
    assert pesquisa_concluida is not None
    assert pesquisa_concluida.dossier_final == "# Dossiê Final Completo"
    assert pesquisa_concluida.webhook_status == "entregue"
    assert pesquisa_concluida.concluido_em is not None
