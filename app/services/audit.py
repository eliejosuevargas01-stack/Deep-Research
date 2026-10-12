import re
from collections import Counter


def deterministic_citation_audit(evidences: list[dict]) -> dict:
    supported, unsupported = [], []
    for evidence in evidences:
        claim = re.sub(r"\s+", " ", str(evidence.get("claim", ""))).strip().casefold()
        excerpt_raw = evidence.get("excerpt") or evidence.get("exact_quote") or ""
        excerpt = re.sub(r"\s+", " ", str(excerpt_raw)).strip().casefold()
        url = evidence.get("url") or evidence.get("source_url")
        item = {"url": url, "claim": evidence.get("claim"), "verbatim_match": bool(claim and claim in excerpt)}
        # ponytail: exact text is necessary traceability, not semantic truth; auditor verdict must also pass.
        (supported if url and item["verbatim_match"] else unsupported).append(item)
    personas = Counter(item.get("persona") for item in evidences)
    return {
        "supported": len(supported), "unsupported": unsupported,
        "personas_present": sorted(p for p in personas if p),
        "complete_personas": all(personas[p] > 0 for p in ("historian", "skeptic", "pragmatist", "futurist")),
    }


def audit_approves(checks: dict, verdict: object) -> bool:
    if checks.get("unsupported"):
        return False
    if not isinstance(verdict, dict) or type(verdict.get("approved")) is not bool:
        return False
    if not all(isinstance(verdict.get(key), list) for key in ("findings", "contradictions", "uncertainties", "outline")):
        return False
    if not all(isinstance(item, str) for key in ("findings", "contradictions", "uncertainties", "outline") for item in verdict[key]):
        return False
    if not checks.get("complete_personas"):
        return False
    if verdict.get("contradictions"):
        return False

    # Score calculation on 12-question checklist
    checklist = verdict.get("checklist")
    if isinstance(checklist, dict) and checklist:
        score = sum(1 for k, v in checklist.items() if isinstance(k, str) and k.lower().startswith("q") and bool(v))
    else:
        # Backward compatibility when checklist is omitted
        score = 12 if verdict.get("approved") else 0

    # Minimum threshold: 10/12 (80%)
    return bool(verdict["approved"] and score >= 10)


def next_audit_state(approved: bool, attempt: int, max_attempts: int = 4) -> str:
    if approved:
        return "approved"
    return "blocked" if attempt >= max_attempts else "retry_required"
