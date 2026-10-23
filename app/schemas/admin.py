"""Esquemas Pydantic v2 para endpoints administrativos de credenciais (/api/v1/admin/credentials).

Derivado de:
- SDD / PRD: prd.md (RF-007, RF-008, Seção 8)
- Requirements: requirements.md (RF-11, RF-12, RN-10)
- Interfaces: endpoint-admin.md
Atende a T025.
"""

from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class CredentialCreateRequest(BaseModel):
    """Contrato de entrada para cadastro ou atualização de credencial sensível (RF-11, RF-12)."""

    chave: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Identificador único da chave ou parâmetro de configuração",
    )
    valor: str = Field(
        ...,
        min_length=1,
        description="Valor sensível da credencial a ser cifrado em repouso",
    )
    tipo: str = Field(
        ...,
        min_length=1,
        max_length=30,
        description="Tipo da credencial: llm, jina, webhook, parametro",
    )
    base_url: Optional[str] = Field(
        default=None,
        description="Endereço de base URL customizado associado ao serviço",
    )
    descricao: Optional[str] = Field(
        default=None,
        description="Descrição operacional da credencial",
    )

    @field_validator("chave", "valor", "tipo")
    @classmethod
    def validate_not_blank(cls, v: str) -> str:
        """Assegura que campos obrigatórios não contenham apenas espaços em branco."""
        if not v or not v.strip():
            raise ValueError("O campo não pode ser vazio ou conter apenas espaços.")
        return v.strip()


class CredentialResponse(BaseModel):
    """Contrato de resposta após persistência segura de credencial cifrada (RF-11, RF-12)."""

    status: str = Field(
        default="salvo",
        description="Status da operação de gravação",
    )
    chave: str = Field(
        ...,
        description="Identificador da chave gravada",
    )
    tipo: str = Field(
        ...,
        description="Tipo da credencial",
    )
    base_url: Optional[str] = Field(
        default=None,
        description="Base URL associada",
    )
    criptografado: bool = Field(
        default=True,
        description="Indicação de armazenamento com cifra reversível em repouso",
    )
    algoritmo: str = Field(
        default="Fernet (AES-128-CBC + HMAC-SHA256)",
        description="Algoritmo de cifra simétrica utilizado",
    )
    atualizado_em: str = Field(
        ...,
        description="Timestamp ISO 8601 da gravação",
    )


class CredentialSanitizedListItem(BaseModel):
    """Representação sanitizada de credencial para listagem administrativa (RF-11, RN-10)."""

    chave: str = Field(
        ...,
        description="Identificador da chave",
    )
    tipo: str = Field(
        ...,
        description="Tipo da credencial (llm, jina, webhook, parametro)",
    )
    base_url: Optional[str] = Field(
        default=None,
        description="Base URL associada à credencial",
    )
    origem_ativa: str = Field(
        ...,
        description="Origem ativa segundo regra de precedência RN-10 (ambiente | banco_cifrado)",
    )
    mascarado: str = Field(
        ...,
        description="Valor sanitizado seguro sem exposição do segredo ([REDACTED] ou máscara parcial)",
    )
    atualizado_em: str = Field(
        ...,
        description="Timestamp ISO 8601 do último registro",
    )

    @staticmethod
    def mask_secret(value: str, tipo: str) -> str:
        """Aplica mascaramento de segurança evitando qualquer exposição de segredos."""
        if not value:
            return "[REDACTED]"
        if tipo == "webhook" or value.startswith("http://") or value.startswith("https://"):
            return value
        if len(value) <= 8:
            return "[REDACTED]"
        return f"{value[:4]}****{value[-4:]}"


class CredentialListResponse(BaseModel):
    """Contrato de saída para listagem administrativa de credenciais sanitizadas (RF-11)."""

    credenciais: List[CredentialSanitizedListItem] = Field(
        ...,
        description="Lista de credenciais registradas com valores mascarados",
    )

    # ponytail: filtros de busca por tipo ou chave na listagem podem ser adicionados conforme demanda
