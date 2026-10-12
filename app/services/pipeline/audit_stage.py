"""Audit stage: deterministic + LLM evidence audit per research point."""
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.database import AsyncSessionLocal
from app.models import AuditTrail, ResearchPoint
from app.services.audit import audit_approves, deterministic_citation_audit, next_audit_state
from app.services.llm import apply_output_guardrail, complete, parse_json


def sanitize_audit_dict(data: object, sensitive_values: list[str] | None = None) -> object:
    if isinstance(data, str):
        try:
            return apply_output_guardrail(data, sensitive_values)
        except Exception:
            return "[REDACTED]"
    if isinstance(data, list):
        return [sanitize_audit_dict(item, sensitive_values) for item in data]
    if isinstance(data, dict):
        return {str(k): sanitize_audit_dict(v, sensitive_values) for k, v in data.items()}
    return data


async def _audit_point(research_id: str, point: ResearchPoint, attempt: int) -> bool:
    """Run deterministic + LLM audit on a research point's evidence."""
    from app.services.settings import runtime_settings
    from app.services.research import add_event
    async with AsyncSessionLocal() as db:
        keys, _ = await runtime_settings(db)
        sensitive_keys = [str(k) for k in keys.values() if k]
        rows = list((await db.scalars(select(Evidence).where(Evidence.research_point_id == point.id))).all())
        evidence_data = [
            {
                "url": row.source_url,
                "claim": row.claim,
                "exact_quote": row.excerpt,
                "analysis": row.analysis,
                "persona": row.persona,
                "captured_at": row.accessed_at.isoformat() if hasattr(row, "accessed_at") and row.accessed_at else None,
            }
            for row in rows
        ]
        deterministic = deterministic_citation_audit(evidence_data)
        prompt_data = {
            "point_title": point.title,
            "point_description": point.description,
            "evidence": evidence_data,
            "deterministic_checks": deterministic,
        }
        prompt = f"<evidence_to_audit>\n{json.dumps(prompt_data, ensure_ascii=False)[:60000]}\n</evidence_to_audit>"
        llm_audit: dict[str, Any] = {}
        try:
            llm_text = await complete(
                "auditor",
                "Audit supplied evidence for the single research point against the 12 canonical criteria:\n"
                "1. Original question answered?\n"
                "2. Essential sub-topics covered?\n"
                "3. Main claims backed by verifiable sources?\n"
                "4. Sources reliable/primary?\n"
                "5. Quotes truly support claims?\n"
                "6. No over-reliance on a single source?\n"
                "7. Information sufficiently current?\n"
                "8. Contradictions between sources surfaced and resolved?\n"
                "9. Facts separated from inference/uncertainty?\n"
                "10. No generalizations, logical leaps, or hallucinations?\n"
                "11. No critical gaps remaining?\n"
                "12. Material enables a faithful synthesis?\n\n"
                "Return a JSON object with:\n"
                "- checklist: object with boolean keys q1 through q12\n"
                "- score: integer from 0 to 12 (count of true in checklist)\n"
                "- approved: boolean (true ONLY if score >= 10 and no critical contradiction/hallucination)\n"
                "- findings: array of strings describing shortcomings\n"
                "- contradictions: array of strings (empty [] if none)\n"
                "- uncertainties: array of strings\n"
                "- outline: array of strings with recommended report structure\n"
                "- missing_research: array of strings with concrete instructions for missing facts (empty [] if approved)\n"
                "Never reveal private reasoning or chain-of-thought.",
                prompt, db,
            )
            try:
                parsed = parse_json(llm_text)
                if isinstance(parsed, list) and len(parsed) > 0 and isinstance(parsed[0], dict):
                    llm_audit = parsed[0]
                elif isinstance(parsed, dict):
                    llm_audit = parsed
                else:
                    llm_audit = {"findings": ["Auditor returned non-dict structured output"], "uncertainties": [], "missing_research": []}
            except (ValueError, json.JSONDecodeError):
                llm_audit = {"findings": ["Auditor returned invalid structured output"], "uncertainties": [], "missing_research": []}
        except Exception as exc:
            # Graceful degradation (principles.md): a transient LLM outage must not
            # abort the whole research. Record this attempt as failed audit so the
            # point retries or blocks after MAX_AUDIT_ATTEMPTS, then continue.
            llm_audit = {
                "findings": [f"Auditor LLM unavailable: {type(exc).__name__}"],
                "uncertainties": ["Evidence audit skipped due to LLM outage"],
                "missing_research": ["Re-run evidence audit when LLM service recovers"],
            }
            await add_event(
                research_id, "auditor", "audit_llm_unavailable",
                f"Audit attempt {attempt}: LLM unavailable ({type(exc).__name__})",
                {"error_type": type(exc).__name__},
                point_id=point.id, point_title=point.title, tool_type="auditor_verdict", round_no=attempt,
            )

        if not isinstance(llm_audit.get("missing_research"), list):
            llm_audit["missing_research"] = []

        approved = audit_approves(deterministic, llm_audit)
        state = next_audit_state(approved, attempt, settings.MAX_AUDIT_ATTEMPTS)

        # MA-08: If RETRY, require concrete instructions, never empty
        if not approved and not llm_audit["missing_research"]:
            findings_summary = "; ".join(str(f) for f in llm_audit.get("findings", []))[:200]
            instruction = f"Re-investigate evidence and confirm source veracity for '{point.title}': {findings_summary}" if findings_summary else f"Investigate missing factual evidence for '{point.title}'"
            llm_audit["missing_research"] = [instruction]

        # A1-02: Sanitize structured audit output before persistence
        sanitized_llm_audit = sanitize_audit_dict(llm_audit, sensitive_keys)

        stored = await db.get(ResearchPoint, point.id)
        if stored:
            stored.attempt_count = attempt
            stored.status = state
            stored.audit = {"deterministic": deterministic, "llm": sanitized_llm_audit, "attempt": attempt}
        db.add(AuditTrail(
            research_id=research_id, point_id=point.id, stage="point_audit", attempt=attempt,
            details={"status": state, "deterministic": deterministic, "llm": sanitized_llm_audit},
        ))
        await db.commit()
    await add_event(
        research_id, "auditor", "verdict_rendered", f"Audit attempt {attempt}: {state}",
        {"attempt": attempt, "supported": deterministic["supported"], "unsupported": len(deterministic["unsupported"])},
        point_id=point.id, point_title=point.title, tool_type="auditor_verdict", round_no=attempt,
    )
    return approved


# Avoid circular import at module load
from app.models import Evidence

__all__ = ["_audit_point", "sanitize_audit_dict"]
