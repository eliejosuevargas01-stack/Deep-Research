"""Worker stage: multi-round LLM-driven evidence collection per persona."""
import asyncio
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.database import AsyncSessionLocal
from app.models import Evidence
from app.services.audit import deterministic_citation_audit
from app.services.llm import apply_output_guardrail, complete, parse_json
from app.services.search import Source, search_read

WORK_LIMIT = asyncio.Semaphore(20)

PERSONA_CONTRACTS = {
    "historian": "Focus on chronological evolution, origin context, historical benchmarks, and verified timeline records. Respond in Brazilian Portuguese (pt-BR).",
    "skeptic": "Focus on falsifying claims, surfacing counter-evidence, conflicts of interest, limitations, and methodological flaws. Respond in Brazilian Portuguese (pt-BR).",
    "pragmatist": "Focus on real-world implementations, benchmark figures, concrete operational parameters, costs, and measurable outcomes. Respond in Brazilian Portuguese (pt-BR).",
    "futurist": "Focus on documented roadmap targets, projected implications, emerging consensus, and upcoming structural milestones. Respond in Brazilian Portuguese (pt-BR).",
}


def _quote_supported(quote: str, source: str) -> bool:
    norm = lambda v: re.sub(r"\s+", " ", v).strip().casefold()
    quote_n, source_n = norm(quote), norm(source)
    if len(quote.strip()) < 15:
        return False
    if quote_n in source_n:
        return True
    # Strip punctuation for normalized contiguous word sequence
    clean_q = re.sub(r"[^\w\s]", "", quote_n).strip()
    clean_s = re.sub(r"[^\w\s]", "", source_n).strip()
    if clean_q and clean_q in clean_s:
        return True
    return False


async def _fetch_direct_urls(feedback: str, seen_urls: set[str]) -> tuple[list[Source], str]:
    """Extract and fetch direct URLs from auditor feedback."""
    from app.services.search import read_source
    feedback_instructions = ""
    sources: list[Source] = []
    if feedback:
        for ref_url in re.findall(r"https?://[^\s\)\];,]+", feedback):
            if ref_url not in seen_urls:
                try:
                    direct_src = await read_source(Source(ref_url, "Audited Source", ""))
                    if direct_src:
                        seen_urls.add(ref_url)
                        sources.append(direct_src)
                except Exception:
                    pass
        feedback_instructions = re.sub(r"https?://[^\s\)\];,]+", "", feedback).strip()
    return sources, feedback_instructions


async def run_worker(
    research_id: str,
    point_id: str,
    title: str,
    description: str,
    persona: str,
    feedback: str = "",
) -> None:
    """Execute worker loop for a single persona on a research point."""
    async with WORK_LIMIT:
        from app.services.research import add_event
        await add_event(
            research_id, persona, "worker_started", f"{persona.title()} started source collection",
            point_id=point_id, point_title=title, tool_type="worker_start",
        )
        async with AsyncSessionLocal() as db:
            settings_mod = __import__("app.services.settings", fromlist=["runtime_settings", "runtime_jina_base_url"])
            keys, _ = await settings_mod.runtime_settings(db)
            jina_base_url = await settings_mod.runtime_jina_base_url(db)
            sensitive_keys = [str(k) for k in keys.values() if k]
            memory: list[dict] = []
            seen_urls: set[str] = set()
            sources: list = []

            # Fetch any direct URLs from auditor feedback
            direct_sources, feedback_instructions = await _fetch_direct_urls(feedback, seen_urls)
            sources.extend(direct_sources)

            max_queries = min(3, max(1, settings.MAX_WORKER_QUERIES))
            cognitive_contract = PERSONA_CONTRACTS.get(persona, "Focus on verified factual investigation.")

            for round_no in range(1, max_queries + 1):
                if not memory:
                    if feedback_instructions:
                        query = f"{title} {persona} {feedback_instructions[:80]}"
                    else:
                        query = f"{title} {persona}"
                else:
                    notes = "\n".join(f"- {m['summary']}" for m in memory)
                    retry_clause = f"\nAuditor instructions to resolve: {feedback_instructions}\n" if feedback_instructions else ""
                    qresp = await complete(
                        persona,
                        f"You are the {persona} researcher. {cognitive_contract} Based on what you learned, either state SATISFIED or produce the single next search query that would fill the biggest remaining gap about the research point. Reply with SATISFIED or one plain-text query line only.",
                        f"Research point: {title}\n{description}{retry_clause}\nLearned so far:\n{notes}", db,
                    )
                    query = qresp.strip().splitlines()[0].strip() if qresp.strip() else "SATISFIED"
                    if query.upper().startswith("SATISFIED"):
                        break
                try:
                    batch = await search_read(query, 5, keys, jina_base_url=jina_base_url)
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
                if round_no >= max_queries:
                    break
            if not sources:
                await add_event(
                    research_id, persona, "sources_scanned", f"{persona.title()} found no readable sources",
                    {"sources": 0}, point_id=point_id, point_title=title, tool_type="worker_search",
                )
                return
            context = "\n\n".join(f"URL: {s.url}\nTITLE: {s.title}\nTEXT: {s.excerpt[:2500]}" for s in sources)
            response = await complete(
                persona,
                f"Analyze evidence as {persona}. {cognitive_contract} Return a strict JSON array only (use double quotes for all keys and string values, e.g. [{{\"source_url\": \"...\"}}]). Each item: source_url, claim, exact_quote, analysis. CRITICAL RULE: exact_quote must be an exact verbatim substring copied from the provided source text without modifications or paraphrasing. Use only supplied URLs. Mark uncertainty in analysis. Never expose chain-of-thought.",
                f"<research_point>\nTitle: {title}\nDescription: {description}\n</research_point>\n\n<untrusted_external_content>\n{context}\n</untrusted_external_content>", db,
            )
            items = parse_json(response)
            by_url = {s.url: s for s in sources}
            count = 0
            seen_evidence_urls: set[str] = set()
            if isinstance(items, list):
                for item in items:
                    if not isinstance(item, dict) or item.get("source_url") not in by_url:
                        continue
                    source = by_url[item["source_url"]]
                    if source.url in seen_evidence_urls:
                        continue
                    quote = str(item.get("exact_quote", ""))
                    if not _quote_supported(quote, source.excerpt):
                        continue
                    claim_text = str(item.get("claim", ""))[:4000]
                    analysis_text = str(item.get("analysis", ""))[:8000]

                    # A1-02: Validate structured fields against guardrails before persistence
                    try:
                        apply_output_guardrail(claim_text, extra_sensitive_values=sensitive_keys)
                        apply_output_guardrail(quote, extra_sensitive_values=sensitive_keys)
                        apply_output_guardrail(analysis_text, extra_sensitive_values=sensitive_keys)
                    except Exception:
                        continue

                    existing = await db.scalar(select(Evidence.id).where(
                        Evidence.research_point_id == point_id,
                        Evidence.persona == persona,
                        Evidence.source_url == source.url,
                    ))
                    if existing:
                        seen_evidence_urls.add(source.url)
                        continue
                    db.add(Evidence(
                        research_point_id=point_id, persona=persona, source_url=source.url,
                        source_title=source.title, excerpt=quote[:4000], claim=claim_text,
                        analysis=analysis_text,
                    ))
                    seen_evidence_urls.add(source.url)
                    count += 1
            try:
                await db.commit()
            except Exception:
                await db.rollback()
                count = 0
                raise
        await add_event(
            research_id, persona, "sources_scanned", f"{persona.title()} retained {count} traceable sources",
            {"sources_fetched": len(sources), "citations_retained": count}, point_id=point_id, point_title=title,
            tool_type="worker_synthesis",
        )


__all__ = ["run_worker", "PERSONA_CONTRACTS", "_quote_supported", "_fetch_direct_urls"]
