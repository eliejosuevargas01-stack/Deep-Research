"""Scout Worker: preliminary exploration, discovering initial sources and structuring research points."""
from __future__ import annotations

import asyncio
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain_models import ResearchPoint
from app.services.workers.base import BaseWorker, WorkerResult


class ScoutWorker(BaseWorker):
    """Executes preliminary domain exploration to formulate research points and dependencies."""

    @classmethod
    def persona_name(cls) -> str:
        return "scout"

    async def execute(
        self,
        point: ResearchPoint | None = None,
        context: dict[str, Any] | None = None,
    ) -> WorkerResult:
        context = context or {}
        theme = context.get("theme", "")
        feedback = context.get("feedback", "")
        base_points = context.get("base_points", [])

        # Invocação protegida da busca preliminar
        query = f"{theme} overview analysis context"
        sources = await self._search_and_read(query=query, limit=5)

        return WorkerResult(
            point_id=str(point.id) if point else "preliminary",
            persona=self.persona_name(),
            evidences=[{"url": s.url, "title": s.title, "excerpt": s.excerpt[:500]} for s in sources],
            metrics={"sources_found": len(sources), "query": query},
        )
