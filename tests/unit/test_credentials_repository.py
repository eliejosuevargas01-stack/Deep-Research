"""Testes unitários para CredentialsRepository.

Cobre persistência cifrada com Fernet, precedência da base de dados cifrada
sobre variáveis de ambiente (com fallback no os.environ), sanitização e mascaramento de saída.
Atende a RF-11 e RF-12.
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
async def test_database_precedence_over_environment(
    db_session: AsyncSession, crypto_service: CryptoService, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verifica que o valor do banco de dados cifrado possui precedência sobre o ambiente."""
    chave = "SHARED_KEY_DB_PRECEDENCE"
    valor_banco = "valor-salvo-no-banco-cifrado"
    valor_ambiente = "valor-do-ambiente-fallback-xyz"

    repo = CredentialsRepository(session=db_session, crypto_service=crypto_service)
    await repo.save_credential(chave=chave, valor=valor_banco, tipo="llm")

    # Define também no ambiente: o valor do banco cifrado deve ter precedência imediata
    monkeypatch.setenv(chave, valor_ambiente)

    obtido = await repo.get_credential(chave)
    assert obtido == valor_banco
    assert obtido != valor_ambiente


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

    with pytest.raises(ValueError, match="não pode ser nulo ou vazio"):
        await repo.save_credential(chave="CHAVE", valor="   ", tipo="llm")


@pytest.mark.asyncio
async def test_get_credential_fallback_when_database_value_is_empty(
    db_session: AsyncSession, crypto_service: CryptoService, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verifica fallback para o ambiente quando a credencial no banco existe mas tem valor vazio."""
    chave = "EMPTY_DB_KEY"
    valor_ambiente = "valor-do-ambiente-quando-db-vazio"
    monkeypatch.setenv(chave, valor_ambiente)

    empty_rec = Credencial(
        chave=chave,
        valor_cifrado="",
        tipo="llm",
        atualizado_em="2026-10-26T00:00:00Z",
    )
    db_session.add(empty_rec)
    await db_session.commit()

    repo = CredentialsRepository(session=db_session, crypto_service=crypto_service)
    obtido = await repo.get_credential(chave)
    assert obtido == valor_ambiente


@pytest.mark.asyncio
async def test_list_sanitized_masking(
    db_session: AsyncSession, crypto_service: CryptoService, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verifica que list_sanitized mascara segredos e identifica corretamente a origem ativa segundo precedência."""
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

    # 3. Webhook URL (deve ser preservada na íntegra por ser URL http/https)
    webhook_url = "https://meu-webhook.com/api"
    await repo.save_credential(
        chave="WEBHOOK_URL",
        valor=webhook_url,
        tipo="webhook",
    )

    # 4. Credencial presente no banco com valor vazio, mas definida no ambiente
    empty_db_rec = Credencial(
        chave="ENV_FALLBACK_KEY",
        valor_cifrado="",
        tipo="llm",
        atualizado_em="2026-10-26T00:00:00Z",
    )
    db_session.add(empty_db_rec)
    await db_session.commit()

    # 5. Webhook HMAC Secret (deve ser mascarado mesmo com tipo="webhook" - REV-SEC-001 / REV-LOG-002)
    webhook_secret = "super-secret-hmac-token-xyz-123456"
    await repo.save_credential(
        chave="WEBHOOK_HMAC_SECRET",
        valor=webhook_secret,
        tipo="webhook",
    )

    # Define no ambiente: banco tem precedência sobre LONG_SECRET_KEY; ENV_FALLBACK_KEY usa ambiente
    monkeypatch.setenv("LONG_SECRET_KEY", "sk-override-env-key-99999999")
    monkeypatch.setenv("ENV_FALLBACK_KEY", "sk-fallback-env-99887766")
    monkeypatch.delenv("SHORT_KEY", raising=False)
    monkeypatch.delenv("WEBHOOK_URL", raising=False)
    monkeypatch.delenv("WEBHOOK_HMAC_SECRET", raising=False)

    sanitized = await repo.list_sanitized()
    item_map = {item["chave"]: item for item in sanitized}

    # Validações: Banco tem precedência se possuir valor válido decifrável
    assert item_map["LONG_SECRET_KEY"]["origem_ativa"] == "banco_cifrado"
    assert item_map["LONG_SECRET_KEY"]["mascarado"].startswith("sk-s****")

    assert item_map["SHORT_KEY"]["origem_ativa"] == "banco_cifrado"
    assert item_map["SHORT_KEY"]["mascarado"] == "[REDACTED]"

    assert item_map["WEBHOOK_URL"]["origem_ativa"] == "banco_cifrado"
    assert item_map["WEBHOOK_URL"]["mascarado"] == webhook_url

    # Validação REV-SEC-001/REV-LOG-002: WEBHOOK_HMAC_SECRET nunca pode vazar em texto claro
    assert item_map["WEBHOOK_HMAC_SECRET"]["origem_ativa"] == "banco_cifrado"
    assert item_map["WEBHOOK_HMAC_SECRET"]["mascarado"] != webhook_secret
    assert item_map["WEBHOOK_HMAC_SECRET"]["mascarado"] == "supe****3456"

    # Validações: Ambiente é origem ativa se registro no banco estiver vazio
    assert item_map["ENV_FALLBACK_KEY"]["origem_ativa"] == "ambiente"
    assert item_map["ENV_FALLBACK_KEY"]["mascarado"].startswith("sk-f****")


@pytest.mark.asyncio
async def test_get_credential_corrupted_cipher_fallback_to_env(
    db_session: AsyncSession, crypto_service: CryptoService, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verifica que erro de decifragem no banco aciona o fallback limpo para a variável de ambiente."""
    chave = "CORRUPTED_CIPHER_FALLBACK"
    valor_ambiente = "valor-recuperado-do-ambiente-123"
    monkeypatch.setenv(chave, valor_ambiente)

    corrupted_rec = Credencial(
        chave=chave,
        valor_cifrado="invalid-corrupted-token-base64",
        tipo="llm",
        atualizado_em="2026-10-26T00:00:00Z",
    )
    db_session.add(corrupted_rec)
    await db_session.commit()

    repo = CredentialsRepository(session=db_session, crypto_service=crypto_service)
    obtido = await repo.get_credential(chave)
    assert obtido == valor_ambiente


@pytest.mark.asyncio
async def test_get_credential_corrupted_cipher_without_env_raises_value_error(
    db_session: AsyncSession, crypto_service: CryptoService, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verifica que erro de decifragem no banco sem variável de ambiente levanta ValueError explícito."""
    chave = "CORRUPTED_CIPHER_NO_ENV"
    monkeypatch.delenv(chave, raising=False)

    corrupted_rec = Credencial(
        chave=chave,
        valor_cifrado="invalid-corrupted-token-base64",
        tipo="llm",
        atualizado_em="2026-10-26T00:00:00Z",
    )
    db_session.add(corrupted_rec)
    await db_session.commit()

    repo = CredentialsRepository(session=db_session, crypto_service=crypto_service)
    with pytest.raises(ValueError, match="Credencial ausente: 'CORRUPTED_CIPHER_NO_ENV'"):
        await repo.get_credential(chave)


@pytest.mark.asyncio
async def test_get_credential_whitespace_in_env_raises_value_error(
    db_session: AsyncSession, crypto_service: CryptoService, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verifica que valor composto apenas por espaços em branco no ambiente é rejeitado com ValueError."""
    chave = "WHITESPACE_ENV_KEY"
    monkeypatch.setenv(chave, "   \t\n   ")

    repo = CredentialsRepository(session=db_session, crypto_service=crypto_service)
    with pytest.raises(ValueError, match="Credencial ausente: 'WHITESPACE_ENV_KEY'"):
        await repo.get_credential(chave)


@pytest.mark.asyncio
async def test_get_credential_record_lookup(
    db_session: AsyncSession, crypto_service: CryptoService
) -> None:
    """Verifica consulta direta de registro bruto com get_credential_record."""
    repo = CredentialsRepository(session=db_session, crypto_service=crypto_service)

    # Inexistente
    rec_none = await repo.get_credential_record("NON_EXISTENT_KEY")
    assert rec_none is None

    # Existente
    salvo = await repo.save_credential(
        chave="EXISTS_RECORD", valor="segredo", tipo="llm", descricao="Descricao teste"
    )
    rec_existente = await repo.get_credential_record("EXISTS_RECORD")
    assert rec_existente is not None
    assert rec_existente.chave == "EXISTS_RECORD"
    assert rec_existente.descricao == "Descricao teste"


@pytest.mark.asyncio
async def test_list_sanitized_handles_corrupted_db_and_plain_urls(
    db_session: AsyncSession, crypto_service: CryptoService, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verifica sanitização quando DB possui cifra corrompida e para endpoints http/https genéricos."""
    chave_corrupted_no_env = "CORRUPTED_NO_ENV"
    chave_corrupted_with_env = "CORRUPTED_WITH_ENV"
    chave_url_param = "CUSTOM_API_ENDPOINT"

    monkeypatch.delenv(chave_corrupted_no_env, raising=False)
    monkeypatch.setenv(chave_corrupted_with_env, "sk-valid-env-token-456789")
    monkeypatch.delenv(chave_url_param, raising=False)

    rec1 = Credencial(
        chave=chave_corrupted_no_env,
        valor_cifrado="bad-cipher",
        tipo="llm",
        atualizado_em="2026-10-26T00:00:00Z",
    )
    rec2 = Credencial(
        chave=chave_corrupted_with_env,
        valor_cifrado="bad-cipher",
        tipo="llm",
        atualizado_em="2026-10-26T00:00:00Z",
    )
    db_session.add_all([rec1, rec2])
    await db_session.commit()

    repo = CredentialsRepository(session=db_session, crypto_service=crypto_service)
    await repo.save_credential(
        chave=chave_url_param,
        valor="http://internal-service.local/v1",
        tipo="parametro",
    )

    sanitized = await repo.list_sanitized()
    item_map = {item["chave"]: item for item in sanitized}

    # Cifra corrompida sem env -> [REDACTED] e origem banco_cifrado
    assert item_map[chave_corrupted_no_env]["origem_ativa"] == "banco_cifrado"
    assert item_map[chave_corrupted_no_env]["mascarado"] == "[REDACTED]"

    # Cifra corrompida com env -> mascaramento do env e origem ambiente
    assert item_map[chave_corrupted_with_env]["origem_ativa"] == "ambiente"
    assert item_map[chave_corrupted_with_env]["mascarado"].startswith("sk-v****")

    # URL genérica http:// ou https:// não é ofuscada
    assert item_map[chave_url_param]["origem_ativa"] == "banco_cifrado"
    assert item_map[chave_url_param]["mascarado"] == "http://internal-service.local/v1"

