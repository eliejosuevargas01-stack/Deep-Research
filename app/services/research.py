"""Research orchestration facade.

T010 (Reversa forward): extracted the five pipeline stages into
app/services/pipeline/: scout, worker, audit_stage, point_executor and writer.
This module remains the public API surface for routers and tests.

ponytail: circular imports between pipeline stages and this facade are resolved
with deferred (function-level) imports inside the stage modules.
"""
import asyncio
import re
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.database import AsyncSessionLocal
from app.models import AuditTrail, Event, Evidence, Report, Research, ResearchPoint
from app.services.llm import apply_output_guardrail, parse_json
from app.services.search import search_read
from app.services.pipeline.constants import PERSONAS
from app.services.pipeline.scout import extract_site_domain, scout, _scout_impl, SCOUT_GLOBAL_TIMEOUT
from app.services.pipeline.worker import PERSONA_CONTRACTS, _quote_supported, run_worker
from app.services.pipeline.audit_stage import _audit_point, sanitize_audit_dict
from app.services.pipeline.point_executor import _run_point, remaining_attempts
from app.services.pipeline.writer import _write_report, validate_report_quality

WORK_LIMIT = asyncio.Semaphore(20)


def sanitize_error(exc: Exception | str, context: str = "execution") -> str:
    """Return a privacy-safe error string that never leaks secrets, stack traces, or prompts."""
    if isinstance(exc, Exception):
        err_type = type(exc).__name__
        status_code = getattr(exc, "status_code", None)
        status_part = f" (status={status_code})" if status_code else ""
        return f"{err_type}{status_part}: {context} failed"
    msg = str(exc)
    msg = re.sub(r"(?:bearer|token|key|secret|password|passwd|api[_-]?key)[=:\s]+[A-Za-z0-9_\-\.]{6,}", "[REDACTED]", msg, flags=re.I)
    msg = re.sub(r"(?:sk|gsk|ghp|gho)_[A-Za-z0-9_\-]{16,}", "[REDACTED]", msg, flags=re.I)
    return f"{context}: {msg[:200]}"


def point_dependencies(points) -> dict[int, set[int]]:
    """Validate 1-based point references (or exact titles) and reject cycles."""
    titles = [point.title if hasattr(point, "title") else point["title"] for point in points]
    if len(set(titles)) != len(titles):
        raise ValueError("Research point titles must be unique")
    graph: dict[int, set[int]] = {}
    for index, point in enumerate(points):
        refs = point.dependencies if hasattr(point, "dependencies") else point.get("dependencies", [])
        deps: set[int] = set()
        for ref in refs:
            ref_str = str(ref).strip()
            m = re.match(r"^(?:point|ponto)\s*(\d+)$", ref_str, re.I)
            if ref_str.isdigit():
                parent = int(ref_str) - 1
            elif m:
                parent = int(m.group(1)) - 1
            elif ref in titles:
                parent = titles.index(ref)
            else:
                raise ValueError(f"Unknown point dependency: {ref}")
            if parent < 0 or parent >= len(points) or parent == index:
                raise ValueError("Invalid or self-referential point dependency")
            deps.add(parent)
        graph[index] = deps
    pending = set(graph)
    while pending:
        ready = {index for index in pending if not (graph[index] & pending)}
        if not ready:
            raise ValueError("Research point dependencies contain a cycle")
        pending -= ready
    return graph


def ready_point_batches(points) -> list[list[int]]:
    if len(points) > 20:
        raise ValueError("Maximum 20 research points allowed")
    graph = point_dependencies(points)
    pending = set(graph)
    batches = []
    while pending:
        ready = sorted(index for index in pending if not graph[index] & pending)
        parallel = [index for index in ready if (points[index].is_parallelizable if hasattr(points[index], "is_parallelizable") else points[index].get("is_parallelizable", True))]
        sequential = [index for index in ready if not (points[index].is_parallelizable if hasattr(points[index], "is_parallelizable") else points[index].get("is_parallelizable", True))]
        # Release independent (parallel) points together with the first sequential point (MA-01)
        batch = (parallel + sequential[:1]) if (parallel or sequential) else ready
        batches.append(batch)
        pending.difference_update(batch)
    return batches


async def add_event(
    research_id: uuid.UUID,
    persona: str,
    event_type: str,
    summary: str,
    metrics: dict | None = None,
    point_id: uuid.UUID | None = None,
    point_title: str | None = None,
    tool_type: str | None = None,
    round_no: int | None = None,
) -> None:
    safe_metrics = dict(metrics or {})
    if point_id:
        safe_metrics["point_id"] = str(point_id)
    if point_title:
        safe_metrics["point_title"] = point_title[:200]
    if tool_type:
        safe_metrics["tool_type"] = tool_type
    if round_no is not None:
        safe_metrics["round"] = round_no
    async with AsyncSessionLocal() as db:
        db.add(Event(research_id=research_id, persona=persona, event_type=event_type, summary=summary[:500], metrics=safe_metrics))
        await db.commit()


async def run_research(research_id: uuid.UUID) -> None:
    try:
        async with AsyncSessionLocal() as db:
            research = await db.get(Research, research_id)
            if not research or research.status not in {"approved", "in_progress", "interrupted"}:
                return
            research.status = "in_progress"
            await db.commit()
            points = list((await db.scalars(select(ResearchPoint).where(ResearchPoint.research_id == research_id).order_by(ResearchPoint.position))).all())
        await add_event(research_id, "system", "research_started", "Approved research work started", {"points": len(points)})
        for batch in ready_point_batches(points):
            await asyncio.gather(*(_run_point(research_id, points[index]) for index in batch))
        async with AsyncSessionLocal() as db:
            points = list((await db.scalars(select(ResearchPoint).where(ResearchPoint.research_id == research_id).order_by(ResearchPoint.position))).all())
        await _write_report(research, points)
        if research.callback_url:
            from app.services.webhook import dispatch_callback
            await dispatch_callback(research_id)
    except Exception as exc:
        safe_msg = sanitize_error(exc, "research execution")
        async with AsyncSessionLocal() as db:
            research = await db.get(Research, research_id)
            if research:
                research.status = "failed"
                research.error = safe_msg
                # Do not mark approved points as failed, keep their evidence
                await db.commit()
        await add_event(research_id, "system", "research_failed", safe_msg)


__all__ = [
    "PERSONAS", "WORK_LIMIT", "SCOUT_GLOBAL_TIMEOUT",
    "extract_site_domain", "sanitize_error", "sanitize_audit_dict",
    "point_dependencies", "ready_point_batches", "remaining_attempts",
    "add_event", "run_research", "_scout_impl", "scout",
    "run_worker", "_worker", "_quote_supported", "PERSONA_CONTRACTS",
    "_audit_point", "_run_point", "_write_report", "validate_report_quality",
]

# Backwards-compatible aliases (tests and internal callers use these names)
_worker = run_worker
