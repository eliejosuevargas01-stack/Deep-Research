"""Testes unitários para CredentialsRepository.

Cobre persistência cifrada com Fernet, regra RN-10 de precedência absoluta
de os.environ sobre a base de dados, sanitização e mascaramento de saída.
Atende a RF-11, RF-12 e RN-10.
"""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.credentials_repository import CredentialsRepository
from app.db.models import Credencial
from app.services.crypto_service import CryptoService


@pytest.mark.asyncio
async def test_save_credential_encrypts_and_saves(
    db_session: AsyncSession, crypto_service: CryptoService
) -> None:
    """Verifica que o valor é salvo cifrado no banco e recuperável em texto claro."""
    repo = CredentialsRepository(session=db_session, crypto_service=crypto_service)
    chave = "TEST_API_KEY"
    valor_secreto = "segredo-super-confidencial-998877"

    salvo = await repo.save_credential(
        chave=chave,
        valor=valor_secreto,
        tipo="llm",
        base_url="https://api.openai.com/v1",
        descricao="Chave de teste de integração",
    )
    assert salvo.chave == chave
    assert salvo.valor_cifrado != valor_secreto

    # Verificação direta no banco
    stmt = select(Credencial).where(Credencial.chave == chave)
    record = (await db_session.execute(stmt)).scalar_one()
    assert record.valor_cifrado != valor_secreto
    assert crypto_service.decrypt(record.valor_cifrado) == valor_secreto


@pytest.mark.asyncio
async def test_get_credential_from_database(
    db_session: AsyncSession, crypto_service: CryptoService, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verifica recuperação da credencial da base cifrada quando ausente no ambiente."""
    chave = "DB_ONLY_SECRET"
    valor_secreto = "segredo-do-banco-12345"
    monkeypatch.delenv(chave, raising=False)

    repo = CredentialsRepository(session=db_session, crypto_service=crypto_service)
    await repo.save_credential(chave=chave, valor=valor_secreto, tipo="llm")

    obtido = await repo.get_credential(chave)
    assert obtido == valor_secreto


@pytest.mark.asyncio
async def test_rn10_environment_precedence(
    db_session: AsyncSession, crypto_service: CryptoService, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verifica aplicação estrita da regra RN-10: os.environ sobrepõe a base cifrada."""
    chave = "SHARED_KEY_ENV_PRECEDENCE"
    valor_banco = "valor-salvo-no-banco-cifrado"
    valor_ambiente = "valor-prioritario-do-ambiente-xyz"

    repo = CredentialsRepository(session=db_session, crypto_service=crypto_service)
    await repo.save_credential(chave=chave, valor=valor_banco, tipo="llm")

    # Define no ambiente: deve ter precedência imediata
    monkeypatch.setenv(chave, valor_ambiente)

    obtido = await repo.get_credential(chave)
    assert obtido == valor_ambiente
    assert obtido != valor_banco


@pytest.mark.asyncio
async def test_get_credential_only_in_environment(
    db_session: AsyncSession, crypto_service: CryptoService, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verifica recuperação de credencial definida unicamente no ambiente."""
    chave = "ENV_ONLY_CREDENTIAL"
    valor_ambiente = "apenas-no-ambiente-999"
    monkeypatch.setenv(chave, valor_ambiente)

    repo = CredentialsRepository(session=db_session, crypto_service=crypto_service)
    obtido = await repo.get_credential(chave)
    assert obtido == valor_ambiente


@pytest.mark.asyncio
async def test_get_credential_absent_in_both_raises_value_error(
    db_session: AsyncSession, crypto_service: CryptoService, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verifica erro explícito sem fallback hardcoded quando ausente em ambos (RN-02/RN-10)."""
    chave = "CHAVE_TOTALMENTE_INEXISTENTE"
    monkeypatch.delenv(chave, raising=False)

    repo = CredentialsRepository(session=db_session, crypto_service=crypto_service)
    with pytest.raises(ValueError, match="Credencial ausente: 'CHAVE_TOTALMENTE_INEXISTENTE'"):
        await repo.get_credential(chave)


@pytest.mark.asyncio
async def test_save_credential_updates_existing_record(
    db_session: AsyncSession, crypto_service: CryptoService
) -> None:
    """Verifica atualização idempotente de registro existente sem criar duplicatas."""
    chave = "UPDATABLE_CONFIG_KEY"
    repo = CredentialsRepository(session=db_session, crypto_service=crypto_service)

    await repo.save_credential(chave=chave, valor="versao_1", tipo="parametro")
    await repo.save_credential(
        chave=chave,
        valor="versao_2",
        tipo="parametro",
        base_url="https://updated.url",
        descricao="Atualizada",
    )

    stmt = select(Credencial).where(Credencial.chave == chave)
    records = (await db_session.execute(stmt)).scalars().all()
    assert len(records) == 1
    assert crypto_service.decrypt(records[0].valor_cifrado) == "versao_2"
    assert records[0].base_url == "https://updated.url"


@pytest.mark.asyncio
async def test_save_credential_invalid_inputs(
    db_session: AsyncSession, crypto_service: CryptoService
) -> None:
    """Verifica rejeição de chave ou valor vazios/nulos."""
    repo = CredentialsRepository(session=db_session, crypto_service=crypto_service)

    with pytest.raises(ValueError, match="não pode ser vazio"):
        await repo.save_credential(chave="", valor="valor", tipo="llm")

    with pytest.raises(ValueError, match="não pode ser nulo ou vazio"):
        await repo.save_credential(chave="CHAVE", valor="", tipo="llm")


@pytest.mark.asyncio
async def test_list_sanitized_masking(
    db_session: AsyncSession, crypto_service: CryptoService, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verifica que list_sanitized mascara segredos e identifica corretamente a origem ativa."""
    repo = CredentialsRepository(session=db_session, crypto_service=crypto_service)

    # 1. Credencial longa salva no banco
    await repo.save_credential(
        chave="LONG_SECRET_KEY",
        valor="sk-supersecretkey1234567890",
        tipo="llm",
    )

    # 2. Credencial curta (<= 8 caracteres)
    await repo.save_credential(
        chave="SHORT_KEY",
        valor="curta12",
        tipo="parametro",
    )

    # 3. Webhook URL (deve ser preservada na íntegra)
    webhook_url = "https://meu-webhook.com/api"
    await repo.save_credential(
        chave="WEBHOOK_URL",
        valor=webhook_url,
        tipo="webhook",
    )

    # Simula precedência de ambiente para LONG_SECRET_KEY
    monkeypatch.setenv("LONG_SECRET_KEY", "sk-supersecretkey1234567890")
    monkeypatch.delenv("SHORT_KEY", raising=False)
    monkeypatch.delenv("WEBHOOK_URL", raising=False)

    sanitized = await repo.list_sanitized()
    item_map = {item["chave"]: item for item in sanitized}

    # Validações
    assert item_map["LONG_SECRET_KEY"]["origem_ativa"] == "ambiente"
    assert item_map["LONG_SECRET_KEY"]["mascarado"].startswith("sk-s****")

    assert item_map["SHORT_KEY"]["origem_ativa"] == "banco_cifrado"
    assert item_map["SHORT_KEY"]["mascarado"] == "[REDACTED]"

    assert item_map["WEBHOOK_URL"]["origem_ativa"] == "banco_cifrado"
    assert item_map["WEBHOOK_URL"]["mascarado"] == webhook_url
