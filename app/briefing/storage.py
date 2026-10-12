"""Conversores puros domain <-> snapshot de persistência (T020) + storage assíncrono (T022).

Conversores sem I/O. Funções assíncronas com transações atômicas curtas
contra `AsyncSession` (D1/D2/D3 de `audit/t011-integration-decomposition.md`).
"""

from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.briefing.domain import Briefing, BriefingPoint, BriefingStatus
from app.models.domain_models import BriefingRecord, BriefingVersion, now


class BriefingVersionConflictError(Exception):
    """Colisão CAS em `save_briefing_transition` (esperado 409 na rota)."""


def points_to_json(points: tuple[BriefingPoint, ...]) -> list[dict[str, str]]:
    return [{"title": p.title, "description": p.description} for p in points]


def json_to_points(data: list[dict[str, Any]]) -> tuple[BriefingPoint, ...]:
    return tuple(BriefingPoint(title=d["title"], description=d["description"]) for d in data)


def briefing_to_record(briefing: Briefing) -> BriefingRecord:
    return BriefingRecord(
        id=briefing.id,
        theme=briefing.theme,
        status=briefing.status.value,
        version=briefing.version,
        points_json=points_to_json(briefing.points),
        error=briefing.error,
        approved_at=briefing.approved_at,
    )


def record_to_briefing(record: BriefingRecord) -> Briefing:
    return Briefing(
        id=UUID(str(record.id)),
        theme=record.theme,
        status=BriefingStatus(record.status),
        points=json_to_points(list(record.points_json)),
        version=record.version,
        approved_at=record.approved_at,
        error=record.error,
    )


def briefing_to_version_dict(briefing: Briefing) -> dict:
    return {
        "briefing_id": briefing.id,
        "version": briefing.version,
        "status": briefing.status.value,
        "points_json": points_to_json(briefing.points),
        "error": briefing.error,
        "approved_at": briefing.approved_at,
    }


async def create_generating_briefing(db: AsyncSession, briefing: Briefing) -> Briefing:
    """Tx1: insere `BriefingRecord` inicial e commit imediato (D1/D3)."""
    db.add(briefing_to_record(briefing))
    await db.commit()
    return briefing


async def get_briefing(db: AsyncSession, briefing_id: UUID) -> Briefing | None:
    """Consulta snapshot corrente por id; None se inexistente."""
    record = await db.get(BriefingRecord, briefing_id)
    if record is None:
        return None
    return record_to_briefing(record)


async def get_briefing_versions(db: AsyncSession, briefing_id: UUID) -> list[BriefingVersion]:
    """Histórico append-only ordenado por `version ASC` (D2)."""
    result = await db.execute(
        select(BriefingVersion)
        .where(BriefingVersion.briefing_id == briefing_id)
        .order_by(BriefingVersion.version.asc())
    )
    return list(result.scalars().all())


async def save_briefing_transition(
    db: AsyncSession, previous_briefing: Briefing, new_briefing: Briefing
) -> Briefing:
    """Tx2 (CAS): UPDATE com `WHERE id AND version=old_v` + INSERT em `briefing_versions` (D2/D3)."""
    result = await db.execute(
        update(BriefingRecord)
        .where(
            BriefingRecord.id == new_briefing.id,
            BriefingRecord.version == previous_briefing.version,
        )
        .values(
            status=new_briefing.status.value,
            version=new_briefing.version,
            points_json=points_to_json(new_briefing.points),
            error=new_briefing.error,
            approved_at=new_briefing.approved_at,
            updated_at=now(),
        )
    )
    updated = getattr(result, "rowcount", 0)
    if updated != 1:
        await db.rollback()
        raise BriefingVersionConflictError(
            f"conflito de versão: id={new_briefing.id} expected={previous_briefing.version}"
        )
    db.add(BriefingVersion(**briefing_to_version_dict(new_briefing)))
    await db.commit()
    return new_briefing
