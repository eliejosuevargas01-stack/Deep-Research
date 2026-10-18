"""Endpoints administrativos do Módulo de Auditoria (T045, RN-301; Feature 003).

- ``POST /api/audit/{research_id}/run``: audita todos os pontos pendentes
  da pesquisa (``AUDIT_PENDING``, ``SCRAPER_RETRY``,
  ``AUDIT_INCONCLUSIVE``); idempotente — sem pendências vira 409.
- ``POST /api/audit/{research_id}/points/{point_id}/run``: auditoria
  isolada de um ponto; retorna ``AuditVerdictResponse`` estruturado.

Ambos protegidos por autenticação de administrador (``require_admin``)
e usam instâncias próprias de ``AuditService(AsyncSessionLocal)``.
Conflito ou estado inválido (pesquisa liberada para o Redator, ponto já
conclusivo ou em coleta) responde HTTP 409.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.schemas import (
    AuditChecklist,
    AuditPointOutcome,
    AuditRunResponse,
    AuditVerdictResponse,
)
from app.audit.service import AuditService
from app.audit.domain import SCRAPER_RETRY
from app.core.security import Principal, require_admin
from app.db.database import AsyncSessionLocal, get_db
from app.models.domain_models import Research, ResearchPoint, ResearchStatus

router = APIRouter(prefix="/api/audit", tags=["audit"])

#: Estados de ponto elegíveis para auditoria via API (RN-301, D-301).
_AUDITABLE_POINT_STATES = ("AUDIT_PENDING", "SCRAPER_RETRY", "AUDIT_INCONCLUSIVE")

NO_PENDING_DETAIL = "Nenhum ponto pendente para auditoria nesta pesquisa"


def _audit_service() -> AuditService:
    """Instância de serviço fabricada por requisição (T045)."""

    return AuditService(AsyncSessionLocal)


def _outcome(point_id: UUID, verdict, attempt: int | None) -> AuditPointOutcome:
    return AuditPointOutcome(
        point_id=point_id,
        attempt=attempt,
        state=verdict.status,
        score=verdict.score,
        approved=verdict.approved,
        missing_research=[str(m) for m in (verdict.missing_research or [])],
        detail=None,
    )


@router.post("/{research_id}/run", response_model=AuditRunResponse)
async def run_research_audit(
    research_id: UUID,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_admin),  # noqa: ARG001
) -> AuditRunResponse:
    """Audita todos os pontos pendentes da pesquisa e transita WRITE (T045/T049)."""

    if db.in_transaction():
        await db.rollback()

    research = await db.get(Research, research_id)
    if research is None:
        raise HTTPException(status_code=404, detail="Pesquisa não encontrada")

    rows = await db.execute(
        select(ResearchPoint)
        .where(
            ResearchPoint.research_id == research_id,
            ResearchPoint.status.in_(_AUDITABLE_POINT_STATES),
        )
        .order_by(ResearchPoint.position.asc(), ResearchPoint.id.asc())
    )
    pending_points = list(rows.scalars().all())
    if not pending_points:
        raise HTTPException(status_code=409, detail=NO_PENDING_DETAIL)

    service = _audit_service()
    outcomes: list[AuditPointOutcome] = []
    for point in pending_points:
        verdict = await service.audit_point(research_id, point.id)
        if verdict.status == SCRAPER_RETRY:
            # RN-303: reprovação incrementa attempt_count do ponto (último
            # passo do ciclo); o re-disparo das personas fica no
            # InvestigationService (T047).
            await service.bump_retry_attempt(research_id, point.id)
        # Attempt executado vem do próprio veredito (None quando
        # AUDIT_INCONCLUSIVE, RN-304).
        outcomes.append(_outcome(point.id, verdict, verdict.attempt))

    # As auditorias rodaram em sessões próprias: expira o identity map desta
    # sessão para que a checagem de transição veja os status recém-persistidos.
    db.expire_all()

    write_transitioned = await service.check_all_points_completed(db, research_id)
    refreshed = await db.get(Research, research_id)
    research_status = refreshed.status if refreshed is not None else research.status

    return AuditRunResponse(
        research_id=research_id,
        requested_points=len(outcomes),
        outcomes=outcomes,
        research_status=research_status,
        write_transitioned=bool(write_transitioned),
    )


@router.post("/{research_id}/points/{point_id}/run", response_model=AuditVerdictResponse)
async def run_point_audit(
    research_id: UUID,
    point_id: UUID,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_admin),  # noqa: ARG001
) -> AuditVerdictResponse:
    """Audita isoladamente um único ponto da pesquisa (T045)."""

    if db.in_transaction():
        await db.rollback()

    research = await db.get(Research, research_id)
    if research is None:
        raise HTTPException(status_code=404, detail="Pesquisa não encontrada")

    point = await db.get(ResearchPoint, point_id)
    if point is None or point.research_id != research_id:
        raise HTTPException(status_code=404, detail="Ponto de pesquisa não encontrado")

    if research.status in (ResearchStatus.WRITE.value, ResearchStatus.DONE.value):
        raise HTTPException(
            status_code=409,
            detail="Pesquisa já liberada para o Redator; auditoria de ponto indisponível",
        )
    if point.status not in _AUDITABLE_POINT_STATES:
        raise HTTPException(
            status_code=409,
            detail=f"Estado do ponto não permite auditoria: {point.status}",
        )

    service = _audit_service()
    try:
        verdict = await service.audit_point(research_id, point_id)
    except ValueError:
        # Corrida: ponto desapareceu entre a checagem e a execução.
        raise HTTPException(
            status_code=404, detail="Ponto de pesquisa não encontrado"
        ) from None

    return AuditVerdictResponse(
        checklist=AuditChecklist(
            **{key: bool(verdict.checklist.get(key, False)) for key in AuditChecklist.model_fields}
        ),
        score=verdict.score,
        approved=verdict.approved,
        findings=list(verdict.findings),
        contradictions=list(verdict.contradictions),
        uncertainties=list(verdict.uncertainties),
        missing_research=list(verdict.missing_research),
    )


__all__ = ["router"]
