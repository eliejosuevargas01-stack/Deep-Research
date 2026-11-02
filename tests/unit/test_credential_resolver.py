"""Testes unitários para o serviço credential_resolver.

Garante que a resolução de parâmetros e credenciais reflete a precedência da base
cifrada sobre o ambiente (Adendo 002 / Revisão RN-10).
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.credentials_repository import CredentialsRepository
from app.services.credential_resolver import (
    resolve_key,
    resolve_n_pontos,
    resolve_personas,
    resolve_callback_webhook_url,
    resolve_webhook_hmac_secret,
)
from app.services.crypto_service import CryptoService


@pytest.mark.asyncio
async def test_resolve_key_precedence_and_fallback(
    db_session: AsyncSession, crypto_service: CryptoService, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verifica que resolve_key respeita precedência: banco cifrado > ambiente > None."""
    chave = "TEST_RESOLVE_KEY"
    repo = CredentialsRepository(session=db_session, crypto_service=crypto_service)

    # 1. Ausente em ambos -> None
    monkeypatch.delenv(chave, raising=False)
    assert await resolve_key(db_session, chave) is None

    # 2. Presente apenas no ambiente -> lê do ambiente
    monkeypatch.setenv(chave, "env-value")
    assert await resolve_key(db_session, chave) == "env-value"

    # 3. Presente em ambos -> banco cifrado vence
    await repo.save_credential(chave=chave, valor="db-encrypted-value", tipo="llm")
    assert await resolve_key(db_session, chave) == "db-encrypted-value"

    # 4. Com test_transport -> retorna None para os callers usarem mocks
    assert await resolve_key(db_session, chave, test_transport=object()) is None


@pytest.mark.asyncio
async def test_resolve_n_pontos(
    db_session: AsyncSession, crypto_service: CryptoService, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verifica resolução do parâmetro N_PONTOS com conversão de tipo e precedência."""
    repo = CredentialsRepository(session=db_session, crypto_service=crypto_service)
    monkeypatch.delenv("N_PONTOS", raising=False)

    # Ausente -> None
    assert await resolve_n_pontos(db_session) is None

    # Ambiente
    monkeypatch.setenv("N_PONTOS", "5")
    assert await resolve_n_pontos(db_session) == 5

    # Banco tem precedência
    await repo.save_credential(chave="N_PONTOS", valor="8", tipo="parametro")
    assert await resolve_n_pontos(db_session) == 8

    # Valor inválido (não numérico ou <= 0)
    await repo.save_credential(chave="N_PONTOS", valor="-1", tipo="parametro")
    assert await resolve_n_pontos(db_session) is None


@pytest.mark.asyncio
async def test_resolve_personas(
    db_session: AsyncSession, crypto_service: CryptoService, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verifica resolução de lista de personas separadas por vírgula."""
    repo = CredentialsRepository(session=db_session, crypto_service=crypto_service)
    monkeypatch.delenv("PERSONAS_CONFIG", raising=False)

    # Ausente -> lista vazia
    assert await resolve_personas(db_session) == []

    # Ambiente
    monkeypatch.setenv("PERSONAS_CONFIG", "generalist, skeptic")
    assert await resolve_personas(db_session) == ["generalist", "skeptic"]

    # Banco tem precedência
    await repo.save_credential(
        chave="PERSONAS_CONFIG", valor="academic, journalist, investigator", tipo="parametro"
    )
    assert await resolve_personas(db_session) == ["academic", "journalist", "investigator"]


@pytest.mark.asyncio
async def test_resolve_webhooks(
    db_session: AsyncSession, crypto_service: CryptoService, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verifica resolução de CALLBACK_WEBHOOK_URL e WEBHOOK_HMAC_SECRET no banco cifrado."""
    repo = CredentialsRepository(session=db_session, crypto_service=crypto_service)
    monkeypatch.delenv("CALLBACK_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("WEBHOOK_HMAC_SECRET", raising=False)

    # Salva webhook e hmac no banco
    await repo.save_credential(
        chave="CALLBACK_WEBHOOK_URL", valor="https://hook.com/cb", tipo="webhook"
    )
    await repo.save_credential(
        chave="WEBHOOK_HMAC_SECRET", valor="super-hmac-secret", tipo="webhook"
    )

    assert await resolve_callback_webhook_url(db_session) == "https://hook.com/cb"
    assert await resolve_webhook_hmac_secret(db_session) == "super-hmac-secret"
