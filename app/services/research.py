import asyncio
import json
import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.database import AsyncSessionLocal
from app.models import AuditTrail, Event, Evidence, Report, Research, ResearchPoint
from app.services.audit import audit_approves, deterministic_citation_audit, next_audit_state
from app.services.llm import complete, parse_json
from app.services.settings import runtime_settings
from app.tools.search_pipeline import search_read

PERSONAS = ("historian", "skeptic", "pragmatist", "futurist")
WORK_LIMIT = asyncio.Semaphore(20)


def point_dependencies(points) -> dict[int, set[int]]:
    """Validate 1-based point references (or exact titles) and reject cycles."""
    titles = [point.title if hasattr(point, "title") else point["title"] for point in points]
    if len(set(titles)) != len(titles):
        raise ValueError("Research point titles must be unique")
    graph: dict[int, set[int]] = {}
    for index, point in enumerate(points):
        refs = point.dependencies if hasattr(point, "dependencies") else point.get("dependencies", [])
        deps: set[int] = set()
        for ref in refs:
            if str(ref).isdigit():
                parent = int(ref) - 1
            elif ref in titles:
                parent = titles.index(ref)
            else:
                raise ValueError(f"Unknown point dependency: {ref}")
            if parent < 0 or parent >= len(points) or parent == index:
                raise ValueError("Invalid or self-referential point dependency")
            deps.add(parent)
        graph[index] = deps
    pending = set(graph)
    while pending:
        ready = {index for index in pending if not (graph[index] & pending)}
        if not ready:
            raise ValueError("Research point dependencies contain a cycle")
        pending -= ready
    return graph


def ready_point_batches(points) -> list[list[int]]:
    graph = point_dependencies(points)
    pending = set(graph)
    batches = []
    while pending:
        ready = sorted(index for index in pending if not graph[index] & pending)
        sequential = [index for index in ready if not points[index].is_parallelizable]
        batch = sequential[:1] if sequential else ready
        batches.append(batch)
        pending.difference_update(batch)
    return batches


def remaining_attempts(point: ResearchPoint, maximum: int) -> list[int]:
    if point.status in {"approved", "blocked"}:
        return []
    return list(range(point.attempt_count + 1, maximum + 1))


async def add_event(research_id: uuid.UUID, persona: str, event_type: str, summary: str, metrics: dict | None = None) -> None:
    async with AsyncSessionLocal() as db:
        db.add(Event(research_id=research_id, persona=persona, event_type=event_type, summary=summary[:500], metrics=metrics or {}))
        await db.commit()


async def scout(theme: str, db: AsyncSession, feedback: str = "", base_points: list[dict] | None = None) -> list[dict]:
    keys, _ = await runtime_settings(db)
    sources = await search_read(theme, 5, keys)
    if not sources:
        raise RuntimeError("Live search returned no readable sources")
    context = "\n\n".join(f"SOURCE {i}: {s.title}\nURL: {s.url}\nEXCERPT: {s.excerpt[:1200]}" for i, s in enumerate(sources, 1))
    revision = f"\nOperator revision request: {feedback}\nPrevious points to revise: {json.dumps(base_points, ensure_ascii=False)[:8000]}" if feedback else ""
    text = await complete(
        "scout",
        "Create a research brief from supplied live sources. Return JSON array only. Exactly five objects with title, description, dependencies (array), is_parallelizable (boolean). Do not invent facts or reveal private reasoning.",
        f"Theme: {theme}{revision}\n\nPreliminary sources:\n{context}", db,
    )
    points = parse_json(text)
    if not isinstance(points, list) or len(points) != 5:
        raise ValueError("Scout must return exactly five briefing points")
    clean = []
    for point in points:
        if not isinstance(point, dict) or not str(point.get("title", "")).strip() or not str(point.get("description", "")).strip():
            raise ValueError("Scout returned invalid point")
        clean.append({"title": str(point["title"])[:500], "description": str(point["description"])[:4000], "dependencies": list(point.get("dependencies", [])), "is_parallelizable": bool(point.get("is_parallelizable", True))})
    return clean


def _quote_supported(quote: str, source: str) -> bool:
    normalize = lambda value: re.sub(r"\s+", " ", value).strip().lower()
    return len(quote) >= 20 and normalize(quote) in normalize(source)


async def _worker(research_id: uuid.UUID, point_id: uuid.UUID, title: str, description: str, persona: str, feedback: str = "") -> None:
    """Search up to MAX_WORKER_QUERIES times, letting the persona decide the next query each round."""
    async with WORK_LIMIT:
        await add_event(research_id, persona, "worker_started", f"{persona.title()} started source collection")
        async with AsyncSessionLocal() as db:
            keys, _ = await runtime_settings(db)
            memory: list[dict] = []   # per-point dynamic memory only; never persisted
            seen_urls: set[str] = set()
            sources: list = []

            # If the auditor specified direct URLs in missing_research, fetch them directly
            if feedback:
                import re as _re
                from app.tools.search_pipeline import read_source, Source
                for ref_url in _re.findall(r"https?://[^\s)\];,]+", feedback):
                    if ref_url not in seen_urls:
                        try:
                            direct_src = await read_source(Source(ref_url, "Audited Source", ""))
                            if direct_src:
                                seen_urls.add(ref_url)
                                sources.append(direct_src)
                        except Exception:
                            pass

            for round_no in range(1, settings.MAX_WORKER_QUERIES + 1):
                if not memory:
                    query = f"{title} {persona}"
                else:
                    notes = "\n".join(f"- {m['summary']}" for m in memory)
                    qresp = await complete(
                        persona,
                        f"You are the {persona} researcher. Based on what you learned, either state SATISFIED or produce the single next search query that would fill the biggest remaining gap about the research point. Reply with SATISFIED or one plain-text query line only.",
                        f"Research point: {title}\n{description}\nLearned so far:\n{notes}", db,
                    )
                    query = qresp.strip().splitlines()[0].strip() if qresp.strip() else "SATISFIED"
                    if query.upper().startswith("SATISFIED"):
                        break
                try:
                    batch = await search_read(query, 5, keys)
                except Exception:
                    batch = []
                new_sources = [s for s in batch if s.url not in seen_urls]
                seen_urls.update(s.url for s in new_sources)
                sources.extend(new_sources)
                if new_sources:
                    notes_resp = await complete(
                        persona,
                        f"As the {persona} researcher, summarise in 2-3 short sentences what these sources teach about the research point. Plain text only.",
                        f"Research point: {title}\nSources:\n" + "\n".join(f"{s.url}\n{s.excerpt[:800]}" for s in new_sources), db,
                    )
                    memory.append({"query": query, "summary": notes_resp.strip()})
                if round_no >= settings.MAX_WORKER_QUERIES:
                    break
            if not sources:
                await add_event(research_id, persona, "sources_scanned", f"{persona.title()} found no readable sources", {"sources": 0})
                return
            context = "\n\n".join(f"URL: {s.url}\nTITLE: {s.title}\nTEXT: {s.excerpt[:2500]}" for s in sources)
            response = await complete(
                persona,
                f"Analyze evidence as {persona}. Return JSON array only. Each item: source_url, claim, exact_quote, analysis. Use only supplied URLs and verbatim quotes. Mark uncertainty in analysis. Never expose chain-of-thought.",
                f"Research point: {title}\n{description}\n\nSources:\n{context}", db,
            )
            items = parse_json(response)
            by_url = {s.url: s for s in sources}
            count = 0
            if isinstance(items, list):
                for item in items:
                    if not isinstance(item, dict) or item.get("source_url") not in by_url:
                        continue
                    source = by_url[item["source_url"]]
                    quote = str(item.get("exact_quote", ""))
                    if not _quote_supported(quote, source.excerpt):
                        continue
                    existing = await db.scalar(select(Evidence.id).where(
                        Evidence.research_point_id == point_id,
                        Evidence.persona == persona,
                        Evidence.source_url == source.url,
                    ))
                    if existing:
                        continue
                    db.add(Evidence(
                        research_point_id=point_id, persona=persona, source_url=source.url,
                        source_title=source.title, excerpt=quote[:4000], claim=str(item.get("claim", ""))[:4000],
                        analysis=str(item.get("analysis", ""))[:8000],
                    ))
                    count += 1
            await db.commit()
        await add_event(research_id, persona, "sources_scanned", f"{persona.title()} retained {count} traceable sources", {"sources_fetched": len(sources), "citations_retained": count})


async def _audit_point(research_id: uuid.UUID, point: ResearchPoint, attempt: int) -> bool:
    async with AsyncSessionLocal() as db:
        rows = list((await db.scalars(select(Evidence).where(Evidence.research_point_id == point.id))).all())
        evidence_data = [{"url": row.source_url, "claim": row.claim, "excerpt": row.excerpt, "persona": row.persona} for row in rows]
        deterministic = deterministic_citation_audit(evidence_data)
        prompt = json.dumps({"point": point.title, "evidence": evidence_data, "deterministic_checks": deterministic}, ensure_ascii=False)[:60000]
        llm_text = await complete(
            "auditor",
            "Audit supplied evidence for the single research point. Answer: was the question directly answered? are essential points covered? do important claims have identifiable sources? are sources adequate (prefer primary)? do sources actually say what workers claim (quote must support claim)? is info current enough? are contradictions surfaced? is fact separated from inference/uncertainty? did research stay in scope? Return JSON object with approved (boolean), findings (array), contradictions (array), uncertainties (array), outline (array), missing_research (array of concrete search instructions describing exactly what is still missing; empty if approved). Approve only when each claim is supported by its exact quote and no contradiction remains. Never reveal private reasoning.",
            prompt, db,
        )
        try:
            llm_audit = parse_json(llm_text)
        except (ValueError, json.JSONDecodeError):
            llm_audit = {"findings": ["Auditor returned invalid structured output"], "uncertainties": [], "missing_research": []}
        if not isinstance(llm_audit.get("missing_research"), list):
            llm_audit["missing_research"] = []
        approved = audit_approves(deterministic, llm_audit)
        state = next_audit_state(approved, attempt, settings.MAX_AUDIT_ATTEMPTS)
        stored = await db.get(ResearchPoint, point.id)
        stored.attempt_count = attempt
        stored.status = state
        stored.audit = {"deterministic": deterministic, "llm": llm_audit, "attempt": attempt}
        db.add(AuditTrail(research_id=research_id, point_id=point.id, stage="point_audit", attempt=attempt,
                          details={"status": state, "deterministic": deterministic, "llm": llm_audit}))
        await db.commit()
    await add_event(research_id, "auditor", "verdict_rendered", f"Audit attempt {attempt}: {state}", {"attempt": attempt, "supported": deterministic["supported"], "unsupported": len(deterministic["unsupported"])})
    return approved


async def _run_point(research_id: uuid.UUID, point: ResearchPoint) -> bool:
    feedback = ""
    for attempt in remaining_attempts(point, settings.MAX_AUDIT_ATTEMPTS):
        async with AsyncSessionLocal() as db:
            stored = await db.get(ResearchPoint, point.id)
            if stored is None:
                return False
            stored.attempt_count = attempt
            stored.status = "in_progress"
            await db.commit()
        results = await asyncio.gather(*(_worker(research_id, point.id, point.title, point.description, persona, feedback) for persona in PERSONAS), return_exceptions=True)
        failures = sum(isinstance(result, Exception) for result in results)
        if failures:
            async with AsyncSessionLocal() as db:
                for persona, result in zip(PERSONAS, results):
                    if isinstance(result, Exception):
                        db.add(AuditTrail(research_id=research_id, point_id=point.id, stage="worker_failure",
                                          attempt=attempt, details={"persona": persona, "error_type": type(result).__name__}))
                await db.commit()
            await add_event(research_id, "system", "worker_failures", f"{failures} worker executions failed safely", {"failed_workers": failures})
        if await _audit_point(research_id, point, attempt):
            return True
        async with AsyncSessionLocal() as db:
            refreshed = await db.get(ResearchPoint, point.id)
            missing = (refreshed.audit or {}).get("llm", {}).get("missing_research", []) if refreshed else []
            findings = (refreshed.audit or {}).get("llm", {}).get("findings", []) if refreshed else []
            feedback = "; ".join(str(m) for m in (missing or findings))[:1000]
    if point.status not in {"approved", "blocked"}:
        async with AsyncSessionLocal() as db:
            stored = await db.get(ResearchPoint, point.id)
            if stored and stored.status not in {"approved", "blocked"}:
                stored.status = "blocked"
                await db.commit()
    return False


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
            "Write a Markdown research report using only supplied evidence. Cite every factual claim with inline Markdown URL. Include uncertainty and blocked-point caveats, then References. Do not invent facts or expose private reasoning.",
            json.dumps({"theme": research.theme, "evidence": bundle, "audits": audits}, ensure_ascii=False)[:100000], db,
        )
        if not text.strip() or not evidence:
            raise RuntimeError("Writer cannot produce a report without evidence")
        cited = sum(1 for row in evidence if row.source_url in text)
        if cited == 0:
            raise RuntimeError("Writer produced report without source citations")
        # ponytail: URL membership is traceability, not factual verification; add claim-level entailment before promising it.
        import re as _re
        linked_urls = set(_re.findall(r"\]\((https?://[^\s)]+)\)", text))
        known_urls = {row.source_url for row in evidence}
        if not linked_urls or not linked_urls.issubset(known_urls):
            raise RuntimeError("Writer used uncollected citation URLs")
        factual_lines = [line.strip() for line in text.splitlines()
                         if line.strip() and not line.lstrip().startswith(("#", "|", "-", "*", ">", "["))
                         and not line.strip().lower().startswith(("references", "fontes", "referências"))]
        for line in factual_lines:
            if _re.search(r"[.!?]\s*$", line) and not _re.search(r"\]\(https?://[^\s)]+\)", line):
                raise RuntimeError("Writer left an uncited factual paragraph")
        report = Report(research_id=research.id, content_markdown=text, citation_metrics={"evidence_records": len(evidence), "source_urls_cited": cited}, audit_findings={"points": audits})
        db.add(report)
        stored = await db.get(Research, research.id)
        stored.status = "completed" if all(point.status == "approved" for point in points) else "blocked"
        await db.commit()
    await add_event(research.id, "writer", "synthesis_completed", "Evidence-grounded report persisted", {"evidence_records": len(evidence), "citations": cited})


async def run_research(research_id: uuid.UUID) -> None:
    try:
        async with AsyncSessionLocal() as db:
            research = await db.get(Research, research_id)
            if not research or research.status not in {"approved", "in_progress", "interrupted"}:
                return
            research.status = "in_progress"
            await db.commit()
            points = list((await db.scalars(select(ResearchPoint).where(ResearchPoint.research_id == research_id).order_by(ResearchPoint.position))).all())
        await add_event(research_id, "system", "research_started", "Approved research work started", {"points": len(points)})
        for batch in ready_point_batches(points):
            await asyncio.gather(*(_run_point(research_id, points[index]) for index in batch))
        async with AsyncSessionLocal() as db:
            points = list((await db.scalars(select(ResearchPoint).where(ResearchPoint.research_id == research_id).order_by(ResearchPoint.position))).all())
        await _write_report(research, points)
        if research.callback_url:
            from app.services.webhook import dispatch_callback
            await dispatch_callback(research_id)
    except Exception as exc:
        import traceback
        traceback.print_exc()
        async with AsyncSessionLocal() as db:
            research = await db.get(Research, research_id)
            if research:
                research.status = "failed"
                research.error = f"{type(exc).__name__}: {str(exc)[:200]}"
                await db.commit()
        await add_event(research_id, "system", "research_failed", f"Research stopped after controlled failure: {type(exc).__name__} - {str(exc)[:200]}")
