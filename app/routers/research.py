import asyncio
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Principal, require_admin
from app.db.database import AsyncSessionLocal, get_db
from app.models import Event, Report, Research, ResearchPoint
from app.schemas import BriefingApproval, BriefingEdit, ResearchCreate
from app.services.llm import ProviderConfigurationError
from app.services.research import add_event, point_dependencies, run_research, scout
from app.services.webhook import dispatch_callback
from app.tools.outbound import SSRFSecurityViolation, validate_public_url
from app.tools.search_pipeline import SearchProviderError

router = APIRouter(prefix="/api", tags=["research"])
_running: set[asyncio.Task] = set()


def schedule(research_id: uuid.UUID) -> None:
    task = asyncio.create_task(run_research(research_id))
    _running.add(task)
    task.add_done_callback(_running.discard)


async def run_scout(research_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as db:
        research = await db.get(Research, research_id)
        if not research or research.status != "scouting":
            return
        try:
            points = await scout(research.theme, db)
            point_dependencies(points)
            research.briefing_draft = {"points": points, "source": "live_search_and_llm"}
            research.status = "pending_approval"
            await db.commit()
            await add_event(research_id, "scout", "briefing_ready", "Five-point briefing ready for one-time approval", {"points": 5})
        except Exception as exc:
            research.status = "failed"
            research.error = f"{type(exc).__name__}: scout failed"
            await db.commit()
            await add_event(research_id, "scout", "scout_failed", "Scout failed; check provider configuration")


def schedule_scout(research_id: uuid.UUID) -> None:
    task = asyncio.create_task(run_scout(research_id))
    _running.add(task)
    task.add_done_callback(_running.discard)


@router.post("/research", status_code=201)
async def create_research(payload: ResearchCreate, _: Principal = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    from app.services.settings import get_record
    cfg = await get_record(db)
    callback = cfg.callback_url
    research = Research(theme=payload.theme.strip(), callback_url=callback, status="scouting", briefing_draft={})
    db.add(research)
    await db.commit()
    await db.refresh(research)
    await add_event(research.id, "scout", "scout_started", "Scout started live preliminary research")
    schedule_scout(research.id)
    return {"research_id": research.id, "status": "scouting", "briefing_url": f"/api/research/{research.id}", "stream_url": f"/api/research/{research.id}/events"}


@router.get("/research")
async def list_research(_: Principal = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    rows = list((await db.scalars(select(Research).order_by(Research.created_at.desc()).limit(100))).all())
    return [{"research_id": row.id, "theme": row.theme, "status": row.status, "created_at": row.created_at} for row in rows]


@router.get("/research/{research_id}")
async def research_status(research_id: uuid.UUID, _: Principal = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    research = await db.get(Research, research_id)
    if not research:
        raise HTTPException(404, "Research not found")
    points = list((await db.scalars(select(ResearchPoint).where(ResearchPoint.research_id == research_id).order_by(ResearchPoint.position))).all())
    return {
        "research_id": research.id, "theme": research.theme, "status": research.status,
        "briefing_draft": research.briefing_draft, "error": research.error,
        "briefing_edit_available": research.status == "pending_approval",
        "points": [{"id": p.id, "title": p.title, "status": p.status, "attempt_count": p.attempt_count, "audit": p.audit} for p in points],
        "created_at": research.created_at, "updated_at": research.updated_at,
    }


@router.post("/research/{research_id}/briefing/edit")
async def edit_briefing(research_id: uuid.UUID, payload: BriefingEdit, _: Principal = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    research = await db.get(Research, research_id)
    if not research:
        raise HTTPException(404, "Research not found")
    if research.status != "pending_approval" or research.approved_at is not None:
        raise HTTPException(409, "Briefing is no longer editable")
    note = payload.note.strip()
    if not note:
        raise HTTPException(422, "Edit note is required")
    draft = dict(research.briefing_draft or {})
    if payload.points:
        point_dependencies(payload.points)
        draft["points"] = [p.model_dump() for p in payload.points]
    draft["edit_note"] = note
    draft["source"] = "operator_edit"
    research.briefing_draft = draft
    await db.commit()
    await add_event(research_id, "system", "briefing_edited", "Operator requested briefing revision", {})
    async def rerun() -> None:
        async with AsyncSessionLocal() as sdb:
            r = await sdb.get(Research, research_id)
            if not r:
                return
            try:
                points = await scout(r.theme, sdb, feedback=note, base_points=[p.model_dump() for p in (payload.points or [])])
                point_dependencies(points)
                r.briefing_draft = {"points": points, "source": "revised_after_edit", "edit_note": note}
                r.status = "approved"
                r.approved_at = datetime.now(timezone.utc)
                for position, pt in enumerate(points):
                    sdb.add(ResearchPoint(research_id=research_id, position=position, **pt))
                await sdb.commit()
                await add_event(research_id, "system", "briefing_approved", "Briefing revised and approved automatically", {"points": len(points)})
                schedule(research_id)
            except Exception as exc:
                r.status = "failed"
                r.error = f"{type(exc).__name__}: briefing revision failed"
                await sdb.commit()
                await add_event(research_id, "system", "research_failed", "Briefing revision failed")
    task = asyncio.create_task(rerun())
    _running.add(task)
    task.add_done_callback(_running.discard)
    return {"research_id": research_id, "status": "revising"}


@router.post("/research/{research_id}/briefing/approve")
async def approve(research_id: uuid.UUID, payload: BriefingApproval, _: Principal = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    try:
        point_dependencies(payload.approved_points)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    draft = {"points": [point.model_dump() for point in payload.approved_points], "source": "operator_approved"}
    result = await db.execute(
        update(Research).where(Research.id == research_id, Research.status == "pending_approval", Research.approved_at.is_(None))
        .values(status="approved", approved_at=datetime.now(timezone.utc), briefing_draft=draft)
    )
    if result.rowcount != 1:
        await db.rollback()
        exists = await db.get(Research, research_id)
        raise HTTPException(404 if not exists else 409, "Research not found" if not exists else "Briefing already approved or no longer approvable")
    for position, point in enumerate(payload.approved_points):
        db.add(ResearchPoint(research_id=research_id, position=position, **point.model_dump()))
    await db.commit()
    await add_event(research_id, "system", "briefing_approved", "Briefing approved exactly once", {"points": len(payload.approved_points)})
    schedule(research_id)
    return {"research_id": research_id, "status": "approved"}


@router.get("/research/{research_id}/events")
@router.get("/research/{research_id}/stream", include_in_schema=False)
async def events(research_id: uuid.UUID, request: Request, last_event_id: int | None = Header(None, alias="Last-Event-ID"), _: Principal = Depends(require_admin)):
    async with AsyncSessionLocal() as db:
        if not await db.get(Research, research_id):
            raise HTTPException(404, "Research not found")

    async def generate():
        cursor = last_event_id or 0
        while not await request.is_disconnected():
            async with AsyncSessionLocal() as db:
                rows = list((await db.scalars(select(Event).where(Event.research_id == research_id, Event.id > cursor).order_by(Event.id))).all())
                research = await db.get(Research, research_id)
            for row in rows:
                cursor = row.id
                data = json.dumps({"id": row.id, "persona": row.persona, "type": row.event_type, "summary": row.summary, "metrics": row.metrics, "created_at": row.created_at.isoformat()})
                yield f"id: {row.id}\nevent: progress\ndata: {data}\n\n"
            if research and research.status in {"completed", "completed_but_callback_failed", "blocked", "failed"} and not rows:
                break
            await asyncio.sleep(0.5)
    return StreamingResponse(generate(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/reports/{research_id}")
async def report(research_id: uuid.UUID, _: Principal = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    row = await db.scalar(select(Report).where(Report.research_id == research_id))
    if not row:
        raise HTTPException(404, "Report not ready")
    return {"report_id": row.id, "research_id": row.research_id, "content_markdown": row.content_markdown, "citation_metrics": row.citation_metrics, "audit_findings": row.audit_findings, "generated_at": row.generated_at}


@router.post("/reports/{research_id}/retry-callback")
async def retry_callback(research_id: uuid.UUID, _: Principal = Depends(require_admin)):
    async with AsyncSessionLocal() as db:
        research = await db.get(Research, research_id)
        if not research:
            raise HTTPException(404, "Research not found")
        if not research.callback_url:
            raise HTTPException(409, "No callback configured")
        if not await db.scalar(select(Report.id).where(Report.research_id == research_id)):
            raise HTTPException(409, "Report not ready")
    delivered = await dispatch_callback(research_id)
    return {"success": delivered}
