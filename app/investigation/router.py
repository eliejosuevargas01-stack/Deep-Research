"""Investigation dispatch endpoint (T013, RN-01)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Principal, require_admin
from app.db.database import AsyncSessionLocal, get_db
from app.investigation.schemas import InvestigateResponse
from app.investigation.service import InvestigationService
from app.models.domain_models import Research, ResearchPoint, ResearchStatus

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
