"""Serviço de criptografia simétrica reversível com Fernet.

Utilizado para proteção de credenciais em repouso com base na chave CREDENTIALS_MASTER_KEY.
Atende a DT-03, RN-10 e RF-12.
"""

import os
from typing import Optional
from cryptography.fernet import Fernet, InvalidToken
from app.config import get_settings


class CryptoService:
    """Serviço de criptografia simétrica baseado no algoritmo Fernet."""

    def __init__(self, master_key: Optional[str] = None) -> None:
        key = master_key or os.environ.get("CREDENTIALS_MASTER_KEY")
        if not key:
            settings = get_settings()
            key = settings.credentials_master_key

        if not key:
            raise ValueError("Chave mestra de criptografia ausente: defina CREDENTIALS_MASTER_KEY.")

        # Validação do formato Fernet (32 bytes em base64 URL-safe)
        try:
            if isinstance(key, str):
                key_bytes = key.strip().encode("utf-8")
            else:
                key_bytes = key
            self._fernet = Fernet(key_bytes)
        except Exception as exc:
            raise ValueError(f"Chave CREDENTIALS_MASTER_KEY inválida para Fernet: [REDACTED]") from exc

    def encrypt(self, plain_text: str) -> str:
        """Cifra uma string em texto claro e retorna token Fernet codificado em Base64."""
        if plain_text is None:
            raise ValueError("O texto a ser cifrado não pode ser nulo.")
        token_bytes = self._fernet.encrypt(plain_text.encode("utf-8"))
        return token_bytes.decode("utf-8")

    def decrypt(self, cipher_text: str) -> str:
        """Decifra token Fernet e retorna texto claro original."""
        if cipher_text is None:
            raise ValueError("O token a ser decifrado não pode ser nulo.")
        try:
            plain_bytes = self._fernet.decrypt(cipher_text.encode("utf-8"))
            return plain_bytes.decode("utf-8")
        except InvalidToken as exc:
            raise ValueError("Falha na decifragem da credencial com a chave mestra ativa.") from exc

    # ponytail: suporte a MultiFernet para rotação de chaves mestras sem downtime pode ser adicionado aqui.
