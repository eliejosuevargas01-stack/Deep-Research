"""Schemas Pydantic estritos do Módulo de Auditoria (T042, Feature 003)."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.audit.domain import MAX_AUDIT_ATTEMPTS


class AuditChecklist(BaseModel):
    """Checklist booleano dos 12 critérios canônicos (q1..q12).

    Critérios não informados pelo auditor contam como falsos (score só
    credita respostas explícitas).
    """

    model_config = ConfigDict(extra="ignore")

    q1: bool = False
    q2: bool = False
    q3: bool = False
    q4: bool = False
    q5: bool = False
    q6: bool = False
    q7: bool = False
    q8: bool = False
    q9: bool = False
    q10: bool = False
    q11: bool = False
    q12: bool = False

    def to_dict(self) -> dict[str, bool]:
        return {key: getattr(self, key) for key in self.model_fields}


class AuditVerdictResponse(BaseModel):
    """Veredito estruturado do Agente Auditor para um único ponto."""

    model_config = ConfigDict(extra="ignore")

    checklist: AuditChecklist = Field(default_factory=AuditChecklist)
    score: int = Field(
        default=0,
        ge=0,
        le=12,
        description="Score S in [0, 12]: nº de critérios atendidos",
    )
    approved: bool = Field(default=False)
    findings: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    missing_research: list[str] = Field(
        default_factory=list,
        description="Instruções concretas de re-pesquisa; obrigatório quando reprovado",
    )


class AuditPointOutcome(BaseModel):
    """Resultado individual da auditoria de um ponto."""

    point_id: UUID
    attempt: int | None = Field(
        default=None,
        ge=1,
        le=MAX_AUDIT_ATTEMPTS,
        description="Ciclo de auditoria executado (1-based); None quando inconclusivo",
    )
    state: str
    score: int | None = None
    approved: bool | None = None
    missing_research: list[str] = Field(default_factory=list)
    detail: str | None = None


class AuditRunResponse(BaseModel):
    """Resposta dos endpoints administrativos de auditoria (RN-301)."""

    research_id: UUID
    requested_points: int = 0
    outcomes: list[AuditPointOutcome] = Field(default_factory=list)
    research_status: str | None = None
    write_transitioned: bool = False
