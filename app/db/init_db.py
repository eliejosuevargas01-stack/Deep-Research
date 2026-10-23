"""Rotina de inicialização idempotente do banco de dados relacional.

Executa DDL inicial (create_all) e valida os pragmas WAL e integridade no boot.
Atende a DT-02 e RNF-08.
"""

from typing import Any, Dict, Optional
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from app.db.models import Base
from app.db.session import get_engine


# ponytail: create_all idempotente direto; adotar migrações Alembic com revisões versionadas para evolução futura
async def init_db(engine: Optional[AsyncEngine] = None) -> Dict[str, Any]:
    """Inicializa o esquema de tabelas e valida pragmas no SQLite permanente."""
    db_engine = engine or get_engine()

    # Criação idempotente de todas as tabelas e índices
    async with db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

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
