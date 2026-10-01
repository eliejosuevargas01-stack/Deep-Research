"""Webhook delivery over same pinned public-address transport as web reads."""
import asyncio
import uuid

import aiohttp
from sqlalchemy import select

from app.core.config import settings
from app.db.database import AsyncSessionLocal
from app.models import AuditTrail, Report, Research
from app.tools.outbound import PinnedResolver, SSRFSecurityViolation, validate_public_url


async def dispatch_callback(research_id: uuid.UUID) -> bool:
    async with AsyncSessionLocal() as db:
        research = await db.get(Research, research_id)
        report = await db.scalar(select(Report).where(Report.research_id == research_id))
        if not research or not report:
            raise ValueError("Completed report not found")
        if not research.callback_url:
            return False
        url = research.callback_url
        payload = {"research_id": str(research_id), "report_id": str(report.id),
                   "theme": research.theme, "content_markdown": report.content_markdown,
                   "generated_at": report.generated_at.isoformat()}

    timeout = aiohttp.ClientTimeout(total=settings.SEARCH_TIMEOUT_SECONDS)
    try:
        validate_public_url(url)
        connector = aiohttp.TCPConnector(resolver=PinnedResolver(), use_dns_cache=False)
        async with aiohttp.ClientSession(connector=connector, timeout=timeout, trust_env=False) as client:
            async with client.post(url, json=payload, allow_redirects=False) as response:
                delivered = 200 <= response.status < 300
    except (aiohttp.ClientError, asyncio.TimeoutError, SSRFSecurityViolation):
        delivered = False
    async with AsyncSessionLocal() as db:
        db.add(AuditTrail(research_id=research_id, stage="callback", details={"delivered": delivered}))
        stored = await db.get(Research, research_id)
        if stored and stored.status in {"completed", "completed_but_callback_failed"}:
            stored.status = "completed" if delivered else "completed_but_callback_failed"
        await db.commit()
    await add_callback_event(research_id, delivered)
    return delivered


async def add_callback_event(research_id: uuid.UUID, delivered: bool) -> None:
    from app.services.research import add_event
    await add_event(research_id, "system", "callback_delivered" if delivered else "callback_failed",
                    "Webhook delivered" if delivered else "Webhook delivery failed; report remains available")
