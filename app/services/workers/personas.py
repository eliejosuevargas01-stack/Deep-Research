"""Persona Workers implementing specific investigative lenses: Historian, Skeptic, Pragmatist, Futurist."""
from __future__ import annotations

import re
from typing import Any

from app.models.domain_models import ResearchPoint
from app.services.workers.base import BaseWorker, WorkerResult


class HistorianWorker(BaseWorker):
    @classmethod
    def persona_name(cls) -> str:
        return "historian"

    async def execute(self, point: ResearchPoint, context: dict[str, Any] | None = None) -> WorkerResult:
        query = f"{point.title} chronological origin context benchmarks timeline"
        sources = await self._search_and_read(query=query, limit=3)
        return WorkerResult(
            point_id=str(point.id),
            persona=self.persona_name(),
            evidences=[{"url": s.url, "title": s.title, "excerpt": s.excerpt} for s in sources],
            metrics={"queries_executed": 1, "sources_extracted": len(sources)},
        )


class SkepticWorker(BaseWorker):
    @classmethod
    def persona_name(cls) -> str:
        return "skeptic"

    async def execute(self, point: ResearchPoint, context: dict[str, Any] | None = None) -> WorkerResult:
        query = f"{point.title} criticism counter-evidence limitations controversy flaws"
        sources = await self._search_and_read(query=query, limit=3)
        return WorkerResult(
            point_id=str(point.id),
            persona=self.persona_name(),
            evidences=[{"url": s.url, "title": s.title, "excerpt": s.excerpt} for s in sources],
            metrics={"queries_executed": 1, "sources_extracted": len(sources)},
        )


class PragmatistWorker(BaseWorker):
    @classmethod
    def persona_name(cls) -> str:
        return "pragmatist"

    async def execute(self, point: ResearchPoint, context: dict[str, Any] | None = None) -> WorkerResult:
        query = f"{point.title} real-world implementation case study benchmarks cost parameters"
        sources = await self._search_and_read(query=query, limit=3)
        return WorkerResult(
            point_id=str(point.id),
            persona=self.persona_name(),
            evidences=[{"url": s.url, "title": s.title, "excerpt": s.excerpt} for s in sources],
            metrics={"queries_executed": 1, "sources_extracted": len(sources)},
        )


class FuturistWorker(BaseWorker):
    @classmethod
    def persona_name(cls) -> str:
        return "futurist"

    async def execute(self, point: ResearchPoint, context: dict[str, Any] | None = None) -> WorkerResult:
        query = f"{point.title} roadmap forecast emerging trends projected implications milestones"
        sources = await self._search_and_read(query=query, limit=3)
        return WorkerResult(
            point_id=str(point.id),
            persona=self.persona_name(),
            evidences=[{"url": s.url, "title": s.title, "excerpt": s.excerpt} for s in sources],
            metrics={"queries_executed": 1, "sources_extracted": len(sources)},
        )
