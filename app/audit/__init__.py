"""Módulo de Auditoria Factual e Julgamento de Evidências (Feature 003).

Exposição pública do domínio puro e dos schemas Pydantic consumidos por
``AuditService`` (T043), ``router`` (T045) e ``investigation`` (T046–T049).
"""

from app.audit.domain import (
    APPROVAL_MIN_SCORE,
    AUDIT_APPROVED,
    AUDIT_CAVEAT,
    AUDIT_CRITERIA,
    CRITERION_IDS,
    MAX_ATTEMPTS,
    REDACTED,
    SCRAPER_RETRY,
    AuditVerdict,
    calculate_score,
    default_missing_research,
    evaluate_audit_verdict,
    normalize_checklist,
    sanitize_audit_dict,
)
from app.audit.service import AuditService
from app.audit.schemas import AuditChecklist, AuditRunResponse, AuditVerdictResponse

__all__ = [
    # Constantes de estado e regras
    "APPROVAL_MIN_SCORE",
    "AUDIT_APPROVED",
    "AUDIT_CAVEAT",
    "AUDIT_CRITERIA",
    "CRITERION_IDS",
    "MAX_ATTEMPTS",
    "REDACTED",
    "SCRAPER_RETRY",
    # Domínio
    "AuditVerdict",
    "calculate_score",
    "default_missing_research",
    "evaluate_audit_verdict",
    "normalize_checklist",
    "sanitize_audit_dict",
    # Schemas
    "AuditChecklist",
    "AuditRunResponse",
    "AuditVerdictResponse",
    # Serviço (T043/T044)
    "AuditService",
]
