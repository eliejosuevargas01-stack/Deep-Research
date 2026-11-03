"""Artefatos JSON do ciclo Hermes — o mesmo shape que o banco e a API esperam.

O perfil `deep-research` não escreve Markdown: cada etapa grava um JSON que é
validado por Pydantic aqui e persistido no banco. Um artefato torto vira erro 422,
nunca uma tela plausível e vazia.
"""

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from app.schemas.plan import PlanoInvestigacao


class PlanoArtefato(PlanoInvestigacao):
    """`PLAN.json`: contrato DR-006 + mapa de personas que roteia os 4 searchers."""

    personas: Dict[str, str] = Field(
        ...,
        min_length=4,
        description="persona → eixo sob sua responsabilidade (chaves fixas)",
    )

    @field_validator("personas")
    @classmethod
    def validate_personas(cls, v: Dict[str, str]) -> Dict[str, str]:
        exatas = {"historiador", "visionario", "cetico", "futurista"}
        if set(v) != exatas:
            raise ValueError(f"personas deve conter exatamente {sorted(exatas)}")
        if any(not str(texto).strip() for texto in v.values()):
            raise ValueError("todo eixo de persona precisa ser não vazio")
        return v


class TentativaBusca(BaseModel):
    """Uma rodada de coleta de uma persona."""

    rodada: int = Field(default=1, ge=1, description="Número da tentativa")
    consultas: List[str] = Field(..., min_length=1, description="Queries executadas")
    analise: str = Field(..., min_length=1, description="Análise em Markdown com os achados e URLs")
    lacunas: List[str] = Field(default_factory=list, description="O que não foi possível confirmar")
    urls_lidas: List[str] = Field(default_factory=list, description="Páginas realmente abertas")
    urls_fonte: List[str] = Field(default_factory=list, description="URLs que sustentam os achados")
    paginas_lidas: int = Field(default=0, ge=0, description="Quantas páginas foram abertas nesta rodada")


class BuscaArtefato(BaseModel):
    """`<PERSONA>_SEARCH.json`: todas as tentativas de uma persona."""

    persona: Literal["historiador", "visionario", "cetico", "futurista"]
    tentativas: List[TentativaBusca] = Field(..., min_length=1)


class CriterioAuditoria(BaseModel):
    """Um dos 12 critérios de `app/CRITERIA.md`."""

    id: int = Field(..., ge=1, le=12)
    nome: str = Field(..., min_length=3)
    aprovado: bool
    justificativa: str = Field(..., min_length=1)


class RodadaAuditoria(BaseModel):
    """Uma rodada de auditoria com o veredito e os 12 critérios."""

    rodada: int = Field(..., ge=1)
    veredito: Literal["APROVADO", "REPROVADO"]
    nota: int = Field(..., ge=0, le=12)
    criterios: List[CriterioAuditoria] = Field(..., min_length=12, max_length=12)
    lacunas: Optional[str] = Field(default=None, description="O que falta para aprovar")

    @field_validator("nota")
    @classmethod
    def validate_nota(cls, v: int, info) -> int:
        criterios = info.data.get("criterios") or []
        if criterios and v != sum(1 for c in criterios if c.aprovado):
            raise ValueError("nota deve ser exatamente o número de critérios aprovados")
        return v


class AuditoriaArtefato(BaseModel):
    """`AUDITORIA.json`: todas as rodadas (o auditor reescreve o arquivo inteiro)."""

    rodadas: List[RodadaAuditoria] = Field(..., min_length=1)


class FontesDossie(BaseModel):
    utilizadas: List[str] = Field(default_factory=list)
    nao_utilizadas: List[str] = Field(default_factory=list)


class DossieArtefato(BaseModel):
    """`DOSSIE.json`: texto final + contabilidade de fontes."""

    dossier_final: str = Field(..., min_length=1)
    reasoning_dossier: Optional[str] = None
    fontes: Optional[FontesDossie] = None
