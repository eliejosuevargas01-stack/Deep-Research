"""Configuração global de fixtures e infraestrutura de testes.

Proêve engine SQLite assíncrono temporário em modo WAL, ciclo de sessão limpa
por teste, gerador de chaves Fernet de teste e isolamento de ambiente.
Atende a DT-02 e RNF-08.
"""

import os
from typing import AsyncGenerator
from cryptography.fernet import Fernet
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)

from app.config import get_settings
from app.db.init_db import init_db
from app.db.models import Base
from app.db.session import create_engine_with_pragmas, reset_engine
from app.services.crypto_service import CryptoService


@pytest.fixture
def test_fernet_key() -> str:
    """Gera chave mestra válida para Fernet (32 bytes em base64 URL-safe)."""
    return Fernet.generate_key().decode("utf-8")


@pytest.fixture
def temp_db_path(tmp_path) -> str:
    """Retorna caminho para arquivo temporário SQLite permanente no escopo do teste."""
    db_file = tmp_path / "test_deep_research.db"
    return str(db_file)


@pytest.fixture
def test_env(test_fernet_key: str, temp_db_path: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Configura variáveis de ambiente mínimas para isolamento do teste."""
    monkeypatch.setenv("CREDENTIALS_MASTER_KEY", test_fernet_key)
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{temp_db_path}")
    monkeypatch.setenv("N_PONTOS", "5")
    monkeypatch.setenv(
        "PERSONAS_CONFIG",
        "planejador,historiador,visionario,cetico,futurista,auditor,redator final",
    )
    monkeypatch.setenv("WEBHOOK_HMAC_SECRET", "test-webhook-secret-key-1234567890")
    monkeypatch.setenv("CALLBACK_WEBHOOK_URL", "https://mock.webhook.test/callback")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-mock-api-key-1234567890")
    monkeypatch.setenv("LLM_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setenv("LLM_MODEL_LIGHT", "gpt-4o-mini")
    monkeypatch.setenv("LLM_MODEL_STRONG", "gpt-4o")
    monkeypatch.setenv("Jina_API_KEY", "jina-test-mock-api-key")
    monkeypatch.setenv("Jina_BASE_URL", "https://s.jina.ai")

    get_settings.cache_clear()
    reset_engine()


@pytest_asyncio.fixture
async def async_engine(temp_db_path: str, test_env: None) -> AsyncGenerator[AsyncEngine, None]:
    """Cria engine SQLite assíncrono temporário com modo WAL e inicialização de DDL."""
    database_url = f"sqlite+aiosqlite:///{temp_db_path}"
    engine = create_engine_with_pragmas(database_url)

    # Inicializa DDL e confere pragmas WAL
    await init_db(engine)

    yield engine

    await engine.dispose()
    reset_engine()
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def db_session(async_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Ciclo de sessão assíncrona isolada e limpa por teste."""
    session_factory = async_sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
def crypto_service(test_fernet_key: str) -> CryptoService:
    """Instância do serviço de criptografia simétrica com chave de teste."""
    return CryptoService(master_key=test_fernet_key)


@pytest_asyncio.fixture(autouse=True)
async def init_test_db_if_integration() -> None:
    """Garante que a base de dados dos testes de integração possua as tabelas e colunas atualizadas."""
    current_test = os.environ.get("PYTEST_CURRENT_TEST", "")
    if "tests/integration/" in current_test:
        from app.main import _setup_integration_test_env
        _setup_integration_test_env()
        from app.db.init_db import init_db
        from app.db.session import get_engine
        await init_db(get_engine())
