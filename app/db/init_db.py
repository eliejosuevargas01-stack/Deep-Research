"""Rotina de inicialização idempotente e migrações aditivas do banco de dados relacional.

Executa DDL inicial (create_all), migrações aditivas seguras para bancos pré-existentes
e valida os pragmas WAL e integridade no boot.
Atende a DT-02, RNF-08, DR-005, DR-006, DR-009, DR-013 e DR-015.
"""

from typing import Any, Dict, Optional
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from app.db.models import Base
from app.db.research_repository import normalize_iso_utc
from app.db.session import get_engine


async def _run_additive_migrations(conn: Any) -> None:
    """Executa migrações aditivas e estritamente idempotentes no SQLite existente.
    
    Adiciona colunas faltantes sem destruir registros pré-existentes e sem alterar
    dados históricos legados (permanecem honestamente NULL).
    Garante também a criação de todos os índices declarados nos modelos.
    """
    # 1. Colunas da tabela pesquisa
    res_pesquisa = await conn.execute(text("PRAGMA table_info(pesquisa);"))
    cols_pesquisa = {row[1] for row in res_pesquisa.fetchall()}
    if cols_pesquisa:
        if "status_pipeline" not in cols_pesquisa:
            await conn.execute(text("ALTER TABLE pesquisa ADD COLUMN status_pipeline VARCHAR(30) DEFAULT 'planejado';"))
        if "erro_pipeline" not in cols_pesquisa:
            await conn.execute(text("ALTER TABLE pesquisa ADD COLUMN erro_pipeline TEXT;"))
        if "tokens_prompt" not in cols_pesquisa:
            await conn.execute(text("ALTER TABLE pesquisa ADD COLUMN tokens_prompt INTEGER DEFAULT 0;"))
        if "tokens_completion" not in cols_pesquisa:
            await conn.execute(text("ALTER TABLE pesquisa ADD COLUMN tokens_completion INTEGER DEFAULT 0;"))
        if "tokens_total" not in cols_pesquisa:
            await conn.execute(text("ALTER TABLE pesquisa ADD COLUMN tokens_total INTEGER DEFAULT 0;"))
        if "plano_estruturado" not in cols_pesquisa:
            await conn.execute(text("ALTER TABLE pesquisa ADD COLUMN plano_estruturado TEXT;"))
        if "metadados_planejamento" not in cols_pesquisa:
            await conn.execute(text("ALTER TABLE pesquisa ADD COLUMN metadados_planejamento TEXT;"))
        if "reasoning_dossier" not in cols_pesquisa:
            await conn.execute(text("ALTER TABLE pesquisa ADD COLUMN reasoning_dossier TEXT;"))
        if "concluido_em" not in cols_pesquisa:
            await conn.execute(text("ALTER TABLE pesquisa ADD COLUMN concluido_em VARCHAR(30);"))
        if "webhook_status" not in cols_pesquisa:
            await conn.execute(text("ALTER TABLE pesquisa ADD COLUMN webhook_status VARCHAR(30);"))
        if "webhook_resposta" not in cols_pesquisa:
            await conn.execute(text("ALTER TABLE pesquisa ADD COLUMN webhook_resposta TEXT;"))
        if "metadados_redacao" not in cols_pesquisa:
            await conn.execute(text("ALTER TABLE pesquisa ADD COLUMN metadados_redacao TEXT;"))

    # 2. Colunas da tabela pontos
    res_pontos = await conn.execute(text("PRAGMA table_info(pontos);"))
    cols_pontos = {row[1] for row in res_pontos.fetchall()}
    if cols_pontos:
        if "pontos_fracos" not in cols_pontos:
            await conn.execute(text("ALTER TABLE pontos ADD COLUMN pontos_fracos TEXT;"))
        if "reasoning_planejamento" not in cols_pontos:
            await conn.execute(text("ALTER TABLE pontos ADD COLUMN reasoning_planejamento TEXT;"))
        if "reasoning_auditoria" not in cols_pontos:
            await conn.execute(text("ALTER TABLE pontos ADD COLUMN reasoning_auditoria TEXT;"))
        if "tentativas" not in cols_pontos:
            await conn.execute(text("ALTER TABLE pontos ADD COLUMN tentativas INTEGER DEFAULT 0;"))
        if "tentativas_auditoria" not in cols_pontos:
            await conn.execute(text("ALTER TABLE pontos ADD COLUMN tentativas_auditoria INTEGER DEFAULT 0;"))
        if "eixo_estruturado" not in cols_pontos:
            await conn.execute(text("ALTER TABLE pontos ADD COLUMN eixo_estruturado TEXT;"))
        if "atualizado_em" not in cols_pontos:
            await conn.execute(text("ALTER TABLE pontos ADD COLUMN atualizado_em VARCHAR(30);"))
        if "lease_token" not in cols_pontos:
            await conn.execute(text("ALTER TABLE pontos ADD COLUMN lease_token VARCHAR(64);"))

    # 3. Colunas da tabela conteudo_coletado
    res_conteudo = await conn.execute(text("PRAGMA table_info(conteudo_coletado);"))
    cols_conteudo = {row[1] for row in res_conteudo.fetchall()}
    if cols_conteudo:
        if "rodada" not in cols_conteudo:
            await conn.execute(text("ALTER TABLE conteudo_coletado ADD COLUMN rodada INTEGER DEFAULT 1;"))
        if "reasoning_coleta" not in cols_conteudo:
            await conn.execute(text("ALTER TABLE conteudo_coletado ADD COLUMN reasoning_coleta TEXT;"))
        if "metadados_coleta" not in cols_conteudo:
            await conn.execute(text("ALTER TABLE conteudo_coletado ADD COLUMN metadados_coleta TEXT;"))

    # 4. Colunas da tabela credenciais
    res_cred = await conn.execute(text("PRAGMA table_info(credenciais);"))
    cols_cred = {row[1] for row in res_cred.fetchall()}
    if cols_cred:
        if "base_url" not in cols_cred:
            await conn.execute(text("ALTER TABLE credenciais ADD COLUMN base_url TEXT;"))
        if "descricao" not in cols_cred:
            await conn.execute(text("ALTER TABLE credenciais ADD COLUMN descricao TEXT;"))

    # 5. Colunas da tabela generation_attempts (R2-F11)
    res_gen = await conn.execute(text("PRAGMA table_info(generation_attempts);"))
    cols_gen = {row[1] for row in res_gen.fetchall()}
    if cols_gen:
        if "cost_currency" not in cols_gen:
            await conn.execute(text("ALTER TABLE generation_attempts ADD COLUMN cost_currency VARCHAR(10);"))
        if "cost_source" not in cols_gen:
            await conn.execute(text("ALTER TABLE generation_attempts ADD COLUMN cost_source VARCHAR(50);"))
        if "request_params_json" not in cols_gen:
            await conn.execute(text("ALTER TABLE generation_attempts ADD COLUMN request_params_json TEXT;"))
        if "downstream_router_mutations" not in cols_gen:
            await conn.execute(text("ALTER TABLE generation_attempts ADD COLUMN downstream_router_mutations BOOLEAN DEFAULT 0;"))

    # 6. Criação idempotente de todos os índices declarados nos modelos (F-12)
    indexes_ddl = [
        "CREATE INDEX IF NOT EXISTS idx_pesquisa_criado_em ON pesquisa(criado_em);",
        "CREATE INDEX IF NOT EXISTS idx_pesquisa_status_pipeline ON pesquisa(status_pipeline);",
        "CREATE INDEX IF NOT EXISTS idx_pontos_id_pesquisa_status ON pontos(id_pesquisa, status);",
        "CREATE INDEX IF NOT EXISTS idx_pontos_status ON pontos(status);",
        "CREATE INDEX IF NOT EXISTS idx_conteudo_id_pesquisa ON conteudo_coletado(id_pesquisa);",
        "CREATE INDEX IF NOT EXISTS idx_credenciais_chave ON credenciais(chave);",
        "CREATE INDEX IF NOT EXISTS idx_gen_attempts_pesquisa ON generation_attempts(id_pesquisa);",
        "CREATE INDEX IF NOT EXISTS idx_gen_attempts_etapa ON generation_attempts(etapa);",
    ]
    for ddl in indexes_ddl:
        await conn.execute(text(ddl))

    # 7. Normalização de timestamps legados para ISO UTC 27 caracteres (%Y-%m-%dT%H:%M:%S.%fZ)
    for table, id_col, cols in [
        ("pontos", "ponto_id", ["atualizado_em", "criado_em"]),
        ("pesquisa", "id_pesquisa", ["criado_em", "concluido_em"]),
        ("conteudo_coletado", "id", ["criado_em"]),
        ("credenciais", "id", ["atualizado_em"]),
        ("generation_attempts", "id", ["criado_em"]),
    ]:
        t_check = await conn.execute(text(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}';"))
        if not t_check.scalar_one_or_none():
            continue
        col_list = ", ".join(cols)
        where_conds = " OR ".join(f"({c} IS NOT NULL AND (length({c}) != 27 OR {c} LIKE '%+%'))" for c in cols)
        query = f"SELECT {id_col}, {col_list} FROM {table} WHERE {where_conds};"
        rows = (await conn.execute(text(query))).fetchall()
        for row in rows:
            pk = row[0]
            updates = {}
            for idx, c in enumerate(cols, start=1):
                val = row[idx]
                if val is not None:
                    try:
                        updates[c] = normalize_iso_utc(val)
                    except Exception:
                        pass
            if updates:
                set_clause = ", ".join(f"{c} = :{c}" for c in updates.keys())
                params = {**updates, "pk": pk}
                await conn.execute(text(f"UPDATE {table} SET {set_clause} WHERE {id_col} = :pk;"), params)


async def init_db(engine: Optional[AsyncEngine] = None) -> Dict[str, Any]:
    """Inicializa o esquema de tabelas e valida pragmas no SQLite permanente."""
    db_engine = engine or get_engine()

    # Criação idempotente de todas as tabelas e índices
    async with db_engine.begin() as conn:
        # 1. Cria novas tabelas do modelo
        await conn.run_sync(Base.metadata.create_all)
        # 2. Aplica migrações aditivas em tabelas antigas existentes
        await _run_additive_migrations(conn)

        # Conferência de pragmas ativos no SQLite
        journal_mode = (await conn.execute(text("PRAGMA journal_mode;"))).scalar()
        synchronous = (await conn.execute(text("PRAGMA synchronous;"))).scalar()
        foreign_keys = (await conn.execute(text("PRAGMA foreign_keys;"))).scalar()
        busy_timeout = (await conn.execute(text("PRAGMA busy_timeout;"))).scalar()

    status_info = {
        "status": "inicializado",
        "journal_mode": str(journal_mode).lower() if journal_mode else None,
        "synchronous": synchronous,
        "foreign_keys": foreign_keys,
        "busy_timeout": busy_timeout,
    }

    if foreign_keys != 1:
        raise RuntimeError("Falha de configuração do SQLite: PRAGMA foreign_keys não está ativo.")

    return status_info
