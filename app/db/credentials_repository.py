"""Repositório de credenciais com criptografia Fernet em repouso.

Aplica estritamente a regra RN-10: variáveis de ambiente (os.environ) possuem
precedência imediata sobre as chaves cifradas na base de dados.
Atende a RF-11, RF-12 e RN-10.
"""

from datetime import datetime, timezone
import os
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Credencial
from app.services.crypto_service import CryptoService


class CredentialsRepository:
    """Acesso e persistência a credenciais sensíveis cifradas em repouso."""

    def __init__(self, session: AsyncSession, crypto_service: Optional[CryptoService] = None) -> None:
        self.session = session
        self.crypto_service = crypto_service or CryptoService()

    async def get_credential(self, chave: str) -> str:
        """Obtém credencial respeitando precedência estrita: ENV primeiro, depois BD cifrado."""
        # 1. Precedência absoluta de variáveis de ambiente (RN-10)
        env_value = os.environ.get(chave)
        if env_value is not None and env_value.strip() != "":
            return env_value.strip()

        # 2. Busca na base de dados relacional cifrada
        stmt = select(Credencial).where(Credencial.chave == chave)
        result = await self.session.execute(stmt)
        record = result.scalar_one_or_none()

        if record is not None:
            return self.crypto_service.decrypt(record.valor_cifrado)

        # 3. Ausente em ambos: erro explícito sem fallback hardcoded
        raise ValueError(
            f"Credencial ausente: '{chave}' não foi encontrada em variáveis de ambiente nem na base de dados."
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
        if not valor:
            raise ValueError("O 'valor' da credencial não pode ser nulo ou vazio.")

        chave_clean = chave.strip()
        valor_cifrado = self.crypto_service.encrypt(valor)
        agora = datetime.now(timezone.utc).isoformat()

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
            is_env = rec.chave in os.environ and bool(os.environ[rec.chave].strip())
            origem = "ambiente" if is_env else "banco_cifrado"

            try:
                raw_val = os.environ[rec.chave] if is_env else self.crypto_service.decrypt(rec.valor_cifrado)
                masked_val = self._mask_value(raw_val, rec.tipo)
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
        if tipo == "webhook" or value.startswith("http://") or value.startswith("https://"):
            return value
        if len(value) <= 8:
            return "[REDACTED]"
        return f"{value[:4]}****{value[-4:]}"

    # ponytail: suporte a deleção e expiração temporal de credenciais pode ser adicionado aqui
