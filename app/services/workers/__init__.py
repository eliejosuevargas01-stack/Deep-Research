"""Workers module exposing BaseWorker, ScoutWorker, Persona Workers, WriterAgent, and factory."""
from app.services.workers.base import BaseWorker, WorkerResult
from app.services.workers.scout import ScoutWorker
from app.services.workers.personas import (
    FuturistWorker,
    HistorianWorker,
    PragmatistWorker,
    SkepticWorker,
)
from app.services.workers.writer import WriterAgent
from app.services.audit_agent import AuditorAgent, AuditVerdict


def create_workers(
    session,
    settings,
    model_names: dict[str, str] | None = None,
) -> dict[str, BaseWorker]:
    """
    Factory to create all worker instances with shared dependencies.

    Args:
        session: AsyncSession for DB operations
        settings: Runtime settings object
        model_names: Optional dict mapping persona -> model name

    Returns:
        Dict with keys: 'scout', 'historian', 'skeptic', 'pragmatist', 'futurist', 'writer', 'auditor'
    """
    model_names = model_names or {}

    return {
        "scout": ScoutWorker(
            session=session,
            settings=settings,
            model_name=model_names.get("scout"),
        ),
        "historian": HistorianWorker(
            session=session,
            settings=settings,
            model_name=model_names.get("historian"),
        ),
        "skeptic": SkepticWorker(
            session=session,
            settings=settings,
            model_name=model_names.get("skeptic"),
        ),
        "pragmatist": PragmatistWorker(
            session=session,
            settings=settings,
            model_name=model_names.get("pragmatist"),
        ),
        "futurist": FuturistWorker(
            session=session,
            settings=settings,
            model_name=model_names.get("futurist"),
        ),
        "writer": WriterAgent(
            session=session,
            settings=settings,
            model_name=model_names.get("writer"),
        ),
        "auditor": AuditorAgent(),
    }


__all__ = [
    "BaseWorker",
    "WorkerResult",
    "ScoutWorker",
    "HistorianWorker",
    "SkepticWorker",
    "PragmatistWorker",
    "FuturistWorker",
    "WriterAgent",
    "AuditorAgent",
    "AuditVerdict",
    "create_workers",
]