"""Repositório de credenciais com criptografia Fernet em repouso.

Aplica estritamente a nova diretriz de governança: o banco de dados cifrado possui
precedência sobre as variáveis de ambiente (os.environ), que atuam como fallback.
Atende a RF-11 e RF-12.
"""

from datetime import datetime, timezone
import os
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Credencial
from app.db.research_repository import _format_iso_utc
from app.services.crypto_service import CryptoService


class CredentialsRepository:
    """Acesso e persistência a credenciais sensíveis cifradas em repouso."""

    def __init__(self, session: AsyncSession, crypto_service: Optional[CryptoService] = None) -> None:
        self.session = session
        self.crypto_service = crypto_service or CryptoService()

    async def get_credential(self, chave: str) -> str:
        """Obtém credencial respeitando precedência estrita: BD cifrado primeiro, depois fallback no ambiente."""
        # 1. Consulta o banco de dados cifrado (tabela credenciais)
        stmt = select(Credencial).where(Credencial.chave == chave)
        result = await self.session.execute(stmt)
        record = result.scalar_one_or_none()

        if record is not None and record.valor_cifrado:
            try:
                decrypted = self.crypto_service.decrypt(record.valor_cifrado)
                if decrypted is not None and decrypted.strip() != "":
                    return decrypted.strip()
            except Exception:
                pass

        # 2. Fallback consultando variáveis de ambiente
        env_value = os.environ.get(chave)
        if env_value is not None and env_value.strip() != "":
            return env_value.strip()

        # 3. Ausente em ambos: erro explícito sem fallback hardcoded
        raise ValueError(
            f"Credencial ausente: '{chave}' não foi encontrada na base de dados nem em variáveis de ambiente."
        )

    async def get_credential_record(self, chave: str) -> Optional[Credencial]:
        """Busca o registro bruto de uma credencial na base de dados relacional."""
        stmt = select(Credencial).where(Credencial.chave == chave)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def save_credential(
        self,
        chave: str,
        valor: str,
        tipo: str,
        base_url: Optional[str] = None,
        descricao: Optional[str] = None,
    ) -> Credencial:
        """Cifra e salva/atualiza uma credencial na tabela credenciais."""
        if not chave or not chave.strip():
            raise ValueError("O identificador 'chave' não pode ser vazio.")
        if not valor or not valor.strip():
            raise ValueError("O 'valor' da credencial não pode ser nulo ou vazio.")

        chave_clean = chave.strip()
        valor_cifrado = self.crypto_service.encrypt(valor)
        agora = _format_iso_utc()

        stmt = select(Credencial).where(Credencial.chave == chave_clean)
        result = await self.session.execute(stmt)
        record = result.scalar_one_or_none()

        if record is not None:
            record.valor_cifrado = valor_cifrado
            record.tipo = tipo
            record.base_url = base_url
            record.descricao = descricao
            record.atualizado_em = agora
        else:
            record = Credencial(
                chave=chave_clean,
                valor_cifrado=valor_cifrado,
                base_url=base_url,
                tipo=tipo,
                descricao=descricao,
                atualizado_em=agora,
            )
            self.session.add(record)

        await self.session.commit()
        await self.session.refresh(record)
        return record

    async def list_sanitized(self) -> List[Dict[str, Any]]:
        """Lista credenciais sanitizadas para visualização administrativa (RF-11)."""
        stmt = select(Credencial).order_by(Credencial.chave)
        result = await self.session.execute(stmt)
        records = result.scalars().all()

        sanitized_list = []
        for rec in records:
            decrypted_val: Optional[str] = None
            if rec.valor_cifrado:
                try:
                    decrypted = self.crypto_service.decrypt(rec.valor_cifrado)
                    if decrypted is not None and decrypted.strip() != "":
                        decrypted_val = decrypted.strip()
                except Exception:
                    decrypted_val = None

            is_env = rec.chave in os.environ and bool(os.environ[rec.chave].strip())

            if decrypted_val is not None:
                origem = "banco_cifrado"
                raw_val = decrypted_val
            elif is_env:
                origem = "ambiente"
                raw_val = os.environ[rec.chave].strip()
            else:
                origem = "banco_cifrado"
                raw_val = ""

            try:
                masked_val = self._mask_value(raw_val, rec.tipo) if raw_val else "[REDACTED]"
            except Exception:
                masked_val = "[REDACTED]"

            sanitized_list.append(
                {
                    "chave": rec.chave,
                    "tipo": rec.tipo,
                    "base_url": rec.base_url,
                    "origem_ativa": origem,
                    "mascarado": masked_val,
                    "atualizado_em": rec.atualizado_em,
                }
            )
        return sanitized_list

    @staticmethod
    def _mask_value(value: str, tipo: str) -> str:
        """Aplica máscara de segurança sobre valores sensíveis."""
        if not value:
            return "[REDACTED]"
        if value.startswith("http://") or value.startswith("https://"):
            return value
        if len(value) <= 8:
            return "[REDACTED]"
        return f"{value[:4]}****{value[-4:]}"

    # ponytail: suporte a deleção e expiração temporal de credenciais pode ser adicionado aqui
