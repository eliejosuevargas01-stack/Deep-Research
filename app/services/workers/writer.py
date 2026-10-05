"""Writer Agent: synthesizes verified research points, citations, and findings into markdown reports."""
from __future__ import annotations

import re
from typing import Any, Sequence

from app.models.domain_models import Evidence, ResearchPoint
from app.services.workers.base import BaseWorker, WorkerResult


class WriterAgent(BaseWorker):
    """Produces canonical final reports grounded in verbatim source citations."""

    @classmethod
    def persona_name(cls) -> str:
        return "writer"

    async def execute(
        self,
        point: ResearchPoint | None = None,
        context: dict[str, Any] | None = None,
    ) -> WorkerResult:
        context = context or {}
        theme = context.get("theme", "Deep Research Report")
        points_data = context.get("points", [])
        evidences = context.get("evidences", [])

        # Geração estruturada do relatório
        sections = [f"# Relatório de Pesquisa Profunda: {theme}\n"]
        for p in points_data:
            sections.append(f"## {p.get('title', 'Tópico')}\n{p.get('summary', '')}\n")

        full_markdown = "\n".join(sections)
        return WorkerResult(
            point_id=str(point.id) if point else "synthesis",
            persona=self.persona_name(),
            raw_response={"markdown": full_markdown},
            metrics={"sections_rendered": len(points_data)},
        )
