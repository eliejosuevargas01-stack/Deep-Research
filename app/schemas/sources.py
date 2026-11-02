"""Esquemas Pydantic v2 para separação contábil e pública de fontes de pesquisa.

Atende ao contrato de separação de fontes consultadas, utilizadas e não utilizadas:
- Fontes consultadas: URLs com leitura efetiva confirmada (read_ok/material corpus).
- Fontes utilizadas: Fontes citadas no dossiê final e rastreáveis às evidências lidas.
- Fontes não utilizadas: Fontes consultadas com sucesso, mas não citadas no artigo.
"""

from typing import List, Literal, Optional
from pydantic import BaseModel, Field

FontesStatus = Literal["completo", "parcial", "indisponivel"]


class FonteItem(BaseModel):
    """Metadados públicos de uma fonte individual."""

    url: str = Field(..., description="URL canônica pública da fonte")
    titulo: Optional[str] = Field(default=None, description="Título público da página quando disponível")
    dominio: Optional[str] = Field(default=None, description="Domínio normalizado extraído da URL")
    uso: Optional[Literal["utilizada", "lida_nao_utilizada"]] = Field(
        default=None,
        description="Uso classificado já na fase de busca (quando o dossiê ainda não existe)",
    )


class FontesResumo(BaseModel):
    """Resumo analítico tipado da contabilidade de fontes de uma pesquisa."""

    id_pesquisa: Optional[str] = Field(default=None, description="Identificador canônico da pesquisa")
    status: FontesStatus = Field(
        ...,
        description="Status da contabilidade das fontes (completo | parcial | indisponivel)",
    )
    total_consultadas: Optional[int] = Field(
        default=None,
        ge=0,
        description="Total de fontes únicas consultadas com leitura confirmada (null se desconhecido)",
    )
    total_utilizadas: Optional[int] = Field(
        default=None,
        ge=0,
        description="Total de fontes citadas no dossiê analítico (null se desconhecido)",
    )
    total_nao_utilizadas: Optional[int] = Field(
        default=None,
        ge=0,
        description="Total de fontes consultadas que não foram citadas (null se desconhecido)",
    )
    consultadas: List[FonteItem] = Field(
        default_factory=list,
        description="Vetor de fontes efetivamente lidas com sucesso",
    )
    utilizadas: List[FonteItem] = Field(
        default_factory=list,
        description="Vetor de fontes citadas no dossiê final publicado",
    )
    nao_utilizadas: List[FonteItem] = Field(
        default_factory=list,
        description="Vetor de fontes consultadas com sucesso que não receberam citação",
    )
    observacao: Optional[str] = Field(
        default=None,
        description="Observação diagnóstica sobre a disponibilidade das evidências",
    )
    artifact_hash: Optional[str] = Field(
        default=None,
        description="Hash SHA-256 do dossiê publicado ao qual este resumo está vinculado",
    )
