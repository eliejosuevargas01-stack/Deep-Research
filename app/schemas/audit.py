"""Esquemas Pydantic v2 para o endpoint de auditoria de qualidade (/api/v1/audit).

Derivado de:
- SDD: endpoint-auditoria-de-qualidade.md (RF-01, RF-04, RF-05, RF-06, RF-07, Seção 9)
- Adendo v5: addendum-confiabilidade-20261024-v5-audit.md
- PRD: prd.md (RF-005)
- Bugs: BUG-20261023-KLXD, BUG-20261023-TKEO, BUG-20261023-VDCJ, BUG-20261023-XAXC
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, StrictBool, StrictInt, field_validator


VALID_PERSONAS = {"historiador", "visionario", "cetico", "futurista"}

CRITERIA_TITLES = {
    1: "clareza_tematica",
    2: "corroboracao_canonica",
    3: "atualidade",
    4: "ausencia_contradicoes",
    5: "embasamento_factual",
    6: "aderencia_escopo",
    7: "profundidade_analitica",
    8: "precisao_dados",
    9: "neutralidade",
    10: "densidade_evidencias",
    11: "declaracao_incertezas",
    12: "solidez_logica",
}


class AuditCriterionDetail(BaseModel):
    """Item individual do vetor tipado dos 12 critérios formais (DR-002, DR-015)."""

    id: StrictInt = Field(..., ge=1, le=12, description="ID ordinal estrito do critério (1..12)")
    aprovado: StrictBool = Field(..., description="Deliberação booleana estrita (sem defaults)")
    justificativa: str = Field(..., min_length=1, description="Justificativa analítica substantiva")
    claim_ids: List[str] = Field(..., description="IDs de alegações/claims referenciadas (obrigatório, vazio permitido apenas se justificado)")
    source_ids: List[str] = Field(..., description="IDs de fontes referenciadas (obrigatório, vazio permitido apenas se justificado)")
    lacuna: Optional[str] = Field(default=None, description="Lacuna apontada em caso de não aprovação")
    correcao: Optional[str] = Field(default=None, description="Ação de correção recomendada")
    personas_pertinentes: List[str] = Field(
        default_factory=list,
        description="Personas pertinentes para ação corretiva",
    )

    @field_validator("justificativa")
    @classmethod
    def validate_justificativa_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("O campo 'justificativa' não pode ser vazio.")
        return v.strip()

    @field_validator("personas_pertinentes")
    @classmethod
    def validate_personas(cls, v: List[str]) -> List[str]:
        for p in v:
            if p not in VALID_PERSONAS:
                raise ValueError(f"Persona inválida: '{p}'. Permitidas: {VALID_PERSONAS}")
        return v


class AuditEvaluationResult(BaseModel):
    """Resposta estruturada do LLM forte para avaliação das 12 perguntas de qualidade (RF-04, RF-05)."""

    criterios: List[AuditCriterionDetail] = Field(
        ...,
        description="Vetor estruturado contendo exatamente os 12 critérios com IDs 1..12",
    )
    resumo_auditoria: Optional[str] = Field(
        default=None,
        description="Resumo analítico do parecer de auditoria",
    )
    diagnostico: Optional[str] = Field(
        default=None,
        description="Diagnóstico técnico de eventuais inconsistências",
    )


class AuditItem(BaseModel):
    """Parecer de auditoria consolidado para um ponto individual (RF-05, RF-07)."""

    ponto_id: str = Field(..., description="Identificador do ponto investigado (UUID)")
    ponto_n: int = Field(..., ge=1, description="Número de ordem do ponto investigado")
    status: str = Field(..., description="Deliberação de qualidade: aprovado ou reprovado")
    pontuacao_percentual: float = Field(default=0.0, description="Pontuação percentual calculada (83.33, 91.67, 100.0)")
    criterios_aprovados: int = Field(default=0, description="Quantidade de critérios atendidos no vetor 12")
    criterios_minimos: int = Field(default=11, description="Limiar mínimo de critérios para aprovação (10, 11 ou 12)")
    valido: bool = Field(default=False, description="Indica se a avaliação cumpriu o contrato estruturado")
    criterios: Optional[List[AuditCriterionDetail]] = Field(default=None, description="Vetor estruturado dos 12 critérios")
    pontos_fracos: Optional[str] = Field(default=None, description="Registro das fragilidades apontadas em caso de reprovação")
    diagnostico: Optional[str] = Field(default=None, description="Diagnóstico técnico de falha ou insuficiência")
    resumo_auditoria: Optional[str] = Field(default=None, description="Resumo do parecer técnico da auditoria")
    tarefas: Optional[List[Dict[str, Any]]] = Field(default=None, description="Tarefas direcionadas projetadas a partir dos critérios não atendidos")
    antes_depois: Optional[Dict[str, Any]] = Field(default=None, description="Comparativo evolutivo por critério em relação à rodada anterior")
    envelope: Optional[Dict[str, Any]] = Field(default=None, description="Envelope de telemetria da chamada LLM")
    reasoning_auditoria: Optional[str] = Field(default=None, description="Compatibilidade interna transitória")


class AuditRequest(BaseModel):
    """Contrato de entrada para a etapa de auditoria de qualidade (RF-01)."""

    id_pesquisa: str = Field(..., min_length=1, description="Identificador canônico da pesquisa (UUID)")
    ponto_id: Optional[str] = Field(default=None, description="Filtro opcional para auditar apenas um ponto específico")
    criterios_minimos: Optional[StrictInt] = Field(
        default=11,
        ge=10,
        le=12,
        description="Limiar mínimo de critérios aprovados para aprovação (10, 11 ou 12)",
    )

    @field_validator("criterios_minimos")
    @classmethod
    def validate_threshold(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v not in (10, 11, 12):
            raise ValueError("O limiar 'criterios_minimos' deve ser 10, 11 ou 12.")
        return v


class AuditResponse(BaseModel):
    """Contrato de saída com o parecer consolidado da auditoria (RF-07)."""

    id_pesquisa: str = Field(..., description="Identificador canônico da pesquisa (UUID)")
    total_pontos: int = Field(..., ge=0, description="Total de pontos submetidos à auditoria")
    aprovados: int = Field(..., ge=0, description="Quantidade de pontos aprovados")
    reprovados: int = Field(..., ge=0, description="Quantidade de pontos reprovados")
    status_geral: str = Field(default="auditado", description="Status geral da etapa de auditoria")
    status_pesquisa: Optional[str] = Field(default=None, description="Status real da pesquisa na base de dados")
    pronto_para_writer: bool = Field(default=False, description="Indica se todos os pontos da pesquisa estão aprovados para o Redator")
    auditorias: List[AuditItem] = Field(..., description="Listagem estruturada das deliberações de auditoria por ponto")
