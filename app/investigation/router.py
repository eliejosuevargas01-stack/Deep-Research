"""Investigation dispatch endpoint (T013, RN-01 + T037 implicit approval)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.briefing.domain import InvalidContent, InvalidTransition, approve_briefing
from app.briefing.storage import (
    BriefingVersionConflictError,
    get_briefing,
    save_briefing_transition,
)
from app.core.security import Principal, require_admin
from app.db.database import AsyncSessionLocal, get_db
from app.investigation.schemas import InvestigateResponse
from app.investigation.service import InvestigationService
from app.models.domain_models import BriefingRecord, Research, ResearchPoint, ResearchStatus

router = APIRouter(tags=["investigation"])

_CONFLICT = "Investigação já iniciada ou em andamento para esta pesquisa"


@router.post(
    "/briefings/{research_id}/investigate",
    response_model=InvestigateResponse,
    status_code=202,
)
async def investigate_briefing(
    research_id: UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_admin),  # noqa: ARG001
) -> InvestigateResponse:
    if db.in_transaction():
        await db.rollback()

    research = await db.get(Research, research_id)
    if research is None:
        raise HTTPException(status_code=404, detail="Pesquisa não encontrada")

    # T037: aprovação implícita sobre o primeiro briefing válido em draft.
    # O status draft e a ausência prévia de research_points não geram 409.
    briefing_record = await db.get(BriefingRecord, research_id)
    if briefing_record is not None and briefing_record.status == "draft":
        rows = await db.execute(
            select(ResearchPoint).where(ResearchPoint.research_id == research_id)
        )
        if list(rows.scalars().all()):
            raise HTTPException(status_code=409, detail=_CONFLICT)
        briefing = await get_briefing(db, research_id)
        if briefing is None:
            raise HTTPException(status_code=404, detail="Briefing não encontrado")
        try:
            changed = approve_briefing(briefing, datetime.now(timezone.utc))
        except (InvalidContent, InvalidTransition):
            raise HTTPException(status_code=409, detail=_CONFLICT) from None
        try:
            await save_briefing_transition(db, briefing, changed)
        except BriefingVersionConflictError:
            raise HTTPException(status_code=409, detail=_CONFLICT) from None
        reservation = await db.execute(
            update(ResearchPoint)
            .where(
                ResearchPoint.research_id == research_id,
                ResearchPoint.status == "SCRAPER_PENDING",
            )
            .values(status="SCRAPER_IN_PROGRESS")
        )
        if (reservation.rowcount or 0) != len(changed.points):
            await db.rollback()
            raise HTTPException(status_code=409, detail=_CONFLICT)
        await db.commit()

        service = InvestigationService(AsyncSessionLocal)
        background_tasks.add_task(service.run_investigation, research_id)

        return InvestigateResponse(
            research_id=research_id,
            status="SCRAPER",
            message="Investigação iniciada em background",
        )

    if research.status not in (ResearchStatus.SCRAPER, ResearchStatus.SCRAPER.value):
        raise HTTPException(status_code=409, detail=_CONFLICT)

    rows = await db.execute(
        select(ResearchPoint).where(ResearchPoint.research_id == research_id)
    )
    points = list(rows.scalars().all())
    if not points:
        raise HTTPException(status_code=409, detail=_CONFLICT)

    if any(p.status != "SCRAPER_PENDING" for p in points):
        raise HTTPException(status_code=409, detail=_CONFLICT)

    reservation = await db.execute(
        update(ResearchPoint)
        .where(
            ResearchPoint.research_id == research_id,
            ResearchPoint.status == "SCRAPER_PENDING",
        )
        .values(status="SCRAPER_IN_PROGRESS")
    )
    if reservation.rowcount != len(points):
        await db.rollback()
        raise HTTPException(status_code=409, detail=_CONFLICT)
    await db.commit()

    service = InvestigationService(AsyncSessionLocal)
    background_tasks.add_task(service.run_investigation, research_id)

    return InvestigateResponse(
        research_id=research_id,
        status="SCRAPER",
        message="Investigação iniciada em background",
    )
