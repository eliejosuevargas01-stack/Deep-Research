"""Writer stage: final report synthesis with evidence grounding and citation validation."""
import json
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import AsyncSessionLocal
from app.models import (
    Evidence,
    InvestigationMerge,
    Report,
    Research,
    ResearchPoint,
    ResearchStatus,
)
from app.services.llm import complete

_LIMITATION_PATTERNS = (
    r"sem evid[êe]ncias? aproveit[áa]ve(is|l)",
    r"sem material verific[áa]vel",
    r"n[ãa]o [ée] poss[íi]vel concluir",
    r"permanecem indeterminad[ao]s?",
    r"nenhuma evid[êe]ncia aproveit[áa]vel",
    r"conte[úu]do n[ãa]o dispon[íi]vel",
    r"sem fontes para citar",
    r"sem evid[êe]ncias?",
    r"sem material",
)


def _is_limitation_notice(text: str) -> bool:
    low = text.lower()
    return any(re.search(pat, low) for pat in _LIMITATION_PATTERNS)


def _is_nonfactual_proposal(text: str) -> bool:
    clean = text.strip()
    clean = re.sub(r"^(?:\*\*|__)(.*?)(?:\*\*|__)", r"\1", clean)
    clean_low = clean.lower()
    if clean_low.startswith("proposta didática:") or clean_low.startswith("proposta didatica:"):
        has_empirical_fact = bool(re.search(r"\d+%|\d{4}|mediu|registrou|custos?", clean_low))
        return not has_empirical_fact
    return False


def _is_table_header_or_divider(line: str) -> bool:
    clean = line.strip()
    if not clean.startswith("|"):
        return False
    if re.match(r"^\|?\s*[-:]+[-|\s:]*$", clean):
        return True
    cells = [c.strip() for c in clean.split("|")[1:-1]]
    if all(len(c.split()) <= 2 and not re.search(r"[.!?]$|\d+%", c) for c in cells):
        return True
    return False


def _requires_citation(line: str) -> bool:
    s = line.strip()
    if not s or s.lstrip().startswith(("#", ">")):
        return False
    if s.lower().startswith(("references", "fontes", "referências")):
        return False
    if _is_table_header_or_divider(s):
        return False
    if _is_limitation_notice(s):
        return False
    if _is_nonfactual_proposal(s):
        return False

    clean_line = re.sub(r"^(?:[-*+]\s+|\d+[.)]\s+|\|?\s*)", "", s)
    clean_line = re.sub(r"\|?\s*$", "", clean_line).strip()
    clean_line = re.sub(r"^(?:\*\*|__)(.*?)(?:\*\*|__)", r"\1", clean_line)

    has_substance = bool(re.search(r"[a-zA-ZÀ-ÿ]{3,}", clean_line)) and len(clean_line.split()) >= 4
    if not has_substance:
        return False

    return True


def validate_report_quality(text: str, point_titles: list[str]) -> None:
    """Do not publish a stub as a completed multi-point research report."""
    headings = {match.group(1).strip().casefold() for match in re.finditer(r"(?m)^#{2,4}\s+(.+?)\s*$", text)}
    if any(
        not any(heading.startswith(title.strip().casefold()) for heading in headings)
        for title in point_titles
    ):
        raise ValueError("Writer returned incomplete report")


async def _write_report(research: Research, points: list[ResearchPoint]) -> None:
    async with AsyncSessionLocal() as db:
        evidence = list(
            (
                await db.scalars(
                    select(Evidence)
                    .join(ResearchPoint)
                    .where(ResearchPoint.research_id == research.id)
                )
            ).all()
        )
        try:
            merges = list(
                (
                    await db.scalars(
                        select(InvestigationMerge)
                        .join(ResearchPoint)
                        .where(ResearchPoint.research_id == research.id)
                    )
                ).all()
            )
        except Exception:
            merges = []

        point_map = {str(point.id): point for point in points}
        bundle = []
        known_urls = {row.source_url for row in evidence if getattr(row, "source_url", None)}

        for row in evidence:
            point = point_map.get(str(row.research_point_id))
            bundle.append(
                {
                    "point": point.title if point else "",
                    "persona": row.persona,
                    "claim": row.claim,
                    "quote": row.excerpt,
                    "url": row.source_url,
                    "analysis": row.analysis,
                }
            )

        for merge in merges:
            if not hasattr(merge, "step_id") or not hasattr(merge, "content"):
                continue
            point = point_map.get(str(merge.step_id))
            mcontent = merge.content if isinstance(merge.content, dict) else {}
            personas_data = mcontent.get("personas", {})
            if isinstance(personas_data, dict):
                for persona_name, pinfo in personas_data.items():
                    if isinstance(pinfo, dict):
                        analysis = pinfo.get("analysis", "")
                        for cit in pinfo.get("citations", []):
                            if isinstance(cit, dict) and cit.get("source_url"):
                                surl = cit["source_url"]
                                known_urls.add(surl)
                                bundle.append(
                                    {
                                        "point": point.title if point else "",
                                        "persona": persona_name,
                                        "claim": cit.get("claim", ""),
                                        "quote": cit.get("exact_quote", ""),
                                        "url": surl,
                                        "analysis": analysis,
                                    }
                                )

        audits = [
            {"point": point.title, "status": point.status, "audit": point.audit}
            for point in points
        ]
        text = await complete(
            "writer",
            "Write a substantive Markdown research report in Brazilian Portuguese (pt-BR) using only supplied evidence. Include a ## heading matching each research point title exactly and explain its evidence, gaps and uncertainty; aim for at least 400 words overall. CRITICAL CITATION RULE: Every sentence and bullet point asserting facts must include an inline markdown link to its source url from the evidence, formatted as [texto](url). Include blocked-point caveats, then References. Do not invent facts or expose private reasoning.",
            json.dumps({"theme": research.theme, "evidence": bundle, "audits": audits}, ensure_ascii=False),
            db,
        )
        if not text.strip():
            raise RuntimeError("Writer cannot produce an empty report")
        validate_report_quality(text, [point.title for point in points])

        if known_urls:
            cited = sum(1 for url in known_urls if url in text)
            if cited == 0:
                raise RuntimeError("Writer produced report without source citations")
        else:
            cited = 0

        # ponytail: URL membership is traceability, not factual verification; add claim-level entailment before promising it.
        linked_urls = set(re.findall(r"\]\((https?://[^\s)]+)\)", text))
        if linked_urls and not linked_urls.issubset(known_urls):
            raise RuntimeError("Writer used uncollected citation URLs")

        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if _requires_citation(line) and not re.search(r"\]\(https?://[^\s)]+\)", line):
                import sys
                sys.stderr.write(f"GUARDRAIL FAIL LINE: {line[:300]}\n")
                raise RuntimeError("Writer published uncited factual content (prose, list, or table)")

        report = Report(
            research_id=research.id,
            content_markdown=text,
            citation_metrics={"evidence_records": len(evidence), "source_urls_cited": cited},
            audit_findings={"points": audits},
        )
        db.add(report)
        stored = await db.get(Research, research.id)
        if stored:
            stored.status = ResearchStatus.DONE.value
        await db.commit()
    from app.services.research import add_event
    await add_event(
        research.id,
        "writer",
        "synthesis_completed",
        "Evidence-grounded report persisted",
        {"evidence_records": len(evidence), "citations": cited},
    )


__all__ = ["_write_report", "validate_report_quality"]
