import re
from collections import Counter


def deterministic_citation_audit(evidences: list[dict]) -> dict:
    supported, unsupported = [], []
    for evidence in evidences:
        claim = re.sub(r"\s+", " ", evidence.get("claim", "")).strip().casefold()
        excerpt = re.sub(r"\s+", " ", evidence.get("excerpt", "")).strip().casefold()
        item = {"url": evidence.get("url"), "claim": evidence.get("claim"), "verbatim_match": bool(claim and claim in excerpt)}
        # ponytail: exact text is necessary traceability, not semantic truth; auditor verdict must also pass.
        (supported if evidence.get("url") and item["verbatim_match"] else unsupported).append(item)
    personas = Counter(item.get("persona") for item in evidences)
    return {
        "supported": len(supported), "unsupported": unsupported,
        "personas_present": sorted(p for p in personas if p),
        "complete_personas": all(personas[p] > 0 for p in ("historian", "skeptic", "pragmatist", "futurist")),
    }


def audit_approves(checks: dict, verdict: object) -> bool:
    if not isinstance(verdict, dict) or type(verdict.get("approved")) is not bool:
        return False
    if not all(isinstance(verdict.get(key), list) for key in ("findings", "contradictions", "uncertainties", "outline")):
        return False
    if not all(isinstance(item, str) for key in ("findings", "contradictions", "uncertainties", "outline") for item in verdict[key]):
        return False
    # LLM approves, no contradictions detected, basic personas present
    return bool(verdict["approved"] and not verdict["contradictions"] and checks["complete_personas"])


def next_audit_state(approved: bool, attempt: int, max_attempts: int = 4) -> str:
    if approved:
        return "approved"
    return "blocked" if attempt >= max_attempts else "retry_required"
