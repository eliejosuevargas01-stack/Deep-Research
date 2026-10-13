# Matriz de erros do módulo de briefing:
# 422 conteúdo inválido (tema fora de 3-300, pontos fora de 3-7 ou vazios);
# 409 conflito de estado/transição (editar aprovado, transição inválida);
# 404 briefing inexistente; 503 falha externa após 4 tentativas.
# Nenhuma resposta carrega segredos.
"""Contratos HTTP do módulo de briefing (Pydantic v2)."""

from datetime import datetime
from uuid import UUID

from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from app.briefing.domain import (
    POINTS_MAX,
    POINTS_MIN,
    THEME_MAX,
    THEME_MIN,
    BriefingStatus,
    validate_points,
    validate_theme,
)


class BriefingPoint(BaseModel):
    model_config = {"extra": "forbid"}

    title: str = Field(min_length=1)
    description: str = Field(min_length=1)

    @field_validator("title", "description", mode="before")
    @classmethod
    def _non_empty(cls, v: object) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("Campo não pode ser vazio")
        return v


class BriefingCreateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    theme: str = Field(min_length=THEME_MIN, max_length=THEME_MAX)

    @field_validator("theme", mode="before")
    @classmethod
    def _theme(cls, v: object) -> str:
        return validate_theme(v)  # type: ignore[arg-type]


class BriefingEditPointsRequest(BaseModel):
    model_config = {"extra": "forbid"}

    points: list[BriefingPoint] = Field(min_length=POINTS_MIN, max_length=POINTS_MAX)

    @field_validator("points", mode="after")
    @classmethod
    def _points(cls, v: list[BriefingPoint]) -> list[BriefingPoint]:
        return validate_points(v)


class BriefingFeedbackRequest(BaseModel):
    """Feedback textual do usuário para revisão do rascunho (T016)."""

    model_config = {"extra": "forbid"}

    note: str = Field(..., min_length=3, max_length=4000, description="Feedback textual do usuário para guiar a revisão do briefing")


class BriefingApproveRequest(BaseModel):
    """Sem corpo: aprova rascunho atual (3-7 pontos válidos exigidos)."""

    model_config = {"extra": "forbid"}


class BriefingReopenRequest(BaseModel):
    """Sem corpo: reabre aprovado para rascunho."""

    model_config = {"extra": "forbid"}


class BriefingResponse(BaseModel):
    model_config = {"extra": "forbid"}

    id: UUID | None = Field(default=None)
    research_id: UUID | None = Field(default=None)
    theme: str
    status: BriefingStatus
    points: list[BriefingPoint] = Field(default_factory=list)
    version: int = Field(default=1, ge=1)
    error: str | None = None
    approved_at: datetime | None = None

    @model_validator(mode="before")
    @classmethod
    def _sync_ids_before(cls, data: Any) -> Any:
        if isinstance(data, dict):
            res_id = data.get("research_id")
            b_id = data.get("id")
            if res_id is not None and b_id is None:
                data = {**data, "id": res_id}
            elif b_id is not None and res_id is None:
                data = {**data, "research_id": b_id}
        return data

    @model_validator(mode="after")
    def _sync_ids_after(self) -> "BriefingResponse":
        if self.research_id is not None and self.id is None:
            self.id = self.research_id
        elif self.id is not None and self.research_id is None:
            self.research_id = self.id
        if self.status in (BriefingStatus.DRAFT, BriefingStatus.APPROVED):
            self.points = validate_points(self.points)
        return self


class BriefingVersionResponse(BaseModel):
    """Snapshot histórico de uma versão do briefing."""

    model_config = {"extra": "forbid"}

    version: int = Field(ge=1)
    status: BriefingStatus
    points: list[BriefingPoint] = Field(default_factory=list)
    error: str | None = None
    approved_at: datetime | None = None
    created_at: datetime

    @model_validator(mode="after")
    def _points_when_content_required(self) -> "BriefingVersionResponse":
        if self.status in (BriefingStatus.DRAFT, BriefingStatus.APPROVED):
            self.points = validate_points(self.points)
        return self


class ApprovedBriefingResponse(BaseModel):
    """Consulta read-only do conteúdo aprovado."""

    model_config = {"extra": "forbid"}

    id: UUID
    theme: str
    points: list[BriefingPoint] = Field(min_length=POINTS_MIN, max_length=POINTS_MAX)
    approved_at: datetime | None = None
