"""Módulo de conexão e gerenciamento de sessões assíncronas do banco de dados.

Configura SQLAlchemy 2.0 com aiosqlite e ativação obrigatória de pragmas WAL,
foreign_keys, synchronous e busy_timeout. Atende a DT-02 e RNF-08.
"""

import os
from typing import AsyncGenerator, Optional
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from app.config import get_settings


def _set_sqlite_pragmas(dbapi_connection, connection_record) -> None:
    """Configura pragmas de integridade e alta concorrência WAL no SQLite."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode = WAL;")
    cursor.execute("PRAGMA synchronous = NORMAL;")
    cursor.execute("PRAGMA foreign_keys = ON;")
    cursor.execute("PRAGMA busy_timeout = 30000;")
    cursor.close()


def create_engine_with_pragmas(database_url: str) -> AsyncEngine:
    """Cria instância de engine assíncrona com os pragmas WAL configurados."""
    if not database_url:
        raise ValueError("DATABASE_URL não pode ser vazia.")
    engine = create_async_engine(database_url, echo=False)
    event.listen(engine.sync_engine, "connect", _set_sqlite_pragmas)
    return engine


_engine: Optional[AsyncEngine] = None
_sessionmaker: Optional[async_sessionmaker[AsyncSession]] = None


def get_engine() -> AsyncEngine:
    """Retorna engine assíncrono configurado via variável de ambiente DATABASE_URL."""
    global _engine
    if _engine is None:
        url = os.environ.get("DATABASE_URL")
        if not url:
            url = get_settings().database_url
        if not url:
            raise ValueError("Configuração ausente: DATABASE_URL deve ser definida via ambiente ou .env.")
        _engine = create_engine_with_pragmas(url)
    return _engine


# ponytail: pooling básico do aiosqlite; evoluir se houver migração para banco relacional externo
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Retorna factory assíncrona de sessões SQLAlchemy."""
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
    return _sessionmaker


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Gerador assíncrono de sessões de banco de dados para injeção de dependência."""
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        yield session


def reset_engine() -> None:
    """Limpa referências de engine e sessionmaker para fins de isolamento em testes."""
    global _engine, _sessionmaker
    _engine = None
    _sessionmaker = None
