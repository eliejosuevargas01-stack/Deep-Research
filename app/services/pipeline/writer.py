"""Writer stage: final report synthesis with evidence grounding and citation validation."""
import json
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import AsyncSessionLocal
from app.models import Evidence, Report, Research, ResearchPoint
from app.services.llm import complete


def validate_report_quality(text: str, point_titles: list[str]) -> None:
    """Do not publish a stub as a completed multi-point research report."""
    headings = {match.group(1).strip().casefold() for match in re.finditer(r"(?m)^#{2,4}\s+(.+?)\s*$", text)}
    if len(text.split()) < 200 or any(
        not any(heading.startswith(title.strip().casefold()) for heading in headings)
        for title in point_titles
    ):
        raise ValueError("Writer returned incomplete report")


async def _write_report(research: Research, points: list[ResearchPoint]) -> None:
    async with AsyncSessionLocal() as db:
        evidence = list((await db.scalars(select(Evidence).join(ResearchPoint).where(ResearchPoint.research_id == research.id))).all())
        point_map = {str(point.id): point for point in points}
        bundle = []
        for row in evidence:
            point = point_map.get(str(row.research_point_id))
            bundle.append({"point": point.title if point else "", "persona": row.persona, "claim": row.claim, "quote": row.excerpt, "url": row.source_url, "analysis": row.analysis})
        audits = [{"point": point.title, "status": point.status, "audit": point.audit} for point in points]
        text = await complete(
            "writer",
            "Write a substantive Markdown research report in Brazilian Portuguese (pt-BR) using only supplied evidence. Include a ## heading matching each research point title exactly and explain its evidence, gaps and uncertainty; aim for at least 400 words overall. CRITICAL CITATION RULE: Every sentence and bullet point asserting facts must include an inline markdown link to its source url from the evidence, formatted as [texto](url). Include blocked-point caveats, then References. Do not invent facts or expose private reasoning.",
            json.dumps({"theme": research.theme, "evidence": bundle, "audits": audits}, ensure_ascii=False)[:100000], db,
        )
        if not text.strip() or not evidence:
            raise RuntimeError("Writer cannot produce a report without evidence")
        validate_report_quality(text, [point.title for point in points])
        cited = sum(1 for row in evidence if row.source_url in text)
        if cited == 0:
            raise RuntimeError("Writer produced report without source citations")
        # ponytail: URL membership is traceability, not factual verification; add claim-level entailment before promising it.
        linked_urls = set(re.findall(r"\]\((https?://[^\s)]+)\)", text))
        known_urls = {row.source_url for row in evidence}
        if not linked_urls or not linked_urls.issubset(known_urls):
            raise RuntimeError("Writer used uncollected citation URLs")
        candidate_lines = [
            line.strip() for line in text.splitlines()
            if line.strip()
            and not line.lstrip().startswith(("#", ">"))
            and not line.strip().lower().startswith(("references", "fontes", "referências"))
            and not re.match(r"^\|?\s*[-:]+[-|\s:]*$", line)
        ]
        for line in candidate_lines:
            clean_line = line.lstrip("-*| \t")
            has_substance = bool(re.search(r"[a-zA-Z]{3,}", clean_line)) and len(clean_line.split()) >= 4
            is_factual_candidate = (
                line.startswith(("-", "*", "|"))
                or bool(re.search(r"[.!?]\s*$", line))
            )
            if has_substance and is_factual_candidate and not re.search(r"\]\(https?://[^\s)]+\)", line):
                if line.startswith("|") and any(w in line.lower() for w in ("point", "ponto", "status", "auditoria", "persona", "coluna")):
                    continue
                import sys
                sys.stderr.write(f"GUARDRAIL FAIL LINE: {line[:300]}\n")
                raise RuntimeError("Writer published uncited factual content (prose, list, or table)")
        report = Report(research_id=research.id, content_markdown=text, citation_metrics={"evidence_records": len(evidence), "source_urls_cited": cited}, audit_findings={"points": audits})
        db.add(report)
        stored = await db.get(Research, research.id)
        stored.status = "completed" if all(point.status == "approved" for point in points) else "blocked"
        await db.commit()
    from app.services.research import add_event
    await add_event(research.id, "writer", "synthesis_completed", "Evidence-grounded report persisted", {"evidence_records": len(evidence), "citations": cited})


__all__ = ["_write_report", "validate_report_quality"]
