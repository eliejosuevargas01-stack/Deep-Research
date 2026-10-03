import asyncio
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Principal, require_admin
from app.db.database import AsyncSessionLocal, get_db
from app.models import AuditTrail, Event, Report, Research, ResearchPoint
from app.schemas import BriefingApproval, BriefingEdit, ResearchCreate
from app.services.llm import ProviderConfigurationError
from app.services.research import add_event, point_dependencies, run_research, sanitize_error, scout
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
        except Exception as exc:
            await db.rollback()
            safe_error = sanitize_error(exc, "scout execution")
            r = await db.get(Research, research_id)
            if r:
                r.status = "failed"
                r.error = safe_error
                await db.commit()
            try:
                await add_event(research_id, "scout", "scout_failed", safe_error)
            except Exception:
                pass
            return

        try:
            await add_event(research_id, "scout", "briefing_ready", "Five-point briefing ready for one-time approval", {"points": 5})
        except Exception:
            pass


def schedule_scout(research_id: uuid.UUID) -> None:
    task = asyncio.create_task(run_scout(research_id))
    _running.add(task)
    task.add_done_callback(_running.discard)


async def run_revision(research_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as sdb:
        r = await sdb.get(Research, research_id)
        if not r or r.status != "revising":
            return
        draft = dict(r.briefing_draft or {})
        note = str(draft.get("edit_note") or "").strip()
        base_pts = list(draft.get("points") or [])
        try:
            points = await scout(
                r.theme,
                sdb,
                feedback=note,
                base_points=base_pts,
            )
            point_dependencies(points)
            update_res = await sdb.execute(
                update(Research)
                .where(
                    Research.id == research_id,
                    Research.status == "revising",
                    Research.approved_at.is_(None),
                )
                .values(
                    status="approved",
                    approved_at=datetime.now(timezone.utc),
                    briefing_draft={"points": points, "source": "revised_after_edit", "edit_note": note},
                )
            )
            if getattr(update_res, "rowcount", -1) != 1:
                await sdb.rollback()
                return
            await sdb.execute(delete(ResearchPoint).where(ResearchPoint.research_id == research_id))
            for position, pt in enumerate(points):
                sdb.add(ResearchPoint(research_id=research_id, position=position, **pt))
            await sdb.commit()
            schedule(research_id)
            try:
                await add_event(
                    research_id,
                    "system",
                    "briefing_approved",
                    "Briefing revised and approved automatically",
                    {"points": len(points)},
                )
            except Exception:
                pass
        except Exception as exc:
            await sdb.rollback()
            safe_error = sanitize_error(exc, "briefing revision")
            err_res = await sdb.get(Research, research_id)
            if err_res and err_res.status == "revising":
                err_res.status = "failed"
                err_res.error = safe_error
                await sdb.commit()
            try:
                await add_event(research_id, "system", "research_failed", safe_error)
            except Exception:
                pass


def schedule_revision(research_id: uuid.UUID) -> None:
    task = asyncio.create_task(run_revision(research_id))
    _running.add(task)
    task.add_done_callback(_running.discard)


@router.post("/research", status_code=201)
async def create_research(payload: ResearchCreate, principal: Principal = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    if principal.session is not None:
        if payload.callback_url is not None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "callback_url is prohibited in research payload for browser sessions; configure it in Settings",
            )
        from app.services.settings import get_record
        cfg = await get_record(db)
        callback = cfg.callback_url
    else:
        # Backend-to-backend client
        if payload.callback_url:
            from app.tools.outbound import validate_public_url
            try:
                validate_public_url(payload.callback_url)
            except Exception as exc:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid callback_url") from exc
            callback = payload.callback_url.strip()
        else:
            callback = None

    research = Research(theme=payload.theme.strip(), callback_url=callback, status="scouting", briefing_draft={})
    db.add(research)
    await db.commit()
    await db.refresh(research)
    schedule_scout(research.id)
    try:
        await add_event(research.id, "scout", "scout_started", "Scout started live preliminary research")
    except Exception:
        pass
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

    callback_configured = bool(research.callback_url)
    callback_status: str | None = None
    if callback_configured:
        latest_callback = await db.scalar(
            select(AuditTrail)
            .where(AuditTrail.research_id == research_id, AuditTrail.stage == "callback")
            .order_by(AuditTrail.id.desc())
            .limit(1)
        )
        if latest_callback:
            callback_status = "delivered" if latest_callback.details.get("delivered") else "failed"
        else:
            latest_ev = await db.scalar(
                select(Event)
                .where(
                    Event.research_id == research_id,
                    Event.event_type.in_(["callback_delivered", "callback_failed"]),
                )
                .order_by(Event.id.desc())
                .limit(1)
            )
            if latest_ev:
                callback_status = "delivered" if latest_ev.event_type == "callback_delivered" else "failed"
            elif research.status == "completed_but_callback_failed":
                callback_status = "failed"
            elif research.status == "failed":
                callback_status = "failed"
            else:
                callback_status = "pending"

    return {
        "research_id": research.id,
        "theme": research.theme,
        "status": research.status,
        "callback_configured": callback_configured,
        "callback_status": callback_status,
        "briefing_draft": research.briefing_draft,
        "error": research.error,
        "briefing_edit_available": research.status == "pending_approval",
        "points": [{"id": p.id, "title": p.title, "status": p.status, "attempt_count": p.attempt_count, "audit": p.audit} for p in points],
        "created_at": research.created_at,
        "updated_at": research.updated_at,
    }


@router.post("/research/{research_id}/briefing/edit")
async def edit_briefing(research_id: uuid.UUID, payload: BriefingEdit, _: Principal = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    note = payload.note.strip()
    if not note:
        raise HTTPException(422, "Edit note is required")
    if payload.points:
        try:
            point_dependencies(payload.points)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    research = await db.get(Research, research_id)
    if not research:
        raise HTTPException(404, "Research not found")
    if research.status != "pending_approval" or research.approved_at is not None:
        raise HTTPException(409, "Briefing is no longer editable")

    draft = dict(research.briefing_draft or {})
    if payload.points:
        draft["points"] = [p.model_dump() for p in payload.points]
    draft["edit_note"] = note
    draft["source"] = "operator_edit"

    try:
        result = await db.execute(
            update(Research)
            .where(
                Research.id == research_id,
                Research.status == "pending_approval",
                Research.approved_at.is_(None),
            )
            .values(
                status="revising",
                briefing_draft=draft,
            )
        )
        if result.rowcount != 1:
            await db.rollback()
            raise HTTPException(409, "Briefing is no longer editable")
        await db.commit()
    except HTTPException:
        raise
    except Exception:
        await db.rollback()
        exists = await db.get(Research, research_id)
        if exists and (exists.status != "pending_approval" or exists.approved_at is not None):
            raise HTTPException(409, "Briefing is no longer editable")
        raise

    schedule_revision(research_id)

    try:
        await add_event(research_id, "system", "briefing_edited", "Operator requested briefing revision", {})
    except Exception:
        pass

    return {"research_id": research_id, "status": "revising"}


@router.post("/research/{research_id}/briefing/approve")
async def approve(research_id: uuid.UUID, payload: BriefingApproval, _: Principal = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    try:
        point_dependencies(payload.approved_points)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    draft = {"points": [point.model_dump() for point in payload.approved_points], "source": "operator_approved"}
    try:
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
    except HTTPException:
        raise
    except Exception:
        await db.rollback()
        exists = await db.get(Research, research_id)
        if exists and (exists.status != "pending_approval" or exists.approved_at is not None):
            raise HTTPException(409, "Briefing already approved or no longer approvable")
        raise
    schedule(research_id)
    try:
        await add_event(research_id, "system", "briefing_approved", "Briefing approved exactly once", {"points": len(payload.approved_points)})
    except Exception:
        pass
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
                if research.callback_url and research.status in {"completed", "blocked"}:
                    async with AsyncSessionLocal() as sdb:
                        has_cb = await sdb.scalar(
                            select(Event.id)
                            .where(
                                Event.research_id == research_id,
                                Event.event_type.in_(["callback_delivered", "callback_failed"]),
                            )
                            .limit(1)
                        )
                    if not has_cb:
                        await asyncio.sleep(0.5)
                        continue
                break
            await asyncio.sleep(0.5)
    return StreamingResponse(generate(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/reports/{identifier}")
async def report(identifier: uuid.UUID, _: Principal = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    from sqlalchemy import or_
    row = await db.scalar(select(Report).where(or_(Report.research_id == identifier, Report.id == identifier)))
    if not row:
        raise HTTPException(404, "Report not found")
    return {"report_id": row.id, "research_id": row.research_id, "content_markdown": row.content_markdown, "citation_metrics": row.citation_metrics, "audit_findings": row.audit_findings, "generated_at": row.generated_at}


@router.post("/reports/{identifier}/retry-callback")
async def retry_callback(identifier: uuid.UUID, _: Principal = Depends(require_admin)):
    async with AsyncSessionLocal() as db:
        from sqlalchemy import or_
        rep = await db.scalar(select(Report).where(or_(Report.research_id == identifier, Report.id == identifier)))
        effective_research_id = rep.research_id if rep else identifier

        research = await db.get(Research, effective_research_id)
        if not research:
            raise HTTPException(404, "Research not found")
        if not research.callback_url:
            raise HTTPException(409, "No callback configured")
        if not await db.scalar(select(Report.id).where(Report.research_id == effective_research_id)):
            raise HTTPException(409, "Report not ready")
    delivered = await dispatch_callback(effective_research_id)
    return {"success": delivered, "delivered": delivered}


@router.post("/research/{research_id}/resume")
async def resume(
    research_id: uuid.UUID,
    _: Principal = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    research = await db.get(Research, research_id)
    if not research:
        raise HTTPException(404, "Research not found")
    if research.status in {"completed", "completed_but_callback_failed"}:
        raise HTTPException(409, "Research already completed")
    if research.status in {"in_progress", "scouting"}:
        raise HTTPException(409, f"Research is already {research.status}")

    points = list(
        (await db.scalars(
            select(ResearchPoint)
            .where(ResearchPoint.research_id == research_id)
            .order_by(ResearchPoint.position)
        )).all()
    )

    if not points:
        research.status = "scouting"
        research.error = None
        await db.commit()
        schedule_scout(research_id)
        try:
            await add_event(research_id, "system", "research_resumed", "Research scout resumed by operator")
        except Exception:
            pass
        return {"research_id": research_id, "status": "scouting"}

    research.status = "in_progress"
    research.error = None
    await db.commit()
    schedule(research_id)
    try:
        await add_event(research_id, "system", "research_resumed", "Research execution resumed by operator", {"points": len(points)})
    except Exception:
        pass
    return {"research_id": research_id, "status": "in_progress"}

