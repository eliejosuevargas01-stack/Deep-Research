"""Regras puras do domínio de briefing."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

THEME_MIN = 3
THEME_MAX = 300
POINTS_MIN = 1
POINTS_MAX = 7


class BriefingStatus(StrEnum):
    GENERATING = "generating"
    DRAFT = "draft"
    FAILED = "failed"
    APPROVED = "approved"


class InvalidContent(ValueError):
    """Conteúdo de briefing fora das regras de domínio."""


class InvalidTransition(ValueError):
    """Transição ou operação incompatível com estado atual."""


def validate_theme(theme: str) -> str:
    if not isinstance(theme, str):
        raise InvalidContent("Tema deve ser uma string")
    normalized = theme.strip()
    if not THEME_MIN <= len(normalized) <= THEME_MAX:
        raise InvalidContent(f"Tema deve conter entre {THEME_MIN} e {THEME_MAX} caracteres")
    return normalized


def validate_points(points: list[Any]) -> list[Any]:
    if not isinstance(points, list) or not POINTS_MIN <= len(points) <= POINTS_MAX:
        raise InvalidContent(f"Briefing deve conter entre {POINTS_MIN} e {POINTS_MAX} pontos")
    for point in points:
        if isinstance(point, dict):
            title, description = point.get("title"), point.get("description")
        else:
            title = getattr(point, "title", None)
            description = getattr(point, "description", None)
        if not isinstance(title, str) or not title.strip():
            raise InvalidContent("Cada ponto deve ter título não vazio")
        if not isinstance(description, str) or not description.strip():
            raise InvalidContent("Cada ponto deve ter descrição não vazia")
    return points


def assert_can_edit(status: BriefingStatus | str) -> None:
    if status != BriefingStatus.DRAFT:
        raise InvalidTransition("Edição permitida somente em rascunho")


def transition(status: BriefingStatus | str, target: BriefingStatus | str) -> BriefingStatus:
    try:
        current, next_status = BriefingStatus(status), BriefingStatus(target)
    except ValueError as exc:
        raise InvalidTransition("Estado de briefing desconhecido") from exc
    allowed = {
        BriefingStatus.GENERATING: {BriefingStatus.DRAFT, BriefingStatus.FAILED},
        BriefingStatus.DRAFT: {BriefingStatus.APPROVED},
        BriefingStatus.APPROVED: set(),
        BriefingStatus.FAILED: set(),
    }
    if next_status not in allowed[current]:
        raise InvalidTransition(f"Transição inválida: {current.value} para {next_status.value}")
    return next_status


@dataclass(frozen=True)
class BriefingPoint:
    title: str
    description: str


@dataclass(frozen=True)
class Briefing:
    id: UUID
    theme: str
    status: BriefingStatus
    points: tuple[BriefingPoint, ...] = ()
    version: int = 1
    approved_at: datetime | None = None
    error: str | None = None


def new_briefing(theme: str) -> Briefing:
    """Cria registro GENERATING com tema validado; sem I/O, UUID4 stdlib."""
    return Briefing(
        id=uuid4(),
        theme=validate_theme(theme),
        status=BriefingStatus.GENERATING,
        points=(),
        version=1,
        approved_at=None,
        error=None,
    )


def _copy_valid_points(points: object) -> tuple[BriefingPoint, ...]:
    if isinstance(points, (str, bytes, bytearray)) or not isinstance(points, Sequence):
        raise InvalidContent("Lista de pontos inválida")
    normalized: list[dict[str, Any]] = []
    for point in points:
        if isinstance(point, Mapping):
            normalized.append({"title": point.get("title"), "description": point.get("description")})
        elif isinstance(point, BriefingPoint):
            normalized.append({"title": point.title, "description": point.description})
        else:
            raise InvalidContent("Ponto inválido")
    validate_points(normalized)
    return tuple(BriefingPoint(p["title"], p["description"]) for p in normalized)


def _require_status(briefing: Briefing, expected: BriefingStatus) -> None:
    if briefing.status != expected:
        raise InvalidTransition(f"Operação permitida somente em {expected.value}")


def complete_briefing(briefing: Briefing, points: Sequence[BriefingPoint | Mapping[str, object]]) -> Briefing:
    _require_status(briefing, BriefingStatus.GENERATING)
    snapshot = _copy_valid_points(points)
    return replace(briefing, status=transition(briefing.status, BriefingStatus.DRAFT),
                   points=snapshot, version=briefing.version + 1)


def fail_briefing(briefing: Briefing, error: str) -> Briefing:
    _require_status(briefing, BriefingStatus.GENERATING)
    if not isinstance(error, str) or not error.strip():
        raise InvalidContent("Mensagem de falha inválida")
    return replace(briefing, status=transition(briefing.status, BriefingStatus.FAILED),
                   points=(), error=error, version=briefing.version + 1)


def edit_briefing(briefing: Briefing, points: Sequence[BriefingPoint | Mapping[str, object]]) -> Briefing:
    assert_can_edit(briefing.status)
    snapshot = _copy_valid_points(points)
    return replace(briefing, status=BriefingStatus.DRAFT, points=snapshot,
                   version=briefing.version + 1)


def approve_briefing(briefing: Briefing, approved_at: datetime) -> Briefing:
    _require_status(briefing, BriefingStatus.DRAFT)
    if not isinstance(approved_at, datetime):
        raise InvalidContent("Instante de aprovação inválido")
    snapshot = _copy_valid_points(list(briefing.points))
    return replace(briefing, status=transition(briefing.status, BriefingStatus.APPROVED),
                   points=snapshot, approved_at=approved_at, version=briefing.version + 1)


def reopen_briefing(briefing: Briefing) -> Briefing:
    if briefing.status == BriefingStatus.APPROVED:
        raise InvalidTransition("Briefing aprovado não pode ser reaberto")
    raise InvalidTransition("Reabertura permitida somente a partir de aprovado")


def read_approved(briefing: Briefing) -> Briefing:
    _require_status(briefing, BriefingStatus.APPROVED)
    return replace(briefing)
