"""Testes de aceitação para persistência estruturada e migração aditiva idempotente (DR-005, DR-006, DR-013, DR-015).

Cobre:
- Transação atômica real da criação da pesquisa, pontos, plano estruturado e tentativas de telemetria via create_research.
- Leitura e integridade das colunas de telemetria (cost_currency, cost_source, request_params_json, downstream_router_mutations).
- Rollback completo em falha de construção ou no commit da transação.
- Migração aditiva em SQLite com dados pré-existentes de esquema antigo.
- Idempotência da migração sem destruição de dados ou duplicação de colunas.
- Preservação honesta de dados antigos como NULL (sem dados fictícios).
"""

import json
import os
import tempfile
import uuid
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.init_db import init_db
from app.db.session import create_engine_with_pragmas
from app.db.models import (
    Base,
    ConteudoColetado,
    GenerationAttempt,
    Pesquisa,
    Ponto,
)
from app.db.research_repository import ResearchRepository


@pytest.mark.asyncio
async def test_roundtrip_all_structured_entities(db_session: AsyncSession) -> None:
    """Valida gravação e leitura estruturada de pesquisa, pontos, plano e envelopes de telemetria via create_research."""
    repo = ResearchRepository(session=db_session)

    pesquisa_id = f"pesq-{uuid.uuid4().hex[:8]}"
    eixo_sample = {
        "pergunta_principal": "Qual o impacto da computação quântica na criptografia?",
        "subperguntas": ["Como o algoritmo de Shor quebra RSA?"],
        "hipoteses": ["Algoritmos pós-quânticos oferecem segurança comprovada"],
        "consultas_iniciais": ["quantum cryptography shor algorithm rsa"],
        "fontes_primarias_desejadas": ["NIST Standards, IEEE Quantum"],
        "riscos_de_vies": ["Hype excessivo da indústria"],
        "evidencias_que_refutariam": ["Quebra teórica do Kyber"],
        "criterio_de_conclusao": "Publicação de normas homologadas pelo NIST",
        "investigabilidade": "Alta via acervos abertos do NIST",
        "eixo_essencial": True,
    }

    gen_attempt_sample = {
        "id": f"att-{uuid.uuid4().hex[:8]}",
        "etapa": "plan",
        "persona": "planejador",
        "model_requested": "gpt-4o",
        "model_used": "gpt-4o-2024-08-06",
        "prompt_hash": "sha256_mock_prompt_hash_12345",
        "prompt_version": "v1.0",
        "system_message": "Você é o Planejador...",
        "messages": [{"role": "user", "content": "Planeje a pesquisa sobre computação quântica"}],
        "content_final": '{"eixos": [...]}',
        "reasoning_content": "Pensamento detalhado do planejador...",
        "finish_reason": "stop",
        "is_regular_finish": True,
        "usage": {"prompt_tokens": 120, "completion_tokens": 350, "total_tokens": 470},
        "cost_estimated": 0.0035,
        "cost_currency": "USD",
        "cost_source": "openrouter",
        "request_params": {"model": "gpt-4o", "stream": False},
        "downstream_router_mutations": False,
        "latency_seconds": 1.82,
        "attempts": 1,
        "errors": [],
    }

    # 1. Criação atômica via create_research
    pesquisa = await repo.create_research(
        id_pesquisa=pesquisa_id,
        tema="Impacto da Computação Quântica na Criptografia",
        pontos_textos=["Qual o impacto da computação quântica na criptografia?"],
        reasoning_planejamento="Pensamento detalhado do planejador...",
        plano_estruturado={"publico": "Especialistas em Segurança", "eixos": [eixo_sample]},
        metadados_planejamento={"model_requested": "gpt-4o", "cost_currency": "USD"},
        eixos_estruturados=[eixo_sample],
        generation_attempts=[gen_attempt_sample],
    )
    assert pesquisa.id_pesquisa == pesquisa_id

    # 2. Leitura e asserções da Pesquisa
    pesq_db = await repo.get_research(pesquisa_id)
    assert pesq_db is not None
    assert pesq_db.tema == "Impacto da Computação Quântica na Criptografia"
    assert pesq_db.plano_estruturado is not None
    assert "Especialistas em Segurança" in pesq_db.plano_estruturado
    assert pesq_db.metadados_planejamento is not None
    assert "openrouter" not in pesq_db.metadados_planejamento or "USD" in pesq_db.metadados_planejamento

    # 3. Leitura e asserções dos Pontos
    pontos_db = await repo.list_points(pesquisa_id)
    assert len(pontos_db) == 1
    ponto = pontos_db[0]
    assert ponto.ponto_n == 1
    assert ponto.ponto == "Qual o impacto da computação quântica na criptografia?"
    assert ponto.reasoning_planejamento == "Pensamento detalhado do planejador..."
    assert ponto.eixo_estruturado is not None
    assert "NIST Standards" in ponto.eixo_estruturado

    # 4. Leitura e asserções de GenerationAttempt (telemetria completa R2-F11)
    attempts_db = await repo.get_generation_attempts(pesquisa_id, etapa="plan")
    assert len(attempts_db) == 1
    att = attempts_db[0]
    assert att.id == gen_attempt_sample["id"]
    assert att.persona == "planejador"
    assert att.model_requested == "gpt-4o"
    assert att.model_used == "gpt-4o-2024-08-06"
    assert att.cost_currency == "USD"
    assert att.cost_source == "openrouter"
    assert att.cost_estimated == 0.0035
    assert att.request_params_json is not None
    assert "stream" in att.request_params_json
    assert att.downstream_router_mutations is False
    assert att.is_regular_finish is True
    assert att.finish_reason == "stop"


@pytest.mark.asyncio
async def test_additive_migration_idempotent_on_legacy_database_with_data() -> None:
    """Verifica migração aditiva em SQLite antigo com registros existentes e prova de idempotência."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
        tmp_db_path = tmp_file.name

    try:
        db_url = f"sqlite+aiosqlite:///{tmp_db_path}"
        engine = create_engine_with_pragmas(db_url)

        # 1. Cria esquema antigo (apenas colunas originais das tabelas legadas)
        async with engine.begin() as conn:
            await conn.execute(text("""
                CREATE TABLE pesquisa (
                    id_pesquisa VARCHAR(36) PRIMARY KEY,
                    tema TEXT NOT NULL,
                    criado_em VARCHAR(30) NOT NULL,
                    dossier_final TEXT,
                    reasoning_dossier TEXT,
                    concluido_em VARCHAR(30),
                    webhook_status VARCHAR(30),
                    webhook_resposta TEXT
                );
            """))
            await conn.execute(text("""
                CREATE TABLE pontos (
                    ponto_id VARCHAR(36) PRIMARY KEY,
                    id_pesquisa VARCHAR(36) NOT NULL,
                    tema TEXT NOT NULL,
                    ponto_n INTEGER NOT NULL,
                    ponto TEXT NOT NULL,
                    status VARCHAR(20) NOT NULL DEFAULT 'pendente',
                    tentativas INTEGER NOT NULL DEFAULT 0,
                    criado_em VARCHAR(30) NOT NULL,
                    atualizado_em VARCHAR(30) NOT NULL
                );
            """))
            await conn.execute(text("""
                CREATE TABLE conteudo_coletado (
                    id VARCHAR(36) PRIMARY KEY,
                    id_pesquisa VARCHAR(36) NOT NULL,
                    ponto_id VARCHAR(36) NOT NULL,
                    rodada INTEGER NOT NULL DEFAULT 1,
                    tema TEXT NOT NULL,
                    ponto TEXT NOT NULL,
                    conteudo_coletado TEXT NOT NULL,
                    reasoning_coleta TEXT,
                    urls_lidas TEXT NOT NULL,
                    urls_fonte TEXT NOT NULL,
                    criado_em VARCHAR(30) NOT NULL
                );
            """))

            # Insere dados legados pré-existentes
            await conn.execute(text("""
                INSERT INTO pesquisa (id_pesquisa, tema, criado_em)
                VALUES ('pesq-legacy-001', 'Tema Legado Histórico', '2026-10-22T10:00:00Z');
            """))
            await conn.execute(text("""
                INSERT INTO pontos (ponto_id, id_pesquisa, tema, ponto_n, ponto, status, criado_em, atualizado_em)
                VALUES ('ponto-legacy-001', 'pesq-legacy-001', 'Tema Legado Histórico', 1, 'Ponto Legado', 'pendente', '2026-10-22T10:00:00Z', '2026-10-22T10:00:00Z');
            """))

        # 2. Executa a primeira migração aditiva via init_db
        status_info1 = await init_db(engine)
        assert status_info1["status"] == "inicializado"

        # Confere que colunas novas foram adicionadas e dados antigos foram preservados
        async with engine.connect() as conn:
            res_pesq = await conn.execute(text("SELECT id_pesquisa, tema, plano_estruturado, status_pipeline FROM pesquisa WHERE id_pesquisa = 'pesq-legacy-001';"))
            row_pesq = res_pesq.fetchone()
            assert row_pesq is not None
            assert row_pesq[0] == "pesq-legacy-001"
            assert row_pesq[1] == "Tema Legado Histórico"
            # O campo novo para registro legado deve ser honestamente NULL, nunca inventado
            assert row_pesq[2] is None
            assert row_pesq[3] == "planejado"

            res_ponto = await conn.execute(text("SELECT ponto_id, ponto, eixo_estruturado, reasoning_auditoria FROM pontos WHERE ponto_id = 'ponto-legacy-001';"))
            row_ponto = res_ponto.fetchone()
            assert row_ponto is not None
            assert row_ponto[0] == "ponto-legacy-001"
            assert row_ponto[2] is None
            assert row_ponto[3] is None

            # Verifica criação da tabela de telemetria generation_attempts
            res_tables = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table';"))
            tables = {r[0] for r in res_tables.fetchall()}
            assert "generation_attempts" in tables

            # Verifica criação dos índices declarados
            res_indices = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='index';"))
            indices = {r[0] for r in res_indices.fetchall()}
            assert "idx_gen_attempts_pesquisa" in indices
            assert "idx_pontos_id_pesquisa_status" in indices

        # Leitura ORM real sobre os registros legados sem erros de mapeamento
        async_session = async_sessionmaker(engine, expire_on_commit=False)
        async with async_session() as session:
            pesq_orm = await session.get(Pesquisa, "pesq-legacy-001")
            assert pesq_orm is not None
            assert pesq_orm.tema == "Tema Legado Histórico"
            assert pesq_orm.plano_estruturado is None
            assert pesq_orm.status_pipeline == "planejado"

            ponto_orm = await session.get(Ponto, "ponto-legacy-001")
            assert ponto_orm is not None
            assert ponto_orm.ponto == "Ponto Legado"
            assert ponto_orm.eixo_estruturado is None
            assert ponto_orm.reasoning_auditoria is None

        # 3. Executa a segunda migração (prova de idempotência)
        status_info2 = await init_db(engine)
        assert status_info2["status"] == "inicializado"

        # Confere que os dados continuam exatamente intactos
        async with engine.connect() as conn:
            res_pesq2 = await conn.execute(text("SELECT id_pesquisa, tema FROM pesquisa WHERE id_pesquisa = 'pesq-legacy-001';"))
            row_pesq2 = res_pesq2.fetchone()
            assert row_pesq2 is not None
            assert row_pesq2[0] == "pesq-legacy-001"

        await engine.dispose()

    finally:
        if os.path.exists(tmp_db_path):
            os.remove(tmp_db_path)


@pytest.mark.asyncio
async def test_atomic_rollback_on_construction_failure(db_session: AsyncSession) -> None:
    """Verifica rollback atômico quando ocorre erro durante a construção dos objetos (R2-F12)."""
    repo = ResearchRepository(session=db_session)
    pesquisa_id = f"pesq-fail-const-{uuid.uuid4().hex[:8]}"

    # Objeto não serializável em json causa TypeError durante a construção
    invalid_attempts = [
        {"id": "att-const-001", "usage": object(), "etapa": "plan", "persona": "planejador"},
    ]

    with pytest.raises(TypeError):
        await repo.create_research(
            id_pesquisa=pesquisa_id,
            tema="Tema com Erro de Construção",
            pontos_textos=["Ponto 1"],
            generation_attempts=invalid_attempts,
        )

    # Prova que nenhum objeto permaneceu na sessão ou foi persistido
    pesq = await repo.get_research(pesquisa_id)
    assert pesq is None, "Rollback atômico deve descartar a pesquisa"
    pontos = await repo.list_points(pesquisa_id)
    assert len(pontos) == 0
    attempts = await repo.get_generation_attempts(pesquisa_id)
    assert len(attempts) == 0


@pytest.mark.asyncio
async def test_atomic_rollback_on_telemetry_persistence_failure(db_session: AsyncSession) -> None:
    """Verifica rollback atômico quando ocorre erro no commit (F-03, F-11, R2-F12)."""
    repo = ResearchRepository(session=db_session)
    pesquisa_id = f"pesq-fail-commit-{uuid.uuid4().hex[:8]}"

    # Dois attempts com a mesma chave primária forçam IntegrityError durante commit
    duplicate_attempts = [
        {"id": "dupe-attempt-001", "etapa": "plan", "persona": "planejador"},
        {"id": "dupe-attempt-001", "etapa": "plan", "persona": "avaliador_semantico"},
    ]

    with pytest.raises(Exception):
        await repo.create_research(
            id_pesquisa=pesquisa_id,
            tema="Tema com Falha Forçada de Telemetria",
            pontos_textos=["Ponto 1", "Ponto 2"],
            generation_attempts=duplicate_attempts,
        )

    # Prova que o rollback atômico ocorreu e nenhum registro parcial foi gravado
    pesq = await repo.get_research(pesquisa_id)
    assert pesq is None, "Rollback atômico deve garantir que pesquisa não foi gravada"

    pontos = await repo.list_points(pesquisa_id)
    assert len(pontos) == 0, "Rollback atômico deve garantir que pontos não foram gravados"

    attempts = await repo.get_generation_attempts(pesquisa_id)
    assert len(attempts) == 0, "Rollback atômico deve garantir que attempts não foram gravados"
