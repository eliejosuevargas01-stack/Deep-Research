"""Persistência dos resultados dos passos de investigação (T011).

Transações atômicas curtas contra `AsyncSession` (mapa de estados da
seção 4 de requirements.md): grava `ResearchStepResult` e consolida o
status do ponto (`AUDIT_PENDING` / `SCRAPER_FAILED`).
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.investigation.prompts import PERSONA_NAMES
from app.models.domain_models import ResearchPoint, ResearchStepResult

STATUS_AUDIT_PENDING = "AUDIT_PENDING"
STATUS_FAILED = "FAILED"
POINT_SCRAPER_FAILED = "SCRAPER_FAILED"


async def save_step_result(
    db: AsyncSession,
    research_id: UUID,
    step_id: UUID,
    step_title: str,
    worker: str,
    result: str,
    used_urls: list[str],
    read_urls: list[str],
    success: bool,
) -> ResearchStepResult:
    """Grava o resultado da persona e transiciona o status do ponto.

    - status = AUDIT_PENDING em sucesso, FAILED caso contrário.
    - Falha incrementa `attempt_count` atomicamente (UPDATE no banco).
    - Estado consolidado: qualquer AUDIT_PENDING mantém o ponto em
      AUDIT_PENDING; todas as 4 personas gravadas e todas FAILED
      marcam o ponto como SCRAPER_FAILED.
    """
    status = STATUS_AUDIT_PENDING if success else STATUS_FAILED
    step_result = ResearchStepResult(
        id=uuid4(),
        research_id=research_id,
        step_id=step_id,
        step_title=step_title,
        result=result,
        used_urls=used_urls,
        read_urls=read_urls,
        worker=worker,
        status=status,
        created_at=datetime.now(timezone.utc),
    )
    db.add(step_result)
    await db.flush()

    point = await db.get(ResearchPoint, step_id)
    if not success and point is not None:
        await db.execute(
            update(ResearchPoint)
            .where(ResearchPoint.id == step_id)
            .values(attempt_count=ResearchPoint.attempt_count + 1)
        )
        await db.flush()

    if point is not None:
        rows = await db.execute(
            select(ResearchStepResult).where(ResearchStepResult.step_id == step_id)
        )
        results = list(rows.scalars().all())
        any_pending = any(r.status == STATUS_AUDIT_PENDING for r in results)
        if any_pending:
            point.status = STATUS_AUDIT_PENDING
        else:
            workers = {r.worker for r in results}
            all_failed = all(r.status == STATUS_FAILED for r in results)
            if set(PERSONA_NAMES).issubset(workers) and all_failed:
                point.status = POINT_SCRAPER_FAILED

    await db.commit()
    return step_result


async def get_step_results(db: AsyncSession, research_id: UUID) -> list[ResearchStepResult]:
    """Todos os resultados da pesquisa ordenados por `created_at`."""
    result = await db.execute(
        select(ResearchStepResult)
        .where(ResearchStepResult.research_id == research_id)
        .order_by(ResearchStepResult.created_at.asc())
    )
    return list(result.scalars().all())


async def get_pending_workers_for_research(db: AsyncSession, research_id: UUID) -> list[dict]:
    """Helper de retomada (T018): personas sem linha gravada por ponto.

    Retorna [{"step_id", "step_title", "persona"}] para cada ponto da
    pesquisa cuja persona ainda não possui resultado persistido.
    """
    points = await db.execute(
        select(ResearchPoint)
        .where(ResearchPoint.research_id == research_id)
        .order_by(ResearchPoint.position.asc())
    )
    stored = await db.execute(
        select(ResearchStepResult.step_id, ResearchStepResult.worker)
        .where(ResearchStepResult.research_id == research_id)
    )
    done: dict[UUID, set[str]] = {}
    for step_id, worker in stored.all():
        done.setdefault(step_id, set()).add(worker)

    pending: list[dict] = []
    for point in points.scalars().all():
        workers = done.get(point.id, set())
        for persona in PERSONA_NAMES:
            if persona not in workers:
                pending.append(
                    {"step_id": point.id, "step_title": point.title, "persona": persona}
                )
    return pending
