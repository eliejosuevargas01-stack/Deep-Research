"""Auditor Agent: independent verification of evidence verbatim citations and persona completeness."""
from __future__ import annotations

from enum import Enum
from typing import Any, Sequence

from app.models.domain_models import Evidence, ResearchPoint
from app.services.audit import audit_approves, deterministic_citation_audit, next_audit_state


class AuditVerdict(str, Enum):
    APPROVED = "approved"
    RETRY_REQUIRED = "retry_required"
    BLOCKED = "blocked"


class AuditorAgent:
    """Performs deterministic verification of citations and personas according to Reversa Principles."""

    def __init__(self, max_attempts: int = 4) -> None:
        self.max_attempts = max_attempts

    def audit_evidences(self, evidences: Sequence[Evidence | dict[str, Any]]) -> dict[str, Any]:
        """Convert Evidence models or dicts to format expected by deterministic_citation_audit."""
        payload: list[dict[str, Any]] = []
        for ev in evidences:
            if isinstance(ev, Evidence):
                payload.append({
                    "url": ev.source_url,
                    "claim": ev.claim,
                    "excerpt": ev.excerpt,
                    "persona": ev.persona,
                })
            elif isinstance(ev, dict):
                payload.append(ev)
        return deterministic_citation_audit(payload)

    def evaluate_verdict(
        self,
        checks: dict[str, Any],
        llm_verdict: dict[str, Any] | None,
        attempt: int,
    ) -> tuple[AuditVerdict, str]:
        """Combine deterministic checks and optional LLM verdict into an AuditVerdict."""
        approved = audit_approves(checks, llm_verdict or {"approved": True, "findings": [], "contradictions": [], "uncertainties": [], "outline": []})
        state = next_audit_state(approved=approved, attempt=attempt, max_attempts=self.max_attempts)
        if state == "approved":
            return AuditVerdict.APPROVED, "Auditoria aprovada com sucesso."
        elif state == "blocked":
            return AuditVerdict.BLOCKED, "Auditoria bloqueada por exceder limite de retentativas."
        return AuditVerdict.RETRY_REQUIRED, "Auditoria requer re-tentativa (evidências incompletas ou citação não verbatim)."
