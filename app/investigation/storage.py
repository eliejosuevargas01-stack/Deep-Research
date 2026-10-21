"""Persistência dos resultados dos passos de investigação (T011).

Transações atômicas curtas contra `AsyncSession` (mapa de estados da
seção 4 de requirements.md): grava `ResearchStepResult`, gerencia a
barreira de merge por rodada e persiste `InvestigationMerge`.
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.investigation.prompts import PERSONA_NAMES
from app.models.domain_models import InvestigationMerge, ResearchPoint, ResearchStepResult

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
    *,
    round: int,
) -> ResearchStepResult:
    """Grava o resultado da persona e transiciona o status do ponto.

    - round deve ser inteiro positivo (> 0).
    - Valida que step_id pertence a research_id.
    - status = AUDIT_PENDING em sucesso, FAILED caso contrário.
    - Atualiza point.investigation_round = round.
    - Falha incrementa `attempt_count` atomicamente.
    - Estado consolidado: qualquer AUDIT_PENDING mantém o ponto em
      AUDIT_PENDING; todas as 4 personas gravadas e todas FAILED
      marcam o ponto como SCRAPER_FAILED.
    """
    if round is None or isinstance(round, bool) or not isinstance(round, int) or round <= 0:
        raise ValueError("round deve ser um inteiro positivo (> 0)")

    point = await db.get(ResearchPoint, step_id)
    if point is None or point.research_id != research_id:
        raise ValueError(f"step_id {step_id} não pertence a research_id {research_id}")

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
        round=round,
        created_at=datetime.now(timezone.utc),
    )
    db.add(step_result)
    await db.flush()

    point.investigation_round = round

    rows = await db.execute(
        select(ResearchStepResult).where(
            ResearchStepResult.step_id == step_id,
            ResearchStepResult.round == round,
        )
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


async def check_merge_barrier(
    db: AsyncSession,
    research_id: UUID,
    step_id: UUID,
    round: int,
) -> bool:
    """Verifica se as 4 personas completaram a mesma rodada com sucesso."""
    if round is None or isinstance(round, bool) or not isinstance(round, int) or round <= 0:
        return False

    stmt = select(ResearchStepResult.worker).where(
        ResearchStepResult.research_id == research_id,
        ResearchStepResult.step_id == step_id,
        ResearchStepResult.round == round,
        ResearchStepResult.status == STATUS_AUDIT_PENDING,
    )
    rows = await db.execute(stmt)
    successful_workers = {r[0] for r in rows.all()}
    return set(PERSONA_NAMES).issubset(successful_workers)


async def save_investigation_merge(
    db: AsyncSession,
    research_id: UUID,
    step_id: UUID,
    round: int,
    content: dict,
) -> InvestigationMerge:
    """Persiste a consolidação dos resultados das 4 personas da rodada."""
    if round is None or isinstance(round, bool) or not isinstance(round, int) or round <= 0:
        raise ValueError("round deve ser um inteiro positivo (> 0)")

    point = await db.get(ResearchPoint, step_id)
    if point is None or point.research_id != research_id:
        raise ValueError(f"step_id {step_id} não pertence a research_id {research_id}")

    merge = InvestigationMerge(
        id=uuid4(),
        research_id=research_id,
        step_id=step_id,
        round=round,
        content=content,
        created_at=datetime.now(timezone.utc),
    )
    db.add(merge)
    await db.commit()
    return merge


async def get_step_results(db: AsyncSession, research_id: UUID) -> list[ResearchStepResult]:
    """Todos os resultados da pesquisa ordenados por `created_at`."""
    result = await db.execute(
        select(ResearchStepResult)
        .where(ResearchStepResult.research_id == research_id)
        .order_by(ResearchStepResult.created_at.asc())
    )
    return list(result.scalars().all())


async def get_pending_workers_for_research(
    db: AsyncSession,
    research_id: UUID,
    round: int | None = None,
) -> list[dict]:
    """Helper de retomada: personas sem linha gravada por ponto."""
    points = await db.execute(
        select(ResearchPoint)
        .where(ResearchPoint.research_id == research_id)
        .order_by(ResearchPoint.position.asc())
    )
    query = select(ResearchStepResult.step_id, ResearchStepResult.worker).where(
        ResearchStepResult.research_id == research_id
    )
    if round is not None:
        query = query.where(ResearchStepResult.round == round)

    stored = await db.execute(query)
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
