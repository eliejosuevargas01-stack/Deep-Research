"""Point executor: run personas, audit, retry loop for one research point."""
import asyncio
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.database import AsyncSessionLocal
from app.models import AuditTrail, ResearchPoint
from app.services.pipeline.audit_stage import _audit_point
from app.services.pipeline.worker import run_worker
from app.services.pipeline.constants import PERSONAS


def remaining_attempts(point: ResearchPoint, maximum: int) -> list[int]:
    if point.status in {"approved", "blocked"}:
        return []
    return list(range(point.attempt_count + 1, maximum + 1))


async def _run_point(research_id: uuid.UUID, point: ResearchPoint) -> bool:
    feedback = ""
    for attempt in remaining_attempts(point, settings.MAX_AUDIT_ATTEMPTS):
        async with AsyncSessionLocal() as db:
            stored = await db.get(ResearchPoint, point.id)
            if stored is None:
                return False
            stored.attempt_count = attempt
            stored.status = "in_progress"
            await db.commit()
        results = await asyncio.gather(
            *(run_worker(research_id, point.id, point.title, point.description, persona, feedback) for persona in PERSONAS),
            return_exceptions=True,
        )
        failures = sum(isinstance(result, Exception) for result in results)
        if failures:
            async with AsyncSessionLocal() as db:
                for persona, result in zip(PERSONAS, results):
                    if isinstance(result, Exception):
                        db.add(AuditTrail(research_id=research_id, point_id=point.id, stage="worker_failure",
                                          attempt=attempt, details={"persona": persona, "error_type": type(result).__name__}))
                await db.commit()
            from app.services.research import add_event
            await add_event(research_id, "system", "worker_failures", f"{failures} worker executions failed safely", {"failed_workers": failures})
        try:
            if await _audit_point(research_id, point, attempt):
                return True
        except Exception as exc:
            # Graceful degradation: audit infrastructure failure must not kill the
            # research. Mark attempt as failed and continue the retry loop.
            async with AsyncSessionLocal() as db:
                db.add(AuditTrail(research_id=research_id, point_id=point.id, stage="audit_failure",
                                  attempt=attempt, details={"error_type": type(exc).__name__}))
                await db.commit()
            from app.services.research import add_event
            await add_event(research_id, "system", "audit_failure",
                            f"Audit attempt {attempt} failed safely: {type(exc).__name__}",
                            {"error_type": type(exc).__name__}, point_id=point.id, point_title=point.title)
            continue
        async with AsyncSessionLocal() as db:
            refreshed = await db.get(ResearchPoint, point.id)
            missing = (refreshed.audit or {}).get("llm", {}).get("missing_research", []) if refreshed else []
            findings = (refreshed.audit or {}).get("llm", {}).get("findings", []) if refreshed else []
            feedback = "; ".join(str(m) for m in (missing or findings))[:1000]
    if point.status not in {"approved", "blocked"}:
        async with AsyncSessionLocal() as db:
            stored = await db.get(ResearchPoint, point.id)
            if stored and stored.status not in {"approved", "blocked"}:
                stored.status = "blocked"
                await db.commit()
    return False


__all__ = ["_run_point", "remaining_attempts"]
