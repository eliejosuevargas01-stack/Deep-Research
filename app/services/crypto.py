import base64
import hashlib
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from app.core.config import settings


def _key() -> bytes:
    try:
        key = base64.urlsafe_b64decode(settings.APP_ENCRYPTION_KEY + "===")
        if len(key) == 32:
            return key
    except ValueError:
        pass
    return hashlib.sha256(settings.APP_ENCRYPTION_KEY.encode()).digest()


def encrypt_secret(value: str) -> str:
    nonce = os.urandom(12)
    ciphertext = AESGCM(_key()).encrypt(nonce, value.encode(), b"deep-research/settings/v1")
    return base64.urlsafe_b64encode(nonce + ciphertext).decode()


def decrypt_secret(value: str) -> str:
    raw = base64.urlsafe_b64decode(value)
    return AESGCM(_key()).decrypt(raw[:12], raw[12:], b"deep-research/settings/v1").decode()


def mask_secret(value: str) -> str:
    if len(value) <= 6:
        return "****"
    return f"{value[:3]}{'*' * min(12, len(value) - 5)}{value[-2:]}"
