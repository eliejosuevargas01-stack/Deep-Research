"""Testes unitários para CryptoService.

Cobre cifragem e decifragem com Fernet, validação de chaves mestras inválidas
ou ausentes e comportamento seguro em erro com redação de segredos.
Atende a DT-03, RN-10 e RF-12.
"""

import os
from cryptography.fernet import Fernet
import pytest
from app.config import get_settings
from app.services.crypto_service import CryptoService


def test_encrypt_and_decrypt_success(test_fernet_key: str) -> None:
    """Verifica cifragem e decifragem bem-sucedida em ciclo completo."""
    service = CryptoService(master_key=test_fernet_key)
    texto_original = "sk-super-secret-api-key-1234567890"

    token = service.encrypt(texto_original)
    assert token != texto_original
    assert isinstance(token, str)

    recuperado = service.decrypt(token)
    assert recuperado == texto_original


def test_fernet_token_uniqueness(test_fernet_key: str) -> None:
    """Verifica que cada cifragem do mesmo texto produz tokens distintos (salting/IV)."""
    service = CryptoService(master_key=test_fernet_key)
    texto = "mesmo_segredo"

    token_1 = service.encrypt(texto)
    token_2 = service.encrypt(texto)

    assert token_1 != token_2
    assert service.decrypt(token_1) == texto
    assert service.decrypt(token_2) == texto


def test_missing_master_key_raises_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifica recusa explícita quando nenhuma chave mestra é informada."""
    monkeypatch.delenv("CREDENTIALS_MASTER_KEY", raising=False)
    get_settings.cache_clear()

    with pytest.raises(ValueError, match="Chave mestra de criptografia ausente"):
        CryptoService(master_key=None)


def test_invalid_master_key_safe_redacted_error() -> None:
    """Verifica que chave mestra inválida é rejeitada e mascarada com [REDACTED]."""
    chave_invalida = "chave-invalida-que-nao-e-base64-32bytes"

    with pytest.raises(ValueError) as exc_info:
        CryptoService(master_key=chave_invalida)

    msg = str(exc_info.value)
    assert "[REDACTED]" in msg
    assert chave_invalida not in msg


def test_decrypt_invalid_or_tampered_token(test_fernet_key: str) -> None:
    """Verifica rejeição segura de token corrompido ou adulterado."""
    service = CryptoService(master_key=test_fernet_key)
    token_adulterado = "gAAAAABlZGVmZ2hpamtsbW5vcHFyc3R1dnd4eXoxMjM0NTY="

    with pytest.raises(ValueError, match="Falha na decifragem da credencial com a chave mestra ativa"):
        service.decrypt(token_adulterado)


def test_decrypt_with_different_key_fails(test_fernet_key: str) -> None:
    """Verifica que decifrar com chave mestra diferente gera erro explícito."""
    service_1 = CryptoService(master_key=test_fernet_key)
    outra_chave = Fernet.generate_key().decode("utf-8")
    service_2 = CryptoService(master_key=outra_chave)

    token = service_1.encrypt("dado_confidencial")

    with pytest.raises(ValueError, match="Falha na decifragem da credencial com a chave mestra ativa"):
        service_2.decrypt(token)


def test_encrypt_none_raises_error(test_fernet_key: str) -> None:
    """Verifica que cifrar None levanta ValueError explicito."""
    service = CryptoService(master_key=test_fernet_key)
    with pytest.raises(ValueError, match="O texto a ser cifrado não pode ser nulo"):
        service.encrypt(None)  # type: ignore[arg-type]


def test_decrypt_none_raises_error(test_fernet_key: str) -> None:
    """Verifica que decifrar None levanta ValueError explicito."""
    service = CryptoService(master_key=test_fernet_key)
    with pytest.raises(ValueError, match="O token a ser decifrado não pode ser nulo"):
        service.decrypt(None)  # type: ignore[arg-type]


def test_crypto_service_uses_environ_when_not_provided(
    test_fernet_key: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verifica inicialização transparente a partir da variável de ambiente CREDENTIALS_MASTER_KEY."""
    monkeypatch.setenv("CREDENTIALS_MASTER_KEY", test_fernet_key)
    service = CryptoService(master_key=None)

    token = service.encrypt("segredo_via_env")
    assert service.decrypt(token) == "segredo_via_env"
